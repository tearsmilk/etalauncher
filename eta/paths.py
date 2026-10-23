"""Settings and folders."""
import json
import os
import sys
from pathlib import Path

from . import APP_ID


def data_dir() -> Path:
    override = os.environ.get("ETA_DATA")
    if override:
        base = Path(override)
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_ID
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")) / APP_ID
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_ID
    base.mkdir(parents=True, exist_ok=True)
    return base


def resource_path(*parts: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base).joinpath(*parts)
    return Path(__file__).resolve().parent.parent.joinpath(*parts)


def system_memory_mb():
    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 / 1024)
    except (ValueError, OSError, AttributeError):
        return 8192


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text("utf-8"))
    except Exception:
        return default


def save_json(path, data):
    path = Path(path)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    os.replace(tmp, path)


class Settings(dict):
    DEFAULTS = {
        "theme": "system", "game_dir": "", "java_path": "", "memory_mb": 4096, "jvm_args": "-XX:+UseG1GC",
        "width": 1280, "height": 720, "fullscreen": False, "close_on_launch": False, "show_console": False,
        "parallel_downloads": 6, "default_source": "modrinth", "selected_account": "", "selected_instance": "",
        "sidebar_hidden": False, "check_updates": True, "sidebar_side": "left", "filters_hidden": False,
        "accent": "#D97757", "backdrop": "none", "glass": False, "glass_opacity": 0.6, "blur": 24, "veil": 18,
        "serif_headings": True, "curseforge_key": "", "csl_skins": True,
    }

    def __init__(self, file=None):
        super().__init__(self.DEFAULTS)
        self.file = Path(file) if file else data_dir() / "settings.json"
        self.update(load_json(self.file, {}))

    def save(self):
        try:
            save_json(self.file, dict(self))
        except OSError:
            pass

    def game_dir(self) -> Path:
        p = Path(self.get("game_dir") or (data_dir() / "minecraft")).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p
