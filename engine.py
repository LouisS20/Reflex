"""Moteur de Reflex : hooks clavier/souris, touche Windows court/long, déclencheurs d'applis."""
import collections
import ctypes
import datetime
import os
import queue
import subprocess
import threading
import time
from ctypes import wintypes

import psutil

from keys import (EXTENDED, MOD_OF_VK, MODS, VK, VK_NAME, build_combo, combo_key, parse, vk_of)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

ULONG_PTR = ctypes.c_size_t
LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

WH_KEYBOARD_LL, WH_MOUSE_LL = 13, 14
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x100, 0x101, 0x104, 0x105
WM_MBUTTONDOWN, WM_MBUTTONUP, WM_XBUTTONDOWN, WM_XBUTTONUP = 0x207, 0x208, 0x20B, 0x20C
LLKHF_INJECTED, LLMHF_INJECTED = 0x10, 0x01
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP = 0x1, 0x2
MAGIC = 0x52454C58
VK_LWIN, VK_MASK = 0x5B, 0xE8
BUTTONS = (0x04, 0x05, 0x06)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wintypes.POINT), ("mouseData", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _InputUnion(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _InputUnion)]


user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
WM_SYSCOMMAND, SC_TASKLIST = 0x0112, 0xF130


def start_menu_open():
    """Vrai si le menu Démarrer est la fenêtre active."""
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        if buf.value == "Windows.UI.Core.CoreWindow":
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return psutil.Process(pid.value).name().lower() == "startmenuexperiencehost.exe"
    except Exception:
        return False


def open_start():
    """Ouvre (ou ferme) le menu Démarrer quelle que soit la fenêtre active.

    On envoie directement à la barre des tâches la commande « Démarrer » (SC_TASKLIST),
    exactement ce que fait Windows après un appui sur la touche Windows. Contrairement à
    une fausse touche Windows, ça ne dépend ni de la fenêtre au premier plan (navigateur,
    appli Electron, bureau...) ni de l'état du clavier. Repli sur la touche Windows simulée.
    """
    try:
        tray = user32.FindWindowW("Shell_TrayWnd", None)
        if tray and user32.PostMessageW(tray, WM_SYSCOMMAND, SC_TASKLIST, 0):
            return
    except Exception:
        pass
    send_keys("win")


def _send(vk, up=False):
    flags = (KEYEVENTF_KEYUP if up else 0) | (KEYEVENTF_EXTENDEDKEY if vk in EXTENDED else 0)
    inp = INPUT(type=1)
    inp.ki = KEYBDINPUT(vk, user32.MapVirtualKeyW(vk, 0), flags, 0, MAGIC)
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def send_keys(combo):
    mods, key = parse(combo)
    mod_vks = [VK[m] for m in mods]
    for v in mod_vks:
        _send(v)
        time.sleep(0.01)
    if key:
        v = vk_of(key)
        _send(v)
        time.sleep(0.01)
        _send(v, True)
        time.sleep(0.01)
    for v in reversed(mod_vks):
        _send(v, True)
        time.sleep(0.01)


def launch(value):
    value = (value or "").strip()
    if not value:
        return
    path = value.strip('"')
    if os.path.exists(path):
        os.startfile(path, cwd=os.path.dirname(path) or None)
    else:
        subprocess.Popen(value, shell=True, creationflags=0x00000008 | 0x00000200)


def target_name(value):
    path = (value or "").strip().strip('"')
    return os.path.basename(path).lower() if path.lower().endswith(".exe") else None


def close_by_name(name):
    for p in psutil.process_iter(["name"]):
        try:
            if (p.info["name"] or "").lower() == name:
                p.terminate()
        except psutil.Error:
            pass


