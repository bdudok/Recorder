# GUI
import sys
import os
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

        #default parameters
        self.wdir = 'E:/_Recorder'
        self.project = 'Test'
        self.prefix = 'Animal_DDMMYYYY_experiment_001'

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
        #path
        p_layout = QtWidgets.QVBoxLayout()
        path_label = QtWidgets.QLabel('Path')
        p_layout.addWidget(path_label)
        self.select_path_button = QtWidgets.QPushButton(self.wdir)
        p_layout.addWidget(self.select_path_button)
        self.select_path_button.clicked.connect(self.select_path_callback)
        horizontal_layout.addLayout(p_layout)

        #project
        pr_layout = QtWidgets.QVBoxLayout()
        project_label = QtWidgets.QLabel('Project')
        pr_layout.addWidget(project_label)
        self.project_field = QtWidgets.QLineEdit(self)
        self.project_field.setText(self.project)
        pr_layout.addWidget(self.project_field)
        horizontal_layout.addLayout(pr_layout)

        #prefix
        pf_layout = QtWidgets.QVBoxLayout()
        prefix_label = QtWidgets.QLabel('Prefix')
        pf_layout.addWidget(prefix_label)
        self.prefix_field = QtWidgets.QLineEdit(self)
        self.prefix_field.setText(self.prefix)
        pf_layout.addWidget(self.prefix_field)
        horizontal_layout.addLayout(pf_layout)

        # button
        self.send_button = QtWidgets.QPushButton('Record', )
        self.set_switch_state('ready')
        horizontal_layout.addWidget(self.send_button)
        self.send_button.clicked.connect(self.send)

        # label (now displays exposure time from cam, make groupboxes for each recorder later)
        self.response_label = QtWidgets.QLabel('...', )
        self.response_label.setWordWrap(True)
        horizontal_layout.addWidget(self.response_label)

        self.setMinimumSize(1024, 98)
        self.setCentralWidget(centralwidget)
        self.centralWidget().setLayout(horizontal_layout)
        self.show()

    def select_path_callback(self, path=None):
        #get a folder
        # if path is None:
        self.wdir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select Folder', self.wdir)
        self.select_path_button.setText(self.wdir)

    def send(self):
        # Button will either set up recorders, start them, or stop them, depending on current state
        if self.state == 'setup':
            #check in with each recorder, and exchange settings info
            success = True

            #get file handle
            self.file_handle = '/'.join((self.wdir, self.project_field.text(), self.prefix_field.text()))
            print(self.file_handle)

            #set up camera
            message = json.dumps({'set': True, 'prefix': self.prefix_field.text(), 'handle': self.file_handle})
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