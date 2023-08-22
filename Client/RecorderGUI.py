# GUI
import sys
import os
from pyqtgraph import Qt
from pyqtgraph.Qt import QtGui, QtCore, QtWidgets
import datetime
import json
import zmq


'''
App for starting all connected recorders with the same prefix.
Each recorder needs to listen to a separate port for requests
'''

class GUI_main(QtWidgets.QMainWindow):
    def __init__(self, app, cam_port=5555, treadmill_port=5556, title='Recorder'):
        super().__init__()
        self.setWindowTitle(title)
        self.app = app

        #default parameters
        self.wdir = 'E:/_Recorder'
        self.prefix = 'Animal_DDMMYYYY_experiment_001'
        self.path = None

        #set up connections to each server
        context = zmq.Context()
         #cam connection
        self.cam_socket = context.socket(zmq.REQ)
        self.cam_socket.connect(f"tcp://localhost:{cam_port}")
         #treadmill connection
        self.trm_socket = context.socket(zmq.REQ)
        self.trm_socket.connect(f"tcp://localhost:{treadmill_port}")

        # list of all sockets to start and stop for each session
        self.sockets = {'cam': self.cam_socket, 'trm': self.trm_socket}
        self.start_socket_order = ('cam', 'trm')
        self.stop_socket_order = ('trm', 'cam')

        # a state variable
        self.state = 'setup'

        #central widget
        centralwidget = QtWidgets.QWidget(self)
        horizontal_layout = QtWidgets.QHBoxLayout()

        # add widgets
        #path
        p_layout = QtWidgets.QVBoxLayout()
        p_layout.addWidget(QtWidgets.QLabel('Path'))
        self.select_path_button = QtWidgets.QPushButton(self.wdir)
        p_layout.addWidget(self.select_path_button)
        self.select_path_button.clicked.connect(self.select_path_callback)
        horizontal_layout.addLayout(p_layout)

        #project
        pr_layout = QtWidgets.QVBoxLayout()
        pr_layout.addWidget(QtWidgets.QLabel('Project'))
        self.project_field = QtWidgets.QLineEdit(self)
        self.project_field.setText('Test')
        pr_layout.addWidget(self.project_field)
        horizontal_layout.addLayout(pr_layout)

        #animal
        a_layout = QtWidgets.QVBoxLayout()
        a_layout.addWidget(QtWidgets.QLabel('Animal'))
        self.animal_field = QtWidgets.QLineEdit(self)
        self.animal_field.setText('Animal')
        a_layout.addWidget(self.animal_field)
        horizontal_layout.addLayout(a_layout)

        #day
        d_layout = QtWidgets.QVBoxLayout()
        d_layout.addWidget(QtWidgets.QLabel('Date'))
        self.date_field = QtWidgets.QLineEdit(self)
        self.date_field.setText(datetime.date.today().isoformat())
        d_layout.addWidget(self.date_field)
        horizontal_layout.addLayout(d_layout)

        #prefix
        pf_layout = QtWidgets.QVBoxLayout()
        pf_layout.addWidget(QtWidgets.QLabel('Experiment'))
        self.prefix_field = QtWidgets.QLineEdit(self)
        self.prefix_field.setText('movie')
        pf_layout.addWidget(self.prefix_field)
        horizontal_layout.addLayout(pf_layout)

        #counter
        c_layout = QtWidgets.QVBoxLayout()
        c_layout.addWidget(QtWidgets.QLabel('Counter'))
        self.counter_field = QtWidgets.QLineEdit(self)
        self.counter_field.setText('000')
        c_layout.addWidget(self.counter_field)
        horizontal_layout.addLayout(c_layout)

        # button
        self.send_button = QtWidgets.QPushButton('Record', )
        self.set_switch_state('ready')
        horizontal_layout.addWidget(self.send_button)
        self.send_button.clicked.connect(self.send)
        #TODO add an abort button that can close the connections in case one didn't start

        # label layout
        label_layout = QtWidgets.QVBoxLayout()
        #add a color button for each host
        self.cam_response_label = QtWidgets.QLabel('Camera', )
        self.cam_response_label.setStyleSheet("background-color : grey")
        label_layout.addWidget(self.cam_response_label)
        self.trm_response_label = QtWidgets.QLabel('Treadmill', )
        self.trm_response_label.setStyleSheet("background-color : grey")
        label_layout.addWidget(self.trm_response_label)
        horizontal_layout.addLayout(label_layout)

        self.setMinimumSize(1024, 98)
        self.setCentralWidget(centralwidget)
        self.centralWidget().setLayout(horizontal_layout)
        self.show()

    def select_path_callback(self):
        #get a folder
        self.wdir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select Folder', self.wdir)
        self.select_path_button.setText(self.wdir)
        self.update_folder()


    def update_folder(self):
        self.path = '/'.join((self.wdir, self.project_field.text(), ))
        if not os.path.exists(self.path):
            os.mkdir(self.path)
            print('Creating folder:', self.path)
            self.counter_field.setText('000')
        else:
            flist = [fn for fn in os.listdir(self.path) if '.log.' in fn]
            counters = [fn.split('.')[0].split('_')[-1] for fn in flist]
            c = len(flist)
            while f'{c:03}' in counters:
                c += 1
            self.counter_field.setText(f'{c:03}')

    def send(self):
        # Button will either set up recorders, start them, or stop them, depending on current state
        #TODO set timeouts for recv
        if self.state == 'setup':
            #check in with each recorder, and exchange settings info
            success = True

            #get file handle
            if self.path is None:
                self.update_folder()
            fn = '_'.join((self.animal_field.text(), self.date_field.text(),
                           self.prefix_field.text(), self.counter_field.text()))
            self.file_handle = '/'.join((self.path, fn))
            print(self.file_handle)

            #open log
            self.log = logger(self.file_handle + '.log.txt')
            self.log.w('Connecting sockets.')

            #set up camera
            message = json.dumps({'set': True, 'prefix': fn, 'handle': self.file_handle})
            self.cam_response_label.setStyleSheet("background-color : lightred")
            self.app.processEvents()
            self.cam_socket.send_json(message)
            sname = 'cam'
            response = json.loads(self.cam_socket.recv_json())
            if not response['set']:
                success = False
                self.cam_response_label.setStyleSheet("background-color : red")
                print('Cam setup failed:', response)
            else:
                if 'log' in response:
                    self.log.w(sname + ' responds ' + response['log'])
                self.cam_response_label.setStyleSheet("background-color : green")

            #set up treadmill
            message = json.dumps({'set': True, 'prefix': fn, 'handle': self.file_handle})
            self.trm_response_label.setStyleSheet("background-color : lightred")
            self.app.processEvents()
            self.trm_socket.send_json(message)
            sname = 'trm'
            response = json.loads(self.trm_socket.recv_json())
            if not response['set']:
                success = False
                self.trm_response_label.setStyleSheet("background-color : red")
                print('Treadmill setup failed:', response)
            else:
                if 'log' in response:
                    self.log.w(sname + ' responds ' + response['log'])
                self.trm_response_label.setStyleSheet("background-color : green")


            if success:
                self.set_switch_state('set')

        elif self.state == 'set':
            self.log.w('Recording start')
            #start all connections
            success = True
            message = json.dumps({'go': True})
            for sname in self.start_socket_order:
                socket = self.sockets[sname]
                socket.send_json(message)
                response = json.loads(socket.recv_json())
                if not response['go']:
                    success = False
                    print('Failed starting', sname)
                    self.log.w(sname + ' start failed')
                else:
                    self.log.w(sname + ' running')

            if success:
                self.set_switch_state('go')
            self.log.dump()

        elif self.state == 'recording':
            #stop all connections
            self.log.w('stopping')
            message = json.dumps({'stop': True})
            buttons = {'cam': self.cam_response_label, 'trm': self.trm_response_label}
            for sname in self.stop_socket_order:
                socket = self.sockets[sname]
                response = json.loads(socket.recv_json())
                if 'log' in response:
                    self.log.w(sname + ' responds ' + response['log'])
                    buttons[sname].setStyleSheet("background-color : lightgreen")
                if not response['stop']:
                    print('Failed stopping', sname)
                    self.log.w(sname + ' not responding to stop')
                    buttons[sname].setStyleSheet("background-color : red")
                    self.log.dump()
            self.log.w('end of log')
            self.log.cl()
            #increment counter
            self.update_folder()

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

class logger:
    def __init__(self, handle):
        if handle is None:
            self.f = None
        else:
            self.f = open(handle, 'a')
        self.s = ''

    def w(self, message):
        ts = datetime.datetime.now().isoformat(timespec='seconds')
        self.s += ts + ':' + message + '\n'
        print(ts, message)

    def dump(self):
        if self.f is not None:
            self.f.write(self.s)
            self.f.flush()
            os.fsync(self.f.fileno())
        self.s = ''

    def cl(self):
        if self.f is not None:
            self.f.write(self.s)
            self.f.close()




def launch_GUI(*args, **kwargs):
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    font = QtGui.QFont()
    app.setFont(font)
    gui_main = GUI_main(app, *args, **kwargs)
    sys.exit(app.exec())

if __name__ == '__main__':
    launch_GUI(title='Recorder')