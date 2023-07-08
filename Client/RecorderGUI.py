# GUI
import sys
from pyqtgraph import Qt
from pyqtgraph.Qt import QtGui, QtCore, QtWidgets

import json
import zmq


'''
App for starting all connected recorders with the same prefix.
Each recorder needs to listen to a separate port for requests
'''

class GUI_main(QtWidgets.QMainWindow):
    def __init__(self, app, cam_port=5555, title='Main'):
        super().__init__()
        self.setWindowTitle(title)
        self.app = app

        #set up connections to each server
        context = zmq.Context()
         #cam connection
        self.cam_socket = context.socket(zmq.REQ)
        self.cam_socket.connect(f"tcp://localhost:{cam_port}")

        # list of all sockets to start and stop for each session
        self.sockets = [('cam', self.cam_socket),]

        # a state variable
        self.state = 'setup'

        #central widget
        centralwidget = QtWidgets.QWidget(self)
        horizontal_layout = QtWidgets.QHBoxLayout()

        # add widgets
        #prefix
        self.input_field = QtWidgets.QLineEdit(self)
        horizontal_layout.addWidget(self.input_field)

        # button
        self.send_button = QtWidgets.QPushButton('Record', )
        self.set_switch_state('ready')
        horizontal_layout.addWidget(self.send_button)
        self.send_button.clicked.connect(self.send)

        # label (now displays exposure time from cam, make groupboxes for each recorder later)
        self.response_label = QtWidgets.QLabel('...', )
        self.response_label.setWordWrap(True)
        horizontal_layout.addWidget(self.response_label)

        self.setCentralWidget(centralwidget)
        self.centralWidget().setLayout(horizontal_layout)
        self.show()

    def send(self):
        # Button will either set up recorders, start them, or stop them, depending on current state
        if self.state == 'setup':
            #check in with each recorder, and exchange settings info
            success = True

            #set up camera
            message = json.dumps({'set': True, 'prefix': self.input_field.text()})
            self.cam_socket.send_json(message)

            response = json.loads(self.cam_socket.recv_json())
            self.response_label.setText(str(response['exposure']))
            if not response['set']:
                success = False
                print('Cam setup failed')

            if success:
                self.set_switch_state('set')

        elif self.state == 'set':
            #start all connections
            success = True
            message = json.dumps({'go': True})
            for sname, socket in self.sockets:
                socket.send_json(message)
            for sname, socket in self.sockets:
                response = json.loads(socket.recv_json())
                if not response['go']:
                    success = False
                    print('Failed starting', sname)

            if success:
                self.set_switch_state('go')

        elif self.state == 'recording':
            #stop all connections
            message = json.dumps({'stop': True})
            for sname, socket in self.sockets:
                socket.send_json(message)
            for sname, socket in self.sockets:
                response = json.loads(socket.recv_json())
                if not response['stop']:
                    print('Failed stopping', sname)

            self.set_switch_state('ready')



    def set_switch_state(self, state):
        if state == 'ready':
            self.send_button.setStyleSheet("background-color : red")
            self.send_button.setText('Ready')
            self.state = 'setup'
        elif state == 'set':
            self.send_button.setStyleSheet("background-color : green")
            self.send_button.setText('Set')
            self.state = 'set'
        elif state == 'go':
            self.send_button.setStyleSheet("background-color : blue")
            self.send_button.setText('Acquiring')
            self.state = 'recording'





def launch_GUI(*args, **kwargs):
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    font = QtGui.QFont()
    app.setFont(font)
    gui_main = GUI_main(app, *args, **kwargs)
    sys.exit(app.exec())

if __name__ == '__main__':
    launch_GUI(title='Recorder')