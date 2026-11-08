import copy
import json
import os

APP_NAME = "Reflex"


def config_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


CONFIG_PATH = os.path.join(config_dir(), "config.json")

DEFAULT = {
    "winkey": {
        "enabled": True,
        "hold_ms": 200,
        "close_start": True,
        "short": {"type": "keys", "value": "alt+space"},
        "long": {"type": "start", "value": ""},
    },
    "app_triggers": [],
    "hotkeys": [],
    "close_to_tray": True,
    "start_minimized": False,
}


def load():
    cfg = copy.deepcopy(DEFAULT)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in data.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    except (OSError, ValueError):
        pass
    return cfg


def save(cfg):
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)
