"""Camera access for the vEEG recorder.

NncamCamera wraps the nncam SDK (ToupTek OEM). FakeCamera produces synthetic frames with the
same interface, for testing without hardware.

The SDK calls the event callback on its own internal thread. The callback only pulls the frame
into a new array and hands it to `on_frame`; it must never touch the GUI or close the camera.
"""
import ctypes
import logging
import threading
import time
from dataclasses import dataclass

import numpy

log = logging.getLogger(__name__)

TTL_LINE = 2  # IoControl line number of GPIO0


@dataclass
class Frame:
    data: numpy.ndarray     # uint8, (height, width)
    seq: int                # frame sequence number from the camera
    cam_time_us: int        # camera timestamp, microseconds
    host_time: float        # time.time() when the frame arrived


class CameraError(Exception):
    pass


class NncamCamera:
    def __init__(self, index, settings):
        from Camera import nncam
        self.nncam = nncam
        self.index = index
        self.settings = settings
        self.cam = None
        self.size = None
        self.info = {}
        self._io_lock = threading.Lock()
        self._ttl_idle = True  # output inverter state when no pulse is given

    def open(self):
        nncam = self.nncam
        devices = nncam.Nncam.EnumV2()
        if self.index >= len(devices):
            raise CameraError(f'camera {self.index} not found ({len(devices)} connected)')
        dev = devices[self.index]
        try:
            cam = nncam.Nncam.Open(dev.id)
        except nncam.HRESULTException as ex:
            raise CameraError(f'open failed: {ex}') from ex
        if cam is None:
            raise CameraError('open failed')
        self.cam = cam
        s = self.settings
        # Same configuration as Camera/EEG-Cam.py, which is known to produce TTL output.
        cam.put_Speed(1)
        cam.put_AutoExpoEnable(0)
        cam.put_VFlip(1 if s.vflip else 0)
        cam.put_ExpoTime(int(s.exposure_ms * 1000))
        cam.put_Option(nncam.NNCAM_OPTION_TRIGGER, 1)  # software trigger, run continuously below
        cam.put_Option(nncam.NNCAM_OPTION_FRAMERATE, s.framerate)
        self._try_option(nncam.NNCAM_OPTION_RGB, 3)  # 8-bit grey output on mono cameras
        self._try_option(nncam.NNCAM_OPTION_NOFRAME_TIMEOUT, 3000)
        cam.IoControl(TTL_LINE, nncam.NNCAM_IOCONTROLTYPE_SET_GPIODIR, 0x01)  # output
        cam.IoControl(TTL_LINE, nncam.NNCAM_IOCONTROLTYPE_SET_OUTPUTINVERTER, self._ttl_idle)
        self.size = cam.get_Size()  # (width, height)
        self.info = {'model': dev.displayname, 'id': dev.id, 'fw': cam.FwVersion(),
                     'sdk': nncam.Nncam.Version(), 'size': self.size}
        log.info('camera opened: %s', self.info)

    def _try_option(self, option, value):
        try:
            self.cam.put_Option(option, value)
        except self.nncam.HRESULTException as ex:
            log.warning('option 0x%x=%s not accepted: %s', option, value, ex)

    def start(self, on_frame, on_event):
        self._on_frame = on_frame
        self._on_event = on_event
        self.cam.StartPullModeWithCallback(self._callback, self)
        self.cam.Trigger(0xFFFF)  # continuous software trigger

    @staticmethod
    def _callback(event, self):
        nncam = self.nncam
        if event == nncam.NNCAM_EVENT_IMAGE:
            w, h = self.size
            data = numpy.empty((h, w), numpy.uint8)
            info = nncam.NncamFrameInfoV3()
            try:
                self.cam.PullImageV3((ctypes.c_char * data.nbytes).from_buffer(data), 0, 8, -1, info)
            except nncam.HRESULTException as ex:
                self._on_event(f'pull failed: {ex}', False)
                return
            self._on_frame(Frame(data, info.seq, info.timestamp, time.time()))
        elif event in (nncam.NNCAM_EVENT_ERROR, nncam.NNCAM_EVENT_DISCONNECTED,
                       nncam.NNCAM_EVENT_NOFRAMETIMEOUT, nncam.NNCAM_EVENT_NOPACKETTIMEOUT):
            self._on_event(f'camera event 0x{event:x}', True)

    def set_exposure(self, ms):
        with self._io_lock:
            self.cam.put_ExpoTime(int(ms * 1000))

    def ttl(self, high):
        with self._io_lock:
            if self.cam is None:
                return
            self.cam.IoControl(TTL_LINE, self.nncam.NNCAM_IOCONTROLTYPE_SET_OUTPUTINVERTER,
                               (not self._ttl_idle) if high else self._ttl_idle)

    def close(self):
        with self._io_lock:
            if self.cam is not None:
                try:
                    self.cam.Close()
                finally:
                    self.cam = None


class FakeCamera:
    """Synthetic camera with the NncamCamera interface. `fail()` simulates a disconnect."""

    def __init__(self, index, settings, size=(320, 240)):
        self.index = index
        self.settings = settings
        self.size = size
        self.info = {'model': 'fake', 'size': size}
        self.ttl_log = []
        self.open_failures = 0  # number of following open() calls that fail
        self._thread = None
        self._stop = threading.Event()
        self._seq = 0

    def open(self):
        if self.open_failures > 0:
            self.open_failures -= 1
            raise CameraError('fake open failure')

    def start(self, on_frame, on_event):
        self._on_frame = on_frame
        self._on_event = on_event
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        w, h = self.size
        period = 1 / self.settings.framerate
        ramp = numpy.arange(w, dtype=numpy.uint8)
        t_next = time.perf_counter()
        while not self._stop.is_set():
            data = numpy.broadcast_to(ramp + numpy.uint8(self._seq % 256), (h, w)).copy()
            self._on_frame(Frame(data, self._seq, int(self._seq * period * 1e6), time.time()))
            self._seq += 1
            t_next += period
            time.sleep(max(0.0, t_next - time.perf_counter()))

    def fail(self):
        self._stop.set()
        self._on_event('fake disconnect', True)

    def set_exposure(self, ms):
        pass

    def ttl(self, high):
        self.ttl_log.append((time.time(), high))

    def close(self):
        self._stop.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join()
