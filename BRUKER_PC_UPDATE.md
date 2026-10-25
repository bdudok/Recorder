# Updating the Bruker PC to the uv environments and pyControl 2.1.1

One-time update of the Bruker acquisition PC (written 2026-10-25). It moves:
- Recorder (RecorderGUI_CL, CamGUI_v2) to its own uv environment, with PySide6 instead of PyQt5.
- The treadmill GUI to our pyControl fork rebased on pyControl 2.1.1, in its own uv environment.

Plan about an hour, on a day without scheduled imaging. The old environment is left in place, so you can
go back (step 9) until the new setup has run a few real sessions.

Commands are for PowerShell. The paths assume the repos are in `C:\Users\User\PycharmProjects`; adjust if
they are elsewhere.

## 1. Note the current state

For each of `Recorder`, `PyControl` and `LNCM-lib`:

```
cd C:\Users\User\PycharmProjects\Recorder
git status
git branch --show-current
git rev-parse HEAD
```

Write down the branch and commit, for going back. If `git status` shows changes (edited tasks,
`config\user_settings.json`, `Recorder\config.py`), commit them on the current branch or ask before
continuing. They must not be lost when switching branches. `Recorder\token.py` is not in git and stays
where it is.

## 2. Install uv

```
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close and reopen PowerShell, then check: `uv --version`. uv downloads Python 3.11 by itself when needed.

## 3. Recorder

```
cd C:\Users\User\PycharmProjects\Recorder
git fetch
git switch pycontrol-v2.1
uv sync
```

After the branch is merged, use `git switch master` and `git pull` instead.
`uv sync` creates `.venv` in the repo folder. Check it:

```
$env:PYTHONPATH = "..\LNCM-lib"
uv run python -c "import PySide6, zmq, cv2, win32com.client; from BaserowAPI.BaserowRequests import GetSessions; print('ok')"
```

If the BaserowAPI import fails, update LNCM-lib (`git pull` in LNCM-lib) and check that it is next to
Recorder.

## 4. pyControl

```
cd C:\Users\User\PycharmProjects\PyControl
git fetch
git switch pycontrol-v2.1.1
uv sync
```

Start the GUI from the PyControl folder, with a console so errors are visible:

```
uv run python pyControl_GUI.pyw
```

- Settings (gear icon): check the tasks and data folders.
- **Load the new framework onto the pyboard.** Select the treadmill board and press Connect. The log shows
  the MicroPython version and a warning that the framework version on the board does not match the GUI.
  Use Config → Load framework, wait for "OK", then disconnect and connect again; the warning should be gone.
  No hardware definition is needed: the treadmill tasks define their hardware in the task file, and the
  device files are sent when a task is uploaded.
- MicroPython itself does not need updating. Only the new UART_handler device (not used by us) needs
  version 1.26 or later.
- If Windows Firewall asks about Python, allow it on private networks. The Recorder connects on the same
  PC, so blocking it would also work.

For daily use without a console window: `.venv\Scripts\pythonw.exe pyControl_GUI.pyw` from the PyControl
folder (a desktop shortcut works with "Start in" set to the PyControl folder). Errors then go to
`ErrorLog.txt` in that folder.

## 5. PyCharm (if the apps are started from PyCharm)

- Recorder project: Settings → Project → Python Interpreter → Add Interpreter → Add Local Interpreter →
  Select existing → `C:\Users\User\PycharmProjects\Recorder\.venv\Scripts\python.exe`. Keep LNCM-lib as a
  module dependency (Project Structure), so BaserowAPI is on the path.
- PyControl project: the same with `PyControl\.venv\Scripts\python.exe`.
- In the run configurations, set the working directory to the repo folder.

Without PyCharm, from the Recorder folder:

```
$env:PYTHONPATH = "..\LNCM-lib"
uv run python -m Camera.CamGUI_v2
uv run python -m Recorder.RecorderGUI_CL
```

## 6. Test without an animal

1. Start CamGUI_v2. The live preview should run; set the exposure and press Arm.
2. In pyControl: connect, select the imaging task, Upload, then press Arm in "Synchronous recording". The
   label should say it is waiting for a file name.
3. Check the valve buttons in the "Remote" box while the task runs: start the task with Start, press
   Reward, then Stop. A task without the matching event prints "Task has no '…' event" in the log instead
   of stopping.
4. In RecorderGUI_CL: set a test project and animal name, tick Auto stop with 1 minute, press the record
   button once ("Set": Camera, Treadmill and Scope turn green), then again to start.
5. After the auto stop, check the session folder: scope TSeries, `.avi` and `_CamTimers.npy` from the
   camera, the pyControl `.tsv` (and position data), and `.log.txt`. The log ends with "end of log", and
   the camera's line reports the number of frames and fps.
6. Check the timeout: disarm pyControl and press the record button. After 15 s Treadmill turns red and
   the Recorder stays usable. Arm again before real sessions.

Test a session without the scope once too (untick Scope): the Recorder now creates the session folder,
and the camera and treadmill files go into it.

## 7. If the remote start from RealTime is used

Click Listen in the Recorder only after detection is running in RealTime. Requests sent before that can
take the trigger; see the note in `RealTime/Experiments/LFP_seizure_detector.py`.

## 8. When something fails

- The Recorder prints what each app answered (for example "pyControl: data folder … does not exist").
  Uncaught errors are also written to the session's `.log.txt`.
- pyControl errors: its log window, and `ErrorLog.txt` in the PyControl folder.
- Report the message and the session name.

## 9. Going back to the old setup

```
cd C:\Users\User\PycharmProjects\Recorder
git switch <branch noted in step 1>
cd ..\PyControl
git switch <branch noted in step 1>
```

Then select the old interpreter in PyCharm again. Load the framework onto the pyboard again from the
old pyControl GUI (Config → Load framework), since the board now has 2.1.1.

Once the new setup has run real sessions without problems, the old environment can be removed.
