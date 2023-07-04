
from multiprocessing import Process
from testApp import launch_GUI

if __name__ == '__main__':
    t1 = Process(target=launch_GUI, kwargs={'title': 'Host', 'socket': 'host'})
    t1.start()

    t2 = Process(target=launch_GUI, kwargs={'title': 'Client', 'socket': 'client'})
    t2.start()

