"""Helpers for the Recorder and CamGUI tests."""
import json
import socket
import threading
import time

import zmq


def pump(app, seconds):
    """Run the Qt event loop for a while."""
    t0 = time.time()
    while time.time() - t0 < seconds:
        app.processEvents()
        time.sleep(0.005)


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class FakeServer:
    """REP server like the cam and treadmill apps. reply(request) returns the reply dict, or None to not reply."""

    def __init__(self, port, reply=None):
        self.requests = []
        self.reply = reply or (lambda request: {k: True for k in ('set', 'go', 'stop') if k in request})
        self.socket = zmq.Context.instance().socket(zmq.REP)
        self.socket.setsockopt(zmq.LINGER, 0)
        for attempt in range(20):  # zmq releases a closed socket's port asynchronously
            try:
                self.socket.bind(f'tcp://127.0.0.1:{port}')
                break
            except zmq.ZMQError:
                if attempt == 19:
                    raise
                time.sleep(0.05)
        self.running = True
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        while self.running:
            if not self.socket.poll(50) & zmq.POLLIN:
                continue
            request = json.loads(self.socket.recv_json())
            self.requests.append(request)
            reply = self.reply(request)
            if reply is None:
                return  # leave the request unanswered and stop serving
            self.socket.send_json(json.dumps(reply))

    def commands(self):
        return [next(iter(r)) for r in self.requests]

    def close(self):
        self.running = False
        self.thread.join()
        self.socket.close()


def request(app, port, message, timeout=5):
    """Send one request the way the Recorder does and return the reply (None on timeout).
    Keeps the Qt event loop running meanwhile, since the apps answer from the GUI thread."""
    s = zmq.Context.instance().socket(zmq.REQ)
    s.setsockopt(zmq.LINGER, 0)
    s.connect(f'tcp://127.0.0.1:{port}')
    s.send_json(json.dumps(message))
    t0 = time.time()
    while not s.poll(0) & zmq.POLLIN:
        if time.time() - t0 > timeout:
            s.close()
            return None
        app.processEvents()
        time.sleep(0.005)
    reply = json.loads(s.recv_json())
    s.close()
    return reply
