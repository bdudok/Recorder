"""RecorderGUI_CL against fake cam/treadmill/RealTime servers, PrairieLink mocked."""
import json
import os
import sys
import threading
import time
from types import SimpleNamespace
from unittest import mock

import numpy
import pytest
import requests
import zmq
from PySide6 import QtCore

from helpers import FakeServer, free_port, pump

import Recorder.RecorderGUI_CL as R


@pytest.fixture
def recorder(app, prairie_link, tmp_path):
    ports = {'cam': free_port(), 'trm': free_port()}
    gui = R.GUI_main(app, cam_port=ports['cam'], treadmill_port=ports['trm'], baserow_enabled=False,
                     wdir=str(tmp_path))
    gui.request_timeout = 1
    gui.ports_for_test = ports
    yield gui
    gui.close()


@pytest.fixture
def servers(recorder):
    s = {name: FakeServer(port) for name, port in recorder.ports_for_test.items()}
    yield s
    for server in s.values():
        server.close()


def press(recorder):
    """Click the main record button (set up, start or stop, depending on the state)."""
    recorder.send()


def test_request_times_out_and_next_request_works(recorder):
    port = recorder.ports_for_test['cam']
    deaf = FakeServer(port, reply=lambda request: None)  # receives but never answers
    t0 = time.time()
    assert recorder.request('cam', {'set': True}) is None
    assert time.time() - t0 < 3
    deaf.close()
    server = FakeServer(port)
    try:
        assert recorder.request('cam', {'go': True}) == {'go': True}
    finally:
        server.close()


def test_no_server_does_not_block(recorder):
    t0 = time.time()
    assert recorder.request('trm', {'set': True}) is None
    assert time.time() - t0 < 3


def test_session_without_scope(recorder, servers, app):
    recorder.checkboxes['scope'].setChecked(False)
    press(recorder)
    assert recorder.state == 'set'
    folder = os.path.dirname(recorder.file_handle_subdir)
    assert os.path.isdir(folder)  # created by the Recorder, since no scope will create it
    press(recorder)
    assert recorder.state == 'recording'
    log = recorder.file_handle_subdir + '.log.txt'
    press(recorder)
    assert recorder.state == 'setup'
    text = open(log).read()
    assert 'cam running' in text and 'trm running' in text and 'end of log' in text
    for server in servers.values():
        assert server.commands() == ['set', 'go', 'stop']


@pytest.mark.parametrize('stim_checked, expected', [(False, None), (True, '{"p": 5}')])
def test_stim_config_in_baserow_follows_stimulator_checkbox(recorder, servers, monkeypatch, stim_checked, expected):
    template = {'Image.ID': 'template', 'Stim.Config': '{"p": 99}'}
    recorder.baserow_enabled = True
    recorder.db = mock.MagicMock()
    recorder.db.get_session.return_value = SimpleNamespace(iloc=[template])
    monkeypatch.setattr(R, 'send_settings', lambda name, settings: {'message': 'OK', 'settings': {'p': 5}})
    recorder.checkboxes['scope'].setChecked(False)
    recorder.checkboxes['stim'].setChecked(stim_checked)
    press(recorder)
    press(recorder)
    assert recorder.state == 'recording'
    sdat = recorder.db.put_new.call_args.args[0]
    assert sdat.get('Stim.Config') == expected
    press(recorder)


@pytest.fixture
def baserow(recorder):
    '''The Recorder with Baserow on, against a fake database with one template.'''
    recorder.baserow_enabled = True
    recorder.db = mock.MagicMock()
    recorder.db.get_session.return_value = SimpleNamespace(iloc=[{'Image.ID': 'template'}])
    recorder.db.put_new.return_value = SimpleNamespace(status_code=200)
    recorder.checkboxes['scope'].setChecked(False)
    return recorder.db


