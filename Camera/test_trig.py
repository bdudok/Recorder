
from Camera import nncam
class App:
    def __init__(self):
        self.hcam = None
        self.buf = None
        self.total = 0

    @staticmethod
    def cameraCallback(nEvent, ctx):
        if nEvent == nncam.NNCAM_EVENT_IMAGE:
            ctx.CameraCallback(nEvent)

    def CameraCallback(self, nEvent=0):
        if nEvent == nncam.NNCAM_EVENT_IMAGE:
            try:
                self.hcam.PullImageV3(self.buf, 0, 24, 0, None)
                self.total += 1
                print('pull image ok', self.total)
            except nncam.HRESULTException as ex:
                print('pull image failed, hr=0x{:x}'.format(ex.hr & 0xffffffff))
        else:
            print('event callback: {}'.format(nEvent))

    def run(self):
        a = nncam.Nncam.EnumV2()
        self.hcam = nncam.Nncam.Open(a[0].id)
        self.hcam.put_VFlip(1)

        #try set to external trigger

        # 0 = video mode, 1 = software or simulated trigger mode, 2 = external trigger mode
        self.hcam.put_Option(nncam.NNCAM_OPTION_TRIGGER, 2)
        # 0x01 => GPIO0
        gpio0 = 0x01
        self.hcam.IoControl(0, nncam.NNCAM_IOCONTROLTYPE_SET_TRIGGERSOURCE, gpio0)

        width, height = self.hcam.get_Size()
        self.sz = (width, height)
        bufsize = nncam.TDIBWIDTHBYTES(width * 24) * height
        self.buf = bytes(bufsize)

        self.hcam.StartPullModeWithCallback(self.cameraCallback, self)
        while self.total < 10:
            pass
        self.hcam.Close()

if __name__ == '__main__':
    app = App()
    app.run()
