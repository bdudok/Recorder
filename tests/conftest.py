import os
import sys
import types
from unittest import mock

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Modules that are only on the acquisition PC: stub them when they can't be imported.
try:
    import win32com.client  # noqa: F401
except ImportError:
    win32com = types.ModuleType('win32com')
    win32com.client = types.ModuleType('win32com.client')
    win32com.client.Dispatch = None
    sys.modules['win32com'] = win32com
    sys.modules['win32com.client'] = win32com.client
try:
    import Recorder.token  # noqa: F401
except ImportError:
    sys.modules['Recorder.token'] = types.SimpleNamespace(token='')
try:
    import BaserowAPI.BaserowRequests  # noqa: F401
except ImportError:
    sys.modules['BaserowAPI'] = types.ModuleType('BaserowAPI')
    sys.modules['BaserowAPI.BaserowRequests'] = types.SimpleNamespace(GetSessions=None)

from PySide6 import QtWidgets  # noqa: E402


@pytest.fixture(scope='session')
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def prairie_link(monkeypatch):
    import Recorder.RecorderGUI_CL as R
    link = mock.MagicMock()
    monkeypatch.setattr(R.win32com.client, 'Dispatch', lambda name: link)
    return link
