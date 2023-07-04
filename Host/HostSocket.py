#
#   Hello World server in Python
#   Binds REP socket to tcp://*:5555

import zmq

class Socket:
    def __init__(self, port=5555):
        context = zmq.Context()
        self.socket = context.socket(zmq.REP)
        self.socket.bind(f"tcp://*:{port}")
        self.gui=None

    def listen(self):
        #  Wait for next request from client
        print('listening')
        message = self.socket.recv_string()
        # if self.gui is not None:
        #     self.gui.response_label.setText(message)
        #  Send reply back to client
        print(message)
        self.socket.send_string(message)

    def send(self, message):
        self.socket.send_string(message)
        return self.socket.recv_string()

if __name__ == '__main__':
    s = Socket()