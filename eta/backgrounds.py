"""Window backgrounds (shared with Альфа): gradients (theme.BACKGROUNDS), solid colours, painted picture scenes ("scene:<name>") and the
user's own pictures (copied into <data>/backgrounds so the launcher keeps its picture when the original moves).
Scaled (and blurred, for the glass look) pictures are cached per size."""
import hashlib
import math
import random
import shutil
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient

from . import theme
from .paths import data_dir

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
SCENES = {
    "mountains": "Горы", "sea": "Море", "dunes": "Дюны", "night": "Ночь", "forest": "Лес", "bokeh": "Огни",
    "sakura": "Сакура", "aurora": "Сияние",
}
SCENE_W, SCENE_H = 1920, 1200


def folder():
    p = data_dir() / "backgrounds"
    p.mkdir(parents=True, exist_ok=True)
    return p


def is_picture(bg):
    bg = str(bg or "")
    return bg.startswith("scene:") or (bool(bg) and not bg.startswith("#") and bg not in theme.BACKGROUNDS
                                       and Path(bg).suffix.lower() in IMAGE_EXT)


def import_image(path):
    """Copy a picture into the backgrounds folder (deduplicated by content); returns the new path."""
    src = Path(path)
    data = src.read_bytes()
    name = hashlib.sha1(data).hexdigest()[:16] + src.suffix.lower()
    dst = folder() / name
    if not dst.exists():
        shutil.copyfile(src, dst)
    return str(dst)


def gallery():
    """The user's pictures, newest first."""
    try:
        files = [p for p in folder().iterdir() if p.suffix.lower() in IMAGE_EXT]
    except OSError:
        return []
    return [str(p) for p in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)]


def remove_from_gallery(path):
    try:
        if Path(path).parent == folder():
            Path(path).unlink()
    except OSError:
        pass
    _source.cache_clear()
    _SCALED.clear()


# ---- painted scenes

def _ridge(p, rng, y0, amp, color, w=SCENE_W, h=SCENE_H, step=24, rough=0.55):
    path = QPainterPath(QPointF(0, h))
    y = y0
    pts = []
    for x in range(0, w + step, step):
        y += rng.uniform(-amp, amp) * rough + (y0 - y) * 0.08
        pts.append(QPointF(x, y))
    path.lineTo(pts[0])
    for pt in pts:
        path.lineTo(pt)
    path.lineTo(QPointF(w, h))
    path.closeSubpath()
    p.fillPath(path, QColor(color))


def _sky(p, top, bottom, w=SCENE_W, h=SCENE_H):
    g = QLinearGradient(0, 0, 0, h)
    g.setColorAt(0, QColor(top))
    g.setColorAt(1, QColor(bottom))
    p.fillRect(QRect(0, 0, w, h), g)


def _glow(p, x, y, r, color, alpha=255):
    c = QColor(color)
    g = QRadialGradient(QPointF(x, y), r)
    c.setAlpha(alpha)
    g.setColorAt(0, c)
    c2 = QColor(color)
    c2.setAlpha(0)
    g.setColorAt(1, c2)
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawEllipse(QPointF(x, y), r, r)


