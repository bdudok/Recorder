"""Hardware check for the vEEG recorder. Run on the recording PC with the camera connected and
no other camera software running:

    python -m VideoEEG.hw_check --cam 0

It lists the cameras, opens one with the recorder's settings, records 20 s through the recorder's
camera and writer code, gives 5 TTL pulses 1 s apart, and writes a report to
~/.veeg_recorder/hw_check_cam<N>.txt. Send that report back.
"""
import argparse
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy

from Camera import nncam
from VideoEEG import config
from VideoEEG.camera import NncamCamera
from VideoEEG.writer import SegmentWriter, choose_encoder

lines = []


def report(*args):
    text = ' '.join(str(a) for a in args)
    print(text)
    lines.append(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cam', type=int, default=0)
    parser.add_argument('--seconds', type=float, default=20)
    args = parser.parse_args()
    settings = config.Settings.load(config.settings_path(args.cam))

    report('python', sys.version.split()[0], platform.platform())
    report('SDK', nncam.Nncam.Version())
    ffmpeg = shutil.which(settings.ffmpeg)
    report('ffmpeg', ffmpeg)
    if ffmpeg:
        out = subprocess.run([ffmpeg, '-hide_banner', '-version'], capture_output=True, text=True).stdout
        report(' ', out.splitlines()[0])
    devices = nncam.Nncam.EnumV2()
    report(f'{len(devices)} camera(s)')
    for i, d in enumerate(devices):
        m = d.model
        report(f'  [{i}] {d.displayname} id={d.id} flag=0x{m.flag:x} mono={bool(m.flag & nncam.NNCAM_FLAG_MONO)} '
               f'usb3={bool(m.flag & nncam.NNCAM_FLAG_USB30)} usb3_on_usb2={bool(m.flag & nncam.NNCAM_FLAG_USB30_OVER_USB20)} '
               f'maxspeed={m.maxspeed} io={m.ioctrol} res={[(r.width, r.height) for r in m.res]}')
    if args.cam >= len(devices):
        report('camera index not found')
        return

    cam = NncamCamera(args.cam, settings)
    cam.open()
    c = cam.cam
    report('opened:', cam.info)
    for name in ('HwVersion', 'FpgaVersion', 'ProductionDate', 'SerialNumber', 'MaxBitDepth'):
        try:
            report(f'  {name}:', getattr(c, name)())
        except Exception as ex:
            report(f'  {name}: n/a ({ex})')
    for name in ('NNCAM_OPTION_RGB', 'NNCAM_OPTION_TRIGGER', 'NNCAM_OPTION_FRAMERATE', 'NNCAM_OPTION_NOFRAME_TIMEOUT',
                 'NNCAM_OPTION_MAX_PRECISE_FRAMERATE', 'NNCAM_OPTION_PRECISE_FRAMERATE', 'NNCAM_OPTION_BANDWIDTH'):
        try:
            report(f'  {name} =', c.get_Option(getattr(nncam, name)))
        except Exception as ex:
            report(f'  {name}: n/a ({ex})')
    for name in ('GET_GPIODIR', 'GET_OUTPUTINVERTER', 'GET_OUTPUTMODE'):
        try:
            report(f'  line 2 {name} =', c.IoControl(2, getattr(nncam, 'NNCAM_IOCONTROLTYPE_' + name), 0))
        except Exception as ex:
            report(f'  line 2 {name}: n/a ({ex})')

    encoder = choose_encoder(settings, cam.size)
    report('encoder:', encoder)
    out_dir = Path(tempfile.mkdtemp(prefix='veeg_hwcheck_'))
    settings.out_dir = str(out_dir)
    settings.prefix = 'hwcheck'
    frames, events = [], []
    cam.start(lambda f: frames.append(f), lambda msg, fatal: events.append(msg))
    writer = SegmentWriter(settings, cam.size, encoder, out_dir / 'ffmpeg.log')
    t_end = time.time() + args.seconds
    n_written, pulse_times = 0, []
    next_pulse = time.time() + 2
    while time.time() < t_end:
        while n_written < len(frames):
            writer.write(frames[n_written], n_written)
            n_written += 1
        if time.time() > next_pulse and len(pulse_times) < 5:
            t0 = time.perf_counter()
            cam.ttl(True)
            t1 = time.perf_counter()
            time.sleep(settings.ttl_width_ms / 1000)
            cam.ttl(False)
            pulse_times.append((t1 - t0) * 1000)
            next_pulse += 1
        time.sleep(0.005)
    cam.close()
    while n_written < len(frames):
        writer.write(frames[n_written], n_written)
        n_written += 1
    writer.close()

    report(f'frames received: {len(frames)} in {args.seconds:.0f} s, events: {events}')
    if len(frames) > 2:
        seq = numpy.array([f.seq for f in frames])
        cam_t = numpy.array([f.cam_time_us for f in frames]) / 1000
        host_t = numpy.array([f.host_time for f in frames]) * 1000
        report(f'  seq gaps (dropped by camera/USB): {int((numpy.diff(seq) - 1).clip(0).sum())}')
        report(f'  camera frame interval ms: mean {numpy.diff(cam_t).mean():.3f} sd {numpy.diff(cam_t).std():.3f} '
               f'-> {1000 / numpy.diff(cam_t).mean():.3f} fps')
        report(f'  PC arrival interval ms: mean {numpy.diff(host_t).mean():.3f} sd {numpy.diff(host_t).std():.3f} '
               f'max {numpy.diff(host_t).max():.1f}')
        report(f'  frame shape {frames[0].data.shape}, mean intensity {frames[0].data.mean():.1f}')
    report(f'TTL IoControl call duration ms: {[round(t, 2) for t in pulse_times]}')
    video = next(out_dir.glob('*.mkv'), None)
    if video:
        size_mb = video.stat().st_size / 1e6
        report(f'test video {video} {size_mb:.1f} MB -> {size_mb / args.seconds * 3.6:.1f} GB/hour')

    path = config.APP_DIR / f'hw_check_cam{args.cam}.txt'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines))
    print(f'\nReport saved to {path}. Test video folder: {out_dir}')


if __name__ == '__main__':
    main()
