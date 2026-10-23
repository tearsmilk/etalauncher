"""Эта: loading page, home, modpacks (catalog like Modrinth + own instances), accounts, settings."""
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QRectF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QKeySequence, QPainter, QPainterPath, QShortcut
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame,
                               QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow, QMenu,
                               QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QRadioButton, QScrollArea,
                               QSizePolicy, QSlider, QSpinBox,
                               QStackedWidget, QTabWidget, QTextBrowser, QToolButton, QVBoxLayout, QWidget)

from . import APP_NAME, LOGO, __version__, backgrounds, discord_rpc, icons, launch, mcru, net, theme
from .accounts import AccountStore, offline_uuid, validate
from .catalog import CATEGORIES, LOADER_TAGS, SORTS, SOURCES, DemoProvider, fmt_count
from .instances import LOADERS, MC_VERSIONS, InstanceStore, describe
from .paths import Settings, data_dir, resource_path, system_memory_mb
from .widgets import block_icon, paint_banner, pixel_head

IS_MAC = sys.platform == "darwin"


def label(text, name=None, wrap=False):
    w = QLabel(text)
    if name:
        w.setObjectName(name)
    w.setWordWrap(wrap)
    return w


def ic(name, color=None):
    return icons.icon(name, color or theme.CURRENT["text"])


def clear_layout(lay):
    while lay.count():
        it = lay.takeAt(0)
        if it.widget():
            it.widget().hide()
            it.widget().deleteLater()
        elif it.layout():
            clear_layout(it.layout())


def tag(text, color=None):
    w = QLabel(text)
    w.setObjectName("Tag")
    if color:
        w.setStyleSheet(f"QLabel#Tag {{ color: {theme.label_hex(color)}; border-color: {theme.label_hex(color)}; }}")
    return w


def ago(ts):
    d = max(0, time.time() - ts)
    if d < 3600:
        return "только что"
    if d < 86400:
        return f"{int(d // 3600)} ч назад"
    if d < 86400 * 30:
        return f"{int(d // 86400)} дн. назад"
    if d < 86400 * 365:
        return f"{int(d // (86400 * 30))} мес. назад"
    return f"{int(d // (86400 * 365))} г. назад"


def rounded(pix, size, radius=None):
    """Scale a picture into a size×size rounded square (project / instance icons)."""
    from PySide6.QtGui import QPixmap

    radius = size * 0.22 if radius is None else radius
    out = QPixmap(size * 2, size * 2)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size * 2, size * 2), radius * 2, radius * 2)
    p.setClipPath(path)
    sc = pix.scaled(size * 2, size * 2, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    p.drawPixmap((size * 2 - sc.width()) // 2, (size * 2 - sc.height()) // 2, sc)
    p.end()
    out.setDevicePixelRatio(2)
    return out


def set_icon(win, lbl, url, seed, size, icon_path=None):
    """Block icon now, the real project icon (Modrinth) when it arrives. icon_path overrides all."""
    from PySide6.QtGui import QPixmap
    if icon_path and Path(icon_path).exists():
        pix = QPixmap(icon_path)
        if not pix.isNull():
            lbl.setPixmap(rounded(pix, size))
            return
    lbl.setPixmap(block_icon(seed or "?", size))
    if url and getattr(win, "icons", None) is not None:
        def done(pix, lbl=lbl):
            if not pix.isNull():
                lbl.setPixmap(rounded(pix, size))
        win.icons.get(url, done)


def skin_head(pix, size, radius):
    """The 8×8 face (8,8) with the hat layer (40,8) from a skin texture, pixel-scaled and rounded."""
    from PySide6.QtGui import QPixmap
    if pix.isNull() or pix.width() < 64:
        return None
    cell = pix.width() // 64
    face = pix.copy(8 * cell, 8 * cell, 8 * cell, 8 * cell)
    out = QPixmap(face.size())
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.drawPixmap(0, 0, face)
    p.drawPixmap(0, 0, pix.copy(40 * cell, 8 * cell, 8 * cell, 8 * cell))
    p.end()
    big = out.scaled(size * 2, size * 2, Qt.IgnoreAspectRatio, Qt.FastTransformation)
    res = QPixmap(size * 2, size * 2)
    res.fill(Qt.transparent)
    p = QPainter(res)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, size * 2, size * 2), radius * 2, radius * 2)
    p.setClipPath(clip)
    p.drawPixmap(0, 0, big)
    p.end()
    res.setDevicePixelRatio(2)
    return res


def set_head(win, lbl, acc, size, radius):
    """pixel_head now; for mc-ru.org accounts the real skin head when it arrives (icon cache → network)."""
    name = acc["name"] if acc else "?"
    lbl.setPixmap(pixel_head(name, size, radius))
    if acc and acc.get("type") == "mcru" and getattr(win, "icons", None) is not None:
        def done(pix, lbl=lbl):
            head = skin_head(pix, size, radius)
            if head:
                lbl.setPixmap(head)
        win.icons.get(mcru.head_url(acc["name"]), done)


def account_kind(acc):
    return "Аккаунт mc-ru.org" if acc.get("type") == "mcru" else "Оффлайн-аккаунт"


LOADER_COLORS = {"fabric": "orange", "forge": "blue", "neoforge": "red", "quilt": "purple", "vanilla": "green"}


# ---------------------------------------------------------------- loading page

