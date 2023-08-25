from Camera import nncam
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
                print('pull image ok')#, total = {}'.format(self.total))
            except nncam.HRESULTException as ex:
                print('pull image failed, hr=0x{:x}'.format(ex.hr & 0xffffffff))
        else:
            print('event callback: {}'.format(nEvent))

    def run(self):
        a = nncam.Nncam.EnumV2()
        self.hcam = nncam.Nncam.Open(a[0].id)
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
