# vEEG recorder

Records a camera continuously for video-EEG on the Pinnacle setups. It writes hourly video files
and gives random-interval TTL pulses from the camera's GPIO so the video can be aligned to the EEG.
It replaces `Camera/EEG-Cam.py`.

## Install (recording PC)

1. Create the environment from the repo root: `conda env create -f VideoEEG/environment.yml`
2. Check the hardware: close any other camera software, then
   `conda activate veeg` and `python -m VideoEEG.hw_check --cam 0`.
   This writes a report to `%USERPROFILE%\.veeg_recorder\hw_check_cam0.txt`.
3. Make a desktop shortcut to `VideoEEG\vEEG.bat` per camera, with `--cam 0` or `--cam 1` as the argument.
   Edit `CONDA_ROOT` in the .bat if conda is not in `%USERPROFILE%\miniforge3`.

Windows settings for 24/7 recording:
- Power plan: never sleep. The recorder also asks Windows to stay awake while it runs.
- Device Manager → USB Root Hubs / USB controllers → Power Management: untick "Allow the computer to turn off this device".
  Power options → USB selective suspend: Disabled.
- Windows Update: set active hours, or pause updates during long recordings. Automatic restarts end the recording.

## Use

Start the shortcut. The window shows the preview, the status line, and the last messages.
Set the exposure, folder and name, then press **Record**. Exposure, folder and name can only be
changed while not recording.

- Closing the window while recording keeps the recording running in the background. Opening the
  shortcut again shows the running recording, where it can be stopped.
- Closing the window while not recording stops the recorder.

## How it runs

The GUI and the recorder are separate processes, so a GUI problem does not affect the recording.

    GUI (VideoEEG.gui) --- local zmq socket, port 5570+cam ---> recorder (VideoEEG.recorder)
                                                                 started and watched by a supervisor

- **Supervisor**: restarts the recorder if it exits with an error or stops updating its heartbeat
  file for 30 s. The restarted recorder resumes recording if it was recording.
- **Camera**: if the camera reports an error, disconnects, or sends no frames for 5 s, the recorder
  closes it and tries to reopen it every 5 s. Recording continues when frames return.
- **Files**: a new file starts every `segment_s` seconds' worth of frames (3600 s = 108000 frames at
  30 fps), without dropping frames at the switch. The finished file is closed right away, so the
  move script can take it. ffmpeg also finishes the file cleanly if the recorder process dies.
- **Encoding**: H.264 in MKV, on the GPU (NVENC) if available, otherwise x264 on the CPU.

## Output files

Each hour produces three files with the same name stem, e.g. `mouse1-2026-10-07T14-00-00`:

| File | Content |
|---|---|
| `.mkv` | video, 8-bit grey, constant frame rate (`framerate` setting) |
| `_frames.csv` | one row per video frame: `frame` (index in this file), `frame_total` (counter since the recorder started), `cam_seq` (camera frame counter; gaps mean frames lost before reaching the PC), `cam_time_us` (camera clock), `pc_time` (Unix time when the frame arrived) |
| `_ttl.csv` | one row per TTL pulse: `pulse` (pulse number), `pc_time` (Unix time at the rising edge), `frame` (index in this file of the last frame received before the pulse), `frame_total`, `cam_seq` |

The TTL pulses are 10 ms long, at random intervals of 0.5–9.5 s (mean 5 s). The `frame` column of
`_ttl.csv` against the TTL times recorded by the EEG system gives the alignment.

## Settings and logs

Folder `%USERPROFILE%\.veeg_recorder\`:
- `cam<N>_settings.json`: settings, including ones not shown in the GUI (`framerate`, `segment_s`,
  `ttl_mean_interval_s`, `encoder`, `quality`, `ffmpeg`, `min_free_gb`). Edit them while the recorder is stopped.
- `logs\cam<N>_recorder.log`, `cam<N>_supervisor.log`, `cam<N>_ffmpeg.log`: check these after any problem.

## Development

Tests use a synthetic camera and need ffmpeg: `python -m pytest VideoEEG/tests` from the repo root.
`python -m VideoEEG.gui --cam 0 --fake` runs the GUI with the synthetic camera.
