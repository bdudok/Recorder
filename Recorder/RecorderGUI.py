# GUI
import sys
import os
import time

from pyqtgraph import Qt
from pyqtgraph.Qt import QtGui, QtCore, QtWidgets
import datetime
import json
import zmq
import win32com.client
import pyperclip


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
         #scope connection
        self.PrairieLink = win32com.client.Dispatch("PrairieLink64.Application")

        # list of sockets to start and stop for each session
        #PrairieLink uses a different logic so will be added separately from the sockets.
        self.sockets = {'cam': self.cam_socket, 'trm': self.trm_socket}
        self.start_socket_order = ('scope', 'cam', 'trm')
        self.stop_socket_order = ('scope', 'trm', 'cam') #removed session start TTL


        # a state variable
        self.state = 'setup'

        #central widget
        centralwidget = QtWidgets.QWidget(self)
        main_vert_layout = QtWidgets.QVBoxLayout()
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
        #filename
        self.fname_label = QtWidgets.QLineEdit(self)
        self.fname_label.setText(self.prefix)
        horizontal_layout.addLayout(c_layout)

        # button
        btn_layout = QtWidgets.QVBoxLayout()
        self.check_button = QtWidgets.QPushButton('Check name', )
        self.check_button.clicked.connect(self.update_fname)

        self.copy_button = QtWidgets.QPushButton('Copy name', )
        self.copy_button.clicked.connect(self.copy_fname)

        self.send_button = QtWidgets.QPushButton('Record', )
        self.set_switch_state('ready')
        btn_layout.addWidget(self.send_button)
        self.send_button.clicked.connect(self.send)
        horizontal_layout.addLayout(btn_layout)

        # label layout
        self.checkboxes = {}
        label_layout = QtWidgets.QVBoxLayout()
        #add a color button for each host

        scope_button_layout = QtWidgets.QHBoxLayout()
        self.scope_response_label = QtWidgets.QLabel('Scope', )
        self.scope_response_label.setStyleSheet("background-color : grey")
        self.scope_checkbox = QtWidgets.QCheckBox()
        self.scope_checkbox.setChecked(True)
        self.checkboxes['scope'] = self.scope_checkbox
        scope_button_layout.addWidget(self.scope_checkbox)
        scope_button_layout.addWidget(self.scope_response_label)
        label_layout.addLayout(scope_button_layout)

        cam_button_layout = QtWidgets.QHBoxLayout()
        self.cam_response_label = QtWidgets.QLabel('Camera', )
        self.cam_response_label.setStyleSheet("background-color : grey")
        self.cam_checkbox = QtWidgets.QCheckBox()
        self.cam_checkbox.setChecked(True)
        self.checkboxes['cam'] = self.cam_checkbox
        cam_button_layout.addWidget(self.cam_checkbox)
        cam_button_layout.addWidget(self.cam_response_label)
        label_layout.addLayout(cam_button_layout)

        trm_button_layout = QtWidgets.QHBoxLayout()
        self.trm_response_label = QtWidgets.QLabel('Treadmill', )
        self.trm_response_label.setStyleSheet("background-color : grey")
        self.trm_checkbox = QtWidgets.QCheckBox()
        self.trm_checkbox.setChecked(True)
        self.checkboxes['trm'] = self.trm_checkbox
        trm_button_layout.addWidget(self.trm_checkbox)
        trm_button_layout.addWidget(self.trm_response_label)
        label_layout.addLayout(trm_button_layout)

        self.buttons = {'scope': self.scope_response_label, 'cam': self.cam_response_label,
                        'trm': self.trm_response_label}
        horizontal_layout.addLayout(label_layout)

        self.setMinimumSize(1024, 98)
        self.setCentralWidget(centralwidget)
        bottom_row_layout = QtWidgets.QHBoxLayout()
        bottom_row_layout.addWidget(self.check_button)
        bottom_row_layout.addWidget(self.copy_button)
        bottom_row_layout.addWidget(self.fname_label)
        main_vert_layout.addLayout(horizontal_layout)
        main_vert_layout.addLayout(bottom_row_layout)
        self.centralWidget().setLayout(main_vert_layout)
        self.update_folder()
        self.show()

    def select_path_callback(self):
        #get a folder
        self.wdir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select Folder', self.wdir)
        self.select_path_button.setText(self.wdir)
        self.update_folder()
        #TODO save settings (filename) at rec start and reload on startup

    def update_folder(self):
        self.path = '/'.join((self.wdir, self.project_field.text(), ))
        if not os.path.exists(self.path):
            os.mkdir(self.path)
            print('Creating folder:', self.path)
            self.counter_field.setText('000')
        else:
            flist = [fn for fn in os.listdir(self.path) if os.path.isdir(os.path.join(self.path, fn))]
            counters = [fn.split('_')[-1].split('-')[0] for fn in flist]
            c = len(flist)
            while f'{c:03}' in counters:
                c += 1
            self.counter_field.setText(f'{c:03}')

    def update_fname(self):
        self.update_folder()
        fn = '_'.join((self.animal_field.text(), self.date_field.text(),
                       self.prefix_field.text(), self.counter_field.text()))
        self.prefix = fn
        self.fname_label.setText(self.prefix)
        self.file_handle = '/'.join((self.path, self.prefix))
        print(self.file_handle)

    def copy_fname(self):
        pyperclip.copy(self.prefix + '-000')

    def send(self):
        # Button will either set up recorders, start them, or stop them, depending on current state
        if self.state == 'setup':
            #check in with each recorder, and exchange settings info
            success = True

            #get file handle
            self.update_fname()
            op_dir = self.file_handle+'-000'
            self.file_handle_subdir = os.path.join(op_dir, self.prefix)

            #open log
            self.log = logger(self.file_handle + '.log.txt')
            self.log.w('Connecting sockets.')

            sname = 'scope'
            if self.checkboxes[sname].isChecked():
                if self.PrairieLink.Connect():
                    self.PrairieLink.SendScriptCommands(f'-SetSavePath "{os.path.dirname(self.file_handle)}"')
                    self.PrairieLink.SendScriptCommands(f'-SetFileName TSeries "{self.prefix}"')
                    self.PrairieLink.SendScriptCommands(f'-SetFileIteration TSeries 0')
                    self.scope_response_label.setStyleSheet("background-color : green")
                    self.log.w(sname + ' connected.')
                else:
                    success = False
                    self.scope_response_label.setStyleSheet("background-color : red")
                    print('Scope connection failed',)

            #set up camera
            sname = 'cam'
            if self.checkboxes[sname].isChecked() and success:
                message = json.dumps({'set': True, 'prefix': fn, 'handle': self.file_handle_subdir})
                self.cam_response_label.setStyleSheet("background-color : lightred")
                self.app.processEvents()
                self.sockets[sname].send_json(message)
                response = json.loads(self.sockets[sname].recv_json())
                if not response['set']:
                    success = False
                    self.cam_response_label.setStyleSheet("background-color : red")
                    print('Cam setup failed:', response)
                else:
                    if 'log' in response:
                        self.log.w(sname + ' responds ' + response['log'])
                    self.cam_response_label.setStyleSheet("background-color : green")

            #set up treadmill
            sname = 'trm'
            if self.checkboxes[sname].isChecked() and success:
                message = json.dumps({'set': True, 'prefix': fn, 'handle': self.file_handle_subdir})
                self.trm_response_label.setStyleSheet("background-color : lightred")
                self.app.processEvents()
                self.sockets[sname].send_json(message)
                response = json.loads(self.sockets[sname].recv_json())
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
                if self.checkboxes[sname].isChecked():
                    if sname not in ('scope', ):
                        socket = self.sockets[sname]
                        socket.send_json(message)
                        response = json.loads(socket.recv_json())
                        go = response['go']
                    elif sname == 'scope':
                        go = self.PrairieLink.SendScriptCommands('-TSeries')
                        time.sleep(1) #wait for scope to start, otherwise can miss the start trigger.
                    if go:
                        self.log.w(sname + ' running')
                    else:
                        success = False
                        print('Failed starting', sname)
                        self.log.w(sname + ' start failed')

            self.log.dump()
            self.set_switch_state('go')
            if not success:
                print('Failed to start, stop everything.')
                self.send()

            ##TODO: check every 5 seconds if the scope and treadmill are still running and stop acquisition if not.

        elif self.state == 'recording':
            #stop all connections
            self.log.w('stopping')
            message = json.dumps({'stop': True})
            for sname in self.stop_socket_order:
                stopmsg = None
                stopSuccess = True
                if self.checkboxes[sname].isChecked():
                    if sname not in ('scope',):
                        socket = self.sockets[sname]
                        socket.send_json(message)
                        response = json.loads(socket.recv_json())
                        if 'log' in response:
                            stopmsg = response['log']
                        if not response['stop']:
                            print('Failed stopping', sname)
                            stopSuccess = False
                    elif sname == 'scope':
                        stopmsg = self.PrairieLink.SendScriptCommands('-Abort')
                        self.PrairieLink.Disconnect()
                        if stopmsg:
                            stopSuccess = True
                    if stopSuccess:
                        self.log.w(sname + ' responds ' + str(stopmsg))
                        self.buttons[sname].setStyleSheet("background-color : lightgreen")
                    else:
                        self.log.w(sname + ' not responding to stop')
                        self.log.dump()

            self.log.w('end of log')
            self.log.cl()
            #increment counter
            self.update_folder()
            self.update_fname()

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