def test_baserow_entry_is_saved(recorder, servers, baserow):
    press(recorder)
    press(recorder)
    assert baserow.put_new.call_count == 1
    assert recorder.baserow_label.isHidden()
    assert not os.path.exists(recorder.file_handle_subdir + '.baserow.json')
    press(recorder)


def test_records_without_baserow_when_template_lookup_fails(recorder, servers, baserow, monkeypatch):
    baserow.get_session.side_effect = requests.ConnectionError('down')
    monkeypatch.setattr(R, 'send_settings', lambda name, settings: {'message': 'OK', 'settings': {'p': 5}})
    recorder.checkboxes['stim'].setChecked(True)
    press(recorder)
    assert not recorder.baserow_label.isHidden()
    press(recorder)
    assert recorder.state == 'recording'
    log = recorder.file_handle_subdir + '.log.txt'
    press(recorder)
    assert recorder.state == 'setup'
    assert 'No Baserow entry' in open(log).read()
    assert baserow.put_new.call_count == 0


@pytest.mark.parametrize('failure', [
    {'side_effect': requests.Timeout('slow')},
    {'return_value': SimpleNamespace(status_code=400)},
    {'side_effect': IndexError('bad row')},
])
def test_recording_continues_when_baserow_entry_fails(recorder, servers, baserow, failure):
    baserow.put_new.configure_mock(**failure)
    recorder.timer_checkbox.setChecked(True)
    recorder.timer_field.setText('1')
    press(recorder)
    press(recorder)
    assert recorder.state == 'recording'
    assert recorder.autostop_timer.isActive()
    assert not recorder.baserow_label.isHidden()
    log = recorder.file_handle_subdir + '.log.txt'
    press(recorder)
    assert recorder.state == 'setup'
    text = open(log).read()
    assert 'No Baserow entry' in text and 'Baserow row saved to' in text
    assert os.path.exists(recorder.file_handle_subdir + '.baserow.json')


def test_saved_baserow_row_can_be_uploaded_later(recorder, servers, baserow):
    if R.GetSessions is None:
        pytest.skip('needs LNCM-lib on PYTHONPATH')
    baserow.get_session.return_value = SimpleNamespace(iloc=[{
        'id': numpy.int64(7), 'Image.ID': 'template', 'Mouse.ID': [{'id': numpy.int64(3), 'value': 'M1'}],
        'Count': numpy.int64(2), 'Flag': numpy.bool_(True), 'Empty': None}])
    baserow.put_new.side_effect = requests.ConnectionError('down')
    press(recorder)
    press(recorder)
    expected = R.GetSessions(token='fake').sanitize_put(baserow.put_new.call_args.args[0])
    with open(recorder.file_handle_subdir + '.baserow.json') as f:
        saved = json.load(f)
    assert R.GetSessions(token='fake').sanitize_put(saved) == expected
    press(recorder)


def test_recording_continues_when_backup_cannot_be_saved(recorder, servers, baserow):
    baserow.put_new.side_effect = requests.ConnectionError('down')
    press(recorder)
    os.makedirs(recorder.file_handle_subdir + '.baserow.json')  # a folder in the way makes open() fail
    press(recorder)
    assert recorder.state == 'recording'
    log = recorder.file_handle_subdir + '.log.txt'
    press(recorder)
    assert 'could not be saved' in open(log).read()


def test_baserow_label_stays_until_next_session(recorder, servers, baserow):
    baserow.get_session.side_effect = requests.ConnectionError('down')
    press(recorder)
    press(recorder)
    baserow.get_session.side_effect = None
    press(recorder)
    assert not recorder.baserow_label.isHidden()  # still shown after the stop, with the server back
    press(recorder)
    assert recorder.baserow_label.isHidden()
    press(recorder)
    press(recorder)
    assert baserow.put_new.call_count == 1


def test_missing_template_stops_setup(recorder, servers, baserow):
    baserow.get_session.return_value = SimpleNamespace(iloc=[])
    with pytest.raises(IndexError):
        press(recorder)
    assert recorder.state == 'setup'
    assert servers['cam'].commands() == []