class SplashPage(QWidget):
    finished = Signal()

    STEPS = ["Проверяем папку игры", "Загружаем аккаунты", "Читаем сборки", "Готовим каталог Modrinth и CurseForge",
             "Почти готово"]

    def __init__(self):
        super().__init__()
        self.setObjectName("Splash")
        lay = QVBoxLayout(self)
        lay.addStretch(3)
        logo = label(LOGO, "SplashLogo")
        logo.setAlignment(Qt.AlignCenter)
        lay.addWidget(logo)
        name = label(APP_NAME, "SplashName")
        name.setAlignment(Qt.AlignCenter)
        lay.addWidget(name)
        sub = label("Лаунчер Minecraft", "Muted")
        sub.setAlignment(Qt.AlignCenter)
        lay.addWidget(sub)
        lay.addSpacing(28)
        row = QHBoxLayout()
        row.addStretch(1)
        self.bar = QProgressBar()
        self.bar.setRange(0, len(self.STEPS) * 10)
        self.bar.setTextVisible(False)
        self.bar.setFixedSize(320, 6)
        row.addWidget(self.bar)
        row.addStretch(1)
        lay.addLayout(row)
        self.status = label("", "Hint")
        self.status.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.status)
        lay.addStretch(4)
        ver = label(f"версия {__version__}", "Hint")
        ver.setAlignment(Qt.AlignCenter)
        lay.addWidget(ver)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.value = 0

    def start(self, fast=False):
        self.value = 0
        self.timer.start(4 if fast else 32)

    def _tick(self):
        self.value += 1
        self.bar.setValue(self.value)
        step = min(len(self.STEPS) - 1, self.value // 10)
        self.status.setText(self.STEPS[step] + "…")
        if self.value >= self.bar.maximum():
            self.timer.stop()
            QTimer.singleShot(120, self.finished.emit)


# ---------------------------------------------------------------- home

class Hero(QFrame):
    """Compact card of the selected instance: icon, name, details, switcher and a big Play button."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setObjectName("Hero")
        self.setFixedHeight(132)
        self.inst = None
        row = QHBoxLayout(self)
        row.setContentsMargins(22, 18, 22, 18)
        row.setSpacing(16)
        self.icon = QLabel()
        row.addWidget(self.icon)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addStretch(1)
        self.title = label("", "HeroTitle")
        self.meta = label("", "HeroMeta")
        col.addWidget(self.title)
        col.addWidget(self.meta)
        tools = QHBoxLayout()
        tools.setSpacing(6)
        self.pick = QComboBox()
        self.pick.setObjectName("HeroPick")
        self.pick.setMinimumWidth(220)
        self.pick.activated.connect(self._picked)
        tools.addWidget(self.pick)
        folder = QToolButton()
        folder.setObjectName("HeroTool")
        folder.setIcon(icons.icon("folder", "#FFFFFF", "#FFFFFF"))
        folder.setToolTip("Открыть папку сборки")
        folder.clicked.connect(lambda: win.open_instance_folder(self.inst) if self.inst else None)
        tools.addWidget(folder)
        tools.addStretch(1)
        col.addSpacing(6)
        col.addLayout(tools)
        col.addStretch(1)
        row.addLayout(col, 1)
        self.play = QPushButton("  Играть")
        self.play.setObjectName("PlayBtn")
        self.play.setIcon(icons.icon("play", "#FFFFFF", "#FFFFFF"))
        self.play.setIconSize(QSize(18, 18))
        self.play.setCursor(Qt.PointingHandCursor)
        self.play.clicked.connect(lambda: win.launch(self.inst))
        row.addWidget(self.play, 0, Qt.AlignVCenter)

    def set_instance(self, inst):
        self.inst = inst
        self.pick.blockSignals(True)
        self.pick.clear()
        for x in self.win.instances.items:
            self.pick.addItem(QIcon(block_icon(x["icon"], 20)), x["name"], x["id"])
        self.pick.addItem(ic("plus"), "Создать сборку…", "+new")
        self.pick.setCurrentIndex(max(0, self.pick.findData(inst["id"] if inst else "")))
        self.pick.blockSignals(False)
        if inst:
            self.title.setText(inst["name"])
            self.meta.setText(describe(inst))
            set_icon(self.win, self.icon, inst.get("icon_url"), inst["icon"], 76, icon_path=inst.get("icon_path"))
            running = inst["id"] in self.win.games
            self.play.setText("  Играет…" if running else "  Играть")
            self.play.setEnabled(not running)
        else:
            self.title.setText("Создайте первую сборку")
            self.meta.setText("Выберите готовую в каталоге Modrinth или соберите свою.")
            self.icon.setPixmap(block_icon("η", 76))
            self.play.setEnabled(False)
        self.update()

    def _picked(self, i):
        data = self.pick.itemData(i)
        if data == "+new":
            self.win.create_instance()
        elif data:
            self.win.select_instance(data)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 18, 18)
        p.setClipPath(path)
        paint_banner(p, self.rect(), (self.inst or {}).get("icon", "η"), theme.CURRENT["name"] == "dark")
        p.fillRect(self.rect(), QColor(0, 0, 0, 70))
        p.end()


class HomePage(QScrollArea):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body.setObjectName("Page")
        self.lay = QVBoxLayout(body)
        self.lay.setContentsMargins(32, 26, 32, 26)
        self.lay.setSpacing(16)
        self.greet = label("", "Title")
        self.lay.addWidget(self.greet)
        self.hero = Hero(win)
        self.lay.addWidget(self.hero)
        self.lay.addWidget(label("НЕДАВНИЕ СБОРКИ", "Section"))
        self.recent = QHBoxLayout()
        self.recent.setSpacing(12)
        self.lay.addLayout(self.recent)
        self.lay.addWidget(label("НОВОСТИ ЛАУНЧЕРА", "Section"))
        news = QHBoxLayout()
        news.setSpacing(12)
        for title, text in (("Modrinth подключён", "Ищите сборки в каталоге и ставьте их в один клик: Эта скачает "
                                                  "все моды и проверит контрольные суммы."),
                            ("Своё оформление", "Цвет акцента, картинка на фоне и стекло — в Настройках → "
                                                "Оформление. Боковую панель можно скрыть или перенести вправо."),
                            ("Оффлайн-аккаунты", "Играйте с любым ником: UUID считается так же, как на серверах в "
                                                 "оффлайн-режиме.")):
            card = QFrame()
            card.setObjectName("Box")
            v = QVBoxLayout(card)
            v.setContentsMargins(16, 14, 16, 14)
            head = QHBoxLayout()
            i = QLabel()
            i.setPixmap(icons.pixmap("news", theme.CURRENT["text"], size=36))
            i.setFixedSize(18, 18)
            i.setScaledContents(True)
            head.addWidget(i)
            head.addWidget(label(title, "H3"), 1)
            v.addLayout(head)
            v.addWidget(label(text, "Muted", wrap=True))
            v.addStretch(1)
            news.addWidget(card, 1)
        self.lay.addLayout(news)
        self.lay.addStretch(1)
        self.setWidget(body)

    def refresh(self):
        acc = self.win.account()
        hour = time.localtime().tm_hour
        hello = "Доброе утро" if 5 <= hour < 12 else "Добрый день" if hour < 18 else "Добрый вечер" if hour < 23 \
            else "Доброй ночи"
        self.greet.setText(f"{hello}, {acc['name']}" if acc else f"{hello}!")
        self.hero.set_instance(self.win.instance())
        clear_layout(self.recent)
        for inst in self.win.instances.recent(5):
            b = QPushButton()
            b.setObjectName("MiniCard")
            b.setCursor(Qt.PointingHandCursor)
            v = QHBoxLayout(b)
            v.setContentsMargins(10, 8, 12, 8)
            i = QLabel()
            set_icon(self.win, i, inst.get("icon_url"), inst["icon"], 36)
            v.addWidget(i)
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(label(inst["name"], "CardTitle"))
            col.addWidget(label(f"{LOADERS.get(inst['loader'], '')} {inst['mc_version']}", "Hint"))
            v.addLayout(col, 1)
            for w in (i,):
                w.setAttribute(Qt.WA_TransparentForMouseEvents)
            b.setMinimumSize(200, 58)
            b.clicked.connect(lambda _=False, x=inst["id"]: self.win.select_instance(x))
            self.recent.addWidget(b)
        if not self.win.instances.items:
            self.recent.addWidget(label("Пока пусто — загляните в «Сборки».", "Hint"))
        self.recent.addStretch(1)


# ---------------------------------------------------------------- modpacks

class ProjectRow(QFrame):
    open = Signal(str)
    install = Signal(str)

    def __init__(self, p, win=None):
        super().__init__()
        self.p = p
        self.setObjectName("ProjectRow")
        self.setCursor(Qt.PointingHandCursor)
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 12, 14, 12)
        h.setSpacing(14)
        i = QLabel()
        set_icon(win, i, p.get("icon_url"), p["title"], 64)
        h.addWidget(i, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(4)
        head = QHBoxLayout()
        head.setSpacing(6)
        head.addWidget(label(p["title"], "ProjectTitle"))
        head.addWidget(label(f"от {p['author']}", "Muted"))
        head.addStretch(1)
        col.addLayout(head)
        col.addWidget(label(p["description"], wrap=True))
        tags = QHBoxLayout()
        tags.setSpacing(4)
        for lo in p["loaders"]:
            tags.addWidget(tag(LOADER_TAGS.get(lo, lo), LOADER_COLORS.get(lo)))
        for c in p["categories"][:2]:
            tags.addWidget(tag(CATEGORIES.get(c, c)))
        vers = p["game_versions"] or ["?"]
        vt = tag(vers[0] + (f" +{len(vers) - 1}" if len(vers) > 1 else ""))
        vt.setToolTip("Версии игры: " + ", ".join(vers))
        tags.addWidget(vt)
        tags.addStretch(1)
        col.addLayout(tags)
        h.addLayout(col, 1)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        side_w = QWidget()
        side_w.setFixedWidth(150)
        side = QVBoxLayout(side_w)
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(3)
        dl = label(f"⤓ <b>{fmt_count(p['downloads'])}</b>")
        dl.setToolTip(f"{p['downloads']:,} скачиваний".replace(",", " "))
        side.addWidget(dl, 0, Qt.AlignRight)
        fo = label(f"♥ <b>{fmt_count(p['follows'])}</b>")
        fo.setToolTip("подписчиков")
        side.addWidget(fo, 0, Qt.AlignRight)
        side.addWidget(label(f"обновлено {ago(p['date_modified'])}", "Hint"), 0, Qt.AlignRight)
        src = label(SOURCES.get(p["source"], p["source"]), "SourceTag")
        side.addWidget(src, 0, Qt.AlignRight)
        side.addStretch(1)
        btn = QPushButton("Установить")
        btn.setObjectName("Accent")
        btn.setIcon(icons.icon("download", "#FFFFFF", "#FFFFFF"))
        btn.clicked.connect(lambda: self.install.emit(p["slug"]))
        side.addWidget(btn, 0, Qt.AlignRight)
        h.addWidget(side_w)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.open.emit(self.p["slug"])


class ProjectDialog(QDialog):
    def __init__(self, win, provider, slug):
        super().__init__(win)
        self.win = win
        self.provider = provider
        self.slug = slug
        p = (provider.cached(slug) if hasattr(provider, "cached") else None) or provider.project(slug)
        self.p = p
        self.setWindowTitle(p["title"])
        self.resize(820, 660)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        head = QHBoxLayout()
        head.setSpacing(14)
        i = QLabel()
        set_icon(win, i, p.get("icon_url"), p["title"], 80)
        head.addWidget(i)
        col = QVBoxLayout()
        col.addWidget(label(p["title"], "Title"))
        col.addWidget(label(f"от {p['author']} · {SOURCES.get(p['source'], p['source'])} · ⤓ {fmt_count(p['downloads'])}"
                            f" · ♥ {fmt_count(p['follows'])}", "Muted"))
        tags = QHBoxLayout()
        for lo in p["loaders"]:
            tags.addWidget(tag(LOADER_TAGS.get(lo, lo), LOADER_COLORS.get(lo)))
        for c in p["categories"]:
            tags.addWidget(tag(CATEGORIES.get(c, c)))
        tags.addStretch(1)
        col.addLayout(tags)
        head.addLayout(col, 1)
        btns = QVBoxLayout()
        inst = QPushButton("Установить")
        inst.setObjectName("Accent")
        inst.clicked.connect(lambda: (self.accept(), win.install_project(self.provider, slug)))
        btns.addWidget(inst)
        if p.get("url"):
            web = QPushButton("Открыть на сайте")
            web.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(p["url"])))
            btns.addWidget(web)
        btns.addStretch(1)
        head.addLayout(btns)
        lay.addLayout(head)
        tabs = QTabWidget()
        tabs.setObjectName("DocTabs")
        self.desc = QTextBrowser()
        self.desc.setOpenExternalLinks(True)
        self.desc.setMarkdown(p.get("body") or p.get("description") or "")
        tabs.addTab(self.desc, "Описание")
        self.vers_host = QWidget()
        self.vl = QVBoxLayout(self.vers_host)
        self.vl.addWidget(label("Загружаем версии…", "Hint"))
        self.vl.addStretch(1)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(self.vers_host)
        tabs.addTab(sc, "Версии")
        lay.addWidget(tabs, 1)
        if p["source"] != "modrinth":
            lay.addWidget(label("Это пример: CurseForge подключим позже (нужен ключ API).", "Hint", wrap=True))
        win.runner.run(lambda: provider.project(slug), self._project, lambda e: None)
        win.runner.run(lambda: provider.versions(slug), self._versions,
                       lambda e: self._versions_error(e))

    def _project(self, p):
        if p and p.get("body"):
            self.desc.setMarkdown(p["body"])

    def _versions_error(self, e):
        clear_layout(self.vl)
        self.vl.addWidget(label(f"Не удалось загрузить версии: {e}", "Warn", wrap=True))
        self.vl.addStretch(1)

    def _versions(self, vs):
        clear_layout(self.vl)
        if not vs:
            self.vl.addWidget(label("Версий пока нет.", "Hint"))
        for v in vs[:40]:
            row = QHBoxLayout()
            row.addWidget(label(f"<b>{v['name']}</b>"), 1)
            row.addWidget(tag({"release": "Релиз", "beta": "Бета", "alpha": "Альфа"}.get(v["type"], v["type"]),
                              {"release": "green", "beta": "yellow", "alpha": "red"}.get(v["type"])))
            row.addWidget(tag(LOADER_TAGS.get(v["loader"], v["loader"]), LOADER_COLORS.get(v["loader"])))
            row.addWidget(tag(v["mc"] or "?"))
            row.addWidget(label(ago(v["date"]), "Hint"))
            b = QPushButton("Установить")
            b.clicked.connect(lambda _=False, v_=v: (self.accept(), self.win.install_project(self.provider, self.slug,
                                                                                            v_)))
            row.addWidget(b)
            self.vl.addLayout(row)
        self.vl.addStretch(1)


class _Progress(QWidget):
    """Carries progress from the install thread to the dialog (queued signal)."""

    changed = Signal(str, int, int)


class InstallDialog(QDialog):
    """Choose name / version, then install: Modrinth — download the .mrpack and every mod in it (sha1-checked) into
    <game>/instances/<id>/.minecraft; examples — a simulated progress bar."""

    def __init__(self, win, provider, p, version=None):
        super().__init__(win)
        self.win = win
        self.provider = provider
        self.p = p
        self.real = getattr(provider, "name", "") == "modrinth"
        self.setWindowTitle("Установка сборки")
        self.setFixedWidth(470)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        head = QHBoxLayout()
        i = QLabel()
        set_icon(win, i, p.get("icon_url"), p["title"], 48)
        head.addWidget(i)
        head.addWidget(label(f"Установка «{p['title']}»", "H2"), 1)
        lay.addLayout(head)
        lay.addWidget(label("Название сборки"))
        self.name = QLineEdit(p["title"])
        lay.addWidget(self.name)
        lay.addWidget(label("Версия"))
        self.version = QComboBox()
        self.version.addItem("Загружаем версии…", None)
        self.version.setEnabled(False)
        lay.addWidget(self.version)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.bar.hide()
        lay.addWidget(self.bar)
        self.status = label("", "Hint", wrap=True)
        lay.addWidget(self.status)
        row = QHBoxLayout()
        row.addStretch(1)
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self.cancel)
        row.addWidget(self.cancel_btn)
        self.go = QPushButton("Установить")
        self.go.setObjectName("Accent")
        self.go.setEnabled(False)
        self.go.clicked.connect(self.start)
        row.addWidget(self.go)
        lay.addLayout(row)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.result_inst = None
        self.cancelled = False
        self.running = False
        self.preferred = version
        self.progress = _Progress()
        self.progress.changed.connect(self._progress)
        win.runner.run(lambda: provider.versions(p["slug"]), self._versions, self._versions_error)

    def _versions(self, vs):
        self.version.clear()
        for v in vs:
            if self.real and not v.get("file"):
                continue
            kind = {"beta": " · бета", "alpha": " · альфа"}.get(v.get("type"), "")
            self.version.addItem(f"{v['version']} · {LOADER_TAGS.get(v['loader'], v['loader'])} {v['mc']}{kind}", v)
        if self.preferred:
            for k in range(self.version.count()):
                d = self.version.itemData(k)
                if d and d.get("version") == self.preferred.get("version") and d.get("mc") == self.preferred.get("mc"):
                    self.version.setCurrentIndex(k)
        self.version.setEnabled(self.version.count() > 0)
        self.go.setEnabled(self.version.count() > 0)
        if not self.version.count():
            self.status.setText("Нет версий для установки.")

    def _versions_error(self, e):
        self.version.clear()
        self.version.addItem("—", None)
        self.status.setText(f"Не удалось загрузить версии: {e}")

    def start(self, fast=False):
        self.go.setEnabled(False)
        self.name.setEnabled(False)
        self.version.setEnabled(False)
        self.bar.show()
        self.bar.setValue(0)
        self.running = True
        if not self.real:
            self.timer.start(2 if fast else 28)
            return
        v = self.version.currentData()
        from .instances import new_id
        from .modrinth import install_mrpack

        iid = new_id()
        root = self.win.settings.game_dir() / "instances" / iid
        mc_dir = root / ".minecraft"
        workers = int(self.win.settings.get("parallel_downloads", 6))
        cache = root / "pack.mrpack"

        def job():
            from . import net

            self.progress.changed.emit("pack", 0, 1)
            net.download(v["file"]["url"], cache, progress=lambda d, t: self.progress.changed.emit("pack", d, t or 1),
                         cancel=lambda: self.cancelled)
            info = install_mrpack(cache, mc_dir, lambda st, d, t: self.progress.changed.emit(st, d, t),
                                  lambda: self.cancelled, workers)
            return info

        def done(info):
            self.running = False
            self.result_inst = self.win.instances.add(
                self.name.text().strip() or self.p["title"], info["mc"] or v["mc"], info["loader"], "modrinth",
                self.p["slug"], info["mods"], self.p["title"], iid=iid, icon_url=self.p.get("icon_url", ""),
                loader_version=info["loader_version"], pack_version=info["version"] or v["version"])
            self.accept()

        def failed(e):
            self.running = False
            import shutil as _sh

            _sh.rmtree(root, ignore_errors=True)
            if self.cancelled:
                self.reject()
                return
            self.status.setText(f"Не получилось: {e}")
            self.status.setObjectName("Warn")
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            self.go.setEnabled(True)
            self.version.setEnabled(True)
            self.name.setEnabled(True)

        self.win.runner.run(job, done, failed)

    def _progress(self, stage, d, t):
        if stage == "pack":
            self.bar.setValue(int(5 * d / max(1, t)))
            self.status.setText("Скачиваем файл сборки…")
        elif stage == "files":
            self.bar.setValue(5 + int(90 * d / max(1, t)))
            self.status.setText(f"Скачиваем моды и ресурсы: {d} из {t}")
        else:
            self.bar.setValue(95 + int(5 * d / max(1, t)))
            self.status.setText("Копируем настройки сборки…")

    def cancel(self):
        if self.running and self.real:
            self.cancelled = True
            self.status.setText("Отменяем…")
            self.cancel_btn.setEnabled(False)
        else:
            self.timer.stop()
            self.reject()

    def closeEvent(self, e):
        if self.running and self.real:
            self.cancel()
            e.ignore()
            return
        super().closeEvent(e)

    def _tick(self):
        v = self.bar.value() + 1
        self.bar.setValue(v)
        steps = ["Получаем список файлов", "Скачиваем Minecraft", "Ставим загрузчик модов", "Скачиваем моды",
                 "Применяем настройки"]
        self.status.setText(f"{steps[min(len(steps) - 1, v // 20)]}… {v}%  (пример, без загрузки)")
        if v >= 100:
            self.timer.stop()
            self.running = False
            d = self.version.currentData() or {"mc": self.p["game_versions"][-1], "loader": self.p["loaders"][0]}
            self.result_inst = self.win.instances.add(self.name.text().strip() or self.p["title"], d["mc"],
                                                      d["loader"], self.p["source"], self.p["slug"],
                                                      self.p.get("mods") or 0, self.p["title"])
            self.accept()


def _modrinth_app_profiles_dir():
    """Return the Modrinth App profiles path for the current OS, or None if not found."""
    import os
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "com.modrinth.theseus" / "profiles"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home())) / "com.modrinth.theseus" / "profiles"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "com.modrinth.theseus" / "profiles"
    return base if base.exists() else None


class ModsPage(QWidget):
    """Manage mods, shaders, resource packs and datapacks — shown as a full launcher page."""

    TABS = [
        ("Моды", ".minecraft/mods", (".jar", ".zip")),
        ("Шейдеры", ".minecraft/shaderpacks", (".zip",)),
        ("Ресурс-паки", ".minecraft/resourcepacks", (".zip",)),
        ("Датапаки", ".minecraft/datapacks", (".zip",)),
    ]

    MODRINTH_TYPES = {
        "Моды": "mod",
        "Шейдеры": "shader",
        "Ресурс-паки": "resourcepack",
        "Датапаки": "datapack",
    }

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.inst = None
        self.setObjectName("Page")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 20, 32, 20)
        lay.setSpacing(12)
        head = QHBoxLayout()
        back = QPushButton("← Назад")
        back.clicked.connect(self._go_back)
        head.addWidget(back, 0, Qt.AlignLeft)
        head.addStretch(1)
        lay.addLayout(head)
        self.title_lbl = label("", "Title")
        lay.addWidget(self.title_lbl)
        self.tabs_widget = QTabWidget()
        self.tabs_widget.setObjectName("DocTabs")
        lay.addWidget(self.tabs_widget, 1)

    def _go_back(self):
        self.win.modpacks.show_tab("mine")
        self.win.pages.setCurrentWidget(self.win.modpacks)

    def set_instance(self, inst):
        self.inst = inst
        self.title_lbl.setText(f"Содержимое — {inst['name']}")
        self.tabs_widget.clear()
        for tab_name, subdir, exts in self.TABS:
            w, _ = self._make_tab(tab_name, subdir, exts)
            self.tabs_widget.addTab(w, tab_name)

    def _inst_dir(self):
        return self.win.settings.game_dir() / "instances" / self.inst["id"]

    def _make_tab(self, tab_name, subdir, exts):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 8, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner.setObjectName("Page")
        list_lay = QVBoxLayout(inner)
        list_lay.setContentsMargins(0, 0, 0, 0)
        list_lay.setSpacing(4)
        scroll.setWidget(inner)
        v.addWidget(scroll, 1)
        add_btn = QPushButton("  Добавить из Modrinth…")
        add_btn.setObjectName("Accent")
        add_btn.setIcon(icons.icon("plus", "#FFFFFF", "#FFFFFF"))
        ptype = self.MODRINTH_TYPES.get(tab_name, "mod")
        add_btn.clicked.connect(lambda: self._open_add_dialog(ptype, subdir, exts, list_lay))
        v.addWidget(add_btn)
        self._fill_list(list_lay, subdir, exts)
        return w, list_lay

    def _fill_list(self, lay, subdir, exts):
        clear_layout(lay)
        folder = self._inst_dir() / subdir
        folder.mkdir(parents=True, exist_ok=True)
        files = sorted(folder.iterdir(), key=lambda p: p.name.lower()) if folder.exists() else []
        enabled_exts = set(exts)
        disabled_exts = {e + ".disabled" for e in enabled_exts}
        shown = [f for f in files if any(f.name.endswith(e) for e in enabled_exts | disabled_exts)]
        if not shown:
            lay.addWidget(label("Нет файлов.", "Hint"))
            return
        for fp in shown:
            is_disabled = fp.name.endswith(".disabled")
            row = QHBoxLayout()
            name_lbl = label(fp.name, wrap=False)
            name_lbl.setToolTip(str(fp))
            row.addWidget(name_lbl, 1)
            tog = QPushButton("Включить" if is_disabled else "Выключить")
            def make_toggle(fp_=fp, is_dis=is_disabled, lay_=lay, sub=subdir, ex=exts):
                def do():
                    if is_dis:
                        new = fp_.with_suffix("") if fp_.suffix == ".disabled" else fp_
                    else:
                        new = fp_.with_suffix(fp_.suffix + ".disabled")
                    try:
                        fp_.rename(new)
                    except OSError:
                        pass
                    self._fill_list(lay_, sub, ex)
                return do
            tog.clicked.connect(make_toggle())
            row.addWidget(tog)
            rem = QPushButton("Удалить")
            def make_remove(fp_=fp, lay_=lay, sub=subdir, ex=exts):
                def do():
                    try:
                        fp_.unlink()
                    except OSError:
                        pass
                    self._fill_list(lay_, sub, ex)
                return do
            rem.clicked.connect(make_remove())
            row.addWidget(rem)
            frame = QFrame()
            frame.setLayout(row)
            lay.addWidget(frame)
        lay.addStretch(1)

    def _open_add_dialog(self, ptype, subdir, exts, list_lay):
        dest_dir = self._inst_dir() / subdir
        dest_dir.mkdir(parents=True, exist_ok=True)
        dlg = ModAddDialog(self.win, self.inst, ptype, dest_dir)
        dlg.exec()
        self._fill_list(list_lay, subdir, exts)


class ModAddDialog(QDialog):
    """Search Modrinth for a content type and download into an instance folder."""

    def __init__(self, win, inst, project_type, dest_dir):
        super().__init__(win)
        self.win = win
        self.inst = inst
        self.project_type = project_type
        self.dest_dir = Path(dest_dir)
        type_names = {"mod": "Моды", "shader": "Шейдеры", "resourcepack": "Ресурс-паки", "datapack": "Датапаки"}
        self.setWindowTitle(f"Добавить из Modrinth — {type_names.get(project_type, project_type)}")
        self.resize(520, 500)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск…")
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(self._search)
        search_row.addWidget(self.search, 1)
        go = QPushButton("Найти")
        go.setObjectName("Accent")
        go.clicked.connect(self._search)
        search_row.addWidget(go)
        lay.addLayout(search_row)
        self.status = label("", "Hint")
        lay.addWidget(self.status)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        inner.setObjectName("Page")
        self.results_lay = QVBoxLayout(inner)
        self.results_lay.setContentsMargins(0, 0, 0, 0)
        self.results_lay.setSpacing(6)
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)
        close = QPushButton("Закрыть")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        lay.addLayout(row)

    def _search(self):
        q = self.search.text().strip()
        self.status.setText("Ищем…")
        mc = self.inst.get("mc_version", "")
        loader = self.inst.get("loader", "")

        def job():
            from .modrinth import search_content
            return search_content(q, self.project_type, loaders=[loader] if loader and loader != "vanilla" else (),
                                  version=mc, limit=20)

        def done(hits):
            clear_layout(self.results_lay)
            self.status.setText(f"Найдено: {len(hits)}" if hits else "Ничего не найдено.")
            for h in hits:
                self.results_lay.addWidget(self._result_row(h))
            self.results_lay.addStretch(1)

        def failed(e):
            self.status.setText(f"Ошибка: {e}")

        self.win.runner.run(job, done, failed)

    def _result_row(self, h):
        frame = QFrame()
        frame.setObjectName("Box")
        row = QHBoxLayout(frame)
        row.setContentsMargins(10, 8, 10, 8)
        icon_lbl = QLabel()
        set_icon(self.win, icon_lbl, h.get("icon_url"), h["title"], 36)
        row.addWidget(icon_lbl)
        col = QVBoxLayout()
        col.addWidget(label(h["title"], "H3"))
        meta = f"{h['author']} · {h.get('downloads', 0):,} скачиваний"
        col.addWidget(label(meta, "Hint"))
        row.addLayout(col, 1)
        dl = QPushButton("Скачать")
        dl.clicked.connect(lambda: self._download(h, dl))
        row.addWidget(dl)
        return frame

    def _download(self, h, btn):
        btn.setEnabled(False)
        btn.setText("…")
        mc = self.inst.get("mc_version", "")
        loader = self.inst.get("loader", "")
        dest_dir = self.dest_dir
        slug = h["slug"]

        def job():
            from .modrinth import content_versions
            vs = content_versions(slug, loader if loader != "vanilla" else "", mc)
            if not vs:
                raise Exception("Нет подходящей версии")
            v = vs[0]
            fn = v["file"]["filename"]
            dest = dest_dir / fn
            dest_dir.mkdir(parents=True, exist_ok=True)
            net.download(v["file"]["url"], dest)
            return fn

        def done(fn):
            btn.setText("✓")
            btn.setEnabled(True)

        def failed(e):
            btn.setText("Ошибка")
            btn.setToolTip(str(e))
            btn.setEnabled(True)

        self.win.runner.run(job, done, failed)


class ImportModrinthAppDialog(QDialog):
    """Import instances from the Modrinth App (Theseus)."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Импорт из Modrinth App")
        self.resize(500, 400)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.addWidget(label("Импорт сборок из Modrinth App", "H2"))
        self.profiles_dir = _modrinth_app_profiles_dir()
        self.checks = {}
        self.profiles = {}
        if not self.profiles_dir:
            lay.addWidget(label("Modrinth App не найден на этом компьютере.", "Muted"))
        else:
            lay.addWidget(label(f"Найдены сборки в: {self.profiles_dir}", "Hint", wrap=True))
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            inner = QWidget()
            inner.setObjectName("Page")
            inner_lay = QVBoxLayout(inner)
            inner_lay.setContentsMargins(0, 0, 0, 0)
            for profile_dir in sorted(self.profiles_dir.iterdir()):
                pjson = profile_dir / "profile.json"
                if not pjson.exists():
                    continue
                try:
                    import json as _json
                    data = _json.loads(pjson.read_text("utf-8"))
                except Exception:
                    continue
                name = data.get("name") or profile_dir.name
                gv = data.get("game_version") or ""
                loader_info = data.get("loader") or {}
                loader = loader_info.get("type") or "vanilla"
                cb = QCheckBox(f"{name}  [{loader} {gv}]")
                inner_lay.addWidget(cb)
                self.checks[profile_dir.name] = cb
                self.profiles[profile_dir.name] = (profile_dir, data, name, gv, loader)
            inner_lay.addStretch(1)
            scroll.setWidget(inner)
            lay.addWidget(scroll, 1)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.bar.hide()
        lay.addWidget(self.bar)
        self.status = label("", "Hint")
        lay.addWidget(self.status)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        self.ok_btn = QPushButton("Импортировать")
        self.ok_btn.setObjectName("Accent")
        self.ok_btn.clicked.connect(self._import)
        self.ok_btn.setEnabled(bool(self.profiles_dir and self.checks))
        row.addWidget(self.ok_btn)
        lay.addLayout(row)

    def _import(self):
        selected = [k for k, cb in self.checks.items() if cb.isChecked()]
        if not selected:
            self.status.setText("Выберите хотя бы одну сборку.")
            return
        self.ok_btn.setEnabled(False)
        self.bar.setRange(0, len(selected))
        self.bar.setValue(0)
        self.bar.show()
        game_dir = self.win.settings.game_dir()

        def job():
            from .instances import new_id
            imported = []
            for i, key in enumerate(selected):
                prof_dir, data, name, gv, loader = self.profiles[key]
                iid = new_id()
                dest = game_dir / "instances" / iid
                shutil.copytree(str(prof_dir), str(dest))
                imported.append((iid, name, gv, loader))
                yield i + 1, len(selected)
            return imported

        results = []
        total = len(selected)

        def _run_import():
            try:
                gen = job()
                while True:
                    try:
                        done_n, tot = next(gen)
                        self.bar.setValue(done_n)
                        self.status.setText(f"Копируем {done_n} из {tot}…")
                    except StopIteration as e:
                        results.extend(e.value)
                        break
                for iid, name, gv, loader in results:
                    self.win.instances.add(name, gv, loader, source="own", iid=iid)
                self.win.refresh()
                self.win.modpacks.show_tab("mine")
                self.accept()
            except Exception as exc:
                self.status.setText(f"Ошибка: {exc}")
                self.ok_btn.setEnabled(True)

        threading.Thread(target=_run_import, daemon=True).start()


class CreateInstanceDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.icon_path = None
        self.setWindowTitle("Новая сборка")
        self.setFixedWidth(440)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.addWidget(label("Новая сборка", "H2"))
        head = QHBoxLayout()
        self.icon = QLabel()
        head.addWidget(self.icon)
        col = QVBoxLayout()
        col.addWidget(label("Название"))
        self.name = QLineEdit()
        self.name.setPlaceholderText("Например, «Выживание с друзьями»")
        self.name.textChanged.connect(self._icon)
        col.addWidget(self.name)
        pick_row = QHBoxLayout()
        self.icon_hint = label("", "Hint")
        pick_row.addWidget(self.icon_hint, 1)
        pick_btn = QPushButton("Выбрать…")
        pick_btn.clicked.connect(self._pick_icon)
        pick_row.addWidget(pick_btn)
        col.addLayout(pick_row)
        head.addLayout(col, 1)
        lay.addLayout(head)
        lay.addWidget(label("Версия игры"))
        self.version = QComboBox()
        for v in MC_VERSIONS:
            self.version.addItem(v, v)
        self.version.setCurrentIndex(1)
        lay.addWidget(self.version)
        lay.addWidget(label("Загрузчик модов"))
        seg = QHBoxLayout()
        seg.setSpacing(0)
        self.loader = "fabric"
        self.loader_btns = {}
        group = QButtonGroup(self)
        for i, (k, t) in enumerate(LOADERS.items()):
            b = QPushButton(t)
            b.setObjectName("Seg")
            b.setCheckable(True)
            b.setChecked(k == self.loader)
            b.clicked.connect(lambda _=False, k_=k: setattr(self, "loader", k_))
            group.addButton(b)
            seg.addWidget(b)
            self.loader_btns[k] = b
        lay.addLayout(seg)
        row = QHBoxLayout()
        row.addStretch(1)
        c = QPushButton("Отмена")
        c.clicked.connect(self.reject)
        row.addWidget(c)
        ok = QPushButton("Создать")
        ok.setObjectName("Accent")
        ok.clicked.connect(self._ok)
        row.addWidget(ok)
        lay.addLayout(row)
        self._icon()

    def _pick_icon(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выбрать иконку", "", "Изображения (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.icon_path = path
            self.icon_hint.setText(Path(path).name)
            from PySide6.QtGui import QPixmap
            pix = QPixmap(path)
            if not pix.isNull():
                self.icon.setPixmap(rounded(pix, 56))

    def _icon(self):
        if not self.icon_path:
            self.icon.setPixmap(block_icon(self.name.text().strip() or "Новая сборка", 56))

    def _ok(self):
        if not self.name.text().strip():
            self.name.setText(f"Сборка {self.version.currentData()}")
        self.accept()


class InstanceCard(QFrame):
    def __init__(self, win, inst):
        super().__init__()
        self.win = win
        self.inst = inst
        selected = win.settings.get("selected_instance") == inst["id"]
        self.setObjectName("InstanceCardOn" if selected else "InstanceCard")
        self.setFixedSize(236, 210)
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 14, 14, 12)
        top = QHBoxLayout()
        i = QLabel()
        set_icon(win, i, inst.get("icon_url"), inst["icon"], 56, icon_path=inst.get("icon_path"))
        top.addWidget(i)
        top.addStretch(1)
        more = QToolButton()
        more.setIcon(ic("dots"))
        more.clicked.connect(lambda: self.menu(more.mapToGlobal(more.rect().bottomLeft())))
        top.addWidget(more, 0, Qt.AlignTop)
        v.addLayout(top)
        v.addWidget(label(inst["name"], "CardTitle"))
        tags = QHBoxLayout()
        tags.setSpacing(4)
        tags.addWidget(tag(LOADERS.get(inst["loader"], inst["loader"]), LOADER_COLORS.get(inst["loader"])))
        tags.addWidget(tag(inst["mc_version"]))
        tags.addStretch(1)
        v.addLayout(tags)
        extra = [SOURCES[inst["source"]]] if inst.get("source") in SOURCES else []
        if inst.get("mods"):
            extra.append(f"{inst['mods']} модов")
        extra.append("играли " + ago(inst["last_played"]) if inst.get("last_played") else "ещё не запускали")
        v.addWidget(label(" · ".join(extra), "Hint"))
        v.addStretch(1)
        row = QHBoxLayout()
        play = QPushButton("Играет…" if inst["id"] in win.games else "Играть")
        play.setObjectName("Accent")
        play.setEnabled(inst["id"] not in win.games)
        play.setIcon(icons.icon("play", "#FFFFFF", "#FFFFFF"))
        play.clicked.connect(lambda: (win.select_instance(inst["id"], go_home=False), win.launch(inst)))
        row.addWidget(play)
        sel = QPushButton("Выбрана" if selected else "Выбрать")
        sel.setEnabled(not selected)
        sel.clicked.connect(lambda: win.select_instance(inst["id"], go_home=False))
        row.addWidget(sel)
        v.addLayout(row)

    def menu(self, pos):
        w = self.win
        m = QMenu(self)
        m.addAction(ic("play"), "Играть", lambda: w.launch(self.inst))
        m.addAction(ic("folder"), "Открыть папку", lambda: w.open_instance_folder(self.inst))
        m.addSeparator()
        m.addAction(ic("desc"), "Управление содержимым…", lambda: w.manage_mods(self.inst))
        m.addAction(ic("image"), "Сменить иконку…", lambda: w.set_instance_icon(self.inst))
        m.addSeparator()
        m.addAction(ic("desc"), "Переименовать…", lambda: w.rename_instance(self.inst))
        m.addAction(ic("copy"), "Копировать", lambda: w.copy_instance(self.inst))
        m.addSeparator()
        m.addAction(ic("trash"), "Удалить…", lambda: w.delete_instance(self.inst))
        m.exec(pos)


class ModpacksPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setObjectName("Page")
        self.offset = 0
        self.limit = 12
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 26, 32, 0)
        lay.setSpacing(12)
        head = QHBoxLayout()
        head.addWidget(label("Сборки", "Title"))
        head.addSpacing(16)
        self.tab_btns = {}
        group = QButtonGroup(self)
        for i, (k, t) in enumerate((("catalog", "Каталог"), ("mine", "Мои сборки"))):
            b = QPushButton(t)
            b.setObjectName("Seg")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k_=k: self.show_tab(k_))
            group.addButton(b)
            head.addWidget(b)
            self.tab_btns[k] = b
        head.addStretch(1)
        imp = QPushButton("Импорт из Modrinth App…")
        imp.clicked.connect(lambda: ImportModrinthAppDialog(win).exec())
        head.addWidget(imp)
        new = QPushButton("Создать сборку")
        new.setObjectName("Accent")
        new.setIcon(icons.icon("plus", "#FFFFFF", "#FFFFFF"))
        new.clicked.connect(win.create_instance)
        head.addWidget(new)
        lay.addLayout(head)
        self.stack = QStackedWidget()
        lay.addWidget(self.stack, 1)
        self.stack.addWidget(self._catalog())
        self.mine_scroll = QScrollArea()
        self.mine_scroll.setWidgetResizable(True)
        self.mine_scroll.setFrameShape(QFrame.NoFrame)
        self.stack.addWidget(self.mine_scroll)
        self.show_tab("catalog")

    # -- catalog: filters on the left, results on the right (like modrinth.com/modpacks)
    def _catalog(self):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(18)
        side = QScrollArea()
        side.setWidgetResizable(True)
        side.setFrameShape(QFrame.NoFrame)
        side.setFixedWidth(230)
        self.filters = side
        fbody = QWidget()
        fbody.setObjectName("Page")
        f = QVBoxLayout(fbody)
        f.setContentsMargins(0, 0, 8, 16)
        f.setSpacing(6)
        f.addWidget(label("ИСТОЧНИК", "Section"))
        self.f_sources = {}
        group = QButtonGroup(self)
        for k, t in (("modrinth", "Modrinth"), ("curseforge", "CurseForge · примеры")):
            rb = QRadioButton(t)
            rb.setChecked(k == (self.win.settings.get("default_source") or "modrinth"))
            rb.toggled.connect(lambda on: on and self.research())
            group.addButton(rb)
            f.addWidget(rb)
            self.f_sources[k] = rb
        if not any(rb.isChecked() for rb in self.f_sources.values()):
            self.f_sources["modrinth"].setChecked(True)
        f.addSpacing(8)
        f.addWidget(label("ЗАГРУЗЧИК", "Section"))
        self.f_loaders = {}
        lg = QGridLayout()
        lg.setSpacing(4)
        for i, (k, t) in enumerate(LOADER_TAGS.items()):
            b = QPushButton(t)
            b.setObjectName("Chip")
            b.setCheckable(True)
            b.toggled.connect(self.research)
            lg.addWidget(b, i // 2, i % 2)
            self.f_loaders[k] = b
        f.addLayout(lg)
        f.addSpacing(8)
        f.addWidget(label("ВЕРСИЯ ИГРЫ", "Section"))
        self.f_version = QComboBox()
        self.f_version.addItem("Любая", "")
        for v in MC_VERSIONS:
            self.f_version.addItem(v, v)
        self.f_version.currentIndexChanged.connect(self.research)
        f.addWidget(self.f_version)
        f.addSpacing(8)
        f.addWidget(label("КАТЕГОРИИ", "Section"))
        self.f_cats = {}
        for k, t in CATEGORIES.items():
            cb = QCheckBox(t)
            cb.toggled.connect(self.research)
            f.addWidget(cb)
            self.f_cats[k] = cb
        f.addSpacing(8)
        reset = QPushButton("Сбросить фильтры")
        reset.clicked.connect(self.reset_filters)
        f.addWidget(reset)
        f.addStretch(1)
        side.setWidget(fbody)
        side.setVisible(not self.win.settings.get("filters_hidden"))
        h.addWidget(side)
        right = QVBoxLayout()
        right.setSpacing(10)
        top = QHBoxLayout()
        self.filter_btn = QPushButton("Фильтры")
        self.filter_btn.setIcon(ic("filter"))
        self.filter_btn.setCheckable(True)
        self.filter_btn.setChecked(side.isVisible())
        self.filter_btn.setToolTip("Показать / скрыть панель фильтров")
        self.filter_btn.toggled.connect(self.toggle_filters)
        top.addWidget(self.filter_btn)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск сборок на Modrinth…")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(ic("search"), QLineEdit.LeadingPosition)
        self.search.textChanged.connect(lambda: self._debounce.start(350))
        top.addWidget(self.search, 1)
        top.addWidget(label("Сортировка"))
        self.sort = QComboBox()
        for k, t in SORTS.items():
            self.sort.addItem(t, k)
        self.sort.currentIndexChanged.connect(self.research)
        top.addWidget(self.sort)
        right.addLayout(top)
        self.count = label("", "Hint")
        right.addWidget(self.count)
        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setFrameShape(QFrame.NoFrame)
        self.results_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        rbody = QWidget()
        rbody.setObjectName("Page")
        self.results = QVBoxLayout(rbody)
        self.results.setContentsMargins(0, 0, 4, 16)
        self.results.setSpacing(10)
        self.results_scroll.setWidget(rbody)
        right.addWidget(self.results_scroll, 1)
        h.addLayout(right, 1)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self.research)
        self.token = 0
        self.loaded_once = False
        return w

    def toggle_filters(self, on):
        self.filters.setVisible(on)
        self.win.settings["filters_hidden"] = not on
        self.win.settings.save()

    def source(self):
        return next((k for k, rb in self.f_sources.items() if rb.isChecked()), "modrinth")

    def provider(self):
        return self.win.providers[self.source()]

    def query(self):
        return dict(query=self.search.text(), sources=[self.source()],
                    loaders=[k for k, b in self.f_loaders.items() if b.isChecked()],
                    version=self.f_version.currentData(),
                    categories=[k for k, cb in self.f_cats.items() if cb.isChecked()],
                    sort=self.sort.currentData())

    def reset_filters(self):
        for d in (self.f_loaders, self.f_cats):
            for b in d.values():
                b.blockSignals(True)
                b.setChecked(False)
                b.blockSignals(False)
        self.f_version.blockSignals(True)
        self.f_version.setCurrentIndex(0)
        self.f_version.blockSignals(False)
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.research()

    def research(self, *_):
        self.offset = 0
        self.fill(reset=True)

    def _drop_tail(self):
        """Remove the trailing stretch / «more» button / status line."""
        while self.results.count():
            it = self.results.itemAt(self.results.count() - 1)
            w = it.widget()
            if w is None or w.objectName() in ("MoreBtn", "Status"):
                self.results.takeAt(self.results.count() - 1)
                if w is not None:
                    w.deleteLater()
            else:
                break

    def fill(self, reset=False):
        self.token += 1
        token = self.token
        q = self.query()
        prov = self.provider()
        offset, limit = self.offset, self.limit
        if reset:
            clear_layout(self.results)
        else:
            self._drop_tail()
        busy = label("Загружаем…", "Status")
        busy.setObjectName("Status")
        self.results.addWidget(busy)
        self.results.addStretch(1)
        self.win.runner.run(lambda: prov.search(offset=offset, limit=limit, **q),
                            lambda res: self._results(token, res, prov), lambda e: self._error(token, e))

    def _results(self, token, res, prov):
        if token != self.token:
            return
        self.loaded_once = True
        hits, total = res
        self._drop_tail()
        for p in hits:
            row = ProjectRow(p, self.win)
            row.open.connect(lambda slug, pr=prov: self.win.open_project(pr, slug))
            row.install.connect(lambda slug, pr=prov: self.win.install_project(pr, slug))
            self.results.addWidget(row)
        shown = self.offset + len(hits)
        src = "Modrinth" if prov.name == "modrinth" else "примеры CurseForge (API подключим позже)"
        self.count.setText(f"Найдено: {total} · {src}")
        if not total:
            st = label("Ничего не нашлось. Попробуйте убрать часть фильтров.", "Hint")
            st.setObjectName("Status")
            self.results.addWidget(st)
        if shown < total:
            more = QPushButton(f"Показать ещё ({total - shown})")
            more.setObjectName("MoreBtn")
            more.clicked.connect(self.more)
            self.results.addWidget(more)
        self.results.addStretch(1)

    def _error(self, token, e):
        if token != self.token:
            return
        self._drop_tail()
        box = QFrame()
        box.setObjectName("Status")
        box.setStyleSheet(f"QFrame#Status {{ background: {theme.CURRENT['popup'] if 'popup' in theme.CURRENT else theme.CURRENT['card']};"
                          f" border: 1px solid {theme.CURRENT['border']}; border-radius: 14px; }}")
        v = QVBoxLayout(box)
        v.setContentsMargins(18, 16, 18, 16)
        v.addWidget(label("Modrinth не отвечает", "H3"))
        v.addWidget(label(str(e), "Muted", wrap=True))
        row = QHBoxLayout()
        again = QPushButton("Повторить")
        again.setObjectName("Accent")
        again.clicked.connect(self.research)
        row.addWidget(again)
        demo = QPushButton("Показать примеры")
        demo.clicked.connect(lambda: self.f_sources["curseforge"].setChecked(True))
        row.addWidget(demo)
        row.addStretch(1)
        v.addLayout(row)
        self.results.addWidget(box)
        self.results.addStretch(1)
        self.count.setText("")

    def more(self):
        self.offset += self.limit
        self.fill()

    # -- mine
    def refresh_mine(self):
        body = QWidget()
        body.setObjectName("Page")
        grid = QGridLayout(body)
        grid.setContentsMargins(0, 0, 0, 16)
        grid.setSpacing(14)
        items = self.win.instances.items
        cols = max(1, (self.width() - 64) // 250)
        for i, inst in enumerate(items):
            grid.addWidget(InstanceCard(self.win, inst), i // cols, i % cols)
        add = QPushButton("+\nСоздать сборку")
        add.setObjectName("AddTile")
        add.setFixedSize(236, 210)
        add.clicked.connect(self.win.create_instance)
        n = len(items)
        grid.addWidget(add, n // cols, n % cols)
        grid.setRowStretch(n // cols + 1, 1)
        grid.setColumnStretch(cols, 1)
        self.mine_scroll.setWidget(body)

    def show_tab(self, key):
        self.tab_btns[key].setChecked(True)
        if key == "catalog":
            self.stack.setCurrentIndex(0)
            if not self.loaded_once and self.token == 0:
                self.research()
        else:
            self.refresh_mine()
            self.stack.setCurrentIndex(1)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.stack.currentIndex() == 1:
            QTimer.singleShot(0, self.refresh_mine)


# ---------------------------------------------------------------- accounts

class AddAccountDialog(QDialog):
    """Оффлайн (ник → UUID) or mc-ru.org (site login → Yggdrasil tokens). self.result_acc holds the created
    account after accept()."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.result_acc = None
        self.mode = "offline"
        self.setWindowTitle("Новый аккаунт")
        self.setFixedWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.addWidget(label("Новый аккаунт", "H2"))
        seg = QHBoxLayout()
        seg.setSpacing(0)
        self.seg = QButtonGroup(self)
        self.seg.setExclusive(True)
        self.off = QPushButton("Оффлайн")
        self.off.setObjectName("Seg")
        self.off.setCheckable(True)
        self.off.setChecked(True)
        self.site = QPushButton("mc-ru.org")
        self.site.setObjectName("Seg")
        self.site.setCheckable(True)
        ms = QPushButton("Microsoft · скоро")
        ms.setObjectName("Seg")
        ms.setEnabled(False)
        ms.setToolTip("Вход через Microsoft появится вместе с загрузкой игры")
        for b in (self.off, self.site, ms):
            seg.addWidget(b)
        self.seg.addButton(self.off)
        self.seg.addButton(self.site)
        self.off.toggled.connect(lambda on: on and self.set_mode("offline"))
        self.site.toggled.connect(lambda on: on and self.set_mode("mcru"))
        seg.addStretch(1)
        lay.addLayout(seg)
        self.hint = label("Оффлайн-аккаунт работает без лицензии: для одиночной игры и серверов в "
                          "оффлайн-режиме.", "Hint", wrap=True)
        self.hint.setOpenExternalLinks(True)
        lay.addWidget(self.hint)
        self.stack = QStackedWidget()
        lay.addWidget(self.stack)
        # offline
        card = QFrame()
        card.setObjectName("Box")
        h = QHBoxLayout(card)
        h.setContentsMargins(14, 14, 14, 14)
        self.head = QLabel()
        h.addWidget(self.head)
        col = QVBoxLayout()
        col.addWidget(label("Ник"))
        self.name = QLineEdit()
        self.name.setPlaceholderText("Steve_2009")
        self.name.setMaxLength(16)
        self.name.textChanged.connect(self.update_preview)
        self.name.returnPressed.connect(self._ok)
        col.addWidget(self.name)
        self.msg = label("3–16 символов: латинские буквы, цифры и «_»", "Hint")
        col.addWidget(self.msg)
        self.uuid = label("", "Hint")
        self.uuid.setTextInteractionFlags(Qt.TextSelectableByMouse)
        col.addWidget(self.uuid)
        h.addLayout(col, 1)
        self.stack.addWidget(card)
        # mc-ru.org
        box = QFrame()
        box.setObjectName("Box")
        v = QVBoxLayout(box)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(6)
        v.addWidget(label("Ник или email"))
        self.login = QLineEdit()
        self.login.setPlaceholderText("Steve_2009 или steve@example.com")
        self.login.textChanged.connect(self.update_preview)
        self.login.returnPressed.connect(self._ok)
        v.addWidget(self.login)
        v.addWidget(label("Пароль"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.textChanged.connect(self.update_preview)
        self.password.returnPressed.connect(self._ok)
        v.addWidget(self.password)
        self.site_msg = label("Вход на mc-ru.org: скин и плащ подтянутся в игру.", "Hint", wrap=True)
        v.addWidget(self.site_msg)
        self.stack.addWidget(box)
        row = QHBoxLayout()
        row.addStretch(1)
        c = QPushButton("Отмена")
        c.clicked.connect(self.reject)
        row.addWidget(c)
        self.ok = QPushButton("Создать")
        self.ok.setObjectName("Accent")
        self.ok.clicked.connect(self._ok)
        row.addWidget(self.ok)
        lay.addLayout(row)
        self.busy = False
        self.update_preview()

    def set_mode(self, mode):
        self.mode = mode
        self.stack.setCurrentIndex(0 if mode == "offline" else 1)
        if mode == "offline":
            self.hint.setText("Оффлайн-аккаунт работает без лицензии: для одиночной игры и серверов в "
                              "оффлайн-режиме.")
            self.ok.setText("Создать")
        else:
            self.hint.setText("Аккаунт сайта mc-ru.org: скин и плащ (в том числе HD и анимированные) подтянутся "
                              f"в игру. Нет аккаунта? <a href=\"{mcru.SITE}/#account\">Зарегистрируйтесь на "
                              "mc-ru.org</a>")
            self.ok.setText("Войти")
        self.update_preview()

    def _set_msg(self, w, text, kind):
        w.setText(text)
        w.setObjectName(kind)
        w.style().unpolish(w)
        w.style().polish(w)

    def update_preview(self):
        if self.mode == "mcru":
            self.ok.setEnabled(bool(self.login.text().strip()) and bool(self.password.text()) and not self.busy)
            return
        name = self.name.text().strip()
        self.head.setPixmap(pixel_head(name or "?", 64, 10))
        err = validate(name, self.win.accounts.names()) if name else None
        self.ok.setEnabled(bool(name) and err is None)
        if err:
            self._set_msg(self.msg, err, "Warn")
        else:
            self._set_msg(self.msg, "3–16 символов: латинские буквы, цифры и «_»" if not name else "Ник свободен ✓",
                          "Hint" if not name else "Ok")
        self.uuid.setText(f"UUID: {offline_uuid(name)}" if name and not err else "")

    def _ok(self):
        if not self.ok.isEnabled():
            return
        if self.mode == "offline":
            self.result_acc = self.win.accounts.add_offline(self.name.text().strip())
            self.accept()
            return
        login, password = self.login.text().strip(), self.password.text()
        self.busy = True
        self.ok.setEnabled(False)
        self._set_msg(self.site_msg, "Входим…", "Hint")

        def done(r):
            self.busy = False
            self.result_acc = self.win.accounts.add_mcru(r["name"], r["uuid"], r["access_token"],
                                                         r["client_token"], login)
            self.accept()

        def failed(e):
            self.busy = False
            self._set_msg(self.site_msg, str(e), "Warn")
            self.update_preview()

        self.win.runner.run(lambda: mcru.authenticate(login, password), done, failed)


class AccountsPage(QScrollArea):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)

    def refresh(self):
        body = QWidget()
        body.setObjectName("Page")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(32, 26, 32, 26)
        lay.setSpacing(12)
        head = QHBoxLayout()
        head.addWidget(label("Аккаунты", "Title"))
        head.addStretch(1)
        add = QPushButton("Добавить аккаунт")
        add.setObjectName("Accent")
        add.setIcon(icons.icon("plus", "#FFFFFF", "#FFFFFF"))
        add.clicked.connect(self.win.add_account)
        head.addWidget(add)
        lay.addLayout(head)
        lay.addWidget(label("Выберите, под каким ником играть. Аккаунт mc-ru.org приносит в игру скин и плащ; "
                            "вход через Microsoft появится позже.", "Muted", wrap=True))
        sel = self.win.settings.get("selected_account")
        if not self.win.accounts.items:
            empty = QFrame()
            empty.setObjectName("Box")
            v = QVBoxLayout(empty)
            v.setContentsMargins(24, 24, 24, 24)
            i = QLabel()
            i.setPixmap(pixel_head("Steve", 72, 12))
            v.addWidget(i, 0, Qt.AlignHCenter)
            v.addWidget(label("Аккаунтов пока нет", "H2"), 0, Qt.AlignHCenter)
            v.addWidget(label("Создайте оффлайн-аккаунт (нужен только ник) или войдите через mc-ru.org.", "Muted"),
                        0, Qt.AlignHCenter)
            b = QPushButton("Создать аккаунт")
            b.setObjectName("Accent")
            b.clicked.connect(self.win.add_account)
            v.addWidget(b, 0, Qt.AlignHCenter)
            lay.addWidget(empty)
        for a in self.win.accounts.items:
            on = a["uuid"] == sel
            card = QFrame()
            card.setObjectName("AccountCardOn" if on else "AccountCard")
            h = QHBoxLayout(card)
            h.setContentsMargins(14, 12, 14, 12)
            h.setSpacing(14)
            i = QLabel()
            set_head(self.win, i, a, 52, 9)
            h.addWidget(i)
            col = QVBoxLayout()
            col.setSpacing(2)
            top = QHBoxLayout()
            top.addWidget(label(a["name"], "CardTitle"))
            if a.get("type") == "mcru":
                top.addWidget(tag("mc-ru.org", "orange"))
            if on:
                top.addWidget(label("Выбран", "Badge"))
            top.addStretch(1)
            col.addLayout(top)
            col.addWidget(label(account_kind(a) + (f" · играли {ago(a['last_used'])}" if a.get("last_used") else ""),
                                "Muted"))
            u = label(a["uuid"], "Hint")
            u.setTextInteractionFlags(Qt.TextSelectableByMouse)
            col.addWidget(u)
            h.addLayout(col, 1)
            if not on:
                pick = QPushButton("Выбрать")
                pick.clicked.connect(lambda _=False, x=a["uuid"]: self.win.select_account(x))
                h.addWidget(pick)
            cp = QToolButton()
            cp.setIcon(ic("copy"))
            cp.setToolTip("Скопировать UUID")
            cp.clicked.connect(lambda _=False, x=a["uuid"]: QApplication.clipboard().setText(x))
            h.addWidget(cp)
            rm = QToolButton()
            rm.setIcon(ic("trash"))
            rm.setToolTip("Удалить аккаунт")
            rm.clicked.connect(lambda _=False, x=a: self.win.remove_account(x))
            h.addWidget(rm)
            lay.addWidget(card)
        lay.addStretch(1)
        self.setWidget(body)


# ---------------------------------------------------------------- settings

def find_java():
    """Java installations: macOS java_home list, $JAVA_HOME, `java` on PATH."""
    out = []
    if IS_MAC:
        try:
            r = subprocess.run(["/usr/libexec/java_home", "-V"], capture_output=True, text=True, timeout=5)
            for line in (r.stderr + r.stdout).splitlines():
                line = line.strip()
                if "/" in line and line[0].isdigit():
                    path = line[line.index("/"):]
                    out.append(path.rstrip("/") + "/bin/java")
        except Exception:
            pass
    import os

    exe = "java.exe" if sys.platform == "win32" else "java"
    if os.environ.get("JAVA_HOME"):
        out.append(os.path.join(os.environ["JAVA_HOME"], "bin", exe))
    if sys.platform == "win32":
        import glob

        for pf in {os.environ.get("ProgramFiles", r"C:\Program Files"),
                   os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")}:
            for vendor in ("Java", "Eclipse Adoptium", "Microsoft", "Zulu", "BellSoft", "Amazon Corretto"):
                out += sorted(glob.glob(os.path.join(pf, vendor, "*", "bin", "java.exe")), reverse=True)
    w = shutil.which("java")
    if w:
        out.append(w)
    seen = []
    for p in out:
        if p not in seen:
            seen.append(p)
    return seen


class SettingsPage(QScrollArea):
    def __init__(self, win):
        super().__init__()
        self.win = win
        s = win.settings
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body.setObjectName("Page")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(32, 26, 32, 26)
        lay.setSpacing(10)
        lay.addWidget(label("Настройки", "Title"))

        def section(t, icon):
            lay.addSpacing(10)
            row = QHBoxLayout()
            i = QLabel()
            i.setPixmap(icons.pixmap(icon, theme.CURRENT["text"], size=36))
            i.setFixedSize(18, 18)
            i.setScaledContents(True)
            row.addWidget(i)
            row.addWidget(label(t, "H3"))
            row.addStretch(1)
            lay.addLayout(row)

        def row(title, w, hint=None):
            r = QHBoxLayout()
            t = label(title)
            t.setFixedWidth(230)
            r.addWidget(t)
            r.addWidget(w, 1)
            lay.addLayout(r)
            if hint:
                h = label(hint, "Hint", wrap=True)
                h.setContentsMargins(234, 0, 0, 0)
                lay.addWidget(h)

        def check(title, key):
            c = QCheckBox(title)
            c.setChecked(bool(s.get(key)))
            c.toggled.connect(lambda v: (s.update({key: v}), s.save()))
            lay.addWidget(c)
            return c

        # ---- look
        section("Оформление", "cover")
        self._apply_timer = QTimer(self)
        self._apply_timer.setSingleShot(True)
        self._apply_timer.timeout.connect(win.apply_theme)

        def setv(**kw):
            s.update(kw)
            s.save()
            self._apply_timer.start(120)
            self._sync_look()

        th = QComboBox()
        for k, t in (("system", "Как в системе"), ("light", "Светлая"), ("dark", "Тёмная")):
            th.addItem(t, k)
        th.setCurrentIndex(max(0, th.findData(s.get("theme"))))
        th.currentIndexChanged.connect(lambda i: setv(theme=th.itemData(i)))
        row("Тема", th)
        acc = QWidget()
        al_ = QHBoxLayout(acc)
        al_.setContentsMargins(0, 0, 0, 0)
        al_.setSpacing(6)
        self.accent_btns = {}
        for key, (hexv, name) in theme.ACCENTS.items():
            b = QToolButton()
            b.setToolTip(name)
            b.setFixedSize(28, 28)
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, h=hexv: setv(accent=h))
            al_.addWidget(b)
            self.accent_btns[hexv] = b
        own = QPushButton("Свой…")
        own.clicked.connect(lambda: self._pick_accent(setv))
        al_.addWidget(own)
        al_.addStretch(1)
        row("Цвет акцента", acc)
        # window background
        bgw = QWidget()
        bgl = QGridLayout(bgw)
        bgl.setContentsMargins(0, 0, 0, 0)
        bgl.setSpacing(6)
        self.bg_btns = {}
        choices = [("none", "Без фона")] + [("scene:" + k, v) for k, v in backgrounds.SCENES.items()] + \
                  [(k, k) for k in ("terracotta", "ocean", "forest", "dusk", "plum", "graphite")] + \
                  [(g, "Ваша картинка") for g in backgrounds.gallery()[:4]]
        for n, (bg, tip) in enumerate(choices + [("+upload", "Загрузить картинку…")]):
            b = QToolButton()
            b.setToolTip(tip)
            b.setIconSize(QSize(64, 40))
            b.setCheckable(True)
            if bg == "+upload":
                b.setText("+ Своя")
                b.setFixedSize(72, 48)
                b.clicked.connect(lambda: self._upload_bg(setv))
            elif bg == "none":
                b.setText("Нет")
                b.setFixedSize(72, 48)
                b.clicked.connect(lambda _=False: setv(backdrop="none"))
            else:
                b.setIcon(backgrounds.swatch(bg, 64, 40))
                b.setFixedSize(72, 48)
                b.clicked.connect(lambda _=False, v=bg: setv(backdrop=v))
            bgl.addWidget(b, n // 8, n % 8)
            self.bg_btns[bg] = b
        bgl.setColumnStretch(8, 1)
        row("Фон окна", bgw, "Картинка или градиент за всеми страницами. Свою картинку можно загрузить.")
        self.glass = QCheckBox("Стекло — полупрозрачные панели поверх размытого фона")
        self.glass.setChecked(bool(s.get("glass")))
        self.glass.toggled.connect(lambda v: setv(glass=v, backdrop=s.get("backdrop") if s.get("backdrop", "none")
                                                  != "none" else "scene:aurora"))
        lay.addWidget(self.glass)
        op = QSlider(Qt.Horizontal)
        op.setRange(20, 95)
        op.setValue(int(float(s.get("glass_opacity", 0.6)) * 100))
        op.valueChanged.connect(lambda v: setv(glass_opacity=v / 100))
        row("Плотность стекла", op)
        bl = QSlider(Qt.Horizontal)
        bl.setRange(0, 60)
        bl.setValue(int(s.get("blur", 24)))
        bl.valueChanged.connect(lambda v: (s.update(blur=v), s.save(), win.backdrop.update()))
        row("Размытие фона", bl)
        ve = QSlider(Qt.Horizontal)
        ve.setRange(0, 60)
        ve.setValue(int(s.get("veil", 18)))
        ve.valueChanged.connect(lambda v: (s.update(veil=v), s.save(), win.backdrop.update()))
        row("Осветление / затемнение фона", ve)
        self.glass_rows = [op, bl, ve]
        hf = QComboBox()
        hf.addItem("С засечками (как у Claude)", True)
        hf.addItem("Без засечек", False)
        hf.setCurrentIndex(0 if s.get("serif_headings", True) else 1)
        hf.currentIndexChanged.connect(lambda i: setv(serif_headings=hf.itemData(i)))
        row("Заголовки", hf)
        side = QComboBox()
        side.addItem("Слева", "left")
        side.addItem("Справа", "right")
        side.setCurrentIndex(1 if s.get("sidebar_side") == "right" else 0)
        side.currentIndexChanged.connect(lambda i: setv(sidebar_side=side.itemData(i)))
        row("Боковая панель", side, "Скрыть и показать панель — кнопка «« / »» в её шапке или ⌘\\.")
        reset = QPushButton("Вернуть оформление по умолчанию")
        reset.clicked.connect(lambda: setv(accent="#D97757", backdrop="none", glass=False, glass_opacity=0.6,
                                           blur=24, veil=18, serif_headings=True, sidebar_side="left"))
        lay.addWidget(reset, 0, Qt.AlignLeft)
        self._sync_look()

        section("Игра", "cube")
        gd = QWidget()
        gl = QHBoxLayout(gd)
        gl.setContentsMargins(0, 0, 0, 0)
        self.game_dir = QLineEdit(str(s.game_dir()))
        self.game_dir.setReadOnly(True)
        gl.addWidget(self.game_dir, 1)
        pick = QPushButton("Выбрать…")
        pick.clicked.connect(self.pick_dir)
        gl.addWidget(pick)
        op = QToolButton()
        op.setIcon(ic("folder"))
        op.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(s.game_dir()))))
        gl.addWidget(op)
        row("Папка игры", gd)
        total = system_memory_mb()
        mem = QWidget()
        ml = QHBoxLayout(mem)
        ml.setContentsMargins(0, 0, 0, 0)
        self.mem = QSlider(Qt.Horizontal)
        self.mem.setRange(1, max(2, total // 1024))
        self.mem.setValue(max(1, int(s.get("memory_mb", 4096)) // 1024))
        self.mem_label = label("", "Muted")
        self.mem_label.setFixedWidth(130)
        self.mem.valueChanged.connect(self._mem)
        ml.addWidget(self.mem, 1)
        ml.addWidget(self.mem_label)
        row("Оперативная память", mem, "Для больших сборок нужно 6–8 ГБ; оставьте системе хотя бы 2–4 ГБ.")
        self._mem(self.mem.value())
        jv = QWidget()
        jl = QHBoxLayout(jv)
        jl.setContentsMargins(0, 0, 0, 0)
        self.java = QComboBox()
        self.java.setEditable(True)
        self.java.addItem("Автоматически (подходящая Java для версии игры)", "")
        for p in find_java():
            self.java.addItem(p, p)
        if s.get("java_path"):
            if self.java.findData(s["java_path"]) < 0:
                self.java.addItem(s["java_path"], s["java_path"])
            self.java.setCurrentIndex(self.java.findData(s["java_path"]))
        self.java.currentIndexChanged.connect(lambda i: (s.update(java_path=self.java.itemData(i) or ""), s.save()))
        jl.addWidget(self.java, 1)
        browse = QPushButton("Обзор…")
        browse.clicked.connect(self.pick_java)
        jl.addWidget(browse)
        row("Java", jv, "«Автоматически» — Эта скачает ту же Java, что и официальный лаунчер (8, 16, 17 или 21 — "
                        "по версии игры), в свою папку. Или укажите свою.")
        args = QLineEdit(s.get("jvm_args", ""))
        args.editingFinished.connect(lambda: (s.update(jvm_args=args.text().strip()), s.save()))
        row("Аргументы JVM", args)
        res = QWidget()
        rl = QHBoxLayout(res)
        rl.setContentsMargins(0, 0, 0, 0)
        w = QSpinBox()
        w.setRange(640, 7680)
        w.setValue(int(s.get("width", 1280)))
        hh = QSpinBox()
        hh.setRange(480, 4320)
        hh.setValue(int(s.get("height", 720)))
        w.valueChanged.connect(lambda v: (s.update(width=v), s.save()))
        hh.valueChanged.connect(lambda v: (s.update(height=v), s.save()))
        rl.addWidget(w)
        rl.addWidget(label("×"))
        rl.addWidget(hh)
        rl.addStretch(1)
        row("Размер окна игры", res)
        check("Запускать на весь экран", "fullscreen")
        check("HD-скины и плащи в игре (CustomSkinLoader для аккаунтов mc-ru.org)", "csl_skins")

        section("Лаунчер", "settings")
        lang = QComboBox()
        lang.addItem("Русский")
        lang.setEnabled(False)
        row("Язык", lang)
        check("Сворачивать лаунчер, когда игра запущена", "close_on_launch")
        check("Показывать консоль игры", "show_console")
        check("Проверять обновления лаунчера", "check_updates")

        section("Загрузки", "download")
        src = QComboBox()
        for k, t in SOURCES.items():
            src.addItem(t, k)
        src.setCurrentIndex(max(0, src.findData(s.get("default_source"))))
        src.currentIndexChanged.connect(lambda i: (s.update(default_source=src.itemData(i)), s.save()))
        row("Источник по умолчанию", src)
        par = QSpinBox()
        par.setRange(1, 32)
        par.setValue(int(s.get("parallel_downloads", 6)))
        par.valueChanged.connect(lambda v: (s.update(parallel_downloads=v), s.save()))
        row("Одновременных загрузок", par)

        section("О программе", "logo")
        lay.addWidget(label(f"{APP_NAME} {__version__} · интерфейс лаунчера. Данные: {data_dir()}", "Hint", wrap=True))
        lay.addWidget(label("Minecraft — торговая марка Mojang Studios. Эта не связана с Mojang и Microsoft.", "Hint",
                            wrap=True))
        lay.addStretch(1)
        self.setWidget(body)

    def _sync_look(self):
        s = self.win.settings
        self.glass.blockSignals(True)
        self.glass.setChecked(bool(s.get("glass")))
        self.glass.blockSignals(False)
        acc = s.get("accent") or "#D97757"
        for hexv, b in self.accent_btns.items():
            on = hexv.lower() == acc.lower()
            b.setChecked(on)
            b.setStyleSheet(f"QToolButton {{ background: {hexv}; border-radius: 14px;"
                            f" border: {'3px solid ' + theme.CURRENT['text'] if on else '1px solid transparent'}; }}")
        cur = s.get("backdrop") or "none"
        for bg, b in self.bg_btns.items():
            b.setChecked(bg == cur)
        glass_ok = cur != "none"
        for w in self.glass_rows:
            w.setEnabled(glass_ok)

    def _pick_accent(self, setv):
        from PySide6.QtWidgets import QColorDialog

        col = QColorDialog.getColor(QColor(self.win.settings.get("accent") or "#D97757"), self, "Цвет акцента")
        if col.isValid():
            setv(accent=col.name().upper())

    def _upload_bg(self, setv):
        path, _ = QFileDialog.getOpenFileName(self, "Картинка для фона", "",
                                              "Картинки (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        if path:
            setv(backdrop=backgrounds.import_image(path))

    def _mem(self, gb):
        total = system_memory_mb() // 1024
        self.mem_label.setText(f"{gb} ГБ из {total} ГБ")
        self.win.settings["memory_mb"] = gb * 1024
        self.win.settings.save()

    def pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Папка игры", str(self.win.settings.game_dir()))
        if d:
            self.win.settings["game_dir"] = d
            self.win.settings.save()
            self.game_dir.setText(d)

    def pick_java(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите java")
        if path:
            self.java.addItem(path, path)
            self.java.setCurrentIndex(self.java.count() - 1)


# ---------------------------------------------------------------- window

class GameProcess(QObject):
    """A running Minecraft: its output line by line and the exit code, delivered on the Qt thread."""

    line = Signal(str)
    exited = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.proc = None
        self.started = time.time()
        self.stopped = False

    def start(self, cmd, cwd, env):
        self.started = time.time()
        extra = ({"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32"
                 else {"start_new_session": True})
        self.proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, text=True, errors="replace", **extra)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        # lines are batched: a game that floods its log (Forge's early display on a broken GL setup writes
        # millions of lines) must not flood the Qt event loop with one signal per line
        buf, last = [], time.monotonic()
        for ln in self.proc.stdout:
            buf.append(ln.rstrip("\n"))
            if len(buf) >= 200 or time.monotonic() - last > 0.1:
                self.line.emit("\n".join(buf[-200:]))
                buf, last = [], time.monotonic()
        if buf:
            self.line.emit("\n".join(buf[-200:]))
        self.exited.emit(self.proc.wait())

    def stop(self):
        self.stopped = True
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

    def running(self):
        return self.proc is not None and self.proc.poll() is None


class _LaunchProgress(QObject):
    changed = Signal(str, int, int, str)
    logged = Signal(str)


class LaunchDialog(QDialog):
    """Gets the game ready (version, Java, loader, libraries, assets) with a progress bar, then starts it and shows
    its console. The dialog stays alive while the game runs; closing it just hides it."""

    SPAN = {"version": (0, 3), "java": (3, 25), "loader": (25, 38), "libraries": (38, 55), "assets": (55, 92),
            "auth": (92, 97), "launch": (97, 100)}

    def __init__(self, win, inst, acc):
        super().__init__(win)
        self.win = win
        self.inst = inst
        self.acc = acc
        self.setWindowTitle(f"Запуск — {inst['name']}")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        head = QHBoxLayout()
        i = QLabel()
        set_icon(win, i, inst.get("icon_url"), inst["icon"], 48)
        head.addWidget(i)
        col = QVBoxLayout()
        col.addWidget(label(inst["name"], "H2"))
        col.addWidget(label(f"{describe(inst)} · {acc['name']}", "Muted"))
        head.addLayout(col, 1)
        lay.addLayout(head)
        self.stage = label("Готовим игру…", "H3")
        lay.addWidget(self.stage)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        lay.addWidget(self.bar)
        self.detail = label("", "Hint", wrap=True)
        lay.addWidget(self.detail)
        self.console = QPlainTextEdit()
        self.console.setObjectName("Console")
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(4000)
        self.console.setMinimumHeight(220)
        self.console.setVisible(bool(win.settings.get("show_console")))
        lay.addWidget(self.console, 1)
        row = QHBoxLayout()
        self.console_btn = QPushButton("Консоль")
        self.console_btn.setCheckable(True)
        self.console_btn.setChecked(self.console.isVisible())
        self.console_btn.toggled.connect(self._toggle_console)
        row.addWidget(self.console_btn)
        folder = QPushButton("Папка сборки")
        folder.clicked.connect(lambda: win.open_instance_folder(inst))
        row.addWidget(folder)
        row.addStretch(1)
        self.hide_btn = QPushButton("Скрыть")
        self.hide_btn.clicked.connect(self.hide)
        self.hide_btn.hide()
        row.addWidget(self.hide_btn)
        self.stop_btn = QPushButton("Отмена")
        self.stop_btn.clicked.connect(self.cancel)
        row.addWidget(self.stop_btn)
        lay.addLayout(row)
        self.phase = "prepare"
        self.cancelled = False
        self.game = None
        self.result = None
        self.progress = _LaunchProgress()
        self.progress.changed.connect(self._progress)
        self.progress.logged.connect(self._log)
        s = win.settings
        inst_dir = s.game_dir() / "instances" / inst["id"]

        def job():
            g = launch.Game(s.game_dir(), progress=self.progress.changed.emit, cancel=lambda: self.cancelled,
                            log=self.progress.logged.emit, workers=int(s.get("parallel_downloads", 6)))
            return g.prepare(inst, acc, s, inst_dir)

        win.runner.run(job, self._ready, self._failed)

    def _toggle_console(self, on):
        self.console.setVisible(on)
        self.adjustSize()

    def _log(self, line):
        self.console.appendPlainText(line)

    def _progress(self, stage, done, total, text):
        lo, hi = self.SPAN.get(stage, (0, 100))
        frac = done / total if total else 0.0
        self.bar.setValue(int(lo + (hi - lo) * frac))
        names = {"version": "Сведения о версии", "java": "Java", "loader": "Загрузчик модов",
                 "libraries": "Библиотеки игры", "assets": "Ресурсы игры", "auth": "Вход mc-ru.org",
                 "launch": "Запуск"}
        self.stage.setText(names.get(stage, stage) + "…")
        self.detail.setText(f"{text} — {done} из {total}" if total and total > 1 else text)

    def _ready(self, r):
        self.result = r
        if self.cancelled:
            self.reject()
            return
        if r.get("loader_version") and r["loader_version"] != self.inst.get("loader_version"):
            self.win.instances.update(self.inst["id"], loader_version=r["loader_version"])
        if r.get("account"):
            a = r["account"]
            self.win.accounts.update(a["uuid"], access_token=a.get("access_token"), client_token=a.get("client_token"),
                                     name=a.get("name", self.acc["name"]))
        self._log("[eta] " + " ".join(r["cmd"]))
        self.game = GameProcess(self)
        self.game.line.connect(self._log, Qt.QueuedConnection)
        self.game.exited.connect(self._exited, Qt.QueuedConnection)
        try:
            self.game.start(r["cmd"], r["cwd"], r["env"])
        except OSError as e:
            self._failed(e)
            return
        self.phase = "running"
        self.win.games[self.inst["id"]] = self.game
        self.win.instances.update(self.inst["id"], last_played=time.time())
        discord_rpc.update(details=self.inst["name"], state="Играет", start_ts=int(time.time()))
        self.win.refresh()
        self.bar.setValue(100)
        self.stage.setText("Игра запущена")
        self.detail.setText(f"Minecraft {r['version']} · {Path(r['java']).parent.parent.name or 'Java'}")
        self.stop_btn.setText("Остановить игру")
        self.hide_btn.show()
        if self.win.settings.get("close_on_launch"):
            self.win.hide()
        if not self.win.settings.get("show_console"):
            self.hide()

    def _exited(self, code):
        self.phase = "done"
        self.win.games.pop(self.inst["id"], None)
        discord_rpc.clear()
        minutes = int((time.time() - self.game.started) // 60) if self.game else 0
        cur = self.win.instances.get(self.inst["id"]) or {}
        self.win.instances.update(self.inst["id"], playtime_min=int(cur.get("playtime_min") or 0) + minutes,
                                  last_played=time.time())
        self.win.show()
        self.win.raise_()
        self.win.refresh()
        self.stop_btn.setText("Закрыть")
        self.hide_btn.hide()
        if code and not (self.game and self.game.stopped):
            self.stage.setText(f"Игра завершилась с ошибкой (код {code})")
            self.detail.setText("Посмотрите конец журнала ниже; подробности также в папке сборки → .minecraft/logs.")
            self.console_btn.setChecked(True)
            self.show()
        else:
            self.stage.setText("Игра закрыта")
            if not self.isVisible():
                self.accept()

    def _failed(self, e):
        self.phase = "failed"
        self.stage.setText("Не получилось запустить")
        self.detail.setText(str(e))
        self.detail.setObjectName("Warn")
        self.detail.style().unpolish(self.detail)
        self.detail.style().polish(self.detail)
        self.console_btn.setChecked(True)
        self.stop_btn.setText("Закрыть")
        self.show()

    def cancel(self):
        if self.phase == "prepare":
            self.cancelled = True
            self.detail.setText("Отменяем…")
            self.stop_btn.setEnabled(False)
        elif self.phase == "running":
            self.game.stop()
            self.detail.setText("Останавливаем игру…")
        else:
            self.accept()

    def reject(self):
        if self.phase == "prepare":
            self.cancel()
        elif self.phase == "running":
            self.hide()
        else:
            super().reject()

    def closeEvent(self, e):
        if self.phase in ("prepare", "running"):
            self.reject()
            e.ignore()
            return
        super().closeEvent(e)


class Backdrop(QWidget):
    """Paints the window background (picture / gradient), blurred and veiled for the glass look."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self._light = {}

    def paintEvent(self, _):
        c = theme.CURRENT
        bg = c.get("backdrop", "none")
        p = QPainter(self)
        if bg == "none":
            p.fillRect(self.rect(), QColor(c.get("dialog", "#FAF9F5")))
            p.end()
            return
        dpr = self.devicePixelRatioF()
        w, h = max(1, int(self.width() * dpr)), max(1, int(self.height() * dpr))
        if c.get("glass"):
            pix = backgrounds.blurred(bg, w, h, int(self.win.settings.get("blur", 24) * dpr))
        else:
            pix = backgrounds._scaled(bg, w, h) if backgrounds.is_picture(bg) else None
            if pix is None or pix.isNull():
                backgrounds.paint(p, self.rect(), bg)
                pix = None
        if pix is not None:
            p.drawPixmap(self.rect(), pix)
        veil = int(self.win.settings.get("veil", 18))
        dark = c["name"] == "dark"
        if self._light.get(bg) is None:
            self._light[bg] = backgrounds.is_light(bg)
        if self._light[bg] == dark:   # dark picture under the light theme (or the other way): keep text readable
            veil += 40
        if dark:
            p.fillRect(self.rect(), QColor(0, 0, 0, int(255 * min(85, veil + 18) / 100)))
        else:
            p.fillRect(self.rect(), QColor(250, 249, 245, int(255 * min(85, veil) / 100)))
        p.end()


class MainWindow(QMainWindow):
    def __init__(self, app, settings=None, accounts=None, instances=None, provider=None):
        super().__init__()
        self.app = app
        self.settings = settings or Settings()
        self.accounts = accounts or AccountStore()
        self.instances = instances or InstanceStore()
        from .modrinth import ModrinthProvider

        self.providers = {"modrinth": provider or ModrinthProvider(), "curseforge": DemoProvider()}
        self.games = {}        # instance id → GameProcess while it runs
        self.launches = {}     # instance id → LaunchDialog (kept alive: it owns the process)
        self.provider = self.providers["modrinth"]
        self.runner = net.Runner(int(self.settings.get("parallel_downloads", 6)))
        self.icons = net.IconCache(self.runner)
        self.setWindowTitle(APP_NAME)
        self.setObjectName("Main")
        self.resize(1240, 800)
        self.setMinimumSize(980, 640)
        self.apply_theme(rebuild=False)
        self.backdrop = Backdrop(self)
        bl = QVBoxLayout(self.backdrop)
        bl.setContentsMargins(0, 0, 0, 0)
        self.root = QStackedWidget()
        bl.addWidget(self.root)
        self.setCentralWidget(self.backdrop)
        self.splash = SplashPage()
        self.splash.finished.connect(self.show_main)
        self.root.addWidget(self.splash)
        shell = QWidget()
        self.shell_lay = QHBoxLayout(shell)
        self.shell_lay.setContentsMargins(0, 0, 0, 0)
        self.shell_lay.setSpacing(0)
        self.side = QFrame()
        self.side.setFixedWidth(210)
        self.side_lay = QVBoxLayout(self.side)
        self.side_lay.setContentsMargins(12, 18, 12, 14)
        self.side_lay.setSpacing(3)
        self.rail = QFrame()
        self.rail.setFixedWidth(56)
        self.rail_lay = QVBoxLayout(self.rail)
        self.rail_lay.setContentsMargins(8, 16, 8, 12)
        self.rail_lay.setSpacing(6)
        self.pages = QStackedWidget()
        self.root.addWidget(shell)
        self.home = HomePage(self)
        self.modpacks = ModpacksPage(self)
        self.accounts_page = AccountsPage(self)
        self.settings_page = SettingsPage(self)
        self._mods_page = ModsPage(self)
        for p in (self.home, self.modpacks, self.accounts_page, self.settings_page, self._mods_page):
            self.pages.addWidget(p)
        discord_rpc.start()
        self.place_side()
        self.build_side()
        for keys, fn in (("Ctrl+1", lambda: self.go("home")), ("Ctrl+2", lambda: self.go("modpacks")),
                         ("Ctrl+3", lambda: self.go("accounts")), ("Ctrl+,", lambda: self.go("settings")),
                         ("Ctrl+\\", self.toggle_sidebar)):
            sc = QShortcut(QKeySequence(keys), self)
            sc.activated.connect(fn)

    def start(self, fast=False):
        self.root.setCurrentWidget(self.splash)
        self.splash.start(fast)

    def show_main(self):
        self.root.setCurrentIndex(1)
        self.go("home" if self.accounts.items else "accounts")

    # -- theme / side bar
    def apply_theme(self, rebuild=True):
        mode = self.settings.get("theme", "system")
        if mode == "system":
            try:
                dark = self.app.styleHints().colorScheme() == Qt.ColorScheme.Dark
            except Exception:
                dark = self.app.palette().window().color().lightness() < 128
        else:
            dark = mode == "dark"
        colors = theme.compose(theme.DARK if dark else theme.LIGHT, self.settings)
        theme.use(colors)
        self.app.setStyleSheet(theme.stylesheet(colors))
        if rebuild:
            self.place_side()
            self.build_side()
            self.refresh()
            self.settings_page._sync_look()
            self.backdrop.update()

    def place_side(self):
        """Side bar (or its icon rail when hidden) on the left or on the right of the pages."""
        right = self.settings.get("sidebar_side") == "right"
        for w in (self.side, self.rail, self.pages):
            self.shell_lay.removeWidget(w)
        order = [self.pages, self.side, self.rail] if right else [self.side, self.rail, self.pages]
        for w in order:
            self.shell_lay.addWidget(w, 1 if w is self.pages else 0)
        for w in (self.side, self.rail):
            w.setObjectName("SideR" if right else "Side")
            w.style().unpolish(w)
            w.style().polish(w)
        hidden = bool(self.settings.get("sidebar_hidden"))
        self.side.setVisible(not hidden)
        self.rail.setVisible(hidden)

    def toggle_sidebar(self):
        self.settings["sidebar_hidden"] = not self.settings.get("sidebar_hidden")
        self.settings.save()
        self.place_side()
        self.build_side()
        self.go(getattr(self, "current_page", "home"))

    def build_side(self):
        right = self.settings.get("sidebar_side") == "right"
        clear_layout(self.rail_lay)
        logo = label(LOGO, "Gamma")
        logo.setAlignment(Qt.AlignCenter)
        self.rail_lay.addWidget(logo)
        expand = QToolButton()
        expand.setObjectName("CollapseBtn")
        expand.setText("«" if right else "»")
        expand.setToolTip("Показать панель  ⌘\\")
        expand.clicked.connect(self.toggle_sidebar)
        self.rail_lay.addWidget(expand, 0, Qt.AlignHCenter)
        self.rail_nav = {}
        for key, tip, icon in (("home", "Главная", "home"), ("modpacks", "Сборки", "cube"),
                               ("accounts", "Аккаунты", "user"), ("settings", "Настройки", "settings")):
            b = QToolButton()
            b.setIcon(ic(icon))
            b.setIconSize(QSize(18, 18))
            b.setToolTip(tip)
            b.setCheckable(True)
            b.setFixedSize(38, 34)
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            self.rail_lay.addWidget(b, 0, Qt.AlignHCenter)
            self.rail_nav[key] = b
        self.rail_lay.addStretch(1)
        acc = self.account()
        head = QToolButton()
        head.setIcon(QIcon(pixel_head(acc["name"] if acc else "?", 30, 6)))
        if acc and acc.get("type") == "mcru":
            self.icons.get(mcru.head_url(acc["name"]),
                           lambda pix, b=head: b.setIcon(QIcon(skin_head(pix, 30, 6) or pixel_head(acc["name"], 30, 6))))
        head.setIconSize(QSize(30, 30))
        head.setToolTip(acc["name"] if acc else "Добавить аккаунт")
        head.clicked.connect(lambda: self.go("accounts"))
        self.rail_lay.addWidget(head, 0, Qt.AlignHCenter)

        clear_layout(self.side_lay)
        brand = QHBoxLayout()
        brand.addWidget(label(LOGO, "Gamma"))
        brand.addWidget(label(APP_NAME, "Logo"))
        brand.addStretch(1)
        hide = QToolButton()
        hide.setObjectName("CollapseBtn")
        hide.setText("»" if right else "«")
        hide.setToolTip("Скрыть панель  ⌘\\")
        hide.clicked.connect(self.toggle_sidebar)
        brand.addWidget(hide)
        self.side_lay.addLayout(brand)
        self.side_lay.addSpacing(14)
        self.nav = {}
        for key, text, icon in (("home", "Главная", "home"), ("modpacks", "Сборки", "cube"),
                                ("accounts", "Аккаунты", "user"), ("settings", "Настройки", "settings")):
            b = QPushButton(text)
            b.setIcon(ic(icon))
            b.setIconSize(QSize(16, 16))
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=key: self.go(k))
            self.side_lay.addWidget(b)
            self.nav[key] = b
        self.side_lay.addStretch(1)
        chip = QPushButton()
        chip.setObjectName("AccountChip")
        chip.setCursor(Qt.PointingHandCursor)
        cl = QHBoxLayout(chip)
        cl.setContentsMargins(8, 6, 8, 6)
        hd = QLabel()
        set_head(self, hd, acc, 30, 6)
        hd.setAttribute(Qt.WA_TransparentForMouseEvents)
        cl.addWidget(hd)
        col = QVBoxLayout()
        col.setSpacing(0)
        n = label(acc["name"] if acc else "Нет аккаунта", "ChipName")
        t = label(("mc-ru.org" if acc.get("type") == "mcru" else "Оффлайн") if acc else "Добавить…", "Hint")
        for w in (n, t):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
            col.addWidget(w)
        cl.addLayout(col, 1)
        chip.setMinimumHeight(48)
        chip.clicked.connect(lambda: self.go("accounts"))
        self.side_lay.addWidget(chip)

    def go(self, key):
        page = {"home": self.home, "modpacks": self.modpacks, "accounts": self.accounts_page,
                "settings": self.settings_page}[key]
        self.current_page = key
        if key == "home":
            self.home.refresh()
        elif key == "accounts":
            self.accounts_page.refresh()
        elif key == "modpacks" and self.modpacks.stack.currentIndex() == 1:
            self.modpacks.refresh_mine()
        self.pages.setCurrentWidget(page)
        for d in (self.nav, getattr(self, "rail_nav", {})):
            for k, b in d.items():
                b.setChecked(k == key)

    def refresh(self):
        key = getattr(self, "current_page", "home")
        self.build_side()
        self.go(key)

    # -- accounts
    def account(self):
        a = self.accounts.get(self.settings.get("selected_account"))
        if not a and self.accounts.items:
            a = self.accounts.items[0]
        return a

    def add_account(self):
        dlg = AddAccountDialog(self)
        if dlg.exec() and dlg.result_acc:
            self.select_account(dlg.result_acc["uuid"])
            return dlg.result_acc
        return None

    def select_account(self, uid):
        self.settings["selected_account"] = uid
        self.settings.save()
        self.refresh()

    def remove_account(self, a):
        if QMessageBox.question(self, "Удалить аккаунт", f"Удалить аккаунт «{a['name']}»?") != QMessageBox.Yes:
            return
        if a.get("type") == "mcru" and a.get("access_token"):
            tok, ct = a["access_token"], a.get("client_token", "")
            self.runner.run(lambda: mcru.invalidate(tok, ct), None, lambda e: None)
        self.accounts.remove(a["uuid"])
        if self.settings.get("selected_account") == a["uuid"]:
            self.settings["selected_account"] = self.accounts.items[0]["uuid"] if self.accounts.items else ""
            self.settings.save()
        self.refresh()

    # -- instances
    def instance(self):
        i = self.instances.get(self.settings.get("selected_instance"))
        if not i and self.instances.items:
            i = self.instances.items[0]
        return i

    def select_instance(self, iid, go_home=True):
        self.settings["selected_instance"] = iid
        self.settings.save()
        if go_home:
            self.go("home")
        else:
            self.refresh()

    def create_instance(self):
        dlg = CreateInstanceDialog(self)
        if dlg.exec():
            name = dlg.name.text().strip()
            from .instances import new_id
            iid = new_id()
            saved_icon_path = None
            if dlg.icon_path:
                saved_icon_path = self._save_instance_icon(iid, dlg.icon_path)
            inst = self.instances.add(name, dlg.version.currentData(), dlg.loader, icon=name, iid=iid,
                                      icon_path=saved_icon_path or "")
            self.select_instance(inst["id"], go_home=False)
            return inst
        self.home.hero.set_instance(self.instance())
        return None

    def _save_instance_icon(self, iid, src_path):
        """Copy & scale src_path to data_dir/icons/<iid>.png, return the dest path string."""
        from PySide6.QtGui import QImage
        icons_dir = data_dir() / "icons"
        icons_dir.mkdir(parents=True, exist_ok=True)
        dest = icons_dir / f"{iid}.png"
        img = QImage(src_path)
        if img.isNull():
            return None
        img = img.scaled(128, 128, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        img.save(str(dest), "PNG")
        return str(dest)

    def set_instance_icon(self, inst):
        path, _ = QFileDialog.getOpenFileName(self, "Выбрать иконку", "", "Изображения (*.png *.jpg *.jpeg *.webp)")
        if not path:
            return
        saved = self._save_instance_icon(inst["id"], path)
        if saved:
            self.instances.update(inst["id"], icon_path=saved)
            self.refresh()

    def rename_instance(self, inst):
        name, ok = QInputDialog.getText(self, "Сборка", "Название:", text=inst["name"])
        if ok and name.strip():
            self.instances.update(inst["id"], name=name.strip())
            self.refresh()

    def copy_instance(self, inst):
        self.instances.add(inst["name"] + " (копия)", inst["mc_version"], inst["loader"], inst.get("source", "own"),
                           inst.get("project"), inst.get("mods", 0), inst.get("icon"))
        self.refresh()

    def delete_instance(self, inst):
        dlg = QMessageBox(self)
        dlg.setWindowTitle("Удалить сборку")
        dlg.setText(f"Удалить сборку «{inst['name']}» и её папку на диске?\nЭто действие необратимо.")
        dlg.setStandardButtons(QMessageBox.Cancel | QMessageBox.Yes)
        dlg.setDefaultButton(QMessageBox.Cancel)
        dlg.button(QMessageBox.Cancel).setText("Отмена")
        dlg.button(QMessageBox.Yes).setText("Удалить")
        if dlg.exec() != QMessageBox.Yes:
            return
        inst_path = self.settings.game_dir() / "instances" / inst["id"]
        if inst_path.exists():
            try:
                if IS_MAC:
                    subprocess.run(["osascript", "-e",
                                    f'tell application "Finder" to delete POSIX file "{inst_path}"'],
                                   check=False, capture_output=True)
                else:
                    try:
                        from send2trash import send2trash
                        send2trash(str(inst_path))
                    except Exception:
                        shutil.rmtree(inst_path, ignore_errors=True)
            except Exception:
                shutil.rmtree(inst_path, ignore_errors=True)
        self.instances.remove(inst["id"])
        if self.settings.get("selected_instance") == inst["id"]:
            self.settings["selected_instance"] = ""
            self.settings.save()
        self.refresh()

    def manage_mods(self, inst):
        self._mods_page.set_instance(inst)
        self.pages.setCurrentWidget(self._mods_page)

    def open_instance_folder(self, inst):
        path = self.settings.game_dir() / "instances" / inst["id"]
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def open_project(self, provider, slug):
        ProjectDialog(self, provider, slug).exec()

    def install_project(self, provider, slug, version=None):
        p = (provider.cached(slug) if hasattr(provider, "cached") else None) or provider.project(slug)
        if not p:
            return None
        dlg = InstallDialog(self, provider, p, version)
        if dlg.exec() and dlg.result_inst:
            self.select_instance(dlg.result_inst["id"], go_home=False)
            self.modpacks.show_tab("mine")
            return dlg.result_inst
        return None

    def launch(self, inst):
        if not inst:
            return
        acc = self.account()
        if not acc:
            QMessageBox.information(self, "Аккаунт", "Сначала создайте аккаунт — нужен только ник.")
            self.go("accounts")
            return
        if inst["id"] in self.games:
            dlg = self.launches.get(inst["id"])
            if dlg:
                dlg.show()
                dlg.raise_()
            return
        self.accounts.touch(acc["uuid"])
        old = self.launches.pop(inst["id"], None)
        if old:
            old.deleteLater()
        dlg = LaunchDialog(self, inst, acc)
        self.launches[inst["id"]] = dlg
        dlg.show()
        return dlg

    def closeEvent(self, event):
        discord_rpc.stop()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("Lotus")
    icon_file = resource_path("assets", "icon.png")
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))
    win = MainWindow(app)
    try:
        app.styleHints().colorSchemeChanged.connect(lambda *_: win.apply_theme())
    except Exception:
        pass
    win.show()
    win.start()
    return app.exec()

