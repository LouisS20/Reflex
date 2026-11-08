import ctypes
import os
import sys
import winreg

APP_NAME = "Reflex"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_mutex = None
_wake_event = None


def single_instance():
    """Retourne False si Reflex tourne déjà (et lui demande alors d'afficher sa fenêtre)."""
    global _mutex, _wake_event
    k32 = ctypes.windll.kernel32
    _mutex = k32.CreateMutexW(None, False, "Local\\ReflexSingleInstance")
    already = k32.GetLastError() == 183  # ERROR_ALREADY_EXISTS
    _wake_event = k32.CreateEventW(None, False, False, "Local\\ReflexWake")
    if already:
        k32.SetEvent(_wake_event)
    return not already


def wake_requested():
    """True si une autre instance vient d'être lancée : la fenêtre doit se rouvrir."""
    if not _wake_event:
        return False
    return ctypes.windll.kernel32.WaitForSingleObject(_wake_event, 0) == 0


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _launch_command(extra=""):
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" {extra}'.strip()
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        exe = exe[:-10] + "pythonw.exe"
    return f'"{exe}" "{os.path.abspath(sys.argv[0])}" {extra}'.strip()


def relaunch_as_admin():
    if getattr(sys, "frozen", False):
        exe, params = sys.executable, ""
    else:
        exe, params = sys.executable, f'"{os.path.abspath(sys.argv[0])}"'
    return ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1) > 32


def get_autostart():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except OSError:
        return False


def set_autostart(on):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, _launch_command("--minimized"))
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except OSError:
                pass


def refresh_autostart():
    """Si le démarrage auto est activé mais pointe vers un ancien chemin (exe déplacé,
    reconstruit ailleurs...), Windows ne trouve plus le programme : on le remet à jour."""
    if not getattr(sys, "frozen", False):
        return
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            current = winreg.QueryValueEx(k, APP_NAME)[0]
    except OSError:
        return
    if current != _launch_command("--minimized"):
        try:
            set_autostart(True)
        except OSError:
            pass


def wait_for_desktop(timeout=90):
    """Au démarrage de Windows, Reflex peut partir avant que le bureau (barre des tâches)
    soit prêt : zone de notification et menu Démarrer sont alors inutilisables."""
    import time
    user32 = ctypes.windll.user32
    end = time.time() + timeout
    while time.time() < end:
        if user32.FindWindowW("Shell_TrayWnd", None):
            time.sleep(1.5)
            return
        time.sleep(0.5)
