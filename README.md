# Recorder
Apps for controlling acquisition on the Bruker 2P setup, LNCM / Dudok lab.

The video-EEG recorder for the Pinnacle setups (VideoEEG, EEG-Cam, ClosedLoop_Pinnacle) moved to
[Pinnacle-vEEG](https://github.com/bdudok/Pinnacle-vEEG) on 2026-10-25.

## Contents

- `Recorder/RecorderGUI_CL.py`: starts and stops a synchronous recording: 2P (PrairieLink), behavior
  camera, treadmill (pyControl) and stimulator, all with the same file name. Optional remote start from
  RealTime (closed loop) on another PC.
- `Camera/CamGUI_v2.py`: preview and recording for the externally triggered ToupCam behavior camera.
- `OptoTrigger/Stim_StateMachine*`: Arduino sketches for the closed-loop optogenetics accessory board.
  `OptoTrigger/serial_send.py` sends stimulation settings to it (configs in that file).
- `TestClient/`, `TestHost/`: minimal zmq examples.

The treadmill runs on our pyControl fork, [bdudok/PyControl](https://github.com/bdudok/PyControl).

## How the apps talk

All on the Bruker PC, except RealTime. RecorderGUI_CL sends `set`, `go` and `stop` requests (zmq REQ/REP)
to the other apps. The camera and pyControl GUIs answer only while armed. Without an answer within 15 s
the Recorder marks that device red and carries on without blocking.

| App | Port | Notes |
|---|---|---|
| CamGUI_v2 | 5555 | arm before recording |
| pyControl GUI | 5556 | "Synchronous recording" box; arm after uploading the task |
| RealTime (other PC) | 5557 | remote start; `closedloop_host` in RecorderGUI_CL |

## Setup

The apps run in a uv environment defined by `pyproject.toml` and `uv.lock` (Python 3.11, PySide6).
RecorderGUI_CL also imports `BaserowAPI` from [LNCM-lib](https://github.com/bdudok/LNCM-lib), which must be
checked out next to this repo and be on the path. `Recorder/token.py` (Baserow token) is not in git.

```
git clone https://github.com/bdudok/Recorder.git
cd Recorder
uv sync
```

Run from the repo folder (PowerShell):

```
$env:PYTHONPATH = "..\LNCM-lib"
uv run python -m Recorder.RecorderGUI_CL
uv run python -m Camera.CamGUI_v2
```

In PyCharm, use `.venv\Scripts\python.exe` as the project interpreter and keep LNCM-lib as a module
dependency of the project, which puts it on the path.

Updating the Bruker PC from the old environment: [BRUKER_PC_UPDATE.md](BRUKER_PC_UPDATE.md).
