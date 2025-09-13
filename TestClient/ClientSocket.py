#
#   Connects REQ socket to tcp://localhost:5555
#   Sends "Hello" to server, expects "World" back
#

import zmq

class Socket:
    def __init__(self, port=5555):
        context = zmq.Context()
        self.socket = context.socket(zmq.REQ)
        self.socket.connect(f"tcp://localhost:{port}")

    def send(self, message):
        self.socket.send_string(message)
        return self.socket.recv_string()

if __name__ == '__main__':
    s = Socket()
    s.send('hello')