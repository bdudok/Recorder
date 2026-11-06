# Recorder
Apps for controlling acquisition on the Bruker 2P setup, LNCM / Dudok lab.

The video-EEG recorder for the Pinnacle setups (VideoEEG, EEG-Cam, ClosedLoop_Pinnacle) moved to
[Pinnacle-vEEG](https://github.com/bdudok/Pinnacle-vEEG) on 2026-10-25.

## Contents

- `Recorder/RecorderGUI_CL.py`: starts and stops a synchronous recording: 2P (PrairieLink), behavior
  camera, treadmill (pyControl) and stimulator, all with the same file name. Optional remote start from
  RealTime (closed loop) on another PC.
- `Camera/CamGUI.py`: preview and recording for the externally triggered ToupCam behavior camera.
- `OptoTrigger/Stim_StateMachine*`: Arduino sketches for the closed-loop optogenetics accessory board.
  `OptoTrigger/serial_send.py` sends stimulation settings to it (configs in that file).
- `dev_scripts/`: hardware checks for the camera and PrairieLink, not used by the apps. See the top of each script.
- `tests/`: pytest tests (`uv run pytest`). Scripts outside this folder should not have "test" in their names.

The treadmill runs on our pyControl fork, [bdudok/PyControl_LNCM](https://github.com/bdudok/PyControl_LNCM).

## How the apps talk

All on the Bruker PC, except RealTime. RecorderGUI_CL sends `set`, `go` and `stop` requests (zmq REQ/REP)
to the other apps. The camera and pyControl GUIs answer only while armed. Without an answer within 15 s
the Recorder marks that device red and carries on without blocking.

| App | Port | Notes |
|---|---|---|
| CamGUI | 5555 | arm before recording |
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

To run the apps, double-click `Recorder.bat` and `CamGUI.bat`, or make desktop shortcuts to them as described
in the [pyControl installation](https://github.com/bdudok/PyControl_LNCM/blob/main/installation.md#desktop-shortcuts).
Each one uses this repo's `.venv` and works from any folder.

Or from the repo folder (PowerShell):

```
$env:PYTHONPATH = "..\LNCM-lib"
uv run python -m Recorder.RecorderGUI_CL
uv run python -m Camera.CamGUI
```

To work on the code in PyCharm, use `.venv\Scripts\python.exe` as the project interpreter and keep LNCM-lib as
a module dependency of the project, which puts it on the path.

The pyControl GUI does not use this environment. It has its own, in `PyControl\.venv`: see
[pyControl installation](https://github.com/bdudok/PyControl_LNCM/blob/main/installation.md).

Updating the Bruker PC from the old environment: [BRUKER_PC_UPDATE.md](BRUKER_PC_UPDATE.md).
