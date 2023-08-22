import matplotlib
import numpy
from matplotlib import pyplot as plt
matplotlib.use('TkAgg')
from PyQt5.QtGui import QPixmap, QImage
from Camera import nncam
import qimage2ndarray
import cv2
class App:
    def __init__(self):
        self.hcam = None
        self.buf = None
        self.total = 0

# the vast majority of callbacks come from nncam.dll/so/dylib internal threads
    @staticmethod
    def cameraCallback(nEvent, ctx):
        if nEvent == nncam.NNCAM_EVENT_IMAGE:
            ctx.CameraCallback(nEvent)

    def CameraCallback(self, nEvent=0):
        if nEvent == nncam.NNCAM_EVENT_IMAGE:
            try:
                self.hcam.PullImageV3(self.buf, 0, 24, 0, None)
                self.total += 1
                print('pull image ok', self.total)#, total = {}'.format(self.total))
            except nncam.HRESULTException as ex:
                print('pull image failed, hr=0x{:x}'.format(ex.hr & 0xffffffff))
        else:
            print('event callback: {}'.format(nEvent))

    def run(self):
        a = nncam.Nncam.EnumV2()
        # if len(a) > 0:
        #     print('{}: flag = {:#x}, preview = {}, still = {}'.format(a[0].displayname, a[0].model.flag, a[0].model.preview, a[0].model.still))
        #     for r in a[0].model.res:
        #         print('\t = [{} x {}]'.format(r.width, r.height))
        self.hcam = nncam.Nncam.Open(a[0].id)
        self.hcam.put_VFlip(1)

        #try set to raw
        # self.hcam.put_Option(nncam.NNCAM_OPTION_RAW, 1) #works. if using, set bufsize to 8

        #try set to external trigger
        gpio0 = 0x02
        self.hcam.put_Option(nncam.NNCAM_OPTION_TRIGGER, 2)
        self.hcam.put_Option(nncam.NNCAM_IOCONTROLTYPE_SET_TRIGGERSOURCE, gpio0)
            # if self.hcam:
            #     try:
        width, height = self.hcam.get_Size()
        rawmode = self.hcam.get_RawFormat()
        print(rawmode)
        self.sz = (width, height)
        bufsize = nncam.TDIBWIDTHBYTES(width * 8) * height
        self.bufsize = bufsize
                    # print('image size: {} x {}, bufsize = {}'.format(width, height, bufsize))
        self.buf = bytes(bufsize)
                    # if self.buf:
                    #     try:
        self.hcam.StartPullModeWithCallback(self.cameraCallback, self)
            #             except nncam.HRESULTException as ex:
            #                 print('failed to start camera, hr=0x{:x}'.format(ex.hr & 0xffffffff))
        while self.total < 10:
            pass
        self.hcam.Close()
        # input('press ENTER to exit')
            #     finally:
            #         self.hcam.Close()
            #         self.hcam = None
            #         self.buf = None
            # else:
            #     print('failed to open camera')
        # else:
        #     print('no camera found')

if __name__ == '__main__':
    import time
    app = App()
    app.run()
    # for i in range(3):
    #     time.sleep(1)
    #     app.CameraCallback()
    self=app
    d = app.buf
    # image = QImage(app.buf, app.sz[0], app.sz[1], QImage.Format_RGB888)
    # pm = QPixmap.fromImage(image) #does not work if an app is not running
    # a = numpy.frombuffer(d, dtype='uint8')
    # imd = a.reshape((3, app.sz[1], app.sz[0])) #this is a disaster
    # g = image.convertToFormat(QImage.Format_Grayscale8)
    # s = g.bits().asstring(app.sz[0] * app.sz[1] )
    # arr = numpy.fromstring(s, dtype='uint8').reshape((app.sz[1], app.sz[0], 1)) #this works
    arr1 = numpy.frombuffer(d, dtype='uint8').reshape((app.sz[1], app.sz[0]))
    # arr3 = numpy.fromstring(image, dtype='uint8').reshape((app.sz[1], app.sz[0], 1))
    plt.imshow(arr1)
    plt.show()
    # qimage2ndarray.raw_view(g) #this works too
    #TODO: for writer, supply isColor = true at init to the feed with grey images