# GUI
import sys
from PyQt5.QtCore import Qt
from pyqtgraph.Qt import QtGui, QtCore, QtWidgets

import json
import zmq

#in this test, zmq listener will run in separate loop. ideally, it would generate qt events
class GUI_main(QtWidgets.QMainWindow):
    def __init__(self, app, port=5555, title='Main'):
        super().__init__()
        self.setWindowTitle(title)
        self.app = app

        #socket
        context = zmq.Context()
        self.server = context.socket(zmq.REP)
        self.server.bind(f"tcp://*:{port}")
        # self.poller = zmq.Poller()
        # self.poller.register(self.server, zmq.POLLIN)

        #set variables
        self.exposure_time = 7
        self.pollinterval = 1000
        self.tcount = 0

        #central widget
        centralwidget = QtWidgets.QWidget(self)
        horizontal_layout = QtWidgets.QHBoxLayout()

        # add widgets
        #input
        self.exposure_setting = QtWidgets.QSlider(Qt.Horizontal)
        self.exposure_setting.setMinimum(1)
        self.exposure_setting.setMaximum(100)
        self.exposure_setting.setValue(self.exposure_time)
        self.exposure_setting.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.exposure_setting.setTickInterval(5)
        self.exposure_setting.valueChanged.connect(self.exposure_update)

        horizontal_layout.addWidget(self.exposure_setting)

        self.exposure_label = QtWidgets.QLabel(str(self.exposure_time), )
        horizontal_layout.addWidget(self.exposure_label)

        # button
        self.arm_toggle = QtWidgets.QPushButton()
        self.arm_toggle.setCheckable(True)
        self.set_switch_state('arm')
        horizontal_layout.addWidget(self.arm_toggle)
        self.arm_toggle.clicked.connect(self.arm)

        # label
        self.filename_label = QtWidgets.QLabel('...', )
        horizontal_layout.addWidget(self.filename_label)

        self.setCentralWidget(centralwidget)
        self.centralWidget().setLayout(horizontal_layout)
        self.show()

    def exposure_update(self):
        self.exposure_time = self.exposure_setting.value()
        self.exposure_label.setText(str(self.exposure_time))

    def set_prefix(self, prefix):
        self.filename_label.setText(prefix)

    def set_switch_state(self, state):
        if state == 'armed':
            self.arm_toggle.setStyleSheet("background-color : green")
            self.arm_toggle.setText('Armed')
        elif state == 'arm':
            self.arm_toggle.setStyleSheet("background-color : red")
            self.arm_toggle.setText('Arm')
        elif state == 'running':
            self.arm_toggle.setStyleSheet("background-color : blue")
            self.arm_toggle.setText('Acquiring')

    def arm(self):
        self.armed = self.arm_toggle.isChecked()
        if self.armed:
            self.set_switch_state('armed')
            self.exposure_setting.setEnabled(False)
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
        # print(f'timer running {self.tcount}')
        # self.tcount += 1
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



    # def oldget(self):
    #     message = self.input_field.text()
    #     self.socket.send_string(message)
    #
    #     response = self.socket.recv_string()
    #     self.response_label.setText(response)
    #
    # def listen(self):
    #     #  Wait for next request from client
    #     print('listening')
    #     message = self.socket.recv_string()
    #     self.response_label.setText(message)
    #     #  Send reply back to client
    #     print(message)
    #     self.socket.send_string(message)





def launch_GUI(*args, **kwargs):
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    font = QtGui.QFont()
    app.setFont(font)
    gui_main = GUI_main(app, *args, **kwargs)
    sys.exit(app.exec())

if __name__ == '__main__':
    launch_GUI(title='CamHost', port=5555)