# GUI
import sys
from pyqtgraph import Qt
from pyqtgraph.Qt import QtGui, QtCore, QtWidgets

from Host.HostSocket import Socket as HostSocket
from Client.ClientSocket import Socket as ClientSocket

class GUI_main(QtWidgets.QMainWindow):
    def __init__(self, app, socket, title='Main'):
        super().__init__()
        self.setWindowTitle(title)
        self.app = app
        if socket == 'client':
            self.socket = ClientSocket()
        elif socket == 'host':
            self.socket = HostSocket()
            # self.socket.gui=self
        else:
            print('Bad socket')

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

        # button
        if socket == 'host':
            listen_button = QtWidgets.QPushButton('Listen', )
            horizontal_layout.addWidget(listen_button)
            send_button.clicked.connect(self.socket.listen)

        self.setCentralWidget(centralwidget)
        self.centralWidget().setLayout(horizontal_layout)
        self.show()
        if socket == 'host':
            self.socket.listen()

    def send(self):
        message = self.input_field.text()
        response = self.socket.send(message)
        self.response_label.setText(response)


def launch_GUI(*args, **kwargs):
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    font = QtGui.QFont()
    app.setFont(font)
    gui_main = GUI_main(app, *args, **kwargs)
    sys.exit(app.exec())