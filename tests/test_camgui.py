"""CamGUI_v2 with a fake camera that delivers frames from its own thread, like the SDK."""
import os
import threading
import time

import pytest

from helpers import free_port, pump, request

from Camera import nncam
import Camera.CamGUI_v2 as C


class FakeCam:
    fail_open = False

    def __init__(self):
        self.open = True
        self.thread = None

    def __bool__(self):
        return self.open

    def get_Size(self):
        return (64, 48)

    def MaxSpeed(self):
        return 4

    def get_FrameRate(self):
        return (30, 1000, 0)

    def StartPullModeWithCallback(self, callback, ctx):
        def run():
            while self.open:
                callback(nncam.NNCAM_EVENT_IMAGE, ctx)
                time.sleep(1 / 60)
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def Close(self):
        self.open = False
        if self.thread is not None and self.thread is not threading.current_thread():
            self.thread.join()

    def __getattr__(self, name):  # put_*, IoControl, PullImageV3
        return lambda *args, **kwargs: None


def open_fake(cam_id):
    if FakeCam.fail_open:
        raise nncam.HRESULTException(0x80004005)
    return FakeCam()


@pytest.fixture
def camgui(app, monkeypatch):
    monkeypatch.setattr(nncam.Nncam, 'EnumV2', staticmethod(lambda: [type('Device', (), {'id': 'fake'})()]))
    monkeypatch.setattr(nncam.Nncam, 'Open', staticmethod(open_fake))
    FakeCam.fail_open = False
    shown_on = set()
    show_frame = C.GUI_main.show_frame

    def recording_show_frame(self, image):
        shown_on.add(threading.current_thread() is threading.main_thread())
        show_frame(self, image)
    monkeypatch.setattr(C.GUI_main, 'show_frame', recording_show_frame)
    port = free_port()
    gui = C.GUI_main(app, port=port)
    gui.port_for_test = port
    gui.shown_on = shown_on
    yield gui
    gui.cam.Close()
    gui.close()


def arm(gui):
    gui.arm_toggle.setChecked(True)
    gui.arm()


def test_preview_is_shown_on_gui_thread(camgui, app):
    pump(app, 0.5)
    assert not camgui.lbl_video.pixmap().isNull()
    assert camgui.shown_on == {True}


def test_set_go_stop_writes_video_and_timestamps(camgui, app, tmp_path):
    arm(camgui)
    handle = str(tmp_path / 'A_001')
    port = camgui.port_for_test
    assert request(app, port, {'set': True, 'prefix': 'A_001', 'handle': handle})['set']
    assert request(app, port, {'go': True}) == {'go': True}
    pump(app, 1.0)
    reply = request(app, port, {'stop': True})
    assert reply['stop'] and 'frames captured' in reply['log']
    pump(app, 2.5)  # the writer is released 2 s after stop
    assert os.path.getsize(handle + '.avi') > 0
    assert os.path.exists(handle + '_CamTimers.npy')
    assert camgui.shown_on == {True}


def test_replies_when_camera_fails(camgui, app, tmp_path):
    arm(camgui)
    port = camgui.port_for_test
    assert request(app, port, {'set': True, 'prefix': 'A_001', 'handle': str(tmp_path / 'A_001')})['set']
    FakeCam.fail_open = True
    reply = request(app, port, {'go': True})
    assert reply['go'] is False and 'cam error' in reply['log']
    # the socket still works after the error
    assert request(app, port, {'hello': True}) == {'log': "cam: unknown request {'hello': True}"}


def test_no_reply_when_not_armed(camgui, app):
    assert request(app, camgui.port_for_test, {'set': True}, timeout=1.5) is None
