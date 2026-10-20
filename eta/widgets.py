"""Procedural pictures (no assets to license): pixel heads for accounts, block-style icons for projects and
instances, a blocky landscape banner for the home page. Deterministic per name."""
import hashlib
import random
from functools import lru_cache

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPixmap

from . import theme

SKINS = ["#F2C6A0", "#E0AC84", "#C68863", "#A0694A", "#7A4E36", "#F6D5B8"]
HAIR = ["#3A2618", "#5A3A22", "#8B5A2B", "#D9A441", "#1F1F1F", "#B5482E", "#E9E2D0", "#6B4A7A"]
EYES = ["#3B6A8F", "#4E7A50", "#5A3A22", "#6B4A7A", "#2F4F6B"]
SHIRT = ["#5DAFC4", "#D97757", "#7BA05B", "#9B7BC4", "#E8B23A", "#5B8CC4", "#D6584B"]


def _rng(text):
    return random.Random(int(hashlib.sha1((text or "?").encode("utf-8")).hexdigest()[:12], 16))


def font(px, bold=False, serif=False, italic=False):
    f = QFont(theme.SERIF.split(",")[0].strip('" ')) if serif else QFont()
    f.setPixelSize(px)
    f.setBold(bold)
    f.setItalic(italic)
    return f


@lru_cache(maxsize=128)
def face_grid(name):
    """8×8 colours of a Minecraft-like face, derived from the nickname."""
    rng = _rng(name)
    skin, hair, eye = QColor(rng.choice(SKINS)), QColor(rng.choice(HAIR)), QColor(rng.choice(EYES))
    grid = [[skin for _ in range(8)] for _ in range(8)]
    fringe = rng.choice([1, 2, 2, 3])
    for y in range(fringe):
        for x in range(8):
            grid[y][x] = hair
    if rng.random() < 0.6:   # side hair
        for y in range(fringe, fringe + rng.randint(1, 3)):
            grid[y][0] = grid[y][7] = hair
    ey = fringe + 1 if fringe < 3 else 4
    ey = min(ey + 1, 4)
    for x in (1, 5):
        grid[ey][x] = QColor("#FFFFFF")
        grid[ey][x + 1] = eye
    nose = skin.darker(118)
    grid[ey + 1][3] = grid[ey + 1][4] = nose
    mouth = QColor("#7A3B2E") if rng.random() < 0.7 else skin.darker(140)
    for x in (3, 4) if rng.random() < 0.5 else (2, 3, 4, 5):
        grid[min(7, ey + 2)][x] = mouth
    if rng.random() < 0.3:   # beard / shading
        for x in range(1, 7):
            grid[7][x] = hair
    return grid


def pixel_head(name, size=48, radius=8):
    pix = QPixmap(size * 2, size * 2)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, size * 2, size * 2), radius * 2, radius * 2)
    p.setClipPath(clip)
    cell = size * 2 / 8
    for y, row in enumerate(face_grid(name)):
        for x, c in enumerate(row):
            p.fillRect(QRectF(x * cell, y * cell, cell + 0.6, cell + 0.6), c)
    p.end()
    pix.setDevicePixelRatio(2)
    return pix


@lru_cache(maxsize=256)
def block_icon(seed, size=56):
    """A 6×6 'block' pattern in two related colours with a soft bevel — icon for projects / instances."""
    rng = _rng(seed)
    palette = [("#D97757", "#C6613F"), ("#5B8CC4", "#3B6A8F"), ("#7BA05B", "#4E7A50"), ("#9B7BC4", "#6B4A7A"),
               ("#E8B23A", "#C08A2A"), ("#5DAFC4", "#3B8A9F"), ("#D97BA6", "#B5647A"), ("#8B6B4A", "#5E4632")]
    a, b = palette[rng.randrange(len(palette))]
    pix = QPixmap(size * 2, size * 2)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, size * 2, size * 2), size * 0.42, size * 0.42)
    p.setClipPath(clip)
    n = 6
    cell = size * 2 / n
    ca, cb = QColor(a), QColor(b)
    for y in range(n):
        for x in range(n):
            c = ca if rng.random() < 0.55 else cb
            c = c.lighter(100 + rng.randint(-8, 14))
            p.fillRect(QRectF(x * cell, y * cell, cell + 0.6, cell + 0.6), c)
    g = QLinearGradient(0, 0, 0, size * 2)
    g.setColorAt(0, QColor(255, 255, 255, 46))
    g.setColorAt(1, QColor(0, 0, 0, 40))
    p.fillRect(QRectF(0, 0, size * 2, size * 2), g)
    p.setClipping(False)
    letter = (seed or "?").strip()[:1].upper()
    p.setFont(font(int(size * 0.9), serif=True))
    p.setPen(QColor(0, 0, 0, 60))
    p.drawText(QRectF(2, 4, size * 2, size * 2), Qt.AlignCenter, letter)
    p.setPen(QColor("#FFFFFF"))
    p.drawText(QRectF(0, 0, size * 2, size * 2), Qt.AlignCenter, letter)
    p.end()
    pix.setDevicePixelRatio(2)
    return pix


def paint_banner(p, rect, seed, dark=False):
    """Blocky landscape: sky, sun, terraced hills of square 'blocks', a few trees."""
    rng = _rng(seed)
    r = QRectF(rect)
    skies = [("#F3D2B3", "#E58F6B"), ("#A8D4DE", "#5DAFC4"), ("#F6E3C6", "#E9B98C"), ("#C9C1E6", "#9B7BC4"),
             ("#CFE0C8", "#8DB08A")]
    top, bottom = skies[rng.randrange(len(skies))]
    if dark:
        top, bottom = "#1F2438", "#3B4A6B"
    g = QLinearGradient(r.topLeft(), r.bottomLeft())
    g.setColorAt(0, QColor(top))
    g.setColorAt(1, QColor(bottom))
    p.fillRect(r, g)
    block = max(12.0, r.height() / 14)
    sx = r.x() + r.width() * rng.uniform(0.55, 0.85)
    p.fillRect(QRectF(sx, r.y() + block * 2, block * 2, block * 2), QColor("#FFF4E0" if not dark else "#F6EBD5"))
    layers = [("#7BA05B", "#5B4632"), ("#5E8A48", "#4A3828"), ("#4E7A50", "#3A2C20")]
    for li, (grass, dirt) in enumerate(layers):
        base = r.bottom() - block * (6 - li * 2)
        h = rng.randint(0, 3)
        x = r.x()
        while x < r.right():
            h = max(0, min(5, h + rng.choice([-1, 0, 0, 1])))
            top_y = base - h * block
            p.fillRect(QRectF(x, top_y, block + 0.5, block), QColor(grass).lighter(100 + rng.randint(-6, 8)))
            p.fillRect(QRectF(x, top_y + block, block + 0.5, r.bottom() - top_y - block + 1),
                       QColor(dirt).lighter(100 + rng.randint(-6, 6)))
            if li == 2 and rng.random() < 0.08:
                tx = x
                p.fillRect(QRectF(tx, top_y - block * 2, block, block * 2), QColor("#6B4A2E"))
                p.fillRect(QRectF(tx - block, top_y - block * 4, block * 3, block * 2), QColor("#3E6B3A"))
            x += block
    shade = QLinearGradient(r.topLeft(), r.bottomLeft())
    shade.setColorAt(0.45, QColor(0, 0, 0, 0))
    shade.setColorAt(1, QColor(0, 0, 0, 120))
    p.fillRect(r, shade)