@pytest.mark.parametrize('setting, expected', [('ON', True), ('OFF', False)])
def test_pupil_light_setting_is_sent_to_treadmill(recorder, servers, setting, expected):
    recorder.checkboxes['scope'].setChecked(False)
    recorder.LED_field.setCurrentText(setting)
    press(recorder)
    assert servers['trm'].requests[0]['houselight'] is expected
    assert 'houselight' not in servers['cam'].requests[0]


def test_start_failure_stops_everything(recorder, servers):
    recorder.checkboxes['scope'].setChecked(False)
    servers['trm'].reply = lambda request: {'go': False, 'log': 'no'} if 'go' in request else {
        k: True for k in ('set', 'stop') if k in request}
    press(recorder)
    press(recorder)
    assert recorder.state == 'setup'
    assert servers['cam'].commands() == ['set', 'go', 'stop']
    assert servers['trm'].commands() == ['set', 'go', 'stop']


def test_setup_fails_when_device_not_armed(recorder, servers):
    recorder.checkboxes['scope'].setChecked(False)
    servers['trm'].close()  # treadmill app not answering
    press(recorder)
    assert recorder.state == 'setup'
    assert 'red' in recorder.trm_response_label.styleSheet()


def test_manual_stop_cancels_autostop(recorder, servers, app):
    recorder.checkboxes['scope'].setChecked(False)
    recorder.timer_checkbox.setChecked(True)
    recorder.timer_field.setText(str(1.5 / 60))  # 1.5 s
    press(recorder)
    press(recorder)
    pump(app, 1.0)
    press(recorder)  # manual stop at 1 s; the auto stop of this recording would come at 1.5 s
    press(recorder)
    press(recorder)  # second recording
    pump(app, 1.0)
    assert recorder.state == 'recording'  # not stopped by the first recording's timer
    pump(app, 1.0)
    assert recorder.state == 'setup'  # stopped by its own timer
    assert servers['cam'].commands() == ['set', 'go', 'stop'] * 2


def test_uncaught_exception_goes_to_session_log(recorder, servers, app, monkeypatch):
    monkeypatch.setattr(sys, 'excepthook', recorder.excepthook)
    recorder.checkboxes['scope'].setChecked(False)
    press(recorder)
    press(recorder)
    log = recorder.file_handle_subdir + '.log.txt'

    def fail():
        raise RuntimeError('test failure')
    QtCore.QTimer.singleShot(0, fail)
    pump(app, 0.2)
    press(recorder)
    assert 'RuntimeError: test failure' in open(log).read()


def test_remote_start(recorder, app):
    """Waits through 'Waiting' replies and one unanswered request (5 s timeout), then starts on 'ON'."""
    port = free_port()
    recorder.closedloop_host, recorder.closedloop_port = '127.0.0.1', port
    for name in ('scope', 'cam', 'trm'):
        recorder.checkboxes[name].setChecked(False)
    recorder.remote_checkbox.setChecked(True)

    def realtime():
        s = zmq.Context.instance().socket(zmq.REP)
        s.setsockopt(zmq.LINGER, 0)
        s.bind(f'tcp://127.0.0.1:{port}')
        for _ in range(3):
            s.recv_json()
            s.send_json(json.dumps({'Waiting': True}))
        s.recv_json()  # leave one request unanswered: the Recorder must replace its socket
        s.close()
        time.sleep(0.2)
        s = zmq.Context.instance().socket(zmq.REP)
        s.setsockopt(zmq.LINGER, 0)
        s.bind(f'tcp://127.0.0.1:{port}')
        s.recv_json()
        s.send_json(json.dumps({'ON': True}))
        s.close()
    thread = threading.Thread(target=realtime, daemon=True)
    thread.start()
    recorder.listen()  # returns after the recording was started
    thread.join(1)
    assert recorder.state == 'recording'
    recorder.remote_checkbox.setChecked(False)
    press(recorder)
