import os
import queue
import threading
from tkinter import filedialog, messagebox

import customtkinter as ctk
import pystray
from PIL import Image

import apps
import config
import icon as iconmod
import system
from engine import Engine
from keys import combo_key, describe_action, pretty

# Encre froide et accent ambre, comme le voyant d'une touche allumée
BG, RAIL, SURFACE, SURFACE2 = "#0F1115", "#0A0B0E", "#171A20", "#21252D"
HOVER, LINE = "#2B303A", "#2A2F39"
TEXT, MUTED = "#EEF1F6", "#8B93A5"
ACCENT, ACCENT_H, ACCENT_T, DANGER = "#FFC247", "#FFD36F", "#14110A", "#FF7A85"
RADIUS = 8
CARD = 14

ctk.set_appearance_mode("dark")

TYPE_LABELS = {
    "none": "Ne rien faire",
    "start": "Ouvrir le menu Démarrer",
    "keys": "Envoyer des touches",
    "launch": "Lancer un programme",
}
TABS = {"Applications": "apps", "Touche Windows": "win", "Raccourcis": "keys",
        "Activité": "log", "Réglages": "settings"}

_fonts = {}


def F(size=13, bold=False):
    key = (size, bold)
    if key not in _fonts:
        _fonts[key] = ctk.CTkFont(family="Segoe UI Semibold" if bold else "Segoe UI", size=size)
    return _fonts[key]


def short(text, n=72):
    text = text or ""
    return text if len(text) <= n else text[: n - 1] + "…"


def btn(parent, text, command, primary=False, width=90, **kw):
    if primary:
        style = dict(fg_color=ACCENT, hover_color=ACCENT_H, text_color=ACCENT_T)
    else:
        style = dict(fg_color=SURFACE2, hover_color=HOVER, text_color=TEXT, border_width=1, border_color=LINE)
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=32,
                         corner_radius=RADIUS, font=F(), **style, **kw)


def entry(parent, **kw):
    return ctk.CTkEntry(parent, height=32, corner_radius=RADIUS, fg_color=SURFACE2, border_color=LINE,
                        text_color=TEXT, font=F(), **kw)


def ctk_image(img, size=24):
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))


class Modal(ctk.CTkToplevel):
    def __init__(self, app, title, width=540, height=420, parent=None):
        super().__init__(app, fg_color=BG)
        self.app, self.parent_modal = app, parent
        self.title(title)
        self.geometry(f"{width}x{height}+{app.winfo_x() + 100}+{app.winfo_y() + 60}")
        self.resizable(False, False)
        self.transient(parent or app)
        self.after(150, self.grab_set)
        self.after(250, lambda: self.iconbitmap(iconmod.ensure_ico()))
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=22, pady=18)
        self.body.grid_columnconfigure(0, weight=1)

    def destroy(self):
        pm = self.parent_modal
        super().destroy()
        if pm is not None:
            try:
                pm.after(50, pm.grab_set)
            except Exception:
                pass

    def label(self, text, row, top=14):
        ctk.CTkLabel(self.body, text=text, text_color=MUTED, anchor="w", font=F(12)).grid(
            row=row, column=0, sticky="w", pady=(top, 4))

    def footer(self, row, on_save):
        bar = ctk.CTkFrame(self.body, fg_color="transparent")
        bar.grid(row=row, column=0, sticky="e", pady=(22, 0))
        btn(bar, "Annuler", self.destroy).pack(side="left", padx=(0, 8))
        btn(bar, "Enregistrer", on_save, primary=True).pack(side="left")