@lru_cache(maxsize=16)
def scene(name):
    img = QImage(SCENE_W, SCENE_H, QImage.Format_RGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    rng = random.Random(sum(map(ord, name)))  # the same picture every run
    W, H = SCENE_W, SCENE_H
    if name == "mountains":
        _sky(p, "#F3D2B3", "#E58F6B")
        _glow(p, W * 0.68, H * 0.36, 320, "#FFF1DC", 200)
        p.setBrush(QColor("#FFF4E6"))
        p.drawEllipse(QPointF(W * 0.68, H * 0.36), 70, 70)
        for i, col in enumerate(("#D9876A", "#BF6A55", "#9C5248", "#6E3E3E", "#4A2C33")):
            _ridge(p, rng, H * (0.48 + i * 0.09), 60 - i * 6, col)
    elif name == "sea":
        _sky(p, "#9FC3DA", "#F2C9A8")
        _glow(p, W * 0.3, H * 0.5, 260, "#FFE8CF", 220)
        for i in range(9):
            y = H * 0.55 + i * 62
            path = QPainterPath(QPointF(0, H))
            path.lineTo(0, y)
            phase = rng.uniform(0, 6.28)
            for x in range(0, W + 20, 20):
                path.lineTo(x, y + math.sin(x / (140 + i * 20) + phase) * (10 + i * 3))
            path.lineTo(W, H)
            c = QColor("#5B8CC4").darker(100 + i * 12)
            c.setAlpha(230)
            p.fillPath(path, c)
    elif name == "dunes":
        _sky(p, "#F6E3C6", "#E9B98C")
        _glow(p, W * 0.78, H * 0.28, 220, "#FFF6E8", 230)
        for i, col in enumerate(("#E7B07E", "#D99A68", "#C98455", "#B06E45", "#94593A")):
            y = H * (0.5 + i * 0.1)
            path = QPainterPath(QPointF(0, H))
            path.lineTo(0, y)
            a, f, ph = rng.uniform(30, 70), rng.uniform(260, 520), rng.uniform(0, 6.28)
            for x in range(0, W + 16, 16):
                path.lineTo(x, y + math.sin(x / f + ph) * a)
            path.lineTo(W, H)
            p.fillPath(path, QColor(col))
    elif name == "night":
        _sky(p, "#141B33", "#3B4A6B")
        for _ in range(420):
            x, y, r = rng.uniform(0, W), rng.uniform(0, H * 0.75), rng.uniform(0.6, 2.4)
            c = QColor("#FFFFFF")
            c.setAlpha(int(rng.uniform(90, 255)))
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawEllipse(QPointF(x, y), r, r)
        _glow(p, W * 0.2, H * 0.22, 200, "#F6E7C8", 120)
        p.setBrush(QColor("#F6EBD5"))
        p.drawEllipse(QPointF(W * 0.2, H * 0.22), 60, 60)
        _ridge(p, rng, H * 0.78, 30, "#1E2440")
        _ridge(p, rng, H * 0.86, 24, "#121629")
    elif name == "forest":
        _sky(p, "#CFE0C8", "#8DB08A")
        for layer, col in enumerate(("#7FA07A", "#5F8660", "#456B4B", "#2F4F38")):
            base = H * (0.55 + layer * 0.12)
            x = rng.uniform(-60, 0)
            while x < W + 60:
                hgt = rng.uniform(160, 300) * (1 + layer * 0.25)
                wd = hgt * rng.uniform(0.3, 0.42)
                tri = QPainterPath(QPointF(x, base - hgt))
                tri.lineTo(x + wd / 2, base)
                tri.lineTo(x - wd / 2, base)
                tri.closeSubpath()
                p.fillPath(tri, QColor(col))
                x += wd * rng.uniform(0.45, 0.8)
            p.fillRect(QRectF(0, base - 2, W, H - base + 2), QColor(col))
            mist = QLinearGradient(0, base - 120, 0, base)
            mist.setColorAt(0, QColor(255, 255, 255, 0))
            mist.setColorAt(1, QColor(255, 255, 255, 40))
            p.fillRect(QRectF(0, base - 120, W, 120), mist)
    elif name == "bokeh":
        _sky(p, "#2B1E2F", "#6B4A7A")
        for _ in range(70):
            col = rng.choice(["#D97757", "#E8B23A", "#D97BA6", "#9B7BC4", "#5DAFC4", "#FFFFFF"])
            _glow(p, rng.uniform(0, W), rng.uniform(0, H), rng.uniform(30, 150), col, int(rng.uniform(40, 120)))
    elif name == "sakura":
        _sky(p, "#FBE4EA", "#F2B8C8")
        pen = QPen(QColor("#5A3A3A"), 18, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        branch = QPainterPath(QPointF(-40, H * 0.15))
        branch.cubicTo(W * 0.25, H * 0.05, W * 0.4, H * 0.3, W * 0.62, H * 0.22)
        p.drawPath(branch)
        pen.setWidth(9)
        p.setPen(pen)
        for t in (0.3, 0.5, 0.7):
            pt = branch.pointAtPercent(t)
            p.drawLine(pt, pt + QPointF(rng.uniform(60, 140), rng.uniform(50, 130)))
        p.setPen(Qt.NoPen)
        for _ in range(260):
            t = rng.uniform(0.05, 1.0)
            pt = branch.pointAtPercent(t) + QPointF(rng.gauss(0, 70), rng.gauss(30, 60))
            c = QColor(rng.choice(["#F7A8BE", "#F9C5D3", "#EE8FAA", "#FFFFFF"]))
            c.setAlpha(int(rng.uniform(170, 255)))
            p.setBrush(c)
            p.drawEllipse(pt, rng.uniform(6, 15), rng.uniform(5, 11))
        for _ in range(60):
            c = QColor("#F7A8BE")
            c.setAlpha(int(rng.uniform(90, 200)))
            p.setBrush(c)
            p.drawEllipse(QPointF(rng.uniform(0, W), rng.uniform(H * 0.3, H)), rng.uniform(4, 9), rng.uniform(3, 6))
    elif name == "aurora":
        _sky(p, "#0B1520", "#1C3442")
        p.setPen(Qt.NoPen)
        for _ in range(220):
            c = QColor("#FFFFFF")
            c.setAlpha(int(rng.uniform(60, 200)))
            p.setBrush(c)
            p.drawEllipse(QPointF(rng.uniform(0, W), rng.uniform(0, H * 0.75)), 1.3, 1.3)
        # soft curtains: thin vertical strokes fading in and out along two wavy ribbons
        for col, base, amp, f1, f2, length in (("#4FD1A5", 0.20, 90, 260, 97, 320), ("#7FA8E0", 0.30, 60, 180, 71, 240),
                                               ("#B08AD8", 0.14, 50, 330, 123, 200)):
            for x in range(0, W, 3):
                top = H * base + math.sin(x / f1) * amp + math.sin(x / f2) * 28
                ln = length * (0.75 + 0.25 * math.sin(x / 140 + base * 10))
                g = QLinearGradient(0, top, 0, top + ln)
                c0, c1, c2 = QColor(col), QColor(col), QColor(col)
                c0.setAlpha(0)
                c1.setAlpha(70)
                c2.setAlpha(0)
                g.setColorAt(0, c0)
                g.setColorAt(0.7, c1)
                g.setColorAt(1, c2)
                p.fillRect(QRectF(x, top, 3, ln), g)
        _ridge(p, rng, H * 0.8, 26, "#08111A")
    p.end()
    return QPixmap.fromImage(img)


@lru_cache(maxsize=24)
def _source(bg):
    if str(bg).startswith("scene:"):
        return scene(bg[6:])
    pix = QPixmap(bg)
    return pix


_SCALED = OrderedDict()


def _scaled(bg, w, h):
    key = (bg, w, h)
    if key in _SCALED:
        _SCALED.move_to_end(key)
        return _SCALED[key]
    src = _source(bg)
    if src.isNull():
        return src
    sc = src.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    sc = sc.copy((sc.width() - w) // 2, (sc.height() - h) // 2, w, h)
    _SCALED[key] = sc
    while len(_SCALED) > 12:
        _SCALED.popitem(last=False)
    return sc


def paint(p, rect, bg, dim=0):
    """Paint a board background into rect; dim = 0..80 % dark veil (keeps lists readable on busy photos)."""
    rect = QRect(rect)
    if is_picture(bg):
        dpr = p.device().devicePixelRatioF() if hasattr(p.device(), "devicePixelRatioF") else 1.0
        sc = _scaled(bg, max(1, int(rect.width() * dpr)), max(1, int(rect.height() * dpr)))
        if not sc.isNull():
            p.drawPixmap(rect, sc)
            if dim:
                p.fillRect(rect, QColor(0, 0, 0, int(255 * min(80, dim) / 100)))
            return
        bg = "graphite"
    a, b = theme.BACKGROUNDS.get(bg, (bg, bg)) if bg else theme.BACKGROUNDS["terracotta"]
    if not str(a).startswith("#"):
        a, b = theme.BACKGROUNDS["terracotta"]
    g = QLinearGradient(QPointF(rect.topLeft()), QPointF(rect.bottomRight()))
    g.setColorAt(0, QColor(a))
    g.setColorAt(1, QColor(b))
    p.fillRect(rect, g)
    if dim:
        p.fillRect(rect, QColor(0, 0, 0, int(255 * min(80, dim) / 100)))


@lru_cache(maxsize=64)
def is_light(bg):
    if is_picture(bg):
        src = _source(bg)
        if src.isNull():
            return False
        small = src.toImage().scaled(16, 16)
        total = sum(QColor(small.pixel(x, y)).lightness() for x in range(16) for y in range(16))
        return total / 256 > 170
    a, _ = theme.BACKGROUNDS.get(bg, (bg, bg)) if bg in theme.BACKGROUNDS or str(bg).startswith("#") else ("#333", "")
    return QColor(a).lightness() > 170


def swatch(bg, w=72, h=46, selected=False):
    """Rounded preview of any background (gradient, colour, scene or picture)."""
    pix = QPixmap(w * 2, h * 2)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(2, 2, w * 2 - 4, h * 2 - 4), 8, 8)
    p.setClipPath(path)
    if bg in theme.LABEL_COLORS:
        bg = theme.label_hex(bg)
    paint(p, QRect(0, 0, w * 2, h * 2), bg)
    p.setClipping(False)
    if selected:
        p.setPen(QPen(QColor("#141413"), 5))
        p.drawPath(path)
        p.setPen(QPen(QColor("#FFFFFF"), 2))
        p.drawPath(path)
    p.end()
    pix.setDevicePixelRatio(2)
    return pix


_BLURRED = OrderedDict()


def blurred(bg, w, h, radius):
    """The background scaled to w×h and softly blurred (down- and up-scaling twice) — the glass backdrop."""
    key = (bg, w, h, radius)
    if key in _BLURRED:
        _BLURRED.move_to_end(key)
        return _BLURRED[key]
    pix = QPixmap(w, h)
    p = QPainter(pix)
    paint(p, QRect(0, 0, w, h), bg)
    p.end()
    if radius > 0:
        img = pix.toImage()
        k = max(2, int(radius / 2))
        for _ in range(2):
            small = img.scaled(max(1, w // k), max(1, h // k), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            img = small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        pix = QPixmap.fromImage(img)
    _BLURRED[key] = pix
    while len(_BLURRED) > 6:
        _BLURRED.popitem(last=False)
    return pix
