"""Render assets/icon.png (1024x1024): terracotta squircle with a serif italic Greek eta (η)."""
import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QTransform, QColor, QFont, QFontDatabase, QGuiApplication, QImage, QPainter, QPainterPath

app = QGuiApplication(sys.argv[:1] + ["-platform", "offscreen"])
size = 1024
img = QImage(size, size, QImage.Format_ARGB32)
img.fill(Qt.transparent)
p = QPainter(img)
p.setRenderHint(QPainter.Antialiasing)
p.setRenderHint(QPainter.TextAntialiasing)
margin = 100
rect = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
bg = QPainterPath()
bg.addRoundedRect(rect, 185, 185)
p.fillPath(bg, QColor("#D97757"))


families = set(QFontDatabase.families())
family = next((f for f in ("FreeSerif", "Georgia", "Times New Roman", "DejaVu Serif", "Liberation Serif", "Noto Serif")
               if f in families), "serif")
font = QFont(family)
font.setItalic(True)
font.setPixelSize(720)
glyph = QPainterPath()
glyph.addText(0, 0, font, "η")
box = glyph.boundingRect()
k = 560 / box.height()  # fill the squircle like the other apps' letters
glyph = QTransform.fromScale(k, k).map(glyph)
box = glyph.boundingRect()
# centre the glyph optically inside the squircle
glyph.translate(size / 2 - box.center().x(), size / 2 - box.center().y())
p.fillPath(glyph, QColor("#FFFFFF"))
p.end()
out = Path(__file__).resolve().parent.parent / "assets" / "icon.png"
img.save(str(out))
print(out, family)
