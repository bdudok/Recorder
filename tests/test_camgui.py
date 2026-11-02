"""CamGUI with a fake camera that delivers frames from its own thread, like the SDK."""
import os
import threading
import time
from unittest import mock

import pytest

from helpers import free_port, pump, request

from Camera import nncam
import Camera.CamGUI as C


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
def camgui(app, monkeypatch, tmp_path):
    monkeypatch.setattr(nncam.Nncam, 'EnumV2', staticmethod(lambda: [type('Device', (), {'id': 'fake'})()]))
    monkeypatch.setattr(nncam.Nncam, 'Open', staticmethod(open_fake))
    FakeCam.fail_open = False
    shown_on = set()
    show_frame = C.GUI_main.show_frame

    def recording_show_frame(self, image):
        shown_on.add(threading.current_thread() is threading.main_thread())
        show_frame(self, image)
    monkeypatch.setattr(C.GUI_main, 'show_frame', recording_show_frame)
    monkeypatch.setattr(C, 'ERROR_LOG', tmp_path / 'ErrorLog.txt')
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


def test_recording_uses_the_delay_slider(camgui, app, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(FakeCam, 'IoControl', lambda self, *args: calls.append(args), raising=False)
    camgui.delay_setting.setValue(20)
    arm(camgui)
    port = camgui.port_for_test
    assert request(app, port, {'set': True, 'prefix': 'A_001', 'handle': str(tmp_path / 'A_001')})['set']
    calls.clear()
    assert request(app, port, {'go': True}) == {'go': True}
    assert calls[-1] == (0, nncam.NNCAM_IOCONTROLTYPE_SET_TRIGGERDELAY, 20000)
    assert request(app, port, {'stop': True})['stop']
    pump(app, 2.5)  # the writer is released 2 s after stop


def test_replies_when_camera_fails(camgui, app, tmp_path):
    arm(camgui)
    port = camgui.port_for_test
    assert request(app, port, {'set': True, 'prefix': 'A_001', 'handle': str(tmp_path / 'A_001')})['set']
    FakeCam.fail_open = True
    reply = request(app, port, {'go': True})
    assert reply['go'] is False and 'cam error' in reply['log']
    # the socket still works after the error
    assert request(app, port, {'hello': True}) == {'log': "cam: unknown request {'hello': True}"}


def from_sdk_thread(function, *args):
    thread = threading.Thread(target=function, args=args)
    thread.start()
    thread.join()


def test_camera_event_is_shown_over_the_image(camgui, app):
    from_sdk_thread(camgui.CameraCallback, nncam.NNCAM_EVENT_DISCONNECTED)
    pump(app, 0.1)
    assert not camgui.error_label.isHidden()
    assert camgui.error_label.parent() is camgui.lbl_video
    assert camgui.error_label.text() == 'Camera disconnected'
    assert 'Camera disconnected' in C.ERROR_LOG.read_text()


def test_routine_camera_events_are_not_errors(camgui, app):
    from_sdk_thread(camgui.CameraCallback, nncam.NNCAM_EVENT_EXPOSURE)
    pump(app, 0.1)
    assert camgui.error_label.isHidden()


def test_repeated_error_is_counted_on_one_line(camgui, app):
    for _ in range(3):
        from_sdk_thread(camgui.CameraCallback, nncam.NNCAM_EVENT_TRIGGERFAIL)
    pump(app, 0.1)
    assert camgui.error_label.text() == 'Camera trigger failed (x3)'
    assert C.ERROR_LOG.read_text().count('Camera trigger failed') == 1


def test_only_the_latest_errors_are_shown(camgui):
    for i in range(camgui.max_error_lines + 3):
        camgui.show_error(f'error {i}')
    assert camgui.error_label.text().count('\n') == camgui.max_error_lines - 1
    assert 'error 0' not in camgui.error_label.text()


def test_exception_on_sdk_thread_is_shown(camgui, app, monkeypatch):
    def fail():
        raise OSError('disk full')
    camgui.stop_cam()
    monkeypatch.setattr(camgui, 'preview_update', fail)
    from_sdk_thread(camgui.CameraCallback, nncam.NNCAM_EVENT_IMAGE)
    pump(app, 0.1)
    assert 'disk full' in camgui.error_label.text()


def test_error_stays_through_stop_and_clears_at_next_session(camgui, app, tmp_path):
    arm(camgui)
    port = camgui.port_for_test
    assert request(app, port, {'set': True, 'prefix': 'A_001', 'handle': str(tmp_path / 'A_001')})['set']
    assert request(app, port, {'go': True})['go']
    from_sdk_thread(camgui.CameraCallback, nncam.NNCAM_EVENT_ERROR)
    pump(app, 0.3)
    assert request(app, port, {'stop': True})['stop']
    assert not camgui.error_label.isHidden()
    assert request(app, port, {'set': True, 'prefix': 'A_002', 'handle': str(tmp_path / 'A_002')})['set']
    assert camgui.error_label.isHidden()


def test_click_dismisses_error(camgui):
    camgui.show_error('some error')
    camgui.error_label.mousePressEvent(None)
    assert camgui.error_label.isHidden()


def test_failed_request_is_shown(camgui, app, tmp_path):
    arm(camgui)
    port = camgui.port_for_test
    assert request(app, port, {'set': True, 'prefix': 'A_001', 'handle': str(tmp_path / 'A_001')})['set']
    FakeCam.fail_open = True
    request(app, port, {'go': True})
    assert "'go' failed" in camgui.error_label.text()
    assert 'Traceback' in C.ERROR_LOG.read_text()


def test_uncaught_exception_is_shown(camgui):
    try:
        raise ValueError('bad slot')
    except ValueError as e:
        camgui.excepthook(ValueError, e, e.__traceback__)
    assert 'bad slot' in camgui.error_label.text()


def test_no_camera_gives_message_box_and_log(app, monkeypatch, tmp_path):
    monkeypatch.setattr(C, 'ERROR_LOG', tmp_path / 'ErrorLog.txt')
    monkeypatch.setattr(nncam.Nncam, 'EnumV2', staticmethod(lambda: []))
    monkeypatch.setattr(C.QtWidgets, 'QApplication', lambda argv: app)
    box = mock.MagicMock()
    monkeypatch.setattr(C.QtWidgets.QMessageBox, 'critical', box)
    with pytest.raises(SystemExit):
        C.launch_GUI(port=free_port())
    assert 'No camera found' in box.call_args.args[2]
    assert 'No camera found' in C.ERROR_LOG.read_text()


def test_waiting_label_is_cleared_when_disarmed(camgui, app):
    arm(camgui)
    assert camgui.filename_label.text() == 'Waiting for recorder'
    camgui.arm_toggle.setChecked(False)
    camgui.arm()
    assert camgui.filename_label.text() == 'Set exposure then arm.'


def test_no_reply_when_not_armed(camgui, app):
    assert request(app, camgui.port_for_test, {'set': True}, timeout=1.5) is None
