import os

from PIL import Image, ImageDraw

import config


def make_icon(size=256):
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    # Fond : dégradé vertical dans un carré arrondi
    grad = Image.new("RGBA", (s, s))
    top, bottom = (46, 55, 82), (20, 24, 34)
    gd = ImageDraw.Draw(grad)
    for y in range(s):
        t = y / (s - 1)
        gd.line([(0, y), (s, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=255)
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)
    # Touche de clavier
    m = int(s * 0.2)
    d.rounded_rectangle([m, m, s - m, s - m * 0.85], radius=int(s * 0.12), fill=(232, 235, 243, 255))
    d.rounded_rectangle([m, s - m * 1.25, s - m, s - m * 0.85], radius=int(s * 0.06), fill=(190, 196, 214, 255))

    # Éclair
    x0, y0 = m, m
    w = h = s - 2 * m
    pts = [(0.58, 0.10), (0.26, 0.54), (0.46, 0.54), (0.38, 0.88), (0.72, 0.42), (0.52, 0.42)]
    d.polygon([(x0 + px * w, y0 + py * h * 0.95) for px, py in pts], fill=(255, 194, 71, 255))

    return img.resize((size, size), Image.LANCZOS)


def glyph(name, color, size=48):
    """Petits pictogrammes de navigation dessinés au vol."""
    S = size * 8
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = color
    w = int(S * 0.085)
    P = lambda x, y: (x * S, y * S)
    if name == "apps":
        for x0, y0 in ((0.14, 0.14), (0.54, 0.14), (0.14, 0.54), (0.54, 0.54)):
            d.rounded_rectangle([*P(x0, y0), *P(x0 + 0.32, y0 + 0.32)], radius=int(S * 0.08), fill=c)
    elif name == "win":
        for x0, y0 in ((0.12, 0.12), (0.53, 0.12), (0.12, 0.53), (0.53, 0.53)):
            d.rounded_rectangle([*P(x0, y0), *P(x0 + 0.35, y0 + 0.35)], radius=int(S * 0.03), fill=c)
    elif name == "keys":
        d.rounded_rectangle([*P(0.07, 0.24), *P(0.93, 0.76)], radius=int(S * 0.1), outline=c, width=w)
        for i in range(4):
            x = 0.2 + i * 0.16
            d.rounded_rectangle([*P(x, 0.38), *P(x + 0.08, 0.46)], radius=int(S * 0.02), fill=c)
        d.rounded_rectangle([*P(0.28, 0.56), *P(0.72, 0.64)], radius=int(S * 0.02), fill=c)
    elif name == "log":
        pts = [(0.07, 0.55), (0.3, 0.55), (0.4, 0.2), (0.56, 0.82), (0.67, 0.42), (0.76, 0.55), (0.93, 0.55)]
        d.line([P(*p) for p in pts], fill=c, width=w, joint="curve")
    elif name == "settings":
        for y, kx in ((0.27, 0.34), (0.5, 0.66), (0.73, 0.44)):
            d.line([P(0.1, y), P(0.9, y)], fill=c, width=int(w * 0.8))
            r = S * 0.1
            cx, cy = kx * S, y * S
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)
    return img.resize((size, size), Image.LANCZOS)


def ensure_ico():
    """Régénère l'icône à chaque lancement : un ancien fichier en cache ne peut plus
    garder une ancienne couleur (c'était la cause de l'éclair bleu)."""
    folder = config.config_dir()
    for old in ("reflex_v2.ico", "reflex_v3.ico"):
        try:
            os.remove(os.path.join(folder, old))
        except OSError:
            pass
    path = os.path.join(folder, "reflex_v4.ico")
    try:
        make_icon(256).save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    except OSError:
        pass
    return path


if __name__ == "__main__":
    make_icon(256).save("reflex.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    make_icon(256).save("reflex.png")
    print("reflex.ico et reflex.png créés")
