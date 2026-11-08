"""Liste des programmes (menu Démarrer + processus en cours) et extraction des icônes."""
import ctypes
import os
import subprocess

import psutil
from PIL import Image, ImageDraw

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
VP = ctypes.c_void_p

user32.GetDC.argtypes = [VP]
user32.GetDC.restype = VP
user32.ReleaseDC.argtypes = [VP, VP]
user32.DrawIconEx.argtypes = [VP, ctypes.c_int, ctypes.c_int, VP, ctypes.c_int, ctypes.c_int,
                              ctypes.c_uint, VP, ctypes.c_uint]
user32.DestroyIcon.argtypes = [VP]
shell32.ExtractIconExW.argtypes = [ctypes.c_wchar_p, ctypes.c_int, ctypes.POINTER(VP),
                                   ctypes.POINTER(VP), ctypes.c_uint]
shell32.ExtractIconExW.restype = ctypes.c_uint
gdi32.CreateCompatibleDC.argtypes = [VP]
gdi32.CreateCompatibleDC.restype = VP
gdi32.CreateDIBSection.argtypes = [VP, VP, ctypes.c_uint, ctypes.POINTER(VP), VP, ctypes.c_uint]
gdi32.CreateDIBSection.restype = VP
gdi32.SelectObject.argtypes = [VP, VP]
gdi32.SelectObject.restype = VP
gdi32.DeleteObject.argtypes = [VP]
gdi32.DeleteDC.argtypes = [VP]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32), ("biHeight", ctypes.c_int32),
                ("biPlanes", ctypes.c_uint16), ("biBitCount", ctypes.c_uint16),
                ("biCompression", ctypes.c_uint32), ("biSizeImage", ctypes.c_uint32),
                ("biXPelsPerMeter", ctypes.c_int32), ("biYPelsPerMeter", ctypes.c_int32),
                ("biClrUsed", ctypes.c_uint32), ("biClrImportant", ctypes.c_uint32)]


_icons = {}
_apps = None


def placeholder(size=32):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([3, 3, size - 4, size - 4], radius=6, fill=(88, 88, 88, 255))
    d.rounded_rectangle([8, 9, size - 9, size - 9], radius=3, fill=(140, 140, 140, 255))
    return img


def _extract(path, sz=32):
    if not os.path.isfile(path):
        return None
    large = VP()
    if shell32.ExtractIconExW(path, 0, ctypes.byref(large), None, 1) < 1 or not large.value:
        return None
    hdc = user32.GetDC(None)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bih = BITMAPINFOHEADER(40, sz, -sz, 1, 32, 0, 0, 0, 0, 0, 0)
    bits = VP()
    hbmp = gdi32.CreateDIBSection(hdc, ctypes.addressof(bih), 0, ctypes.byref(bits), None, 0)
    frames = []
    try:
        if not hbmp or not bits.value:
            return None
        old = gdi32.SelectObject(mdc, hbmp)
        n = sz * sz * 4
        # On dessine l'icône sur fond noir puis blanc pour retrouver la transparence.
        for fill in (0x00, 0xFF):
            ctypes.memset(bits.value, fill, n)
            user32.DrawIconEx(mdc, 0, 0, large, sz, sz, 0, None, 3)
            gdi32.GdiFlush()
            frames.append(ctypes.string_at(bits.value, n))
        gdi32.SelectObject(mdc, old)
    finally:
        if hbmp:
            gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(mdc)
        user32.ReleaseDC(None, hdc)
        user32.DestroyIcon(large)
    if len(frames) < 2:
        return None
    b, w = frames
    out = bytearray(sz * sz * 4)
    for i in range(0, sz * sz * 4, 4):
        a = 255 - max(w[i] - b[i], w[i + 1] - b[i + 1], w[i + 2] - b[i + 2])
        if a <= 0:
            continue
        k = 255 / a if a < 255 else 1
        out[i] = min(255, int(b[i + 2] * k))
        out[i + 1] = min(255, int(b[i + 1] * k))
        out[i + 2] = min(255, int(b[i] * k))
        out[i + 3] = min(255, a)
    return Image.frombytes("RGBA", (sz, sz), bytes(out))


def icon_image(path):
    key = (path or "").lower()
    if key not in _icons:
        try:
            img = _extract(path)
        except Exception:
            img = None
        _icons[key] = img or placeholder()
    return _icons[key]


_PS = r"""
[Console]::OutputEncoding=[Text.Encoding]::UTF8
$s=New-Object -ComObject WScript.Shell
$d=@("$env:ProgramData\Microsoft\Windows\Start Menu\Programs","$env:APPDATA\Microsoft\Windows\Start Menu\Programs")
Get-ChildItem $d -Recurse -Filter *.lnk -ErrorAction SilentlyContinue | ForEach-Object {
  $t=$s.CreateShortcut($_.FullName).TargetPath
  if($t -like '*.exe'){ $_.BaseName + '|' + $t }
}
"""


def _start_menu():
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS],
                           capture_output=True, timeout=30, creationflags=0x08000000)
        text = r.stdout.decode("utf-8", errors="replace")
    except Exception:
        return []
    out = []
    for line in text.splitlines():
        if "|" not in line:
            continue
        name, path = line.rsplit("|", 1)
        name, path = name.strip(), path.strip()
        low = name.lower()
        if not path or "unins" in path.lower() or "uninstall" in low or "désinstall" in low:
            continue
        out.append((name, path))
    return out


def list_apps(force=False):
    global _apps
    if _apps is not None and not force:
        return _apps
    found = {}
    for name, path in _start_menu():
        found.setdefault(path.lower(), {"name": name, "path": path})
    windir = os.environ.get("WINDIR", "C:\\Windows").lower()
    for p in psutil.process_iter(["exe"]):
        try:
            exe = p.info["exe"]
        except psutil.Error:
            continue
        if not exe or exe.lower().startswith(windir):
            continue
        found.setdefault(exe.lower(), {"name": os.path.splitext(os.path.basename(exe))[0], "path": exe})
    _apps = sorted(found.values(), key=lambda a: a["name"].casefold())
    return _apps
