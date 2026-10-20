"""Claude-like look (shared with the other apps of the repo): ivory / charcoal, terracotta accent, serif headings.
LABEL_COLORS tint loader / category tags; BACKGROUNDS paint instance banners."""

LIGHT = dict(
    name="light",
    bg="#FAF9F5", sidebar="#F0EEE6", panel="#F0EEE6", card="#FFFFFF", border="#E3DFD3", text="#141413",
    muted="#6F6E69", faint="#A8A59C", accent="#D97757", accent_hover="#C6613F", accent_text="#FFFFFF",
    selected="#E6E2D6", hover="#E9E6DC", input="#FFFFFF", ok="#4E8A5A", warn="#B5642E",
        rec="#D64545", dim="#99141413", list="#F0EEE6", list_text="#141413", shadow="#1A141413",
    due_soon="#E8B23A", overdue="#D64545", done="#4E8A5A",
)

DARK = dict(
    name="dark",
    bg="#262624", sidebar="#1F1E1D", panel="#1F1E1D", card="#30302E", border="#3E3D39", text="#F4F2EC",
    muted="#A6A39A", faint="#6E6C66", accent="#D97757", accent_hover="#E08A6D", accent_text="#FFFFFF",
    selected="#3A3936", hover="#34332F", input="#262624", ok="#7BB487", warn="#E59866",
        rec="#E05A5A", dim="#99141413", list="#1F1E1D", list_text="#F4F2EC", shadow="#40000000",
    due_soon="#E8B23A", overdue="#E05A5A", done="#7BB487",
)

# Trello's ten label colours, muted
LABEL_COLORS = {
    "green": ("#7BA05B", "Зелёный"), "yellow": ("#E8B23A", "Жёлтый"), "orange": ("#E08A4A", "Оранжевый"),
    "red": ("#D6584B", "Красный"), "purple": ("#9B7BC4", "Фиолетовый"), "blue": ("#5B8CC4", "Синий"),
    "sky": ("#5DAFC4", "Голубой"), "lime": ("#9CC45B", "Салатовый"), "pink": ("#D97BA6", "Розовый"),
    "black": ("#5E5D59", "Графит"),
}
# board backgrounds: solid colours and two-stop gradients
BACKGROUNDS = {
    "terracotta": ("#D97757", "#C6613F"), "ocean": ("#3B6A8F", "#5B8CC4"), "forest": ("#4E7A50", "#7BA05B"),
    "dusk": ("#3B4A6B", "#D97757"), "plum": ("#6B4A7A", "#9B7BC4"), "sand": ("#C9B48A", "#E3D5B8"),
    "graphite": ("#3E3D39", "#5E5D59"), "rose": ("#B5647A", "#D97BA6"), "sky": ("#5DAFC4", "#A8D4DE"),
    "ivory": ("#E9E6DC", "#F0EEE6"),
}

SERIF = '"Georgia", "Tiempos Text", "Times New Roman", serif'


