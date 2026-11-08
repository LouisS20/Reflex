import os
import sys
import traceback
from datetime import datetime

from system import single_instance


def _crash_log(text):
    """Pas de console dans le .exe : sans ça, un plantage au démarrage est invisible."""
    try:
        import config
        with open(os.path.join(config.config_dir(), "crash.log"), "a", encoding="utf-8") as f:
            f.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S} ---\n{text}\n")
    except Exception:
        pass


def main():
    if not single_instance():
        return
    try:
        import system
        system.refresh_autostart()
        if "--minimized" in sys.argv:
            system.wait_for_desktop()
        from ui import App
        App(start_hidden="--minimized" in sys.argv).mainloop()
    except Exception:
        _crash_log(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
