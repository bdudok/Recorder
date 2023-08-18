# GUI
import sys
from PyQt5.QtCore import Qt, pyqtSignal
from pyqtgraph.Qt import QtGui, QtCore, QtWidgets
from PyQt5.QtGui import QPixmap, QImage
from Camera import nncam
from Camera.simplest import App as CamApp

import json
import zmq

'''
App for displaying camera preview, setting exposure time, and saving stream during recording
Acquisition start controlled by the recorder client
'''
#in this implementation, zmq poll runs in method of App. ideally, it would generate qt events
class GUI_main(QtWidgets.QMainWindow):
    def __init__(self, app, port=5555, title='Main'):
        super().__init__()
        self.setWindowTitle(title)
        self.app = app

        # this process will act as server, and listen to the port for settings and commands to start/stop acquisition
        context = zmq.Context()
        self.server = context.socket(zmq.REP)
        self.server.bind(f"tcp://*:{port}")

        #open camera
        a = nncam.Nncam.EnumV2()
        self.cam = nncam.Nncam.Open(a[0].id)
        self.bits = 24
        # print(a[i].id, 'connected')
        self.sz = self.cam.get_Size()  # width, height
        self.bufsize = nncam.TDIBWIDTHBYTES(self.sz[0] * self.bits) * self.sz[1]
        self.buf = bytes(self.bufsize)
        self.set_exptime()
        self.cam.put_AutoExpoEnable(0)
        self.pDate = None

        #set variables
        self.exposure_time = 4
        self.pollinterval = 1000
        self.vidres = (1440, 1080)
        self.framerate = 30

        #central widget
        self.setMinimumSize(1024, 768)
        centralwidget = QtWidgets.QWidget(self)
        vertical_layout = QtWidgets.QVBoxLayout()
        horizontal_layout = QtWidgets.QHBoxLayout()

        # add widgets
        #slider for exposure time
        self.exposure_setting = QtWidgets.QSlider(Qt.Horizontal)
        self.exposure_setting.setMinimum(1)
        self.exposure_setting.setMaximum(30)
        self.exposure_setting.setValue(self.exposure_time)
        self.exposure_setting.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.exposure_setting.setTickInterval(2)
        self.exposure_setting.valueChanged.connect(self.exposure_update)
        horizontal_layout.addWidget(self.exposure_setting)

        self.exposure_label = QtWidgets.QLabel(str(self.exposure_time), )
        horizontal_layout.addWidget(self.exposure_label)

        # button to 'Arm' for recording
        self.arm_toggle = QtWidgets.QPushButton()
        self.arm_toggle.setCheckable(True)
        self.set_switch_state('arm')
        horizontal_layout.addWidget(self.arm_toggle)
        self.arm_toggle.clicked.connect(self.arm)

        # self.test_button = QtWidgets.QPushButton()
        # self.test_button.setText('Pull')
        # horizontal_layout.addWidget(self.test_button)
        # self.test_button.clicked.connect(self.pullImage)

        # label to display prefix
        self.filename_label = QtWidgets.QLabel('...', )
        horizontal_layout.addWidget(self.filename_label)

        #image
        self.lbl_video = QtWidgets.QLabel()
        self.lbl_video.resize(1024, 768)

        self.setCentralWidget(centralwidget)
        vertical_layout.addLayout(horizontal_layout)
        vertical_layout.addWidget(self.lbl_video)
        self.centralWidget().setLayout(vertical_layout)

        #start live view
        self.cam.StartPullModeWithCallback(self.cameraCallback, self)

        self.show()

    def set_exptime(self, ms=8):
        self.cam.put_ExpoTime(int(ms * 1000))

    def exposure_update(self):
        self.exposure_time = self.exposure_setting.value()
        self.exposure_label.setText(str(self.exposure_time))
        self.set_exptime(float(self.exposure_time))

    def set_prefix(self, prefix):
        self.filename_label.setText(prefix)

    def set_switch_state(self, state):
        # we will have a base state when exposure can be modified, stream not saved
        # after 'arming', exposure is fixed, listening to requests from client
        # when acquisition running, all controls are disabled
        if state == 'armed':
            self.arm_toggle.setStyleSheet("background-color : green")
            self.arm_toggle.setText('Armed')
        elif state == 'arm':
            self.arm_toggle.setStyleSheet("background-color : red")
            self.arm_toggle.setText('Arm')
        elif state == 'running':
            self.arm_toggle.setStyleSheet("background-color : blue")
            self.arm_toggle.setText('Acquiring')

    @staticmethod
    def cameraCallback(nEvent, ctx):
        if nEvent == nncam.NNCAM_EVENT_IMAGE:
            ctx.CameraCallback(nEvent)

    def CameraCallback(self, nEvent):
        if nEvent == nncam.NNCAM_EVENT_IMAGE:
            try:
                self.cam.PullImageV3(self.buf, 0, 24, 0, None)
                self.preview_update()
                # print('pull image ok')#, total = {}'.format(self.total))
            except nncam.HRESULTException as ex:
                print('pull image failed, hr=0x{:x}'.format(ex.hr & 0xffffffff))
        else:
            print('event callback: {}'.format(nEvent))

    def preview_update(self):
        image = QImage(self.buf, self.sz[0], self.sz[1], QImage.Format_RGB888)
        newimage = image.scaled(self.lbl_video.width(), self.lbl_video.height(), Qt.KeepAspectRatio,
                                Qt.FastTransformation)
        self.lbl_video.setPixmap(QPixmap.fromImage(newimage))
        print('Frame grabbed')

    def arm(self):
        #the two states of the button. nb a 3rd state is controlled by the client.
        # could clean this up by handling the state in a consolidated method
        self.armed = self.arm_toggle.isChecked()
        if self.armed:
            self.set_switch_state('armed')
            self.exposure_setting.setEnabled(False)
            #will poll request queue periodically
            self.timer = QtCore.QTimer()
            self.timer.setInterval(self.pollinterval)
            self.timer.timeout.connect(self.listen)
            self.timer.start()

        else:
            self.arm_toggle.setStyleSheet("background-color : red")
            self.arm_toggle.setText('Arm')
            self.exposure_setting.setEnabled(True)
            self.timer.stop()

    def listen(self):
        # poll the request queue, and respond if anything.
        # not in cycle, non-blocking, called periodically by a Qt timer
        if (self.server.poll(self.pollinterval*0.01) & zmq.POLLIN) != 0:
            request = json.loads(self.server.recv_json())
            print(request)
            if 'set' in request:
                self.set_prefix(request['prefix'])
                message = {'set': True, 'exposure': self.exposure_time}
                self.server.send_json(json.dumps(message))
                self.arm_toggle.setEnabled(False)
            elif 'go' in request:
                self.set_switch_state('running')
                message = {'go': True}
                self.server.send_json(json.dumps(message))
            elif 'stop' in request:
                self.timer.stop()
                self.set_switch_state('arm')
                self.arm_toggle.setEnabled(True)
                self.arm_toggle.setChecked(False)
                self.arm()
                message = {'stop': True}
                self.server.send_json(json.dumps(message))


def launch_GUI(*args, **kwargs):
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    font = QtGui.QFont()
    app.setFont(font)
    gui_main = GUI_main(app, *args, **kwargs)
    sys.exit(app.exec())

if __name__ == '__main__':
    launch_GUI(title='Camera', port=5555)