def stylesheet(c):
    return f"""
* {{ color: {c['text']}; font-size: 12px; }}
QMainWindow, #Main {{ background: {c['bg']}; }}
QDialog {{ background: {c['bg']}; }}
QToolTip {{ background: {c['card']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 4px; }}
#Side {{ background: {c['sidebar']}; border-right: 1px solid {c['border']}; }}
#Side QPushButton {{ text-align: left; border: none; background: transparent; padding: 7px 10px; border-radius: 7px; }}
#Side QPushButton:hover {{ background: {c['hover']}; }}
#Side QPushButton:checked {{ background: {c['selected']}; }}
#Gamma {{ color: {c['accent']}; font-family: {SERIF}; font-style: italic; font-size: 30px; }}
#Logo {{ font-family: {SERIF}; font-size: 17px; }}
#Title {{ font-family: {SERIF}; font-size: 28px; }}
#H2 {{ font-family: {SERIF}; font-size: 18px; }}
#Section {{ color: {c['muted']}; font-size: 10px; font-weight: 600; letter-spacing: 1px; }}
#Muted {{ color: {c['muted']}; }}
#Hint {{ color: {c['muted']}; font-size: 11px; }}
#Warn {{ color: {c['warn']}; font-size: 11px; }}
#Ok {{ color: {c['ok']}; font-size: 11px; }}
#Sep {{ background: {c['border']}; }}
#Page {{ background: {c['bg']}; }}

QPushButton {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 7px; padding: 5px 12px; }}
QPushButton:hover {{ background: {c['hover']}; }}
QPushButton:disabled {{ color: {c['faint']}; }}
QPushButton#Accent {{ background: {c['accent']}; color: {c['accent_text']}; border: none; font-weight: 600; }}
QPushButton#Accent:hover {{ background: {c['accent_hover']}; }}
QPushButton#Accent:disabled {{ background: {c['selected']}; color: {c['faint']}; }}
QPushButton#Rec {{ background: {c['rec']}; color: #FFFFFF; border: none; font-weight: 600; }}
QPushButton#Link {{ background: transparent; border: none; color: {c['accent']}; padding: 3px 4px; text-align: left; }}
QPushButton#Seg {{ border-radius: 0; padding: 5px 12px; }}
QPushButton#Seg:checked {{ background: {c['selected']}; border: 1px solid {c['accent']}; }}
QToolButton {{ background: transparent; border: none; border-radius: 6px; padding: 3px 5px; }}
QToolButton:hover {{ background: {c['hover']}; }}
QToolButton:checked {{ background: {c['selected']}; }}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {c['input']}; border: 1px solid {c['border']}; border-radius: 6px; padding: 3px 6px; min-height: 16px; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border: 1px solid {c['accent']}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{ background: {c['card']}; border: 1px solid {c['border']};
    selection-background-color: {c['selected']}; selection-color: {c['text']}; outline: none; }}
QCheckBox {{ spacing: 6px; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border-radius: 4px; border: 1px solid {c['muted']}; background: {c['input']}; }}
QCheckBox::indicator:checked {{ background: {c['accent']}; border: 1px solid {c['accent']}; }}
QMenu {{ background: {c['card']}; border: 1px solid {c['border']}; padding: 6px; border-radius: 10px; }}
QMenu::item {{ padding: 5px 22px 5px 10px; border-radius: 6px; }}
QMenu::item:selected {{ background: {c['selected']}; color: {c['text']}; }}
QMenu::item:disabled {{ color: {c['faint']}; }}
QMenu::separator {{ height: 1px; background: {c['border']}; margin: 4px 6px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 4px; min-height: 24px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {c['border']}; border-radius: 4px; min-width: 24px; margin: 2px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget#Page {{ background: transparent; }}
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ padding: 4px; border-radius: 8px; }}
QListWidget::item:selected {{ background: {c['selected']}; color: {c['text']}; }}
QListWidget::item:hover {{ background: {c['hover']}; }}
#Card {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 14px; }}
#Card:hover {{ border: 1px solid {c['accent']}; }}
#CardTitle {{ font-family: {SERIF}; font-size: 16px; }}
#Box {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 14px; }}
#ReplayOn {{ background: {c['card']}; border: 1px solid {c['accent']}; border-radius: 14px; }}
#CollapseBtn {{ font-size: 16px; color: {c['muted']}; padding: 0 6px; }}
#UploadTile {{ background: {c['panel']}; border: 1px dashed {c['faint']}; border-radius: 8px; color: {c['muted']}; }}
QSlider::groove:horizontal {{ height: 4px; background: {c['border']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {c['accent']}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {c['card']}; border: 2px solid {c['accent']}; width: 12px; height: 12px;
    margin: -6px 0; border-radius: 8px; }}
#Splash {{ background: {c['bg']}; }}
#SplashLogo {{ color: {c['accent']}; font-family: {SERIF}; font-style: italic; font-size: 120px; }}
#SplashName {{ font-family: {SERIF}; font-size: 30px; }}
#Hero {{ border-radius: 18px; }}
#HeroTitle {{ font-family: {SERIF}; font-size: 34px; color: #FFFFFF; }}
#HeroMeta {{ color: rgba(255, 255, 255, 0.86); font-size: 13px; }}
QPushButton#PlayBtn {{ background: {c['accent']}; color: #FFFFFF; border: none; border-radius: 10px;
    padding: 10px 30px; font-size: 16px; font-weight: 700; }}
QPushButton#PlayBtn:hover {{ background: {c['accent_hover']}; }}
QPushButton#PlayBtn:disabled {{ background: rgba(255, 255, 255, 0.4); }}
#HeroPick {{ background: rgba(255, 255, 255, 0.92); color: #141413; border: none; border-radius: 8px; padding: 8px 10px; }}
#HeroTool {{ background: rgba(255, 255, 255, 0.18); border-radius: 8px; padding: 8px; }}
#HeroTool:hover {{ background: rgba(255, 255, 255, 0.3); }}
QPushButton#MiniCard {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px; text-align: left; }}
QPushButton#MiniCard:hover {{ border: 1px solid {c['accent']}; }}
#ProjectRow {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 14px; }}
#ProjectRow:hover {{ border: 1px solid {c['accent']}; }}
#ProjectTitle {{ font-family: {SERIF}; font-size: 18px; }}
#Tag {{ color: {c['muted']}; border: 1px solid {c['border']}; border-radius: 9px; padding: 1px 8px; font-size: 11px; }}
#SourceTag {{ color: {c['muted']}; font-size: 11px; font-weight: 600; }}
QPushButton#Chip {{ border-radius: 14px; padding: 4px 10px; }}
QPushButton#Chip:checked {{ background: {c['accent']}; color: #FFFFFF; border: 1px solid {c['accent']}; }}
#InstanceCard {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 14px; }}
#InstanceCard:hover {{ border: 1px solid {c['accent']}; }}
#InstanceCardOn {{ background: {c['card']}; border: 2px solid {c['accent']}; border-radius: 14px; }}
QPushButton#AddTile {{ background: {c['panel']}; border: 1px dashed {c['faint']}; border-radius: 14px; color: {c['muted']};
    font-size: 14px; }}
QPushButton#AddTile:hover {{ border: 1px dashed {c['accent']}; color: {c['text']}; }}
#AccountCard {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 14px; }}
#AccountCardOn {{ background: {c['card']}; border: 2px solid {c['accent']}; border-radius: 14px; }}
QPushButton#AccountChip {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px; text-align: left; }}
QPushButton#AccountChip:hover {{ border: 1px solid {c['accent']}; }}
#ChipName {{ font-weight: 600; }}
QTextBrowser {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 10px; padding: 8px; }}
QTabWidget#DocTabs QTabBar::tab {{ background: transparent; color: {c['muted']}; padding: 6px 12px; border: none;
    border-bottom: 2px solid transparent; }}
QTabWidget#DocTabs QTabBar::tab:selected {{ color: {c['text']}; border-bottom: 2px solid {c['accent']}; }}
#Tile {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px; }}
#Tile:hover {{ border: 1px solid {c['accent']}; }}
#H3 {{ font-family: {SERIF}; font-size: 16px; }}
#Badge {{ color: {c['accent_text']}; background: {c['accent']}; border-radius: 8px; padding: 1px 8px; font-size: 11px; }}
#BoardBar {{ background: rgba(20, 20, 19, 0.28); }}
#BoardBar QLabel, #BoardBar QPushButton, #BoardBar QToolButton {{ color: #FFFFFF; }}
#BoardBar QPushButton {{ background: rgba(255, 255, 255, 0.16); border: none; border-radius: 7px; padding: 5px 10px; }}
#BoardBar QPushButton:hover {{ background: rgba(255, 255, 255, 0.28); }}
#BoardBar QPushButton:checked {{ background: rgba(255, 255, 255, 0.92); color: #141413; }}
#BoardBar QToolButton:hover {{ background: rgba(255, 255, 255, 0.22); }}
#BoardBar QLineEdit {{ background: rgba(255, 255, 255, 0.92); color: #141413; border: none; }}
#BoardName {{ font-family: {SERIF}; font-size: 20px; color: #FFFFFF; padding: 0 4px; }}
#ListCol {{ background: {c['list']}; border-radius: 12px; }}
#ListTitle {{ font-weight: 600; font-size: 13px; color: {c['list_text']}; }}
#ListCount {{ color: {c['muted']}; font-size: 11px; padding: 0 4px; }}
#ListCountOver {{ color: #FFFFFF; background: {c['overdue']}; border-radius: 6px; font-size: 11px; padding: 0 6px; }}
#ListScroll, #ListScroll > QWidget > QWidget, #CardStack {{ background: transparent; }}
#AddCard {{ background: transparent; border: none; color: {c['muted']}; text-align: left; padding: 6px 8px;
    border-radius: 8px; }}
#AddCard:hover {{ background: {c['hover']}; color: {c['text']}; }}
#AddList {{ background: rgba(255, 255, 255, 0.24); border-radius: 12px; }}
#AddListOpen {{ background: {c['list']}; border-radius: 12px; }}
#AddListBtn {{ background: transparent; border: none; color: #FFFFFF; text-align: left; padding: 6px 8px;
    font-weight: 600; }}
#Composer QPlainTextEdit, #Composer QLineEdit {{ background: {c['card']}; border: 1px solid {c['border']};
    border-radius: 8px; padding: 6px; }}
#Popup {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px; }}
#PopupTitle {{ color: {c['muted']}; font-weight: 600; padding: 2px; }}
#SideBtn {{ text-align: left; background: {c['panel']}; border: none; border-radius: 6px; padding: 6px 10px; }}
#SideBtn:hover {{ background: {c['hover']}; }}
#DangerBtn {{ text-align: left; background: {c['overdue']}; color: #FFFFFF; border: none; border-radius: 6px;
    padding: 6px 10px; }}
#CardDialog, #CardBody {{ background: {c['bg']}; }}
#CardTitleEdit {{ font-family: {SERIF}; font-size: 22px; background: transparent; border: 1px solid transparent; }}
#CardTitleEdit:focus {{ background: {c['input']}; border: 1px solid {c['accent']}; }}
#DescPlaceholder {{ text-align: left; background: {c['panel']}; border: none; padding: 14px 12px; color: {c['muted']}; }}
#DescView {{ padding: 2px; }}
#AttThumb {{ background: {c['panel']}; border-radius: 6px; color: {c['muted']}; font-weight: 600; }}
#ItemDone {{ color: {c['muted']}; }}
QProgressBar {{ background: {c['border']}; border: none; border-radius: 4px; }}
QProgressBar::chunk {{ background: {c['accent']}; border-radius: 4px; }}
#ProgressDone::chunk {{ background: {c['done']}; }}
#DueChip_overdue {{ background: {c['overdue']}; color: #FFFFFF; border: none; }}
#DueChip_soon {{ background: {c['due_soon']}; color: #141413; border: none; }}
#DueChip_done {{ background: {c['done']}; color: #FFFFFF; border: none; }}
#MemberRow {{ text-align: left; border: none; background: transparent; padding: 5px; }}
#MemberRow:checked {{ background: {c['selected']}; }}
#RuleRow {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 12px; }}
#Nav::item {{ padding: 7px 8px; }}
#CardTable {{ background: {c['card']}; alternate-background-color: {c['bg']}; border: none; }}
QHeaderView::section {{ background: {c['panel']}; border: none; padding: 6px; font-weight: 600; }}
QCalendarWidget QWidget {{ alternate-background-color: {c['panel']}; }}
QCalendarWidget QToolButton {{ color: {c['text']}; }}
#NoteRow {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 10px; }}
"""


CURRENT = dict(LIGHT)


def use(colors):
    """Switch the palette custom-painted widgets read from (theme.CURRENT)."""
    CURRENT.clear()
    CURRENT.update(colors)


def label_hex(color):
    return LABEL_COLORS.get(color, (color if str(color).startswith("#") else "#5E5D59", ""))[0]
