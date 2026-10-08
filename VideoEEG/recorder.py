"""Headless vEEG recorder: camera acquisition, video writing, TTL sync pulses.

Run one recorder per camera. The GUI starts it in supervised mode:
    python -m VideoEEG.recorder --cam 0 --supervise
The supervisor restarts the recorder if it crashes or stops responding, and the recorder resumes
recording if it was recording before. The GUI talks to the recorder over a local zmq socket, so
closing or crashing the GUI does not affect the recording.

Threads:
    camera (SDK thread)   pulls each frame and puts it in a queue, nothing else
    writer                writes frames and TTL log entries to the current segment
    ttl                   gives TTL pulses at random intervals while recording
    main                  commands from the GUI, camera watchdog and reconnect, heartbeat
"""
import argparse
import ctypes
import json
import logging
import logging.handlers
import os
import queue
import random
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import zmq

from VideoEEG import config
from VideoEEG.camera import CameraError, FakeCamera, NncamCamera, short_id
from VideoEEG.writer import SegmentWriter, choose_encoder

log = logging.getLogger(__name__)

FRAME_TIMEOUT_S = 5      # reopen the camera if no frame arrives for this long
REOPEN_INTERVAL_S = 5
EXIT_ALREADY_RUNNING = 3


class Recorder:
    def __init__(self, cam_index, settings_file, camera_cls=NncamCamera):
        self.cam_index = cam_index
        self.settings_file = settings_file
        self.settings = config.Settings.load(settings_file)
        self.camera = camera_cls(cam_index, self.settings)
        self.camera_ok = False
        self._camera_failed = threading.Event()
        self._last_open_attempt = 0.0
        self.frames = queue.Queue(maxsize=20 * self.settings.framerate)
        self.ttl_events = queue.Queue()
        self.stopping = threading.Event()
        self.encoder = None
        # counters, written by the camera thread
        self.frame_total = 0
        self.last_seq = None
        self.last_frame_time = 0.0
        self.dropped_queue = 0
        self.dropped_camera = 0
        # status, written by the writer and ttl threads
        self.latest = None
        self.current_file = ''
        self.n_pulses = 0
        self.messages = []
        self._fps = (time.time(), 0, 0.0)  # time, frame_total, fps
        self._free_gb = (0.0, None)
        self._threads = [threading.Thread(target=self._writer_loop, name='writer', daemon=True),
                         threading.Thread(target=self._ttl_loop, name='ttl', daemon=True)]

    @property
    def recording(self):
        return self.settings.recording

    def note(self, msg, level=logging.WARNING):
        log.log(level, msg)
        self.messages = (self.messages + [time.strftime('%H:%M:%S ') + msg])[-5:]

    def start(self):
        for t in self._threads:
            t.start()
        if self.recording:
            self.note('resuming recording', logging.INFO)

    # --- camera ---
    def _on_frame(self, frame):
        if self.last_seq is not None and frame.seq > self.last_seq + 1:
            self.dropped_camera += frame.seq - self.last_seq - 1
        self.last_seq = frame.seq
        self.frame_total += 1
        self.last_frame_time = frame.host_time
        try:
            self.frames.put_nowait((frame, self.frame_total))
        except queue.Full:
            self.dropped_queue += 1

    def _on_camera_event(self, msg, fatal):
        if fatal:
            self._camera_failed.set()
        self.note(msg)

    def _open_camera(self):
        self._last_open_attempt = time.time()
        pinned = self.settings.camera_id
        try:
            self.camera.open()
            if self.settings.camera_id != pinned:
                self.settings.save(self.settings_file)
                self.note(f'camera USB {short_id(self.settings.camera_id)} assigned to this window', logging.INFO)
            self.last_seq = None
            self.last_frame_time = time.time()
            self._camera_failed.clear()
            self.camera.start(self._on_frame, self._on_camera_event)
            self.camera_ok = True
            self.note('camera started', logging.INFO)
        except (CameraError, OSError) as ex:
            self.note(f'camera not available: {ex}')
            self._close_camera()

    def _close_camera(self):
        self.camera_ok = False
        try:
            self.camera.close()
        except OSError as ex:
            log.error('camera close failed: %s', ex)

    def check_camera(self):
        now = time.time()
        if self.camera_ok:
            stalled = now - self.last_frame_time > FRAME_TIMEOUT_S
            if self._camera_failed.is_set() or stalled:
                self.note('no frames from camera, reopening' if stalled else 'camera failed, reopening')
                self._close_camera()
        elif now - self._last_open_attempt > REOPEN_INTERVAL_S:
            self._open_camera()

    # --- writer thread ---
    def _writer_loop(self):
        writer = None
        pending_ttl = []
        while not self.stopping.is_set():
            try:
                frame, frame_total = self.frames.get(timeout=0.5)
            except queue.Empty:
                frame = None
            try:
                if writer is not None and not self.recording:
                    writer.close()
                    writer = None
                    pending_ttl.clear()
                    self.current_file = ''
                if frame is None:
                    continue
                self.latest = frame
                if not self.recording:
                    continue
                if writer is None:
                    if self.encoder is None:
                        self.encoder = choose_encoder(self.settings, self.camera.size)
                    writer = SegmentWriter(self.settings, self.camera.size, self.encoder,
                                           config.log_dir() / f'cam{self.cam_index}_ffmpeg.log')
                writer.write(frame, frame_total)
                self.current_file = writer.current_file
                while not self.ttl_events.empty():
                    pending_ttl.append(self.ttl_events.get_nowait())
                while pending_ttl and pending_ttl[0][2] <= frame_total:
                    writer.ttl(*pending_ttl.pop(0))
            except Exception as ex:  # e.g. ffmpeg missing or output folder not writable: retry
                log.exception('writer error')
                self.note(f'writer error: {ex}, retrying in 5 s', logging.ERROR)
                self.current_file = ''
                if writer is not None:
                    try:
                        writer.close()
                    except Exception:
                        log.exception('closing the writer failed')
                writer = None
                self.stopping.wait(5)
        if writer is not None:
            writer.close()

    # --- ttl thread ---
    def _ttl_loop(self):
        s = self.settings
        while not self.stopping.wait(s.ttl_mean_interval_s * random.uniform(0.1, 1.9)):
            if not (self.current_file and self.camera_ok):
                continue
            try:
                pc_time, frame_total, cam_seq = time.time(), self.frame_total, self.last_seq
                self.camera.ttl(True)
                time.sleep(s.ttl_width_ms / 1000)
                self.camera.ttl(False)
            except Exception as ex:  # a failed pulse must not stop the recording
                self.note(f'TTL failed: {ex}')
                continue
            self.n_pulses += 1
            self.ttl_events.put((self.n_pulses, pc_time, frame_total, cam_seq))

    # --- commands ---
    def start_recording(self, prefix=None, out_dir=None):
        if prefix is not None:
            self.settings.prefix = prefix
        if out_dir is not None:
            self.settings.out_dir = out_dir
        self.settings.recording = True
        self.settings.save(self.settings_file)
        self.note(f'recording started: {self.settings.out_dir} {self.settings.prefix}', logging.INFO)

    def stop_recording(self):
        self.settings.recording = False
        self.settings.save(self.settings_file)
        self.note('recording stopped', logging.INFO)

    def set_exposure(self, ms):
        self.settings.exposure_ms = int(ms)
        self.settings.save(self.settings_file)
        if self.camera_ok:
            self.camera.set_exposure(self.settings.exposure_ms)

    def set_camera(self, camera_id):
        """Use another camera; '' picks the first one that no window has pinned."""
        self.settings.camera_id = camera_id
        self.settings.save(self.settings_file)
        self._close_camera()
        self._last_open_attempt = time.time()  # reopen after REOPEN_INTERVAL_S, so a swap partner can release it
        self.note(f'switching to camera USB {short_id(camera_id) or "(first unassigned)"}', logging.INFO)

    def cameras(self):
        visible = self.camera.list_devices()
        return {'self': self.settings.camera_id, 'visible': visible,
                'assigned': {str(i): cid for i, cid in config.assigned_cameras().items()}}

    def status(self):
        now = time.time()
        t0, n0, fps = self._fps
        if now - t0 >= 2:
            fps = (self.frame_total - n0) / (now - t0)
            self._fps = (now, self.frame_total, fps)
        t_disk, free_gb = self._free_gb
        if now - t_disk >= 30:
            free_gb = free_space_gb(self.settings.out_dir)
            self._free_gb = (now, free_gb)
        return {'cam': self.cam_index, 'camera_ok': self.camera_ok, 'camera': self.camera.info,
                'camera_id': self.settings.camera_id,
                'recording': self.recording, 'fps': fps, 'frames': self.frame_total,
                'dropped_queue': self.dropped_queue, 'dropped_camera': self.dropped_camera,
                'queue': self.frames.qsize(), 'file': self.current_file, 'pulses': self.n_pulses,
                'encoder': self.encoder, 'free_gb': free_gb, 'messages': self.messages,
                'settings': {k: getattr(self.settings, k) for k in
                             ('out_dir', 'prefix', 'exposure_ms', 'framerate', 'min_free_gb')}}

    def preview(self):
        frame = self.latest
        if frame is None:
            return None
        return frame.data[::2, ::2].copy()

    def handle(self, request):
        """Handle one GUI command. Returns (reply dict, optional bytes)."""
        cmd = request.get('cmd')
        if cmd == 'status':
            return self.status(), None
        if cmd == 'preview':
            img = self.preview()
            if img is None:
                return {'ok': False}, None
            return {'ok': True, 'shape': img.shape}, img.tobytes()
        if cmd == 'start':
            self.start_recording(request.get('prefix'), request.get('out_dir'))
            return {'ok': True}, None
        if cmd == 'stop':
            self.stop_recording()
            return {'ok': True}, None
        if cmd == 'cameras':
            return self.cameras(), None
        if cmd == 'set_camera' and not self.recording:
            self.set_camera(request['camera_id'])
            return {'ok': True}, None
        if cmd == 'set' and not self.recording:
            if 'exposure_ms' in request:
                self.set_exposure(request['exposure_ms'])
            for key in ('prefix', 'out_dir'):
                if key in request:
                    setattr(self.settings, key, request[key])
            self.settings.save(self.settings_file)
            return {'ok': True}, None
        if cmd == 'quit' and not self.recording:
            self.stopping.set()
            return {'ok': True}, None
        return {'ok': False, 'error': f'command not accepted: {cmd}'}, None

    def shutdown(self):
        self.stopping.set()
        for t in self._threads:
            t.join(timeout=150)
        self._close_camera()


