# GUI
import sys
import numpy
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QElapsedTimer
from pyqtgraph.Qt import QtGui, QtCore, QtWidgets
from PyQt5.QtGui import QPixmap, QImage
from Camera import nncam
import cv2


import json
import zmq

'''
App for displaying camera preview, setting exposure time, and saving stream during recording
Acquisition start controlled by the recorder client (RecorderGUI)
'''
#in this implementation, zmq poll runs in method of App. ideally, it would generate qt events
class GUI_main(QtWidgets.QMainWindow):
    def __init__(self, app, port=5555, title='Cam'):
        super().__init__()
        self.setWindowTitle(title)
        self.app = app

        #set variables
        self.exposure_time = 4
        self.delay_time = 35
        self.pollinterval = 1000
        self.vidres = (1440, 1080)
        self.framerate = 30
        self.fpsvals = []
        self.camspeed = 1 # 0:15 fps ; 1:30 fps; 2:45;3:60... etc, does not depend on exposure. Not exact.
        self.format = '24rgb' # 24rgb works, working on implementing 8grey, future:16rgb (for zero padded 12 raw data)
        assert self.format in ('24rgb', '8grey')
        self.fourcc = cv2.VideoWriter_fourcc(*'DIVX')
        self.file_ext = '.avi'

        # this process will act as zmq server, and listen to the port for settings and commands to start/stop acquisition
        context = zmq.Context()
        self.server = context.socket(zmq.REP)
        self.server.bind(f"tcp://*:{port}")

        #open camera
        a = nncam.Nncam.EnumV2()
        self.cam = False
        self.camID = a[0].id

        #set up output
        self.is_writing = False
        self.outfile = None

        #central widget
        self.setMinimumSize(1024, 768)
        centralwidget = QtWidgets.QWidget(self)
        grid_layout = QtWidgets.QGridLayout()
        horizontal_layout = QtWidgets.QHBoxLayout()

        # add widgets
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

        #slider for exposure delay
        self.delay_label = QtWidgets.QLabel(f'Delay: {self.delay_time} ms')
        horizontal_layout.addWidget(self.delay_label)
        self.delay_setting = QtWidgets.QSlider(Qt.Horizontal)
        self.delay_setting.setMinimum(0)
        self.delay_setting.setMaximum(60)
        self.delay_setting.setValue(self.delay_time)
        self.delay_setting.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.delay_setting.setTickInterval(2)
        self.delay_setting.valueChanged.connect(self.delay_update)
        horizontal_layout.addWidget(self.delay_setting)

        #dropdown for FPS limit
        self.limit_box = QtWidgets.QComboBox()
        self.fps_limits = {0: '<15 FPS', 1: '<30 FPS', 2: '<45 FPS', 3: '<60 FPS', 4: 'MAX'}
        for key, value in self.fps_limits.items():
            self.limit_box.insertItem(key, value)
        self.limit_box.setCurrentIndex(2)
        self.limit_box.currentIndexChanged.connect(self.limit_update)
        horizontal_layout.addWidget(self.limit_box)


        self.lbl_frame = QtWidgets.QLabel('FPS')
        horizontal_layout.addWidget(self.lbl_frame)

        # button to 'Arm' for recording
        self.arm_toggle = QtWidgets.QPushButton()
        self.arm_toggle.setCheckable(True)
        horizontal_layout.addWidget(self.arm_toggle)
        self.arm_toggle.clicked.connect(self.arm)

        #button to start/stop live
        self.live_toggle = QtWidgets.QPushButton()
        self.live_toggle.setCheckable(True)
        horizontal_layout.addWidget(self.live_toggle)
        self.live_toggle.setText('Live')
        self.live_toggle.setChecked(True)
        self.live_toggle.setStyleSheet("background-color : green")
        self.live_toggle.clicked.connect(self.live)

        # label to display prefix
        self.filename_label = QtWidgets.QLabel('Set exposure then arm.', )
        horizontal_layout.addWidget(self.filename_label)

        #image
        self.lbl_video = QtWidgets.QLabel()
        self.lbl_video.resize(1024, 768)

        self.setCentralWidget(centralwidget)
        grid_layout.addLayout(horizontal_layout, 0, 0, 1, 8)
        grid_layout.addWidget(self.lbl_video, 1, 0, 8, 10)
        self.centralWidget().setLayout(grid_layout)

        #start live vieo
        self.set_switch_state('arm')
        self.start_cam_live()
        self.show()

    def set_exptime(self, ms=8):
        self.cam.put_ExpoTime(int(ms * 1000))

    def set_delay(self, ms=35):
        self.cam.IoControl(0, nncam.NNCAM_IOCONTROLTYPE_SET_TRIGGERDELAY , int(ms * 1000))  # gpio0 = 0x01

    def open_cam(self, maxspeed=False):
        self.cam = nncam.Nncam.Open(self.camID)
        if self.format == '24rgb':
            self.bits = 24
        elif self.format == '8grey':
            self.bits = 8
            self.cam.put_Option(nncam.NNCAM_OPTION_RAW, 1)
        # print(a[i].id, 'connected')
        if maxspeed:
            self.cam.put_Speed(self.cam.MaxSpeed())
        else:
            self.cam.put_Speed(self.camspeed)
        self.sz = self.cam.get_Size()  # width, height
        self.bufsize = nncam.TDIBWIDTHBYTES(self.sz[0] * self.bits) * self.sz[1]
        self.buf = bytes(self.bufsize)
        self.set_exptime()
        self.cam.put_AutoExpoEnable(0)
        self.cam.put_VFlip(1)
        self.cam.put_HFlip(1)

    def exposure_update(self):
        self.exposure_time = self.exposure_setting.value()
        self.exposure_label.setText(f'Exposure: {self.exposure_time} ms')
        self.set_exptime(float(self.exposure_time))

    def delay_update(self):
        self.delay_time = self.delay_setting.value()
        self.delay_label.setText(f'Delay: {self.delay_time} ms')
        self.set_delay(float(self.delay_time))

    def limit_update(self, index):
        if index == 4:
            self.camspeed = self.cam.MaxSpeed()
        else:
            self.camspeed = index

    def set_prefix(self, prefix):
        self.filename_label.setText(prefix)

    def set_handle(self):
        # self.outfile_handle = handle+self.file_ext
        is_color = self.format in ('24rgb',)
        shape = (self.sz[0], self.sz[1])
        self.outfile = cv2.VideoWriter(self.outfile_handle, self.fourcc, self.framerate, shape, is_color)

        print('Saving file:', self.outfile_handle)
        self.frame_counter = 0
        self.has_writer = True

    def set_switch_state(self, state):
        # we will have a base state when exposure can be modified, stream not saved
        # after 'arming', exposure is fixed, listening to requests from client
        # when acquisition running, all controls are disabled
        if state == 'armed':
            self.start_cam_live()
            self.live_toggle.setCheckable(False)
            self.limit_box.setEnabled(False)
            self.arm_toggle.setStyleSheet("background-color : green")
            self.filename_label.setText('Waiting for recorder', )
            self.arm_toggle.setText('Armed')
        elif state == 'arm':
            if self.is_writing:
                self.is_writing = False
                self.stop_cam()
                self.save_container()
                self.start_cam_live()
                QTimer.singleShot(2000, self.release_outfile)
            self.arm_toggle.setStyleSheet("background-color : red")
            self.arm_toggle.setText('Arm')
            self.live_toggle.setCheckable(True)
        elif state == 'running':
            self.start_cam_triggered()
            self.lbl_frame.setText('Waiting for hardware trigger.')
            self.arm_toggle.setStyleSheet("background-color : blue")
            self.arm_toggle.setText('Acquiring')
            self.is_writing = True

    def release_outfile(self):
        if self.outfile is not None:
            self.outfile = None
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
            nFrame, nTime, nTotalFrame = self.cam.get_FrameRate()
            if nTime:
                fps = nFrame * 1000.0 / nTime
                self.lbl_frame.setText("{}, fps = {:.1f}".format(self.frame_counter, fps))
                if self.is_writing:
                    self.fpsvals.append(fps)

    def preview_update(self):
        if self.is_writing:
            self.update_container()
            if self.format in ('24rgb'):
                arr = numpy.frombuffer(self.buf, dtype='uint8').reshape((self.sz[1], self.sz[0], 3))
            elif self.format in ('8grey'):
                arr = numpy.frombuffer(self.buf, dtype='uint8').reshape((self.sz[1], self.sz[0]))
            if not self.has_writer:
                self.set_handle()
            self.outfile.write(arr)
            self.frame_counter += 1
            # print(self.frame_counter)
            if not self.frame_counter % self.framerate:
                self.update_fps()
        if self.format in ('24rgb'):
            image = QImage(self.buf, self.sz[0], self.sz[1], QImage.Format_RGB888)
        elif self.format in ('8grey'):
            image = QImage(self.buf, self.sz[0], self.sz[1], QImage.Format_Grayscale8).mirrored(False, True)
        if (not self.is_writing) or self.frame_counter % 2: #skip when writing to save performance
            newimage = image.scaled(self.lbl_video.width(), self.lbl_video.height(), Qt.KeepAspectRatio,
                                    Qt.FastTransformation)
            self.lbl_video.setPixmap(QPixmap.fromImage(newimage))
        # self.onTimer()
        # print('Frame grabbed')

    def arm(self):
        #the two states of the button. nb a 3rd state is controlled by the client.
        # could clean this up by handling the state in a consolidated method
        self.armed = self.arm_toggle.isChecked()
        if self.armed:
            self.set_switch_state('armed')
            self.exposure_setting.setEnabled(False)
            self.live_toggle.setCheckable(False)
            self.live_toggle.setStyleSheet("background-color : grey")
            #will poll request queue periodically
            self.timer = QtCore.QTimer()
            self.timer.setInterval(self.pollinterval)
            self.timer.timeout.connect(self.listen)
            self.timer.start()

        else:
            self.arm_toggle.setStyleSheet("background-color : red")
            self.arm_toggle.setText('Arm')
            self.exposure_setting.setEnabled(True)
            self.live_toggle.setCheckable(True)
            self.limit_box.setEnabled(True)
            self.timer.stop()

    def live(self):
        #the two states of the button. live: cam running with software trigger and displaying. otherwise, cam stopped.
        #recording will start the cam in external trigger mode, so cam is either in live or in arm.
        if not self.is_writing:
            if self.live_toggle.isChecked():
                self.start_cam_live()
                self.live_toggle.setStyleSheet("background-color : green")
            else:
                self.stop_cam()
                self.filename_label.setText('Camera closed.')
                self.live_toggle.setStyleSheet("background-color : grey")

    def start_cam_live(self):
        # print('start called')
        if not self.cam:
            self.open_cam()
            self.cam.put_Option(nncam.NNCAM_OPTION_TRIGGER, 0)
            self.cam.StartPullModeWithCallback(self.cameraCallback, self)
            self.live_toggle.setStyleSheet("background-color : green")

    def start_cam_triggered(self):
        # print('start triggered called')
        if self.cam:
            self.stop_cam()
        self.reset_container()
        self.open_cam(maxspeed=False)
        self.cam.put_Option(nncam.NNCAM_OPTION_TRIGGER, 2)
        self.cam.IoControl(0, nncam.NNCAM_IOCONTROLTYPE_SET_TRIGGERSOURCE, 0x01) #gpio0 = 0x01
        self.set_delay()
        self.cam.StartPullModeWithCallback(self.cameraCallback, self)


    def reset_container(self):
        max_frames = int(100 * 60 * 60) #1 hr at 100 fps
        self.internal_counter = 0
        self.internal_timer = QElapsedTimer()
        self.internal_timer.restart()
        self.internal_container = numpy.empty((max_frames, 2), dtype='int64')

    def update_container(self):
        self.internal_container[self.internal_counter] = (self.frame_counter, self.internal_timer.elapsed(),)
        self.internal_counter += 1

    def save_container(self):
        numpy.save(self.outfile_handle.replace(self.file_ext, '_CamTimers.npy'), self.internal_container[:self.internal_counter])

    def stop_cam(self):
        # print('stop called')
        if self.cam:
            self.cam.Close()

    def listen(self):
        # poll the request queue, and respond if anything.
        # not in cycle, non-blocking, called periodically by a Qt timer
        if (self.server.poll(self.pollinterval*0.01) & zmq.POLLIN) != 0:
            request = json.loads(self.server.recv_json())
            print(request)
            if 'set' in request:
                self.set_prefix(request['prefix'])
                self.frame_counter = 0
                self.outfile_handle = request['handle'] + self.file_ext
                self.has_writer= False
                fpsinex = self.limit_box.currentIndex()
                logstring = f'exp:{self.exposure_time}, fps:{self.fps_limits[fpsinex]}, sz:{self.sz}, delay:{self.delay_time}'
                message = {'set': True, 'exposure': self.exposure_time, 'log': logstring}
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
                self.arm_toggle.setChecked(True)
                self.arm()
                logstring = f'{self.frame_counter} frames captured, {numpy.mean(self.fpsvals):.2f} fps'
                message = {'stop': True, 'log': logstring}
                self.fpsvals = []
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