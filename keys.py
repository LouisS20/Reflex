"""Noms de touches, analyse et affichage des combinaisons (aucune dépendance Windows)."""

MODS = ("ctrl", "alt", "shift", "win")

VK = {
    "ctrl": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B,
    "space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B, "backspace": 0x08,
    "delete": 0x2E, "insert": 0x2D, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "capslock": 0x14, "printscreen": 0x2C, "pause": 0x13, "scrolllock": 0x91, "numlock": 0x90,
    "volumeup": 0xAF, "volumedown": 0xAE, "volumemute": 0xAD,
    "playpause": 0xB3, "nexttrack": 0xB0, "prevtrack": 0xB1, "stop": 0xB2,
    "mbutton": 0x04, "xbutton1": 0x05, "xbutton2": 0x06,
    ",": 0xBC, ".": 0xBE, ";": 0xBA, "/": 0xBF, "`": 0xC0, "[": 0xDB,
    "\\": 0xDC, "]": 0xDD, "'": 0xDE, "-": 0xBD, "=": 0xBB,
}
for _c in "abcdefghijklmnopqrstuvwxyz":
    VK[_c] = ord(_c.upper())
for _d in "0123456789":
    VK[_d] = ord(_d)
for _i in range(1, 25):
    VK[f"f{_i}"] = 0x6F + _i
for _i in range(10):
    VK[f"num{_i}"] = 0x60 + _i

ALIASES = {
    "control": "ctrl", "ctl": "ctrl", "windows": "win", "super": "win", "cmd": "win",
    "option": "alt", "escape": "esc", "return": "enter", "del": "delete", "ins": "insert",
    "pgup": "pageup", "pgdn": "pagedown", "spacebar": "space", "caps": "capslock",
    "plus": "=",
}

MOD_OF_VK = {
    0xA0: "shift", 0xA1: "shift", 0x10: "shift",
    0xA2: "ctrl", 0xA3: "ctrl", 0x11: "ctrl",
    0xA4: "alt", 0xA5: "alt", 0x12: "alt",
    0x5B: "win", 0x5C: "win",
}

# Touches qui demandent le drapeau « étendu » à l'envoi
EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x5B, 0x5C, 0x90}

VK_NAME = {}
for _n, _v in VK.items():
    if _n not in MODS and _v not in VK_NAME:
        VK_NAME[_v] = _n

DISPLAY = {
    "ctrl": "Ctrl", "alt": "Alt", "shift": "Maj", "win": "Win", "space": "Espace",
    "enter": "Entrée", "esc": "Échap", "backspace": "Retour arrière", "delete": "Suppr",
    "insert": "Inser", "pageup": "Page haut", "pagedown": "Page bas", "capslock": "Verr. Maj",
    "printscreen": "Impr. écran", "volumeup": "Volume +", "volumedown": "Volume −",
    "volumemute": "Muet", "playpause": "Lecture/Pause", "nexttrack": "Piste suivante",
    "prevtrack": "Piste précédente", "mbutton": "Clic molette",
    "xbutton1": "Bouton souris 4", "xbutton2": "Bouton souris 5",
    "up": "Haut", "down": "Bas", "left": "Gauche", "right": "Droite", "tab": "Tab",
}


def parse(text):
    """'ctrl+alt+t' -> (['ctrl', 'alt'], 't'). Lève ValueError si invalide."""
    parts = [p for p in (text or "").lower().replace(" ", "").split("+") if p]
    if not parts:
        raise ValueError("Combinaison vide")
    mods, key = [], None
    for p in parts:
        p = ALIASES.get(p, p)
        if p in MODS:
            if p not in mods:
                mods.append(p)
        elif p in VK or (p.startswith("vk") and p[2:].isdigit()):
            if key is not None:
                raise ValueError("Une seule touche non modificatrice par combinaison")
            key = p
        else:
            raise ValueError(f"Touche inconnue : {p}")
    return mods, key


def vk_of(name):
    return VK[name] if name in VK else int(name[2:])


def combo_key(text):
    """Clé de règle : (frozenset(modificateurs), code de touche)."""
    mods, key = parse(text)
    if key is None:
        raise ValueError("Ajoute une touche en plus des modificateurs")
    return frozenset(mods), vk_of(key)


def build_combo(mods, key_name):
    ordered = [m for m in MODS if m in mods]
    return "+".join(ordered + [key_name])


def pretty(text):
    try:
        mods, key = parse(text)
    except ValueError:
        return text or ""
    names = list(mods) + ([key] if key else [])
    out = []
    for n in names:
        out.append(DISPLAY.get(n, n.upper() if len(n) == 1 else n.capitalize()))
    return " + ".join(out)


def describe_action(action):
    t = (action or {}).get("type", "none")
    v = ((action or {}).get("value") or "").strip()
    if t == "start":
        return "Ouvrir le menu Démarrer"
    if t == "keys":
        return f"Envoyer {pretty(v)}" if v else "Envoyer des touches"
    if t == "launch":
        return f"Lancer {v}" if v else "Lancer un programme"
    return "Ne rien faire"
