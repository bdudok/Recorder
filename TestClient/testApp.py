# GUI
import sys
from pyqtgraph import Qt
import zmq
from pyqtgraph.Qt import QtGui, QtCore, QtWidgets

from TestHost.HostSocket import Socket as HostSocket
from TestClient.ClientSocket import Socket as ClientSocket

class GUI_main(QtWidgets.QMainWindow):
    def __init__(self, app, port=5555, title='Main'):
        super().__init__()
        self.setWindowTitle(title)
        self.app = app
        context = zmq.Context()
        self.socket = context.socket(zmq.REQ)
        self.socket.connect(f"tcp://localhost:{port}")

        #central widget
        centralwidget = QtWidgets.QWidget(self)
        horizontal_layout = QtWidgets.QHBoxLayout()

        # add widgets
        #input
        self.input_field = QtWidgets.QLineEdit(self)
        horizontal_layout.addWidget(self.input_field)

        # button
        send_button = QtWidgets.QPushButton('Send', )
        horizontal_layout.addWidget(send_button)
        send_button.clicked.connect(self.send)

        # label
        self.response_label = QtWidgets.QLabel('...', )
        self.response_label.setWordWrap(True)
        horizontal_layout.addWidget(self.response_label)

        self.setCentralWidget(centralwidget)
        self.centralWidget().setLayout(horizontal_layout)
        self.show()

    def send(self):
        message = self.input_field.text()
        self.socket.send_string(message)

        response = self.socket.recv_string()
        self.response_label.setText(response)

    def listen(self):
        #  Wait for next request from client
        print('listening')
        message = self.socket.recv_string()
        if self.gui is not None:
            self.gui.response_label.setText(message)
        #  Send reply back to client
        print(message)
        self.socket.send_string(message)





def launch_GUI(*args, **kwargs):
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    font = QtGui.QFont()
    app.setFont(font)
    gui_main = GUI_main(app, *args, **kwargs)
    sys.exit(app.exec())

if __name__ == '__main__':
    launch_GUI(title='Client')