class Engine:
    def __init__(self):
        self.enabled = True
        self.logs = collections.deque(maxlen=300)
        self.log_version = 0
        self._lock = threading.Lock()
        self._held, self._swallowed, self._suppressed = set(), set(), set()
        self._reinject = {}
        self._pending = None
        self._capture = None
        self._rules, self._win, self._triggers = {}, {}, []
        self._intercept_win = False
        self._jobs = queue.Queue()
        self._tid = None
        self._stop = threading.Event()

    # ---------- journal ----------
    def log(self, msg):
        self.logs.append((datetime.datetime.now().strftime("%H:%M:%S"), msg))
        self.log_version += 1

    # ---------- configuration ----------
    def configure(self, cfg):
        rules = {}
        for h in cfg.get("hotkeys", []):
            if not h.get("enabled", True):
                continue
            try:
                rules[combo_key(h["combo"])] = (h["action"], h["combo"])
            except (ValueError, KeyError):
                continue
        win = cfg.get("winkey", {})
        self._rules, self._win = rules, win
        self._triggers = list(cfg.get("app_triggers", []))
        self._intercept_win = bool(win.get("enabled")) or any("win" in m for (m, _) in rules)

    def set_enabled(self, on):
        with self._lock:
            self.enabled = on
            self._pending = None
            self._held.clear()
            self._suppressed.clear()
        self.log("Reflex activé" if on else "Reflex en pause")

    # ---------- cycle de vie ----------
    def start(self):
        for target in (self._hook_main, self._job_worker, self._watch_loop):
            threading.Thread(target=target, daemon=True).start()
        self.log("Reflex démarré")

    def stop(self):
        self._stop.set()
        self._jobs.put(None)
        if self._tid:
            user32.PostThreadMessageW(self._tid, 0x12, 0, 0)  # WM_QUIT

    # ---------- actions ----------
    def run_action(self, action, label=""):
        t = (action or {}).get("type", "none")
        v = ((action or {}).get("value") or "").strip()
        if t == "none":
            return
        self.log(f"{label} : {t} {v}".strip())
        if t == "launch":
            def go():
                try:
                    launch(v)
                except Exception as e:
                    self.log(f"Échec du lancement : {e}")
            threading.Thread(target=go, daemon=True).start()
        elif t == "keys":
            self._jobs.put(lambda: send_keys(v))
        elif t == "start":
            self._jobs.put(open_start)

    def _job_worker(self):
        while not self._stop.is_set():
            job = self._jobs.get()
            if job is None:
                break
            try:
                job()
            except Exception as e:
                self.log(f"Erreur d'envoi de touches : {e}")

    # ---------- capture d'une combinaison ----------
    def capture(self, callback, timeout=10):
        with self._lock:
            self._pending = None
            self._capture = callback

        def expire():
            with self._lock:
                if self._capture is callback:
                    self._capture = None
                else:
                    return
            callback(None)
        t = threading.Timer(timeout, expire)
        t.daemon = True
        t.start()

    def _capture_key(self, vk, down, mod):
        if mod:
            if down:
                self._held.add(vk)
                self._swallowed.add(vk)
                return True
            self._held.discard(vk)
            if vk in self._swallowed:
                self._swallowed.discard(vk)
                return True
            return False
        if down:
            if vk in self._suppressed:
                return True
            cb, self._capture = self._capture, None
            combo = build_combo(self._mods(), VK_NAME.get(vk, f"vk{vk}"))
            self._suppressed.add(vk)
            if cb:
                cb(combo)
            return True
        if vk in self._suppressed:
            self._suppressed.discard(vk)
            return True
        return False

    # ---------- logique des touches ----------
    def _mods(self):
        return frozenset(MOD_OF_VK[v] for v in self._held if v in MOD_OF_VK)

    def _handle_key(self, vk, down, button=False):
        mod = MOD_OF_VK.get(vk)
        if self._capture is not None:
            return self._capture_key(vk, down, mod)
        if not self.enabled:
            return False
        if mod:
            if not down and vk in self._swallowed:
                self._swallowed.discard(vk)
                self._held.discard(vk)
                return True
            if mod == "win" and self._intercept_win:
                return self._handle_win(vk, down)
            (self._held.add if down else self._held.discard)(vk)
            return False

        if not down:
            if vk in self._suppressed:
                self._suppressed.discard(vk)
                return True
            with self._lock:
                rec = self._reinject.get(vk)
                if rec:
                    rec["released"] = True
                    return True
            return False

        if vk in self._suppressed:
            return True
        mods = self._mods()
        hit = self._rules.get((mods, vk))
        if hit:
            action, combo = hit
            self._suppressed.add(vk)
            with self._lock:
                if self._pending:
                    self._pending["handled"] = True
            if "alt" in mods:
                self._jobs.put(lambda: (_send(VK_MASK), _send(VK_MASK, True)))
            self.run_action(action, f"Raccourci {combo}")
            return True

        if button:
            return False
        with self._lock:
            p = self._pending
            if p and not p["long"] and not p["injected"]:
                p["injected"] = True
                rec = {"released": False}
                self._reinject[vk] = rec
            else:
                return False
        # La touche Windows était retenue : on la renvoie avant la touche pour que Win+X fonctionne.
        self._jobs.put(lambda: self._reinject_job(vk, rec))
        return True

    def _reinject_job(self, vk, rec):
        _send(VK_LWIN)
        _send(vk)
        with self._lock:
            released = rec["released"]
            self._reinject.pop(vk, None)
        if released:
            _send(vk, True)

    def _handle_win(self, vk, down):
        w = self._win
        if down:
            if vk in self._held:
                return True
            self._held.add(vk)
            with self._lock:
                if self._pending is not None:
                    return True
                p = {"long": False, "injected": False, "handled": False}
                self._pending = p
            long_type = (w.get("long") or {}).get("type", "none")
            if w.get("enabled") and long_type != "none":
                t = threading.Timer(max(0.1, w.get("hold_ms", 350) / 1000), self._win_long, (p,))
                t.daemon = True
                t.start()
            return True

        self._held.discard(vk)
        with self._lock:
            p, self._pending = self._pending, None
        if p is None:
            return False
        if p["injected"]:
            self._jobs.put(lambda: _send(VK_LWIN, True))
        elif p["handled"] or p["long"]:
            pass
        elif w.get("enabled"):
            if w.get("close_start", True) and start_menu_open():
                self.run_action({"type": "start"}, "Fermeture du menu Démarrer")
            else:
                self.run_action(w.get("short") or {"type": "start"}, "Touche Windows (appui court)")
        else:
            self._jobs.put(lambda: send_keys("win"))
        return True

    def _win_long(self, p):
        with self._lock:
            if self._pending is not p or p["long"] or p["injected"] or p["handled"]:
                return
            p["long"] = True
        if self._win.get("close_start", True) and start_menu_open():
            self.run_action({"type": "start"}, "Fermeture du menu Démarrer")
            return
        self.run_action(self._win.get("long") or {"type": "start"}, "Touche Windows (appui long)")

    # ---------- hooks Windows ----------
    def _on_key(self, nCode, wParam, lParam):
        if nCode == 0:
            try:
                kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if not (kb.flags & LLKHF_INJECTED):
                    down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
                    if self._handle_key(kb.vkCode, down):
                        return 1
            except Exception as e:
                self.log(f"Erreur clavier : {e}")
        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    def _on_mouse(self, nCode, wParam, lParam):
        if nCode == 0 and wParam in (WM_MBUTTONDOWN, WM_MBUTTONUP, WM_XBUTTONDOWN, WM_XBUTTONUP):
            try:
                ms = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                if not (ms.flags & LLMHF_INJECTED):
                    if wParam in (WM_MBUTTONDOWN, WM_MBUTTONUP):
                        vk = 0x04
                    else:
                        vk = 0x05 if ((ms.mouseData >> 16) & 0xFFFF) == 1 else 0x06
                    down = wParam in (WM_MBUTTONDOWN, WM_XBUTTONDOWN)
                    if self._handle_key(vk, down, button=True):
                        return 1
            except Exception as e:
                self.log(f"Erreur souris : {e}")
        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    def _hook_main(self):
        self._tid = kernel32.GetCurrentThreadId()
        self._kb_proc = HOOKPROC(self._on_key)
        self._ms_proc = HOOKPROC(self._on_mouse)
        hmod = kernel32.GetModuleHandleW(None)
        kb = ms = None
        for attempt in range(10):  # au démarrage de Windows, l'installation peut échouer un moment
            kb = kb or user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._kb_proc, hmod, 0)
            ms = ms or user32.SetWindowsHookExW(WH_MOUSE_LL, self._ms_proc, hmod, 0)
            if kb and ms:
                break
            time.sleep(2)
        if not kb:
            self.log("Impossible d'installer le hook clavier")
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        for h in (kb, ms):
            if h:
                user32.UnhookWindowsHookEx(h)

    # ---------- déclencheurs d'applications ----------
    @staticmethod
    def running_names():
        names = set()
        for p in psutil.process_iter(["name"]):
            try:
                if p.info["name"]:
                    names.add(p.info["name"].lower())
            except psutil.Error:
                pass
        return names

    def _watch_loop(self):
        try:
            prev = self.running_names()
        except Exception:
            prev = set()
        while not self._stop.wait(1.0):
            try:
                cur = self.running_names()
            except Exception:
                continue
            started, stopped = cur - prev, prev - cur
            prev = cur
            if not self.enabled:
                continue
            for t in self._triggers:
                if not t.get("enabled", True):
                    continue
                name = (t.get("process") or "").lower()
                if name in started:
                    delay = float(t.get("delay", 0) or 0)
                    self.log(f"{name} s'est ouvert")
                    timer = threading.Timer(delay, self.run_action, (t.get("action"), f"Déclencheur {name}"))
                    timer.daemon = True
                    timer.start()
                if name in stopped and t.get("close_with"):
                    target = target_name((t.get("action") or {}).get("value"))
                    if target:
                        self.log(f"{name} s'est fermé : fermeture de {target}")
                        close_by_name(target)