def free_space_gb(path):
    path = Path(path)
    while not path.exists() and path != path.parent:
        path = path.parent
    try:
        return shutil.disk_usage(path).free / 1e9
    except OSError:
        return None


def keep_awake():
    """Keep Windows from sleeping while the recorder runs."""
    if os.name == 'nt':
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)


def setup_logging(name):
    config.log_dir().mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(config.log_dir() / name, maxBytes=10_000_000, backupCount=5)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(threadName)s %(name)s: %(message)s',
                        handlers=[handler, logging.StreamHandler()])
    threading.excepthook = lambda args: log.critical('uncaught exception in thread %s', args.thread.name,
                                                     exc_info=(args.exc_type, args.exc_value, args.exc_traceback))


def serve(recorder):
    """Main loop: answers GUI commands, checks the camera and writes the heartbeat."""
    ctx = zmq.Context()
    sock = ctx.socket(zmq.REP)
    sock.setsockopt(zmq.LINGER, 0)
    try:
        sock.bind(f'tcp://127.0.0.1:{config.port(recorder.cam_index)}')
    except zmq.ZMQError as ex:
        log.error('cannot bind port, another recorder for this camera is probably running: %s', ex)
        return EXIT_ALREADY_RUNNING
    keep_awake()
    recorder.start()
    heartbeat = config.heartbeat_path(recorder.cam_index)
    try:
        while not recorder.stopping.is_set():
            if sock.poll(200):
                try:
                    request = json.loads(sock.recv())
                    reply, data = recorder.handle(request)
                except Exception as ex:  # a bad request must not stop the recorder
                    log.exception('command failed')
                    reply, data = {'ok': False, 'error': str(ex)}, None
                if data is None:
                    sock.send(json.dumps(reply).encode())
                else:
                    sock.send_multipart([json.dumps(reply).encode(), data])
            recorder.check_camera()
            if not recorder.stopping.is_set() and not all(t.is_alive() for t in recorder._threads):
                log.error('a recorder thread died, exiting so the supervisor restarts the recorder')
                return 1
            heartbeat.touch()
    finally:
        recorder.shutdown()
        sock.close()
        ctx.term()
    return 0


