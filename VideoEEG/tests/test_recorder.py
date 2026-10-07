"""Tests with the synthetic camera. Need ffmpeg (with libx264) and ffprobe on PATH.

Run from the repo root: python -m pytest VideoEEG/tests
The supervisor test uses pgrep and SIGKILL, so it runs on Linux only.
"""
import csv
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
import zmq

from VideoEEG import config, recorder as rec_mod
from VideoEEG.camera import FakeCamera
from VideoEEG.recorder import Recorder

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def app_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'APP_DIR', tmp_path / 'app')
    config.log_dir().mkdir(parents=True)
    return tmp_path


def make_recorder(tmp_path, **settings):
    s = config.Settings(out_dir=str(tmp_path / 'vid'), segment_s=1, framerate=30, encoder='libx264',
                        ttl_mean_interval_s=0.2, **settings)
    path = tmp_path / 'settings.json'
    s.save(path)
    return Recorder(0, path, FakeCamera)


def run_for(recorder, seconds):
    t_end = time.time() + seconds
    while time.time() < t_end:
        recorder.check_camera()
        time.sleep(0.05)


def read_csv(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


def count_video_frames(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                          '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0', str(path)],
                         capture_output=True, text=True, check=True)
    return int(out.stdout.strip())


def test_segments_ttl_and_no_frame_loss(app_dir):
    r = make_recorder(app_dir)
    r.start()
    run_for(r, 0.5)
    r.start_recording(prefix='test')
    run_for(r, 3.6)
    r.stop_recording()
    run_for(r, 1)
    r.shutdown()

    videos = sorted((app_dir / 'vid').glob('test-*.mkv'))
    assert len(videos) >= 3
    totals = []
    for v in videos:
        stem = str(v)[:-4]
        frames = read_csv(stem + '_frames.csv')
        assert count_video_frames(v) == len(frames)
        totals += [int(row['frame_total']) for row in frames]
        for row in read_csv(stem + '_ttl.csv'):
            assert 0 <= int(row['frame']) < len(frames)
    assert all(len(read_csv(str(v)[:-4] + '_frames.csv')) == 30 for v in videos[:-1])
    assert totals == list(range(totals[0], totals[0] + len(totals)))  # no frame lost at rotation
    assert sum(len(read_csv(str(v)[:-4] + '_ttl.csv')) for v in videos) >= 5
    assert r.dropped_queue == 0 and r.dropped_camera == 0


def test_reconnect_after_disconnect(app_dir, monkeypatch):
    monkeypatch.setattr(rec_mod, 'REOPEN_INTERVAL_S', 0.3)
    r = make_recorder(app_dir)
    r.start()
    r.start_recording(prefix='rc')
    run_for(r, 1)
    r.camera.open_failures = 2
    r.camera.fail()
    run_for(r, 0.2)
    assert not r.camera_ok
    run_for(r, 2)
    assert r.camera_ok
    n = r.frame_total
    run_for(r, 1)
    assert r.frame_total > n + 20
    r.shutdown()
    assert any('fake open failure' in m for m in r.messages)


def test_stalled_camera_is_reopened(app_dir, monkeypatch):
    monkeypatch.setattr(rec_mod, 'FRAME_TIMEOUT_S', 0.5)
    monkeypatch.setattr(rec_mod, 'REOPEN_INTERVAL_S', 0.3)
    r = make_recorder(app_dir)
    r.start()
    run_for(r, 0.5)
    r.camera._stop.set()  # frames stop without an error event
    run_for(r, 2)
    assert r.camera_ok and time.time() - r.last_frame_time < 0.5
    r.shutdown()


def test_resumes_recording_from_settings(app_dir):
    r = make_recorder(app_dir, recording=True, prefix='resume')
    r.start()
    run_for(r, 1.5)
    r.shutdown()
    assert list((app_dir / 'vid').glob('resume-*.mkv'))


def request(sock, **msg):
    sock.send(json.dumps(msg).encode())
    assert sock.poll(5000), f'no reply to {msg}'
    return json.loads(sock.recv_multipart()[0])


def wait_for_status(sock, condition, timeout=10):
    t_end = time.time() + timeout
    while True:
        status = request(sock, cmd='status')
        if condition(status) or time.time() > t_end:
            return status
        time.sleep(0.2)


@pytest.mark.skipif(sys.platform == 'win32', reason='uses pgrep and SIGKILL')
def test_supervisor_restarts_killed_recorder(tmp_path):
    cam = 9
    env = dict(os.environ, HOME=str(tmp_path), USERPROFILE=str(tmp_path), PYTHONPATH=str(REPO))
    app = tmp_path / '.veeg_recorder'
    config.Settings(out_dir=str(tmp_path / 'vid'), encoder='libx264').save(app / f'cam{cam}_settings.json')
    sup = subprocess.Popen([sys.executable, '-m', 'VideoEEG.recorder', '--cam', str(cam), '--fake', '--supervise'],
                           cwd=REPO, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           start_new_session=True)
    ctx = zmq.Context()

    def connect():
        s = ctx.socket(zmq.REQ)
        s.setsockopt(zmq.LINGER, 0)
        s.connect(f'tcp://127.0.0.1:{config.port(cam)}')
        return s

    try:
        sock = connect()
        assert request(sock, cmd='start', prefix='sup')['ok']
        status = wait_for_status(sock, lambda st: st['file'])
        assert status['recording'] and status['camera_ok'] and status['file'], status['messages']
        time.sleep(1)
        pid = int(subprocess.run(['pgrep', '-f', f'VideoEEG.recorder --cam {cam} --fake$'],
                                 capture_output=True, text=True).stdout.split()[0])
        os.kill(pid, signal.SIGKILL)
        time.sleep(6)  # supervisor notices within 2 s and restarts after 2 s
        sock.close()
        sock = connect()
        status = wait_for_status(sock, lambda st: st['file'], timeout=20)
        assert status['recording'] and status['camera_ok'] and status['file'], status['messages']
        videos = sorted((tmp_path / 'vid').glob('sup-*.mkv'))
        assert len(videos) == 2
        # ffmpeg finalizes the killed recorder's file when its stdin closes
        n_logged = len(read_csv(str(videos[0])[:-4] + '_frames.csv'))
        assert count_video_frames(videos[0]) >= n_logged > 0
        assert request(sock, cmd='quit')['ok'] is False  # refused while recording
        request(sock, cmd='stop')
        assert request(sock, cmd='quit')['ok']
        assert sup.wait(timeout=20) == 0
    finally:
        sock.close()
        ctx.term()
        try:
            os.killpg(sup.pid, signal.SIGKILL)  # supervisor and recorder
        except ProcessLookupError:
            pass
