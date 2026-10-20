"""Line icons drawn with QPainter on a 24-unit grid (ink strokes + terracotta details), cached
per colour. Same drawing style as Мю."""
import math
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap


@lru_cache(maxsize=512)
def pixmap(name, ink="#141413", accent="#D97757", size=40, rec="#D64545"):
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 24.0
    P = lambda x, y: QPointF(x * s, y * s)  # noqa: E731
    pen = QPen(QColor(ink), 1.6 * s, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    acc = QPen(QColor(accent), 1.6 * s, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    dash = QPen(QColor(ink), 1.4 * s, Qt.DashLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    def poly(*pts, close=False, fill=None, pen_=None):
        path = QPainterPath(P(*pts[0]))
        for q in pts[1:]:
            path.lineTo(P(*q))
        if close:
            path.closeSubpath()
        if fill:
            p.fillPath(path, QColor(fill))
        p.setPen(pen if pen_ is None else pen_)
        p.drawPath(path)
        p.setPen(pen)

    def curve(*pts, pen_=None):
        path = QPainterPath(P(*pts[0]))
        for i in range(1, len(pts) - 1, 2):
            path.quadTo(P(*pts[i]), P(*pts[i + 1]))
        p.setPen(pen if pen_ is None else pen_)
        p.drawPath(path)
        p.setPen(pen)

    def rect(x, y, w, h, r=0, fill=None, pen_=None):
        p.setBrush(QColor(fill) if fill else Qt.NoBrush)
        p.setPen(pen if pen_ is None else pen_)
        p.drawRoundedRect(QRectF(P(x, y), P(x + w, y + h)), r * s, r * s)
        p.setBrush(Qt.NoBrush)
        p.setPen(pen)

    def circle(x, y, r, fill=None, pen_=None):
        p.setBrush(QColor(fill) if fill else Qt.NoBrush)
        p.setPen(pen if pen_ is None else pen_)
        p.drawEllipse(P(x, y), r * s, r * s)
        p.setBrush(Qt.NoBrush)
        p.setPen(pen)

    def text(t, x, y, w, h, px, italic=False, color=None):
        f = QFont("Georgia")
        f.setPixelSize(max(1, int(px * s)))
        f.setItalic(italic)
        p.setFont(f)
        p.setPen(QColor(color or ink))
        p.drawText(QRectF(P(x, y), P(x + w, y + h)), Qt.AlignCenter, t)
        p.setPen(pen)

    def corners(x0, y0, x1, y1, L=4, pen_=None):
        for a, b, c in (((x0, y0 + L), (x0, y0), (x0 + L, y0)), ((x1 - L, y0), (x1, y0), (x1, y0 + L)),
                        ((x1, y1 - L), (x1, y1), (x1 - L, y1)), ((x0 + L, y1), (x0, y1), (x0, y1 - L))):
            poly(a, b, c, pen_=pen_)

    if name == "home":
        poly((4, 11), (12, 4), (20, 11))
        poly((6, 9.5), (6, 20), (18, 20), (18, 9.5))
        rect(10, 14, 4, 6, 1, pen_=acc)
    elif name == "board":
        rect(3, 4, 18, 16, 2.5)
        rect(6, 7, 4, 10, 1, fill=accent, pen_=acc)
        rect(11.5, 7, 4, 6, 1)
    elif name == "template":
        rect(3, 4, 18, 16, 2.5, pen_=dash)
        rect(6, 7, 4, 10, 1, pen_=acc)
        rect(11.5, 7, 4, 6, 1)
    elif name == "settings":
        for k in range(8):
            a = k * math.pi / 4
            poly((12 + 6.5 * math.cos(a), 12 + 6.5 * math.sin(a)), (12 + 9 * math.cos(a), 12 + 9 * math.sin(a)))
        circle(12, 12, 6)
        circle(12, 12, 2.5, pen_=acc)
    elif name == "plus":
        poly((12, 5), (12, 19))
        poly((5, 12), (19, 12))
    elif name == "close":
        poly((6, 6), (18, 18))
        poly((18, 6), (6, 18))
    elif name == "check":
        poly((5, 12.5), (10, 17), (19, 7), pen_=acc)
    elif name == "star":
        poly((12, 3.5), (14.5, 9), (20.5, 9.5), (16, 13.5), (17.5, 19.5), (12, 16.3), (6.5, 19.5), (8, 13.5),
             (3.5, 9.5), (9.5, 9), close=True)
    elif name == "star_on":
        poly((12, 3.5), (14.5, 9), (20.5, 9.5), (16, 13.5), (17.5, 19.5), (12, 16.3), (6.5, 19.5), (8, 13.5),
             (3.5, 9.5), (9.5, 9), close=True, fill="#E8B23A", pen_=QPen(QColor("#E8B23A"), 1.6 * s))
    elif name == "label":
        poly((3, 12), (8, 5), (21, 5), (21, 19), (8, 19), close=True)
        circle(9, 12, 1.6, fill=accent, pen_=acc)
    elif name == "member":
        circle(12, 8.5, 3.8)
        curve((4.5, 20), (5, 13.5), (12, 13.5), (19, 13.5), (19.5, 20), pen_=acc)
    elif name == "members":
        circle(9, 9, 3.2)
        curve((3, 19), (3.5, 13.5), (9, 13.5), (14.5, 13.5), (15, 19))
        circle(16.5, 8, 2.6, pen_=acc)
        curve((17, 12.5), (20.5, 12.8), (21, 17), pen_=acc)
    elif name == "clock":
        circle(12, 12, 8.5)
        poly((12, 7), (12, 12), (15.5, 14), pen_=acc)
    elif name == "calendar":
        rect(3.5, 5, 17, 15, 2)
        poly((3.5, 9.5), (20.5, 9.5))
        poly((8, 3), (8, 6.5))
        poly((16, 3), (16, 6.5))
        rect(7, 12.5, 3, 3, 0.5, fill=accent, pen_=acc)
    elif name == "checklist":
        rect(3.5, 4, 5, 5, 1)
        poly((4.6, 6.4), (5.8, 7.6), (7.8, 5.2), pen_=acc)
        poly((11, 6.5), (20, 6.5))
        rect(3.5, 14, 5, 5, 1)
        poly((11, 16.5), (20, 16.5))
    elif name == "attach":
        curve((15.5, 7), (15.5, 4), (12.5, 4), (9.5, 4), (9.5, 7))
        poly((9.5, 7), (9.5, 16))
        curve((9.5, 16), (9.5, 19.5), (12.5, 19.5), (16, 19.5), (16, 16), pen_=acc)
        poly((16, 16), (16, 9), pen_=acc)
        poly((12.8, 8), (12.8, 15.5))
    elif name == "comment":
        poly((4, 5), (20, 5), (20, 16), (11, 16), (7, 20), (7, 16), (4, 16), close=True)
        poly((8, 9.5), (16, 9.5), pen_=acc)
        poly((8, 12.5), (13, 12.5), pen_=acc)
    elif name == "desc":
        for y, x2 in ((6, 20), (10, 20), (14, 20), (18, 13)):
            poly((4, y), (x2, y), pen_=acc if y == 18 else pen)
    elif name == "cover":
        rect(3.5, 4, 17, 16, 2)
        rect(3.5, 4, 17, 6, 2, fill=accent, pen_=acc)
    elif name == "archive":
        rect(3, 4, 18, 5, 1)
        poly((5, 9), (5, 20), (19, 20), (19, 9))
        poly((10, 13), (14, 13), pen_=acc)
    elif name == "copy":
        rect(4, 7, 11, 13, 2)
        rect(9, 3, 11, 13, 2, pen_=acc)
    elif name == "move":
        poly((4, 12), (19, 12), pen_=acc)
        poly((14, 7), (19, 12), (14, 17), pen_=acc)
        poly((4, 5), (4, 19))
    elif name == "trash":
        poly((4, 7), (20, 7))
        poly((9, 7), (9, 4), (15, 4), (15, 7))
        poly((6, 7), (7, 20), (17, 20), (18, 7))
        poly((10, 11), (10, 17), pen_=acc)
        poly((14, 11), (14, 17), pen_=acc)
    elif name == "filter":
        poly((3.5, 5), (20.5, 5), (14, 12.5), (14, 19), (10, 20.5), (10, 12.5), close=True)
    elif name == "search":
        circle(10.5, 10.5, 6)
        poly((15, 15), (20, 20), pen_=acc)
    elif name == "table":
        rect(3, 5, 18, 14, 2)
        poly((3, 10), (21, 10))
        poly((3, 14.5), (21, 14.5))
        poly((10, 5), (10, 19), pen_=acc)
    elif name == "dashboard":
        rect(4, 12, 3.5, 8, 0.8, fill=accent, pen_=acc)
        rect(10.25, 6, 3.5, 14, 0.8)
        rect(16.5, 9, 3.5, 11, 0.8)
    elif name == "bolt":
        poly((13.5, 2.5), (5.5, 13.5), (11.5, 13.5), (10, 21.5), (18.5, 10), (12.5, 10), close=True, fill=accent,
             pen_=acc)
    elif name == "button":
        rect(3, 7, 18, 10, 5)
        poly((10, 9.5), (15, 12), (10, 14.5), close=True, fill=accent, pen_=acc)
    elif name == "play":
        poly((7, 4), (19, 12), (7, 20), close=True, fill=accent, pen_=acc)
    elif name == "dots":
        for x in (6, 12, 18):
            circle(x, 12, 1.5, fill=ink)
    elif name == "undo":
        curve((8, 9), (19, 8), (19, 14), (19, 19), (10, 19))
        poly((11, 5), (7, 9), (11, 13), pen_=acc)
    elif name == "redo":
        curve((16, 9), (5, 8), (5, 14), (5, 19), (14, 19))
        poly((13, 5), (17, 9), (13, 13), pen_=acc)
    elif name == "field":
        rect(3, 7, 18, 10, 2)
        poly((7, 12), (13, 12), pen_=acc)
        poly((16, 10), (16, 14))
    elif name == "import":
        poly((12, 3), (12, 15), pen_=acc)
        poly((8, 11), (12, 15), (16, 11), pen_=acc)
        poly((5, 13), (5, 20), (19, 20), (19, 13))
    elif name == "export":
        poly((12, 15), (12, 3), pen_=acc)
        poly((8, 7), (12, 3), (16, 7), pen_=acc)
        poly((5, 12), (5, 20), (19, 20), (19, 12))
    elif name == "bell":
        curve((6, 16), (6, 6), (12, 5), (18, 6), (18, 16))
        poly((4.5, 16.5), (19.5, 16.5))
        curve((10, 19), (12, 21.5), (14, 19), pen_=acc)
    elif name == "eye":
        curve((3, 12), (12, 4), (21, 12))
        curve((3, 12), (12, 20), (21, 12))
        circle(12, 12, 3, fill=accent, pen_=acc)
    elif name == "vote":
        poly((7, 11), (7, 20), (4, 20), (4, 11), close=True)
        poly((7, 11), (11, 4), (12.5, 5), (12, 10), (19, 10), (18, 19), (7, 19), pen_=acc)
    elif name == "list":
        rect(4, 3.5, 7, 17, 2)
        rect(13, 3.5, 7, 11, 2, pen_=acc)
    elif name == "cube":
        poly((12, 3), (20, 7.5), (20, 16.5), (12, 21), (4, 16.5), (4, 7.5), close=True)
        poly((4, 7.5), (12, 12), (20, 7.5))
        poly((12, 12), (12, 21), pen_=acc)
    elif name == "download":
        poly((12, 3), (12, 15), pen_=acc)
        poly((7.5, 10.5), (12, 15), (16.5, 10.5), pen_=acc)
        poly((4, 18), (4, 20.5), (20, 20.5), (20, 18))
    elif name == "user":
        rect(5, 3, 14, 14, 2)
        rect(8, 8, 2.5, 2.5, 0.3, fill=ink)
        rect(13.5, 8, 2.5, 2.5, 0.3, fill=ink)
        poly((9, 13.5), (15, 13.5), pen_=acc)
        poly((7, 21), (7, 18.5), (17, 18.5), (17, 21))
    elif name == "folder":
        poly((3, 6), (9, 6), (11, 8), (21, 8), (21, 19), (3, 19), close=True)
        poly((3, 11), (21, 11), pen_=acc)
    elif name == "memory":
        rect(3, 7, 18, 10, 1.5)
        for x in (6.5, 10.5, 14.5):
            rect(x, 9.5, 3, 5, 0.5, pen_=acc)
        for x in (5, 9, 13, 17):
            poly((x, 17), (x, 20))
    elif name == "java":
        curve((6, 11), (6, 19), (12, 19), (18, 19), (18, 11))
        poly((6, 11), (18, 11))
        curve((18, 12.5), (21.5, 12.5), (21, 15), (20.5, 17), (17.5, 16.5))
        curve((10, 8), (8.5, 6), (10, 4), pen_=acc)
        curve((14, 8), (12.5, 6), (14, 4), pen_=acc)
    elif name == "globe":
        circle(12, 12, 8.5)
        p.drawEllipse(QRectF(P(8, 3.5), P(16, 20.5)))
        poly((3.5, 12), (20.5, 12), pen_=acc)
    elif name == "heart":
        path = QPainterPath(P(12, 20))
        path.cubicTo(P(2, 13), P(3, 4), P(12, 8))
        path.cubicTo(P(21, 4), P(22, 13), P(12, 20))
        p.setPen(acc)
        p.drawPath(path)
        p.setPen(pen)
    elif name == "back":
        poly((14, 5), (7, 12), (14, 19))
    elif name == "refresh":
        p.drawArc(QRectF(P(5, 5), P(19, 19)), 60 * 16, 300 * 16)
        poly((15, 3.5), (15.5, 7.5), (19.5, 6), pen_=acc)
    elif name == "news":
        rect(3, 5, 15, 14, 2)
        poly((18, 9), (21, 9), (21, 17), (19.5, 19))
        poly((6, 9), (15, 9), pen_=acc)
        poly((6, 12.5), (15, 12.5))
        poly((6, 15.5), (12, 15.5))
    elif name == "terminal":
        rect(3, 5, 18, 14, 2)
        poly((7, 10), (10, 12.5), (7, 15), pen_=acc)
        poly((12, 15), (16, 15))
    elif name == "logo":
        text("η", 0, -1, 24, 24, 20, italic=True, color=accent)
    else:
        circle(12, 12, 6)
    p.end()
    return pix


def icon(name, ink="#141413", accent="#D97757", size=40):
    return QIcon(pixmap(name, ink, accent, size))

