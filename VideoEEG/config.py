"""Settings and file locations for the vEEG recorder."""
import dataclasses
import json
import os
from pathlib import Path

APP_DIR = Path.home() / '.veeg_recorder'
DEFAULT_OUT_DIR = Path('C:/EEG/vid') if os.name == 'nt' else Path.home() / 'EEG' / 'vid'
BASE_PORT = 5570  # command port of camera i is BASE_PORT + i


@dataclasses.dataclass
class Settings:
    out_dir: str = str(DEFAULT_OUT_DIR)
    prefix: str = 'vEEG'
    exposure_ms: int = 8
    framerate: int = 30
    segment_s: int = 3600       # new file after this many seconds worth of frames
    ttl_mean_interval_s: float = 5.0
    ttl_width_ms: int = 10
    vflip: bool = True
    encoder: str = 'auto'       # 'auto', 'h264_nvenc' or 'libx264'
    quality: int = 23           # CQ (nvenc) or CRF (x264); lower is better quality
    ffmpeg: str = 'ffmpeg'
    min_free_gb: float = 50.0   # status shows a warning below this
    recording: bool = False     # resume recording after a restart of the recorder

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.exists():
            return cls()
        with open(path) as f:
            data = json.load(f)
        fields = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in fields})

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix('.tmp')
        with open(tmp, 'w') as f:
            json.dump(dataclasses.asdict(self), f, indent=2)
        os.replace(tmp, path)


def settings_path(cam_index):
    return APP_DIR / f'cam{cam_index}_settings.json'


def heartbeat_path(cam_index):
    return APP_DIR / f'cam{cam_index}_heartbeat'


def log_dir():
    return APP_DIR / 'logs'


def port(cam_index):
    return BASE_PORT + cam_index
