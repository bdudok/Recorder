from multiprocessing import Process, freeze_support, set_start_method

from Client.RecorderGUI import launch_GUI as launch_recorder
from Host.CamGUI import launch_GUI as launch_camera

cam_port = 5555
trm_port = 5554
if __name__ == '__main__':
    freeze_support()
    try:
        set_start_method('spawn')
    except:
        pass
    Process(target=launch_camera, kwargs={'title': 'Camera', 'port': cam_port}).start()
    Process(target=launch_recorder, kwargs={'title': 'Recorder', 'cam_port': cam_port}).start()
    # camera app not working properly when started like this
