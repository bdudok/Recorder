"""vEEG recorder GUI: camera preview, recording controls and status.

    python -m VideoEEG.gui --cam 0

The GUI starts the recorder for the camera if it is not running yet, and only sends it commands.
Closing the GUI while recording leaves the recording running; reopen the GUI to see or stop it.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import zmq
from PySide6 import QtCore, QtGui, QtWidgets

from VideoEEG import config

REPO = Path(__file__).resolve().parents[1]
POLL_MS = 200


class RecorderClient:
    """REQ socket that is recreated after a timeout, so a restarted recorder is picked up again."""

    def __init__(self, cam):
        self.address = f'tcp://127.0.0.1:{config.port(cam)}'
        self.ctx = zmq.Context()
        self.sock = None
        self._connect()

    def _connect(self):
        if self.sock is not None:
            self.sock.close()
        self.sock = self.ctx.socket(zmq.REQ)
        self.sock.setsockopt(zmq.LINGER, 0)
        self.sock.connect(self.address)

    def request(self, timeout_ms=1000, **msg):
        """Returns (reply, data), or (None, None) if the recorder does not answer."""
        self.sock.send(json.dumps(msg).encode())
        if not self.sock.poll(timeout_ms):
            self._connect()
            return None, None
        parts = self.sock.recv_multipart()
        return json.loads(parts[0]), (parts[1] if len(parts) > 1 else None)

    def close(self):
        self.sock.close()
        self.ctx.term()


def start_recorder(cam, fake=False):
    """Start the supervised recorder as an independent process that outlives the GUI."""
    cmd = [sys.executable, '-m', 'VideoEEG.recorder', '--cam', str(cam), '--supervise'] + (['--fake'] if fake else [])
    if os.name == 'nt':
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(cmd, cwd=REPO, creationflags=flags, close_fds=True)
    else:
        subprocess.Popen(cmd, cwd=REPO, start_new_session=True, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)


def sanitize(name):
    return re.sub(r'[^\w\-.]', '_', name.strip()) or 'vEEG'


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, cam, fake=False):
        super().__init__()
        self.cam = cam
        self.client = RecorderClient(cam)
        self.status = None
        self.fields_loaded = False
        self.missed = 0
        self.setWindowTitle(f'vEEG camera {cam}')
        self.setMinimumSize(1024, 768)

        self.exposure = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.exposure.setRange(1, 30)
        self.exposure.setTickInterval(2)
        self.exposure.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.exposure_label = QtWidgets.QLabel()
        self.exposure.valueChanged.connect(lambda v: self.exposure_label.setText(f'Exposure: {v} ms'))
        self.exposure.sliderReleased.connect(self.send_exposure)
        self.folder_button = QtWidgets.QPushButton('Select folder')
        self.folder_button.clicked.connect(self.choose_folder)
        self.folder_label = QtWidgets.QLabel()
        self.prefix = QtWidgets.QLineEdit()
        self.prefix.setPlaceholderText('file name prefix')
        self.rec_button = QtWidgets.QPushButton()
        self.rec_button.setMinimumWidth(140)
        self.rec_button.clicked.connect(self.toggle_recording)

        self.state_label = QtWidgets.QLabel()
        font = self.state_label.font()
        font.setPointSize(font.pointSize() + 4)
        font.setBold(True)
        self.state_label.setFont(font)
        self.details_label = QtWidgets.QLabel()
        self.file_label = QtWidgets.QLabel()
        self.file_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.messages = QtWidgets.QPlainTextEdit()
        self.messages.setReadOnly(True)
        self.messages.setMaximumHeight(90)
        self.video = QtWidgets.QLabel()
        self.video.setAlignment(QtCore.Qt.AlignCenter)
        self.video.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)
        self.video.setStyleSheet('background-color: black')

        self.prefix.setMinimumWidth(250)
        row1 = QtWidgets.QHBoxLayout()
        row1.addWidget(self.exposure_label)
        row1.addWidget(self.exposure, stretch=1)
        row1.addWidget(self.rec_button)
        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(self.folder_button)
        row2.addWidget(self.folder_label, stretch=1)
        row2.addWidget(QtWidgets.QLabel('Name:'))
        row2.addWidget(self.prefix)
        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addWidget(self.state_label)
        layout.addWidget(self.details_label)
        layout.addWidget(self.file_label)
        layout.addWidget(self.video, stretch=1)
        layout.addWidget(self.messages)
        central = QtWidgets.QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        reply, _ = self.client.request(timeout_ms=1000, cmd='status')
        if reply is None:
            start_recorder(cam, fake)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(POLL_MS)
        self.update_controls()

    # --- commands ---
    def send_exposure(self):
        self.client.request(cmd='set', exposure_ms=self.exposure.value())

    def choose_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select folder', self.folder_label.text())
        if folder:
            self.folder_label.setText(folder)
            self.client.request(cmd='set', out_dir=folder)

    def toggle_recording(self):
        if self.status is None:
            return
        if self.status['recording']:
            answer = QtWidgets.QMessageBox.question(self, 'Stop recording', 'Stop the recording?')
            if answer == QtWidgets.QMessageBox.Yes:
                self.client.request(cmd='stop')
        else:
            prefix = sanitize(self.prefix.text())
            self.prefix.setText(prefix)
            self.client.request(cmd='start', prefix=prefix, out_dir=self.folder_label.text())
        self.poll()

    # --- display ---
    def poll(self):
        status, _ = self.client.request(timeout_ms=500, cmd='status')
        if status is None:
            self.missed += 1
            if self.missed > 3:
                self.status = None
                self.update_controls()
            return
        self.missed = 0
        self.status = status
        if not self.fields_loaded:
            s = status['settings']
            self.exposure.setValue(s['exposure_ms'])
            self.exposure_label.setText(f'Exposure: {s["exposure_ms"]} ms')
            self.folder_label.setText(s['out_dir'])
            self.prefix.setText(s['prefix'])
            self.fields_loaded = True
        self.update_controls()
        reply, data = self.client.request(timeout_ms=500, cmd='preview')
        if reply and reply.get('ok'):
            h, w = reply['shape']
            image = QtGui.QImage(data, w, h, w, QtGui.QImage.Format_Grayscale8)
            pixmap = QtGui.QPixmap.fromImage(image).scaled(self.video.size(), QtCore.Qt.KeepAspectRatio,
                                                          QtCore.Qt.FastTransformation)
            self.video.setPixmap(pixmap)

    def update_controls(self):
        st = self.status
        recording = bool(st and st['recording'])
        for w in (self.exposure, self.folder_button, self.prefix):
            w.setEnabled(st is not None and not recording)
        self.rec_button.setEnabled(st is not None)
        self.rec_button.setText('Stop' if recording else 'Record')
        self.rec_button.setStyleSheet('background-color: #c62828; color: white' if recording else '')
        if st is None:
            self.set_state('RECORDER NOT RESPONDING (restarting)', '#c62828')
            return
        if not st['camera_ok']:
            self.set_state('CAMERA NOT CONNECTED' + (' (recording resumes when it returns)' if recording else ''),
                           '#c62828')
        elif recording:
            self.set_state('RECORDING', '#2e7d32')
        else:
            self.set_state('Preview (not recording)', '#555555')
        free = st['free_gb']
        low_disk = free is not None and free < st['settings']['min_free_gb']
        disk = f'disk free: {free:.0f} GB' if free is not None else 'disk free: ?'
        if low_disk:
            disk = f'<span style="color:#c62828"><b>{disk} (LOW)</b></span>'
        self.details_label.setText(
            f'{st["fps"]:.1f} fps | frames: {st["frames"]} | dropped: {st["dropped_camera"] + st["dropped_queue"]} | '
            f'TTL pulses: {st["pulses"]} | encoder: {st["encoder"] or "-"} | {disk}')
        self.file_label.setText(f'File: {st["file"]}' if st['file'] else '')
        text = '\n'.join(st['messages'])
        if self.messages.toPlainText() != text:
            self.messages.setPlainText(text)

    def set_state(self, text, color):
        self.state_label.setText(text)
        self.state_label.setStyleSheet(f'color: {color}')

    def closeEvent(self, event):
        if self.status and self.status['recording']:
            answer = QtWidgets.QMessageBox.question(
                self, 'Recording continues',
                'The recording continues in the background after closing this window.\n'
                'Reopen the app to see or stop it. Close the window?')
            if answer != QtWidgets.QMessageBox.Yes:
                event.ignore()
                return
        elif self.status is not None:
            self.client.request(cmd='quit')
        self.timer.stop()
        self.client.close()
        event.accept()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--cam', type=int, help='camera index; asked at startup if not given')
    parser.add_argument('--fake', action='store_true', help='start the recorder with a synthetic camera')
    args = parser.parse_args()
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    cam = args.cam
    if cam is None:
        cam, ok = QtWidgets.QInputDialog.getInt(None, 'vEEG recorder', 'Camera index:', 0, 0, 7)
        if not ok:
            return
    window = MainWindow(cam, args.fake)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
