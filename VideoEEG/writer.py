"""Writes frames to hourly video segments through an ffmpeg subprocess.

Each segment is a set of files sharing one stem, e.g. `vEEG-2026-10-07T14-00-00`:
    .mkv          H.264 video, constant frame rate
    _frames.csv   one row per frame: camera sequence number, camera and PC timestamps
    _ttl.csv      one row per TTL pulse: PC time and the frame index at the pulse

ffmpeg finalizes the file when its stdin closes, including when the recorder process dies,
so segments stay readable after a crash.
"""
import datetime
import logging
import os
import subprocess
import threading
from pathlib import Path

log = logging.getLogger(__name__)

NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
FRAMES_HEADER = 'frame,frame_total,cam_seq,cam_time_us,pc_time\n'
TTL_HEADER = 'pulse,pc_time,frame,frame_total,cam_seq\n'


def encoder_args(encoder, quality):
    if encoder == 'h264_nvenc':
        return ['-c:v', 'h264_nvenc', '-preset', 'p4', '-rc', 'vbr', '-cq', str(quality), '-b:v', '0']
    if encoder == 'libx264':
        return ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', str(quality)]
    raise ValueError(f'unknown encoder {encoder}')


def choose_encoder(settings, size):
    """Return the configured encoder, or for 'auto' the GPU encoder if a test encode works."""
    if settings.encoder != 'auto':
        return settings.encoder
    cmd = [settings.ffmpeg, '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
           '-i', f'color=black:s={size[0]}x{size[1]}:r={settings.framerate}', '-frames:v', '5',
           *encoder_args('h264_nvenc', settings.quality), '-pix_fmt', 'yuv420p', '-f', 'null', '-']
    try:
        ok = subprocess.run(cmd, capture_output=True, timeout=30, creationflags=NO_WINDOW).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        ok = False
    encoder = 'h264_nvenc' if ok else 'libx264'
    log.info('encoder: %s', encoder)
    return encoder


class Segment:
    def __init__(self, stem, settings, size, encoder, stderr):
        self.stem = stem
        self.path = Path(f'{stem}.mkv')
        self.n_frames = 0
        self.start_total = 0
        w, h = size
        fps = settings.framerate
        cmd = [settings.ffmpeg, '-hide_banner', '-nostats', '-loglevel', 'warning', '-y',
               '-f', 'rawvideo', '-pix_fmt', 'gray', '-s', f'{w}x{h}', '-framerate', str(fps), '-i', '-',
               *encoder_args(encoder, settings.quality), '-pix_fmt', 'yuv420p', '-g', str(2 * fps),
               '-flush_packets', '1', '-f', 'matroska', str(self.path)]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=stderr,
                                     creationflags=NO_WINDOW)
        self.frames_csv = open(f'{stem}_frames.csv', 'w', newline='')
        self.frames_csv.write(FRAMES_HEADER)
        self.ttl_csv = open(f'{stem}_ttl.csv', 'w', newline='')
        self.ttl_csv.write(TTL_HEADER)

    def close(self):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=120)
        except subprocess.TimeoutExpired:
            log.error('ffmpeg did not finish %s, killing it', self.path)
            self.proc.kill()
        if self.proc.returncode != 0:
            log.error('ffmpeg exited with %s for %s', self.proc.returncode, self.path)
        self.frames_csv.close()
        log.info('closed %s (%d frames)', self.path, self.n_frames)


class SegmentWriter:
    """Not thread-safe: call all methods from the writer thread."""

    def __init__(self, settings, size, encoder, stderr_path):
        self.settings = settings
        self.size = size
        self.encoder = encoder
        self.frames_per_segment = settings.segment_s * settings.framerate
        self.stderr = open(stderr_path, 'a')
        self.segment = None
        self.previous = None  # last segment, its TTL log stays open briefly for late pulses
        self._closing = []

    @property
    def current_file(self):
        return str(self.segment.path) if self.segment else ''

    def _new_segment(self, host_time):
        out_dir = Path(self.settings.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.fromtimestamp(host_time).isoformat(timespec='seconds').replace(':', '-')
        self.segment = Segment(out_dir / f'{self.settings.prefix}-{timestamp}', self.settings, self.size,
                               self.encoder, self.stderr)
        log.info('new segment %s', self.segment.path)

    def _close_segment_async(self):
        # Frames keep flowing into the next segment while ffmpeg finishes this one.
        t = threading.Thread(target=self.segment.close, daemon=True)
        t.start()
        self._closing = [c for c in self._closing if c.is_alive()] + [t]
        self._close_previous_ttl()
        self.previous = self.segment
        self.segment = None

    def _close_previous_ttl(self):
        if self.previous is not None:
            self.previous.ttl_csv.close()
            self.previous = None

    def write(self, frame, frame_total):
        if self.segment is not None and self.segment.n_frames >= self.frames_per_segment:
            self._close_segment_async()
        if self.segment is None:
            self._new_segment(frame.host_time)
            self.segment.start_total = frame_total
        seg = self.segment
        try:
            seg.proc.stdin.write(frame.data.tobytes())
        except OSError as ex:
            log.error('writing to ffmpeg failed (%s), starting a new segment', ex)
            self._close_segment_async()
            return
        seg.frames_csv.write(f'{seg.n_frames},{frame_total},{frame.seq},{frame.cam_time_us},{frame.host_time:.6f}\n')
        seg.n_frames += 1
        if seg.n_frames % self.settings.framerate == 0:
            seg.frames_csv.flush()
            self._close_previous_ttl()

    def ttl(self, pulse, pc_time, frame_total, cam_seq):
        """Log a pulse given at frame `frame_total` (the last frame received before the pulse)."""
        seg = self.segment
        if seg is None or frame_total < seg.start_total and self.previous is not None:
            seg = self.previous
        if seg is None:
            return
        seg.ttl_csv.write(f'{pulse},{pc_time:.6f},{frame_total - seg.start_total},{frame_total},{cam_seq}\n')
        seg.ttl_csv.flush()

    def close(self):
        if self.segment is not None:
            self._close_segment_async()
        self._close_previous_ttl()
        for t in self._closing:
            t.join()
        self.stderr.close()
