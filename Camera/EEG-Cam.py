# GUI
import sys
import numpy
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from pyqtgraph.Qt import QtGui, QtCore, QtWidgets
from PyQt5.QtGui import QPixmap, QImage
from Camera import nncam
import cv2
import os
import datetime


import json
import zmq

'''
For Video-EEG
App for displaying camera preview, setting exposure time, and saving stream during recording
'''
#in this implementation, zmq poll runs in method of App. ideally, it would generate qt events
class GUI_main(QtWidgets.QMainWindow):
    def __init__(self, app, title='Main'):
        super().__init__()
        self.setWindowTitle(title)
        self.app = app

        #set variables
        self.cam_index = 0
        self.wdir = 'C:\EEG/vid/'
        self.exposure_time = 4
        self.vidres = (1440, 1080)
        self.framerate = 30
        self.fpsvals = []
        self.camspeed = 1 # 0:15 fps ; 1:30 fps; 2:45;3:60... etc, does not depend on exposure. Not exact.
        self.ipi = 5 #(mean interval of rsync signals in sec)
        self.reclen = 60*60 #file length, in seconds
        self.nsync = 0
        self.synctimes = numpy.empty((int(2*60*60/self.ipi), 5), dtype=numpy.int32)
        self.frame_counter = 0
        self.bits = 24

        #open camera
        self.cam = None
        self.camlist = nncam.Nncam.EnumV2()
        self.open_camera()

        #set up output
        # self.timer = QTimer(self)
        # self.timer.timeout.connect(self.onTimer)
        self.is_writing = False
        self.outfile = None
        self.fourcc = cv2.VideoWriter_fourcc(*'DIVX')
        self.file_ext = '.avi'


        #central widget
        self.setMinimumSize(1024, 768)
        centralwidget = QtWidgets.QWidget(self)
        grid_layout = QtWidgets.QGridLayout()
        horizontal_layout = QtWidgets.QHBoxLayout()

        # add widgets
        #camera selector
        horizontal_layout.addWidget(QtWidgets.QLabel('Cam'))
        self.cam_box = QtWidgets.QComboBox()
        for cami in range(len(self.camlist)):
            self.cam_box.insertItem(cami, str(cami))
        self.cam_box.setCurrentIndex(self.cam_index)
        self.cam_box.currentIndexChanged.connect(self.change_camera)
        horizontal_layout.addWidget(self.cam_box)

        #slider for exposure time
        self.exposure_label = QtWidgets.QLabel(f'Exposure: {self.exposure_time} ms')
        horizontal_layout.addWidget(self.exposure_label)
        self.exposure_setting = QtWidgets.QSlider(Qt.Horizontal)
        self.exposure_setting.setMinimum(1)
        self.exposure_setting.setMaximum(30)
        self.exposure_setting.setValue(self.exposure_time)
        self.exposure_setting.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.exposure_setting.setTickInterval(2)
        self.exposure_setting.valueChanged.connect(self.exposure_update)
        horizontal_layout.addWidget(self.exposure_setting)

        self.lbl_frame = QtWidgets.QLabel('FPS')
        horizontal_layout.addWidget(self.lbl_frame)

        # button to start recording
        self.rec_toggle = QtWidgets.QPushButton()
        self.rec_toggle.setCheckable(True)
        self.set_switch_state('arm')
        horizontal_layout.addWidget(self.rec_toggle)
        self.rec_toggle.clicked.connect(self.rec)

        # self.test_button = QtWidgets.QPushButton()
        # self.test_button.setText('Pull')
        # horizontal_layout.addWidget(self.test_button)
        # self.test_button.clicked.connect(self.pullImage)

        # label to display prefix
        select_path_button = QtWidgets.QPushButton('Select folder', )
        horizontal_layout.addWidget(select_path_button)
        select_path_button.clicked.connect(self.filedialog)


        self.filename_label = QtWidgets.QLineEdit(self)
        self.filename_label.setText('Set file name')
        # self.filename_label.editingFinished.connect(self.set_handle)
        horizontal_layout.addWidget(self.filename_label)


        #image
        self.lbl_video = QtWidgets.QLabel()
        self.lbl_video.resize(1024, 768)

        self.setCentralWidget(centralwidget)
        grid_layout.addLayout(horizontal_layout, 0, 0, 1, 8)
        grid_layout.addWidget(self.lbl_video, 1, 0, 8, 10)
        self.centralWidget().setLayout(grid_layout)

        self.start_preview()

        self.show()

    def change_camera(self, index):
        self.cam_index = index
        self.open_camera()
        self.start_preview()

    def start_preview(self):
        if self.cam_active:
            #start live view
            self.cam.StartPullModeWithCallback(self.cameraCallback, self)
            # self.timer.start(int(1000/self.framerate))

            # start software trigger
            self.cam.Trigger(0xFFFF) #0xFFFF: continous trigger mode

    def open_camera(self):
        if self.cam is not None:
            self.cam.Close()
            self.cam = None
        try:
            self.cam = nncam.Nncam.Open(self.camlist[self.cam_index].id)
            self.cam.put_Speed(self.camspeed)
            success = True
        except:
            success = False
            print(f'Cam {self.cam_index} could not be opened')
        if success:
            self.sz = self.cam.get_Size()  # width, height
            self.bufsize = nncam.TDIBWIDTHBYTES(self.sz[0] * self.bits) * self.sz[1]
            self.buf = bytes(self.bufsize)
            self.set_exptime()
            self.cam.put_AutoExpoEnable(0)
            self.cam.put_VFlip(1)
            self.pDate = None
            #set trigger out
            self.cam.put_Option(nncam.NNCAM_OPTION_TRIGGER, 1) #0-video 1-software
            self.cam.put_Option(nncam.NNCAM_OPTION_FRAMERATE, self.framerate)
            #gpio0 is line 2
            self.cam.IoControl(2, nncam.NNCAM_IOCONTROLTYPE_SET_GPIODIR, 0x01)  # 0x01 = Output
            self.op_state = True
            self.cam.IoControl(2, nncam.NNCAM_IOCONTROLTYPE_SET_OUTPUTINVERTER, self.op_state)
        self.cam_active = success


    def set_exptime(self, ms=8):
        self.cam.put_ExpoTime(int(ms * 1000))

    def exposure_update(self):
        self.exposure_time = self.exposure_setting.value()
        self.exposure_label.setText(f'Exposure: {self.exposure_time} ms')
        self.set_exptime(float(self.exposure_time))

    # def set_prefix(self, prefix):
    #     self.filename_label.setText(prefix)

    def filedialog(self):
        self.wdir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select Folder', self.wdir)
        # self.set_handle()

    def set_handle(self):
        timestamp = datetime.datetime.now().isoformat(timespec='seconds').replace(':', '-')
        self.outfile_handle = os.path.join(self.wdir, self.filename_label.text()+'-'+timestamp+self.file_ext)
        if not os.path.exists(self.wdir):
            os.mkdir(self.wdir)
        self.outfile = cv2.VideoWriter(self.outfile_handle, self.fourcc, self.framerate, (self.sz[0], self.sz[1]))
        print('Saving file:', self.outfile_handle)
        self.nsync = 0

    def set_switch_state(self, state):
        # we will have a base state when exposure can be modified, stream not saved
        # after 'arming', exposure is fixed, listening to requests from client
        # when acquisition running, all controls are disabled
        if state == 'arm':
            if self.is_writing:
                #end of acq
                self.is_writing = False
                self.release_outfile()
                numpy.save(self.outfile_handle.replace(self.file_ext, '.npy'), self.synctimes[:self.nsync])
            self.rec_toggle.setStyleSheet("background-color : red")
            self.rec_toggle.setText('Rec')
            self.exposure_setting.setEnabled(True)
        elif state == 'running':
            self.rec_toggle.setStyleSheet("background-color : blue")
            self.rec_toggle.setText('Acquiring')
            self.exposure_setting.setEnabled(False)
            self.set_handle()
            self.is_writing = True
            self.acq_start_time = datetime.datetime.now()
            QTimer.singleShot(100, self.sync_pulse)
        elif state == 'restart':
            if self.is_writing:
                self.is_writing = False
                self.release_outfile()
                numpy.save(self.outfile_handle.replace(self.file_ext, '.npy'), self.synctimes[:self.nsync])
                self.set_switch_state('running')



    def rec(self, toggle=False):
        if not self.rec_toggle.isChecked():
            self.set_switch_state('arm')
        else:
            self.set_switch_state('running')

    def release_outfile(self):
        if self.outfile is not None:
            self.outfile = None

    def sync_pulse(self):
        if self.is_writing:
            rsync = self.nsync, *self.cam.get_FrameRate(), self.frame_counter
            print(self.outfile_handle, f'TTL {rsync[0]}, Frame {rsync[-1]}')
            self.synctimes[self.nsync] = rsync
            self.nsync += 1
            #flip GPIO hold
            self.flip_on()
            QTimer.singleShot(10, self.flip_off)

            #re-trigger cam to get a ttl out
            # self.cam.Trigger(0xFFFF)  # 0xFFFF: continous trigger mode
            QTimer.singleShot(int(1000 * numpy.random.random()*1.8*self.ipi+0.1*self.ipi), self.sync_pulse)

    def flip_off(self):
        self.cam.IoControl(2, nncam.NNCAM_IOCONTROLTYPE_SET_OUTPUTINVERTER, self.op_state)

    def flip_on(self):
        self.cam.IoControl(2, nncam.NNCAM_IOCONTROLTYPE_SET_OUTPUTINVERTER, not self.op_state)


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

    def update_fps(self):
        if self.cam:
            #restart acq if over time limit
            time_running = datetime.datetime.now() - self.acq_start_time
            # print('timedelte:', time_running)
            if time_running > datetime.timedelta(seconds=self.reclen):
                self.restart_acq()
            else:
                nFrame, nTime, nTotalFrame = self.cam.get_FrameRate()
                fps = nFrame * 1000.0 / nTime
                self.lbl_frame.setText("{}, fps = {:.1f}".format(self.frame_counter, fps))
                if self.is_writing:
                    self.fpsvals.append(fps)

    def preview_update(self):
        if self.is_writing:
            arr = numpy.frombuffer(self.buf, dtype='uint8').reshape((self.sz[1], self.sz[0], 3))
            self.outfile.write(arr)
            self.frame_counter += 1
            # print(self.frame_counter)
            if not self.frame_counter % self.framerate:
                self.update_fps()
        image = QImage(self.buf, self.sz[0], self.sz[1], QImage.Format_RGB888).convertToFormat(QImage.Format_Grayscale8)#.mirrored(False, True)
        newimage = image.scaled(self.lbl_video.width(), self.lbl_video.height(), Qt.KeepAspectRatio,
                                Qt.FastTransformation)
        self.lbl_video.setPixmap(QPixmap.fromImage(newimage))
        # self.onTimer()
        # print('Frame grabbed')

    def restart_acq(self):
        self.set_switch_state('restart')

def launch_GUI(*args, **kwargs):
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    font = QtGui.QFont()
    app.setFont(font)
    gui_main = GUI_main(app, *args, **kwargs)
    sys.exit(app.exec())

if __name__ == '__main__':
    launch_GUI(title='vEEG Camera',)