class AppPicker(Modal):
    """Liste de programmes avec recherche et icônes."""

    def __init__(self, app, on_pick, parent=None):
        super().__init__(app, "Choisir un programme", 560, 620, parent)
        self.on_pick, self._tok, self._after, self._items = on_pick, 0, None, []
        self._blank = ctk_image(Image.new("RGBA", (32, 32), (0, 0, 0, 0)))
        self.body.grid_rowconfigure(1, weight=1)
        self.search = entry(self.body, placeholder_text="Rechercher un programme")
        self.search.grid(row=0, column=0, sticky="ew")
        self.search.bind("<KeyRelease>", self._on_key)
        self.list = ctk.CTkScrollableFrame(self.body, fg_color="transparent")
        self.list.grid(row=1, column=0, sticky="nsew", pady=10)
        ctk.CTkLabel(self.list, text="Chargement des programmes…", text_color=MUTED, font=F()).pack(pady=20)
        bar = ctk.CTkFrame(self.body, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew")
        btn(bar, "Parcourir…", self._browse).pack(side="left")
        btn(bar, "Annuler", self.destroy).pack(side="right")
        self.after(300, self.search.focus)
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        items = apps.list_apps()
        self.app.post(lambda: self._loaded(items))

    def _loaded(self, items):
        if self.winfo_exists():
            self._items = items
            self._render()

    def _on_key(self, _=None):
        if self._after:
            self.after_cancel(self._after)
        self._after = self.after(150, self._render)

    def _render(self):
        q = self.search.get().strip().lower()
        res = [a for a in self._items if q in a["name"].lower() or q in a["path"].lower()][:80]
        for w in self.list.winfo_children():
            w.destroy()
        self._tok += 1
        tok = self._tok
        if not res:
            ctk.CTkLabel(self.list, text="Aucun programme trouvé.", text_color=MUTED, font=F()).pack(pady=20)
            return
        rows = []
        for a in res:
            b = ctk.CTkButton(self.list, text=f"{a['name']}\n{short(a['path'], 62)}", image=self._blank,
                              compound="left", anchor="w", height=50, fg_color="transparent",
                              hover_color=HOVER, text_color=TEXT, corner_radius=RADIUS, font=F(12),
                              command=lambda a=a: self._pick(a["path"]))
            b.pack(fill="x", pady=1)
            rows.append((b, a["path"]))
        threading.Thread(target=self._icons, args=(rows, tok), daemon=True).start()

    def _icons(self, rows, tok):
        for b, path in rows:
            if tok != self._tok:
                return
            img = apps.icon_image(path)
            self.app.post(lambda b=b, img=img: self._set_icon(b, img, tok))

    def _set_icon(self, b, img, tok):
        if tok != self._tok:
            return
        try:
            b.configure(image=ctk_image(img))
        except Exception:
            pass

    def _pick(self, path):
        self.on_pick(path)
        self.destroy()

    def _browse(self):
        path = filedialog.askopenfilename(parent=self, title="Choisir un programme",
                                          filetypes=[("Programmes", "*.exe"), ("Tous les fichiers", "*.*")])
        if path:
            self._pick(path.replace("/", "\\"))


class ActionEditor(ctk.CTkFrame):
    """Choix d'une action : rien, menu Démarrer, touches, programme."""

    def __init__(self, master, app, allowed, action=None, owner=None):
        super().__init__(master, fg_color="transparent")
        self.app, self.allowed, self.owner = app, list(allowed), owner
        self.grid_columnconfigure(0, weight=1)
        self.menu = ctk.CTkOptionMenu(
            self, values=[TYPE_LABELS[t] for t in self.allowed], command=self._on_type, height=32,
            corner_radius=RADIUS, fg_color=SURFACE2, button_color=SURFACE2, button_hover_color=HOVER,
            dropdown_fg_color=SURFACE2, dropdown_hover_color=HOVER, text_color=TEXT, font=F(),
            dropdown_font=F())
        self.menu.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.entry = entry(self)
        self.entry.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.btn = btn(self, "", self._on_btn, width=100)
        self.btn.grid(row=1, column=1, padx=(8, 0), pady=(8, 0))
        self.btn2 = btn(self, "Parcourir…", self._browse, width=100)
        self.btn2.grid(row=1, column=2, padx=(8, 0), pady=(8, 0))
        self.set(action or {"type": self.allowed[0], "value": ""})

    def _type(self):
        label = self.menu.get()
        return next(k for k, v in TYPE_LABELS.items() if v == label)

    def _on_type(self, _=None):
        t = self._type()
        if t == "keys":
            self.entry.grid()
            self.btn.grid()
            self.btn2.grid_remove()
            self.entry.configure(placeholder_text="ex. alt+space ou ctrl+shift+esc")
            self.btn.configure(text="Enregistrer")
        elif t == "launch":
            self.entry.grid()
            self.btn.grid()
            self.btn2.grid()
            self.entry.configure(placeholder_text="Chemin du programme ou commande")
            self.btn.configure(text="Choisir…")
        else:
            self.entry.grid_remove()
            self.btn.grid_remove()
            self.btn2.grid_remove()

    def _set_value(self, value):
        self.entry.delete(0, "end")
        self.entry.insert(0, value)

    def _on_btn(self):
        if self._type() == "launch":
            parent = self.owner if isinstance(self.owner, Modal) else None
            AppPicker(self.app, self._set_value, parent)
        else:
            self.btn.configure(text="Appuie sur les touches…", state="disabled")

            def done(combo):
                def apply():
                    if combo:
                        self._set_value(combo)
                    self.btn.configure(text="Enregistrer", state="normal")
                self.app.post(apply)
            self.app.engine.capture(done)

    def _browse(self):
        parent = self.owner if isinstance(self.owner, Modal) else self.app
        path = filedialog.askopenfilename(parent=parent, title="Choisir un programme")
        if path:
            self._set_value(path.replace("/", "\\"))

    def set(self, action):
        t = action.get("type", "none")
        if t not in self.allowed:
            t = self.allowed[0]
        self.menu.set(TYPE_LABELS[t])
        self._set_value(action.get("value", "") or "")
        self._on_type()

    def get(self):
        t = self._type()
        v = self.entry.get().strip() if t in ("keys", "launch") else ""
        return {"type": t, "value": v}


class TriggerDialog(Modal):
    def __init__(self, app, existing, on_done):
        super().__init__(app, "Règle d'application", 600, 470)
        self.on_done = on_done
        t = existing or {"enabled": True, "process": "", "process_path": "",
                         "action": {"type": "launch", "value": ""}, "delay": 0, "close_with": False}
        self.proc_path = t.get("process_path", "")
        self.label("Quand cette application s'ouvre", 0, 0)
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew")
        row.grid_columnconfigure(0, weight=1)
        self.proc = entry(row, placeholder_text="ex. spotify.exe")
        self.proc.insert(0, t["process"])
        self.proc.grid(row=0, column=0, sticky="ew")
        btn(row, "Choisir…", lambda: AppPicker(app, self._picked, self), width=100).grid(
            row=0, column=1, padx=(8, 0))
        self.label("Alors", 2)
        self.action = ActionEditor(self.body, app, ("launch", "keys"), t["action"], owner=self)
        self.action.grid(row=3, column=0, sticky="ew")
        self.label("Délai avant l'action, en secondes", 4)
        self.delay = entry(self.body, width=100)
        self.delay.insert(0, str(t.get("delay", 0)))
        self.delay.grid(row=5, column=0, sticky="w")
        self.close_var = ctk.BooleanVar(value=t.get("close_with", False))
        ctk.CTkCheckBox(self.body, text="Fermer aussi ce programme quand l'application se ferme",
                        variable=self.close_var, fg_color=ACCENT, hover_color=ACCENT_H, checkmark_color=ACCENT_T,
                        corner_radius=3, font=F()).grid(row=6, column=0, sticky="w", pady=(18, 0))
        self.footer(7, lambda: self._save(t))

    def _picked(self, path):
        self.proc_path = path
        self.proc.delete(0, "end")
        self.proc.insert(0, os.path.basename(path))

    def _save(self, t):
        name = self.proc.get().strip().lower()
        if not name:
            messagebox.showwarning("Reflex", "Indique l'application à surveiller.", parent=self)
            return
        if "." not in name:
            name += ".exe"
        try:
            delay = max(0.0, float(self.delay.get().replace(",", ".") or 0))
        except ValueError:
            messagebox.showwarning("Reflex", "Le délai doit être un nombre.", parent=self)
            return
        action = self.action.get()
        if action["type"] in ("keys", "launch") and not action["value"]:
            messagebox.showwarning("Reflex", "Complète l'action à exécuter.", parent=self)
            return
        path = self.proc_path if os.path.basename(self.proc_path).lower() == name else ""
        self.on_done({"enabled": t.get("enabled", True), "process": name, "process_path": path,
                      "action": action, "delay": delay, "close_with": self.close_var.get()})
        self.destroy()


class HotkeyDialog(Modal):
    def __init__(self, app, existing, on_done):
        super().__init__(app, "Raccourci", 600, 380)
        self.on_done = on_done
        h = existing or {"enabled": True, "combo": "", "action": {"type": "launch", "value": ""}}
        self.label("Quand j'appuie sur", 0, 0)
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew")
        row.grid_columnconfigure(0, weight=1)
        self.combo = entry(row, placeholder_text="ex. ctrl+alt+t, win+f1, xbutton1")
        self.combo.insert(0, h["combo"])
        self.combo.grid(row=0, column=0, sticky="ew")
        self.rec = btn(row, "Enregistrer", self._record, width=100)
        self.rec.grid(row=0, column=1, padx=(8, 0))
        self.label("Alors", 2)
        self.action = ActionEditor(self.body, app, ("launch", "keys", "start"), h["action"], owner=self)
        self.action.grid(row=3, column=0, sticky="ew")
        self.footer(4, lambda: self._save(h))

    def _record(self):
        self.rec.configure(text="Appuie…", state="disabled")

        def done(combo):
            def apply():
                if combo:
                    self.combo.delete(0, "end")
                    self.combo.insert(0, combo)
                self.rec.configure(text="Enregistrer", state="normal")
            self.app.post(apply)
        self.app.engine.capture(done)

    def _save(self, h):
        combo = self.combo.get().strip().lower()
        try:
            combo_key(combo)
        except ValueError as e:
            messagebox.showwarning("Reflex", str(e), parent=self)
            return
        action = self.action.get()
        if action["type"] in ("keys", "launch") and not action["value"]:
            messagebox.showwarning("Reflex", "Complète l'action à exécuter.", parent=self)
            return
        self.on_done({"enabled": h.get("enabled", True), "combo": combo, "action": action})
        self.destroy()


class App(ctk.CTk):
    NAV = (("apps", "Applis"), ("win", "Windows"), ("keys", "Raccourcis"), ("log", "Activité"),
           ("settings", "Réglages"))

    def __init__(self, start_hidden=False):
        super().__init__(fg_color=BG)
        self.cfg = config.load()
        self.engine = Engine()
        self.engine.configure(self.cfg)
        self._q = queue.Queue()
        self._log_seen = -1
        self._icon_cache, self._glyph_cache = {}, {}
        self.tray = None

        self.title("Reflex")
        self.geometry("1020x690")
        self.minsize(940, 620)
        try:
            self.iconbitmap(iconmod.ensure_ico())
        except Exception:
            pass

        self._build_rail()
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(side="left", fill="both", expand=True, padx=(30, 34), pady=(28, 22))
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        self.pages = {}
        for key, builder in (("apps", self._page_apps), ("win", self._page_win), ("keys", self._page_keys),
                             ("log", self._page_log), ("settings", self._page_settings)):
            f = ctk.CTkFrame(self.content, fg_color="transparent")
            f.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = f
            builder(f)
        self.show("apps")

        self.engine.start()
        self._start_tray()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._pump)
        if start_hidden or self.cfg.get("start_minimized"):
            self.after(50, self.withdraw)

    # ---------- infrastructure ----------
    def post(self, fn):
        self._q.put(fn)

    def _pump(self):
        if system.wake_requested():
            self.show_window()
        try:
            while True:
                self._q.get_nowait()()
        except queue.Empty:
            pass
        if self.engine.log_version != self._log_seen:
            self._refresh_log()
        self.after(150, self._pump)

    def save(self):
        config.save(self.cfg)
        self.engine.configure(self.cfg)

    def show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _on_close(self):
        # Fermer la fenêtre ne quitte jamais Reflex : il continue en arrière-plan.
        # L'option ne décide que de la présence de l'icône dans la zone de notification.
        self.withdraw()

    def quit_app(self):
        self.engine.stop()
        if self.tray:
            self.tray.stop()
        self.destroy()

    def _start_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("Ouvrir Reflex", lambda: self.post(self.show_window), default=True),
            pystray.MenuItem("Actif", lambda: self.post(self._toggle_from_tray),
                             checked=lambda item: self.engine.enabled),
            pystray.MenuItem("Quitter", lambda: self.post(self.quit_app)))
        self.tray = pystray.Icon("Reflex", iconmod.make_icon(64), "Reflex", menu)
        show = self.cfg.get("close_to_tray", True)
        self.tray.run_detached(setup=lambda icon: setattr(icon, "visible", show))

    def _apply_tray_visibility(self):
        if self.tray:
            self.tray.visible = bool(self.cfg.get("close_to_tray", True))

    def _toggle_from_tray(self):
        self.active_var.set(not self.active_var.get())
        self._on_active()

    def _on_active(self):
        self.engine.set_enabled(self.active_var.get())
        if self.tray:
            self.tray.update_menu()

    def _set(self, obj, key, value):
        obj[key] = value
        self.save()

    # ---------- barre de navigation ----------
    def _build_rail(self):
        rail = ctk.CTkFrame(self, fg_color=RAIL, corner_radius=0, width=98)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)
        ctk.CTkLabel(rail, text="", image=ctk_image(iconmod.make_icon(112), 46)).pack(pady=(26, 24))
        self.nav = {}
        for key, label in self.NAV:
            imgs = (ctk_image(iconmod.glyph(key, MUTED, 56), 26), ctk_image(iconmod.glyph(key, ACCENT, 56), 26))
            b = ctk.CTkButton(rail, text=label, image=imgs[0], compound="top", width=80, height=66,
                              corner_radius=12, fg_color="transparent", hover_color=SURFACE, text_color=MUTED,
                              font=F(11), command=lambda k=key: self.show(k))
            b.pack(pady=3)
            self.nav[key] = (b, imgs)
        self.active_var = ctk.BooleanVar(value=True)
        ctk.CTkLabel(rail, text="Actif", font=F(11), text_color=MUTED).pack(side="bottom", pady=(0, 24))
        ctk.CTkSwitch(rail, text="", variable=self.active_var, command=self._on_active, progress_color=ACCENT,
                      width=44).pack(side="bottom", pady=(0, 6))

    def show(self, key):
        self.pages[key].tkraise()
        for k, (b, imgs) in self.nav.items():
            sel = k == key
            b.configure(fg_color=SURFACE2 if sel else "transparent", text_color=TEXT if sel else MUTED,
                        image=imgs[1 if sel else 0])

    # ---------- éléments communs ----------
    def _head(self, parent, title, sub, action=None):
        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 20))
        box = ctk.CTkFrame(bar, fg_color="transparent")
        box.pack(side="left")
        ctk.CTkLabel(box, text=title, font=F(28, True), text_color=TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(box, text=sub, font=F(13), text_color=MUTED, anchor="w").pack(anchor="w", pady=(2, 0))
        if action:
            btn(bar, action[0], action[1], primary=True, width=150).pack(side="right", anchor="s")

    def _card(self, parent):
        return ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=CARD)

    def _glyph(self, name, size=24):
        key = (name, size)
        if key not in self._glyph_cache:
            self._glyph_cache[key] = ctk_image(iconmod.glyph(name, MUTED, size * 2), size)
        return self._glyph_cache[key]

    def _icon(self, path, fallback):
        if path and os.path.isfile(path):
            if path not in self._icon_cache:
                self._icon_cache[path] = ctk_image(apps.icon_image(path), 28)
            return self._icon_cache[path]
        return self._glyph(fallback)

    def _row(self, parent, enabled, title, subtitle, on_toggle, on_edit, on_delete, icon_path=None, fallback="apps"):
        f = self._card(parent)
        f.pack(fill="x", pady=4, padx=(0, 8))
        f.grid_columnconfigure(1, weight=1)
        tile = ctk.CTkFrame(f, fg_color=SURFACE2, corner_radius=11, width=48, height=48)
        tile.grid(row=0, column=0, padx=(14, 14), pady=13)
        tile.grid_propagate(False)
        ctk.CTkLabel(tile, text="", image=self._icon(icon_path, fallback)).place(relx=0.5, rely=0.5, anchor="center")
        box = ctk.CTkFrame(f, fg_color="transparent")
        box.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(box, text=title, text_color=TEXT, font=F(14, True), anchor="w").pack(anchor="w")
        ctk.CTkLabel(box, text=short(subtitle), text_color=MUTED, font=F(12), anchor="w").pack(anchor="w", pady=(1, 0))
        var = ctk.BooleanVar(value=enabled)
        ctk.CTkSwitch(f, text="", width=44, variable=var, progress_color=ACCENT,
                      command=lambda: on_toggle(var.get())).grid(row=0, column=2, padx=10)
        btn(f, "Modifier", on_edit, width=84).grid(row=0, column=3, padx=4)
        ctk.CTkButton(f, text="Supprimer", width=84, height=32, corner_radius=RADIUS, fg_color="transparent",
                      hover_color=HOVER, text_color=DANGER, font=F(), command=on_delete).grid(
            row=0, column=4, padx=(0, 12))

    def _empty(self, parent, text, glyph):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.pack(pady=70)
        ctk.CTkLabel(box, text="", image=self._glyph(glyph, 40)).pack()
        ctk.CTkLabel(box, text=text, text_color=MUTED, font=F(13)).pack(pady=(10, 0))

    def _scroll(self, parent):
        s = ctk.CTkScrollableFrame(parent, fg_color="transparent", scrollbar_button_color=SURFACE2,
                                   scrollbar_button_hover_color=HOVER)
        s.pack(fill="both", expand=True)
        return s

    def _delete(self, key, index, refresh):
        if messagebox.askyesno("Reflex", "Supprimer cette règle ?"):
            del self.cfg[key][index]
            self.save()
            refresh()

    # ---------- Applis ----------
    def _page_apps(self, page):
        self._head(page, "Applis", "Quand une application s'ouvre, une autre se lance.",
                   ("Ajouter une règle", lambda: self._edit_trigger(None)))
        self.apps_list = self._scroll(page)
        self._render_apps()

    def _render_apps(self):
        for w in self.apps_list.winfo_children():
            w.destroy()
        items = self.cfg["app_triggers"]
        if not items:
            self._empty(self.apps_list, "Aucune règle pour l'instant.", "apps")
        for i, t in enumerate(items):
            extra = f" · après {t['delay']:g} s" if t.get("delay") else ""
            extra += " · se ferme avec elle" if t.get("close_with") else ""
            self._row(self.apps_list, t.get("enabled", True), t["process"], describe_action(t["action"]) + extra,
                      lambda v, t=t: self._set(t, "enabled", v),
                      lambda i=i: self._edit_trigger(i),
                      lambda i=i: self._delete("app_triggers", i, self._render_apps),
                      icon_path=t.get("process_path"), fallback="apps")

    def _edit_trigger(self, index):
        items = self.cfg["app_triggers"]

        def done(t):
            if index is None:
                items.append(t)
            else:
                items[index] = t
            self.save()
            self._render_apps()
        TriggerDialog(self, items[index] if index is not None else None, done)

    # ---------- Windows ----------
    def _action_card(self, parent, col, title, sub, action):
        card = self._card(parent)
        card.grid(row=0, column=col, sticky="nsew", padx=(0, 8) if col == 0 else (8, 0))
        ctk.CTkLabel(card, text=title, font=F(15, True), text_color=TEXT, anchor="w").pack(
            anchor="w", padx=18, pady=(16, 0))
        ctk.CTkLabel(card, text=sub, font=F(12), text_color=MUTED, anchor="w").pack(anchor="w", padx=18)
        editor = ActionEditor(card, self, ("none", "start", "keys", "launch"), action)
        editor.pack(fill="x", padx=18, pady=(12, 18))
        return editor

    def _page_win(self, page):
        w = self.cfg["winkey"]
        self._head(page, "Touche Windows", "Un appui court et un appui long peuvent faire deux choses différentes.")
        self.win_var = ctk.BooleanVar(value=w["enabled"])
        ctk.CTkSwitch(page, text="Personnaliser la touche Windows", variable=self.win_var, progress_color=ACCENT,
                      font=F(13, True), command=lambda: self._set(self.cfg["winkey"], "enabled", self.win_var.get())
                      ).pack(anchor="w", pady=(0, 14))
        cols = ctk.CTkFrame(page, fg_color="transparent")
        cols.pack(fill="x")
        cols.grid_columnconfigure((0, 1), weight=1, uniform="c")
        self.win_short = self._action_card(cols, 0, "Appui court", "Un appui bref sur la touche.", w["short"])
        self.win_long = self._action_card(cols, 1, "Appui long", "Touche maintenue au-delà du seuil.", w["long"])

        opt = self._card(page)
        opt.pack(fill="x", pady=(16, 0))
        self.close_var = ctk.BooleanVar(value=w.get("close_start", True))
        ctk.CTkSwitch(opt, text="Si le menu Démarrer est ouvert, un appui sur Windows le ferme",
                      variable=self.close_var, progress_color=ACCENT, font=F(),
                      command=lambda: self._set(self.cfg["winkey"], "close_start", self.close_var.get())
                      ).pack(anchor="w", padx=18, pady=(16, 0))
        ctk.CTkFrame(opt, height=1, fg_color=LINE).pack(fill="x", padx=18, pady=14)
        bar = ctk.CTkFrame(opt, fg_color="transparent")
        bar.pack(anchor="w", padx=18, pady=(0, 16))
        ctk.CTkLabel(bar, text="Un appui est long à partir de", text_color=MUTED, font=F()).pack(side="left")
        self.hold_slider = ctk.CTkSlider(bar, from_=150, to=800, number_of_steps=65, width=240,
                                         progress_color=ACCENT, button_color=ACCENT, button_hover_color=ACCENT_H,
                                         command=self._on_hold)
        self.hold_slider.set(w["hold_ms"])
        self.hold_slider.pack(side="left", padx=14)
        self.hold_lbl = ctk.CTkLabel(bar, text=f"{w['hold_ms']} ms", text_color=TEXT, font=F(13, True))
        self.hold_lbl.pack(side="left")

        foot = ctk.CTkFrame(page, fg_color="transparent")
        foot.pack(anchor="w", pady=(18, 0))
        btn(foot, "Appliquer", self._apply_win, primary=True, width=120).pack(side="left")
        btn(foot, "Préréglage Flow Launcher", self._preset_flow, width=200).pack(side="left", padx=10)
        ctk.CTkLabel(page, text="Pour Flow Launcher, son raccourci d'ouverture doit être Alt + Espace.",
                     text_color=MUTED, font=F(12)).pack(anchor="w", pady=(12, 0))

    def _on_hold(self, value):
        ms = int(round(value / 10) * 10)
        self.hold_lbl.configure(text=f"{ms} ms")
        self.cfg["winkey"]["hold_ms"] = ms
        self.save()

    def _apply_win(self):
        for key, editor in (("short", self.win_short), ("long", self.win_long)):
            a = editor.get()
            if a["type"] in ("keys", "launch") and not a["value"]:
                messagebox.showwarning("Reflex", "Complète les deux actions avant d'appliquer.")
                return
            self.cfg["winkey"][key] = a
        self.save()
        self.engine.log("Réglages de la touche Windows appliqués")

    def _preset_flow(self):
        self.win_short.set({"type": "keys", "value": "alt+space"})
        self.win_long.set({"type": "start", "value": ""})
        self._apply_win()

    # ---------- Raccourcis ----------
    def _page_keys(self, page):
        self._head(page, "Raccourcis", "Une touche, une combinaison ou un bouton de souris lance une action.",
                   ("Ajouter un raccourci", lambda: self._edit_hotkey(None)))
        self.keys_list = self._scroll(page)
        self._render_keys()

    def _render_keys(self):
        for w in self.keys_list.winfo_children():
            w.destroy()
        items = self.cfg["hotkeys"]
        if not items:
            self._empty(self.keys_list, "Aucun raccourci pour l'instant.", "keys")
        for i, h in enumerate(items):
            a = h["action"]
            self._row(self.keys_list, h.get("enabled", True), pretty(h["combo"]), describe_action(a),
                      lambda v, h=h: self._set(h, "enabled", v),
                      lambda i=i: self._edit_hotkey(i),
                      lambda i=i: self._delete("hotkeys", i, self._render_keys),
                      icon_path=a.get("value") if a.get("type") == "launch" else None, fallback="keys")

    def _edit_hotkey(self, index):
        items = self.cfg["hotkeys"]

        def done(h):
            if index is None:
                items.append(h)
            else:
                items[index] = h
            self.save()
            self._render_keys()
        HotkeyDialog(self, items[index] if index is not None else None, done)

    # ---------- Activité ----------
    def _page_log(self, page):
        self._head(page, "Activité", "Ce que Reflex a détecté et exécuté récemment.")
        self.log_box = ctk.CTkTextbox(page, fg_color=SURFACE, text_color=TEXT, font=F(), corner_radius=CARD,
                                      border_spacing=14, state="disabled")
        self.log_box.pack(fill="both", expand=True)

    def _refresh_log(self):
        self._log_seen = self.engine.log_version
        lines = [f"{t}   {m}" for t, m in reversed(list(self.engine.logs))]
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.insert("1.0", "\n".join(lines) if lines else "Rien pour l'instant.")
        self.log_box.configure(state="disabled")

    # ---------- Réglages ----------
    def _page_settings(self, page):
        self._head(page, "Réglages", "Comportement de Reflex au quotidien.")
        self.auto_var = ctk.BooleanVar(value=system.get_autostart())
        self.tray_var = ctk.BooleanVar(value=self.cfg.get("close_to_tray", True))
        self.min_var = ctk.BooleanVar(value=self.cfg.get("start_minimized", False))
        card = self._card(page)
        card.pack(fill="x")
        options = (
            ("Démarrer avec Windows", self.auto_var, lambda: system.set_autostart(self.auto_var.get())),
            ("Afficher l'icône dans la zone de notification", self.tray_var,
             lambda: (self._set(self.cfg, "close_to_tray", self.tray_var.get()),
                      self._apply_tray_visibility())),
            ("Démarrer réduit", self.min_var, lambda: self._set(self.cfg, "start_minimized", self.min_var.get())))
        for i, (text, var, cmd) in enumerate(options):
            ctk.CTkSwitch(card, text=text, variable=var, command=cmd, progress_color=ACCENT, font=F()).pack(
                anchor="w", padx=18, pady=(16, 16 if i == len(options) - 1 else 0))
            if i < len(options) - 1:
                ctk.CTkFrame(card, height=1, fg_color=LINE).pack(fill="x", padx=18, pady=(16, 0))
        quit_card = self._card(page)
        quit_card.pack(fill="x", pady=(16, 0))
        ctk.CTkLabel(quit_card, text="Fermer la fenêtre laisse Reflex actif en arrière-plan. Pour l'arrêter "
                                     "complètement :", text_color=MUTED, font=F(), wraplength=640,
                     justify="left").pack(anchor="w", padx=18, pady=(16, 10))
        btn(quit_card, "Quitter Reflex", self.quit_app, width=210).pack(anchor="w", padx=18, pady=(0, 16))
        adm = self._card(page)
        adm.pack(fill="x", pady=(16, 0))
        if system.is_admin():
            ctk.CTkLabel(adm, text="Reflex tourne en administrateur : il agit aussi dans les fenêtres lancées "
                                   "en administrateur.", text_color=MUTED, font=F(), wraplength=640,
                         justify="left").pack(anchor="w", padx=18, pady=16)
        else:
            ctk.CTkLabel(adm, text="Sans droits administrateur, Reflex ne voit pas les touches dans les fenêtres "
                                   "lancées en administrateur.", text_color=MUTED, font=F(), wraplength=640,
                         justify="left").pack(anchor="w", padx=18, pady=(16, 10))
            btn(adm, "Relancer en administrateur", self._admin, width=210).pack(anchor="w", padx=18, pady=(0, 16))

    def _admin(self):
        if system.relaunch_as_admin():
            self.quit_app()
