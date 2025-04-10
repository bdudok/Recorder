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
from BaserowAPI.BaserowRequests import GetSessions
from Recorder.config import *
from OptoTrigger.serial_send import send_settings, configs
stim_configs = configs

'''
App for starting all connected recorders with the same prefix.
Each recorder needs to listen to a separate port for requests
To edit stimulator configs, go to Recorder.config
'''


config_list = list(stim_configs.keys())
config_list.sort()
script_list = list(set([y['v'] for x, y in stim_configs.items()]))
script_list.sort()


class GUI_main(QtWidgets.QMainWindow):
    def __init__(self, app, cam_port=5555, treadmill_port=5556, title='Recorder'):
        super().__init__()
        self.setWindowTitle(title)
        self.app = app

        self.debug = False

        #default parameters
        if self.debug:
            self.wdir = '/Users/u247640/tmp'
        else:
            self.wdir = 'E:/_Recorder'
        self.prefix = 'Animal_DDMMYYYY_experiment_001'
        self.path = None
        self.saved_fields = ('project_field', 'animal_field', 'prefix_field', 'template_field', 'user_field')
        self.selector_fields = ('user_field', )
        self.settings_name = self.wdir + '_recorder_fields.json'
        self.stripchars = "'+. *?~!@#$%^&*(){}:[]><,/"+'"'+'\\'
        if os.path.exists(self.settings_name):
            with open(self.settings_name) as f:
                self.settings_dict = json.load(f)
            print(self.settings_dict)
        else:
            self.settings_dict = {}

        #set up connection to Baserow database
        self.db = GetSessions(token)

        #set up connections to each server
        context = zmq.Context()
         #cam connection
        self.cam_socket = context.socket(zmq.REQ)
        self.cam_socket.connect(f"tcp://localhost:{cam_port}")
         #treadmill connection
        self.trm_socket = context.socket(zmq.REQ)
        self.trm_socket.connect(f"tcp://localhost:{treadmill_port}")
         #scope connection
        if not self.debug:
            self.PrairieLink = win32com.client.Dispatch("PrairieLink64.Application")

        # list of sockets to start and stop for each session
        #PrairieLink uses a different logic so will be added separately from the sockets.
        self.sockets = {'cam': self.cam_socket, 'trm': self.trm_socket}
        self.start_socket_order = ('cam', 'scope', 'trm', ) #unfortunately scope has to start first with empty folder
        self.stop_socket_order = ('scope', 'trm', 'cam') #removed session start TTL


        # a state variable
        self.state = 'setup'

        #tabs
        self.table_widget = QtWidgets.QWidget(self) #central widget
        self.table_widget.layout = QtWidgets.QVBoxLayout(self.table_widget)
        self.tabs = QtWidgets.QTabWidget()
        self.tab1 = QtWidgets.QWidget()
        self.tab2 = QtWidgets.QWidget()
        self.tabs.resize(300, 100)

        self.tabs.addTab(self.tab1, "Session")
        self.tabs.addTab(self.tab2, "Stimulator")

        ##TAB1 acquisition controls
        self.tab1.layout = QtWidgets.QVBoxLayout()
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

        #user
        u_layout = QtWidgets.QVBoxLayout()
        u_layout.addWidget(QtWidgets.QLabel('User'))
        self.user_field = QtWidgets.QComboBox(self)
        self.user_field.addItems(user_list)
        u_layout.addWidget(self.user_field)
        horizontal_layout.addLayout(u_layout)

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

        #template prefix
        self.template_label = QtWidgets.QLabel('Template', )

        self.template_field = QtWidgets.QLineEdit(self)
        self.template_field.setText('JEDI-Sncg104_2025-04-02_Veh_549-000')

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

        stim_button_layout = QtWidgets.QHBoxLayout()
        self.stim_response_label = QtWidgets.QLabel('Stimulator', )
        self.stim_response_label.setStyleSheet("background-color : grey")
        self.stim_checkbox = QtWidgets.QCheckBox()
        self.stim_checkbox.setChecked(False)
        self.checkboxes['stim'] = self.stim_checkbox
        stim_button_layout.addWidget(self.stim_checkbox)
        stim_button_layout.addWidget(self.stim_response_label)
        label_layout.addLayout(stim_button_layout)

        self.buttons = {'scope': self.scope_response_label, 'cam': self.cam_response_label,
                        'trm': self.trm_response_label}
        horizontal_layout.addLayout(label_layout)

        self.setMinimumSize(1024, 98)
        # self.setCentralWidget(centralwidget)
        bottom_row_layout = QtWidgets.QHBoxLayout()
        bottom_row_layout.addWidget(self.template_label)
        bottom_row_layout.addWidget(self.template_field)
        bottom_row_layout.addWidget(self.check_button)
        bottom_row_layout.addWidget(self.copy_button)
        bottom_row_layout.addWidget(self.fname_label)
        self.tab1.layout.addLayout(horizontal_layout)
        self.tab1.layout.addLayout(bottom_row_layout)

        #add all this on tab1
        self.tab1.setLayout(self.tab1.layout)

        #TAB2: stim controls
        ##TAB1 acquisition controls
        self.tab2.layout = QtWidgets.QVBoxLayout()
        horizontal_layout = QtWidgets.QHBoxLayout()

        #selector for configs
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel('Load Config'))
        self.stim_config_field = QtWidgets.QComboBox(self)
        self.stim_config_field.addItems(config_list)
        self.stim_config_field.currentTextChanged.connect(self.select_config_callback)
        layout.addWidget(self.stim_config_field)
        horizontal_layout.addLayout(layout)

        #selector for scripts
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel('Script version'))
        self.script_config_field = QtWidgets.QComboBox(self)
        self.script_config_field.addItems(script_list)
        layout.addWidget(self.script_config_field)
        horizontal_layout.addLayout(layout)

        #fields for config
        self.config_setting_fields = {}
        for fieldname in stim_config_fields:
            layout = QtWidgets.QVBoxLayout()
            layout.addWidget(QtWidgets.QLabel(f"'{fieldname}':"+stim_field_labels[fieldname]))
            self.config_setting_fields[fieldname] = QtWidgets.QLineEdit(self)
            # self.config_setting_fields[fieldname].setText('')
            layout.addWidget(self.config_setting_fields[fieldname])
            horizontal_layout.addLayout(layout)

        #add all this on tab2
        self.tab2.layout.addLayout(horizontal_layout)
        self.tab2.setLayout(self.tab2.layout)

        #add tabs to table
        self.table_widget.layout.addWidget(self.tabs)
        self.table_widget.setLayout(self.table_widget.layout)

        self.setCentralWidget(self.table_widget)
        # self.centralWidget().setLayout(main_vert_layout)
        #update fields from file
        for fieldname in self.saved_fields:
            if fieldname in self.settings_dict:
                if fieldname in self.selector_fields:
                    getattr(self, fieldname).setCurrentText(self.settings_dict[fieldname])
                else:
                    getattr(self, fieldname).setText(self.settings_dict[fieldname])

        self.update_folder()
        self.select_config_callback(config_list[0])
        self.show()

    def select_path_callback(self):
        #get a folder
        self.wdir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select Folder', self.wdir)
        self.select_path_button.setText(self.wdir)
        self.update_folder()

    def select_config_callback(self, configname):
        config = stim_configs[configname]
        self.script_config_field.setCurrentText(config['v'])
        for fn in stim_config_fields:
            self.config_setting_fields[fn].setText(str(config.get(fn, '')))

    def update_folder(self):
        fn = ''.join([c for c in self.project_field.text() if c not in self.stripchars])
        self.path = '/'.join((self.wdir, fn))
        if not os.path.exists(self.path):
            os.mkdir(self.path)
            print('Creating folder:', self.path)
            self.counter_field.setText('000')
        else:
            flist = [fn for fn in os.listdir(self.path) if os.path.isdir(os.path.join(self.path, fn))]
            counters = [fn.split('_')[-1].split('-')[0] for fn in flist]
            c = max(len(flist), int(self.counter_field.text()))
            while f'{c:03}' in counters:
                c += 1
            self.counter_field.setText(f'{c:03}')

    def update_fname(self):
        self.update_folder()
        fn = '_'.join((self.animal_field.text(), self.date_field.text(),
                       self.prefix_field.text(), self.counter_field.text()))
        # sanitize it because ppl use whatever
        fn = ''.join([c for c in fn if c not in self.stripchars])
        self.prefix = fn
        self.fname_label.setText(self.prefix)
        self.file_handle = '/'.join((self.path, self.prefix))
        print(self.file_handle)

        #get and populate session data
        sdat = dict(self.db.get_session(self.template_field.text().strip(' \r\n\t')).iloc[0])
        sdat['User'] = self.user_field.currentText()
        sdat['Image.ID'] = self.prefix + '-000'
        sdat['Task'] = 'MotionCorr'
        sdat['Date'] = self.date_field.text()
        self.sdat = sdat

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
            # if not os.path.exists(op_dir):
            #     os.mkdir(op_dir)
            self.file_handle_subdir = os.path.join(op_dir, self.prefix)

            #open log
            self.log = logger(self.file_handle_subdir + '.log.txt')
            print(self.file_handle_subdir + '.log.txt')
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

            #set up stimulator
            sname = 'stim'
            if self.checkboxes[sname].isChecked() and success:
                settings = {'v': self.script_config_field.currentText()}
                for fn in stim_config_fields:
                    v = self.config_setting_fields[fn].text()
                    if len(v):
                        settings[fn] = v
                self.stim_response_label.setStyleSheet("background-color : lightred")
                self.app.processEvents()
                response = send_settings(self.stim_config_field.currentText(), settings)
                rtext = response['message']
                if not 'OK' in rtext:
                    success = False
                    self.stim_response_label.setStyleSheet("background-color : red")
                    print('stim setup failed:', rtext)
                else:
                    #store config in DB
                    self.sdat['Stim.Config'] = json.dumps(response['settings'])
                    self.log.w(sname + ' responds ' + rtext)
                    self.stim_response_label.setStyleSheet("background-color : green")

            #set up camera
            sname = 'cam'
            if self.checkboxes[sname].isChecked() and success:
                message = json.dumps({'set': True, 'prefix': self.prefix, 'handle': self.file_handle_subdir})
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
                message = json.dumps({'set': True, 'prefix': self.prefix, 'handle': self.file_handle_subdir})
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
            self.send_button.setText('Starting...')
            for sname in self.start_socket_order:
                if self.checkboxes[sname].isChecked():
                    if sname not in ('scope', ):
                        socket = self.sockets[sname]
                        socket.send_json(message)
                        response = json.loads(socket.recv_json())
                        go = response['go']
                    elif sname == 'scope':
                        go = self.PrairieLink.SendScriptCommands('-TSeries')
                        time.sleep(0.5)  # wait for everything else to start
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
            else:
                for fieldname in self.saved_fields:
                    if fieldname in ('user_field', ):
                        v = getattr(self, fieldname).currentText() #dropdowns
                    else:
                        v = getattr(self, fieldname).text() #simple entry
                    self.settings_dict[fieldname] = v
                with open(self.settings_name, 'w') as f:
                    json.dump(self.settings_dict, f)
                #after everything is started fine, create entry in BaseRow
                self.db.put_new(self.sdat)

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
    def __init__(self, handle, defer_until='scope running'):
        self.defer_until = defer_until #create file only after image folder exists
        self.handle=handle
        self.f = None
        self.s = ''

    def w(self, message):
        ts = datetime.datetime.now().isoformat(timespec='seconds')
        self.s += ts + ':' + message + '\n'
        print(ts, message)

    def dump(self):
        if self.defer_until is not None:
            if self.defer_until in self.s:
                self.f = open(self.handle, 'a')
                self.defer_until = None
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