def supervise(args):
    """Run the recorder in a child process and restart it if it exits with an error or hangs."""
    cmd = [sys.executable, '-m', 'VideoEEG.recorder', '--cam', str(args.cam)] + (['--fake'] if args.fake else [])
    heartbeat = config.heartbeat_path(args.cam)
    while True:
        started = time.time()
        child = subprocess.Popen(cmd)
        log.info('started recorder pid %d', child.pid)
        while child.poll() is None:
            time.sleep(2)
            age = time.time() - heartbeat.stat().st_mtime if heartbeat.exists() else 0
            if time.time() - started > 60 and age > 30:
                log.error('recorder heartbeat is %.0f s old, restarting it', age)
                child.kill()
                child.wait()
        if child.returncode in (0, EXIT_ALREADY_RUNNING):
            log.info('recorder exited with %d', child.returncode)
            return child.returncode
        log.error('recorder exited with %d, restarting in 2 s', child.returncode)
        time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--cam', type=int, default=0, help='camera index')
    parser.add_argument('--supervise', action='store_true', help='run and restart the recorder in a child process')
    parser.add_argument('--fake', action='store_true', help='use a synthetic camera')
    args = parser.parse_args()
    if args.supervise:
        setup_logging(f'cam{args.cam}_supervisor.log')
        sys.exit(supervise(args))
    setup_logging(f'cam{args.cam}_recorder.log')
    recorder = Recorder(args.cam, config.settings_path(args.cam), FakeCamera if args.fake else NncamCamera)
    sys.exit(serve(recorder))


if __name__ == '__main__':
    main()
