"""Visual theme, stylesheet and application icon for the LearnTrack desktop UI."""

from __future__ import annotations

import string
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QBrush, QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPalette,
    QPen,
)

LIGHT = {
    "bg": "#F3F6FB",
    "panel": "#FFFFFF",
    "card": "#FFFFFF",
    "card_hover": "#F6FAFF",
    "border": "#E4E9F3",
    "border_strong": "#D3DAE8",
    "text": "#182134",
    "muted": "#67718A",
    "subtle": "#98A2B6",
    "accent": "#0F8A7B",
    "accent_hover": "#0C7567",
    "accent_soft": "#E1F3F0",
    "on_accent": "#FFFFFF",
    "header_from": "#0F8A7B",
    "header_to": "#21B49B",
    "header_text": "#FFFFFF",
    "header_sub": "#D8F5EE",
    "danger": "#CF4F45",
    "danger_soft": "#FBE9E7",
    "warn": "#B87A16",
    "warn_soft": "#FCF2DF",
    "ok": "#178A66",
    "ok_soft": "#E2F5EC",
    "info": "#3069D6",
    "info_soft": "#E7EEFC",
    "p1": "#CF4F45",
    "p2": "#C07A18",
    "p3": "#3F6FC4",
    "p4": "#8490A6",
}

DARK = {
    "bg": "#0E1320",
    "panel": "#161D2B",
    "card": "#1B2333",
    "card_hover": "#212B3D",
    "border": "#293344",
    "border_strong": "#39455A",
    "text": "#E8EDF7",
    "muted": "#98A3BA",
    "subtle": "#6E7A92",
    "accent": "#37C5AD",
    "accent_hover": "#4BD8C0",
    "accent_soft": "#16332F",
    "on_accent": "#08201C",
    "header_from": "#123B36",
    "header_to": "#1B6C5F",
    "header_text": "#EBFBF6",
    "header_sub": "#A6D6CC",
    "danger": "#F0786E",
    "danger_soft": "#3A2325",
    "warn": "#E5AB51",
    "warn_soft": "#3A2E1B",
    "ok": "#4AC99B",
    "ok_soft": "#17332B",
    "info": "#7BA2FF",
    "info_soft": "#1C2740",
    "p1": "#F0786E",
    "p2": "#E9B45F",
    "p3": "#84A6F2",
    "p4": "#8892A6",
}

_TEMPLATE = """
* { outline: 0; }
QWidget {
    color: $text;
    font-family: "Microsoft YaHei UI", "Segoe UI", "Segoe UI Emoji";
    font-size: 13px;
}
QMainWindow, #Root { background: $bg; }

#Header {
    border-radius: 20px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 $header_from, stop:1 $header_to);
}
#HeaderTitle { color: $header_text; font-size: 23px; font-weight: 700; }
#HeaderSub { color: $header_sub; font-size: 12px; }
#HeaderBadge {
    color: $header_sub; font-size: 11px; padding: 3px 10px;
    border: 1px solid rgba(255, 255, 255, 0.35); border-radius: 9px;
}

#Panel, #DetailPanel { background: $panel; border: 1px solid $border; border-radius: 18px; }
#Toolbar { background: $panel; border: 1px solid $border; border-radius: 16px; }
#StatCard { background: $panel; border: 1px solid $border; border-radius: 14px; }
#StatValue { font-size: 21px; font-weight: 700; }
#StatLabel { color: $muted; font-size: 11px; }
#SectionTitle { color: $muted; font-size: 11px; font-weight: 600; letter-spacing: 2px; }
#Subtle { color: $subtle; font-size: 12px; }
#Muted { color: $muted; font-size: 12px; }
#DetailTitle { font-size: 18px; font-weight: 700; }
#MetaKey { color: $subtle; font-size: 12px; }
#MetaValue { color: $text; font-size: 12px; }
#Mono { color: $muted; font-family: "Consolas", "Cascadia Mono", monospace; font-size: 11px; }
#Divider { background: $border; border: none; }
#Chip { border-radius: 9px; padding: 2px 9px; font-size: 11px; font-weight: 600; }

QPushButton {
    background: $panel; color: $text; border: 1px solid $border_strong;
    border-radius: 11px; padding: 8px 14px;
}
QPushButton:hover { border-color: $accent; color: $accent; }
QPushButton:disabled { color: $subtle; border-color: $border; }

QPushButton[kind="primary"] {
    background: $accent; color: $on_accent; border: 1px solid $accent;
    font-weight: 700; padding: 9px 18px;
}
QPushButton[kind="primary"]:hover { background: $accent_hover; border-color: $accent_hover; }

QPushButton[kind="hero"] {
    background: rgba(255, 255, 255, 0.96); color: $accent; font-weight: 700;
    border: 1px solid rgba(255, 255, 255, 0.96); border-radius: 12px; padding: 10px 18px;
}
QPushButton[kind="hero"]:hover { background: #FFFFFF; border-color: #FFFFFF; }

QPushButton[kind="heroGhost"] {
    background: rgba(255, 255, 255, 0.14); color: $header_text;
    border: 1px solid rgba(255, 255, 255, 0.30); border-radius: 12px; padding: 9px 15px;
}
QPushButton[kind="heroGhost"]:hover { background: rgba(255, 255, 255, 0.26); }

QPushButton[kind="ghost"] {
    background: $panel; color: $muted; border: 1px solid $border_strong;
    padding: 8px 14px;
}
QPushButton[kind="ghost"]:hover { color: $accent; border-color: $accent; background: $accent_soft; }

QPushButton[kind="danger"] {
    background: $danger_soft; color: $danger; border: 1px solid transparent;
    font-weight: 600; padding: 8px 16px;
}
QPushButton[kind="danger"]:hover { background: $danger; color: #FFFFFF; }

QPushButton[kind="nav"] {
    background: transparent; border: 1px solid transparent; border-radius: 11px;
    padding: 9px 12px; text-align: left; color: $muted; font-weight: 500;
}
QPushButton[kind="nav"]:hover { background: $card_hover; color: $text; }
QPushButton[kind="nav"]:checked {
    background: $accent_soft; color: $accent; font-weight: 700; border: 1px solid transparent;
}

QLineEdit, QComboBox, QPlainTextEdit, QDateEdit, QSpinBox {
    background: $panel; color: $text; border: 1px solid $border_strong;
    border-radius: 10px; padding: 7px 11px; selection-background-color: $accent;
    selection-color: $on_accent;
}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QDateEdit:focus {
    border: 1px solid $accent;
}
QLineEdit { padding: 8px 12px; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: $panel; border: 1px solid $border; border-radius: 10px; padding: 4px;
    selection-background-color: $accent_soft; selection-color: $accent; outline: 0;
}
QDateEdit::drop-down { border: none; width: 24px; }

QCheckBox { color: $muted; spacing: 8px; }
QCheckBox::indicator {
    width: 16px; height: 16px; border-radius: 8px;
    border: 1px solid $border_strong; background: $panel;
}
QCheckBox::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked { background: $accent; border-color: $accent; }

QListView { background: transparent; border: none; }
QListView::item { border: none; }

QProgressBar {
    background: $accent_soft; border: none; border-radius: 5px; height: 8px;
    text-align: center; color: transparent;
}
QProgressBar::chunk { background: $accent; border-radius: 5px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 4px 2px 4px 2px; }
QScrollBar::handle:vertical { background: $border_strong; border-radius: 5px; min-height: 32px; }
QScrollBar::handle:vertical:hover { background: $accent; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollArea { background: $panel; border: none; }
QScrollArea > QWidget#qt_scrollarea_viewport { background: $panel; }
#SubtaskHost { background: $panel; }

#Toast { border-radius: 12px; padding: 0px; }
#Toast[kind="ok"] { background: $ok_soft; border: 1px solid $ok; }
#Toast[kind="warn"] { background: $warn_soft; border: 1px solid $warn; }
#Toast[kind="error"] { background: $danger_soft; border: 1px solid $danger; }
#ToastText { font-size: 12px; font-weight: 600; }

#DialogBody {
    background: $panel; border: 1px solid $border; border-radius: 18px;
}
QDialog { background: $bg; }
#DialogTitle { font-size: 17px; font-weight: 700; }
#FormLabel { color: $muted; font-size: 12px; font-weight: 600; }
#ErrorText { color: $danger; font-size: 12px; }

QStatusBar { background: $bg; color: $muted; font-size: 11px; }
QStatusBar::item { border: none; }
QToolTip {
    background: $panel; color: $text; border: 1px solid $border_strong;
    border-radius: 8px; padding: 6px 9px;
}
QCalendarWidget QWidget { background: $panel; }
"""


def theme(name: str) -> dict[str, str]:
    return DARK if name == "dark" else LIGHT


def build_palette(colors: dict[str, str]) -> QPalette:
    """Force a light/dark palette so the OS dark mode cannot leak through."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(colors["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(colors["panel"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["card_hover"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(colors["panel"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(colors["danger"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(colors["accent"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(colors["on_accent"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(colors["panel"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Mid, QColor(colors["border_strong"]))
    palette.setColor(QPalette.ColorRole.Midlight, QColor(colors["border"]))
    palette.setColor(QPalette.ColorRole.Dark, QColor(colors["muted"]))
    palette.setColor(QPalette.ColorRole.Light, QColor(colors["panel"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(colors["subtle"]))
    return palette


def build_qss(palette: dict[str, str], chevron: str = "") -> str:
    qss = string.Template(_TEMPLATE).substitute(**palette)
    if chevron:
        qss += (
            "\nQComboBox::drop-down, QDateEdit::drop-down {"
            " border: none; width: 26px; subcontrol-position: center right; }\n"
            'QComboBox::down-arrow, QDateEdit::down-arrow {'
            f' image: url("{chevron}"); width: 12px; height: 12px; }}\n'
        )
    return qss


def _chevron_image(size: int, color: str) -> QImage:
    """Small downward caret used by combo boxes in the stylesheet."""
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(QColor(color))
    pen.setWidthF(size * 0.14)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    path = QPainterPath()
    path.moveTo(size * 0.28, size * 0.38)
    path.lineTo(size * 0.50, size * 0.62)
    path.lineTo(size * 0.72, size * 0.38)
    painter.drawPath(path)
    painter.end()
    return image


def _icon_image(size: int) -> QImage:
    """Draw the application mark: a gradient tile holding a task card and a check."""
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    margin = size * 0.055
    tile = QPainterPath()
    tile.addRoundedRect(QRectF(margin, margin, size - 2 * margin, size - 2 * margin),
                        size * 0.21, size * 0.21)
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0.0, QColor("#0F8A7B"))
    gradient.setColorAt(1.0, QColor("#27BE9F"))
    painter.fillPath(tile, QBrush(gradient))

    card = QPainterPath()
    card.addRoundedRect(QRectF(size * 0.20, size * 0.18, size * 0.50, size * 0.56),
                        size * 0.06, size * 0.06)
    painter.fillPath(card, QColor(255, 255, 255, 235))

    pen = QPen(QColor("#0F8A7B"))
    pen.setWidthF(size * 0.022)
    painter.setPen(pen)
    for index, (top, width) in enumerate(((0.30, 0.26), (0.40, 0.30), (0.50, 0.18))):
        line = QRectF(size * 0.265, size * top, size * width, size * 0.075)
        painter.drawRoundedRect(line, size * 0.022, size * 0.022)

    badge_center = QRectF(size * 0.58, size * 0.52, size * 0.30, size * 0.30)
    badge = QPainterPath()
    badge.addEllipse(badge_center)
    painter.fillPath(badge, QColor("#0C7567"))

    tick_pen = QPen(QColor("#FFFFFF"))
    tick_pen.setWidthF(size * 0.030)
    tick_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(tick_pen)
    path = QPainterPath()
    path.moveTo(size * 0.645, size * 0.675)
    path.lineTo(size * 0.705, size * 0.735)
    path.lineTo(size * 0.815, size * 0.610)
    painter.drawPath(path)

    painter.end()
    return image


def ensure_assets(base_dir: Path) -> tuple[Path, Path]:
    """Write the PNG, ICO and caret assets beside the source when they are missing."""
    assets = base_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    png_path = assets / "learn_track.png"
    ico_path = assets / "learn_track.ico"
    if not png_path.exists():
        _icon_image(256).save(str(png_path), "PNG")
    if not ico_path.exists():
        _icon_image(256).save(str(ico_path), "ICO")

    chevrons = {"chevron_light.png": LIGHT["muted"], "chevron_dark.png": DARK["muted"]}
    for name, color in chevrons.items():
        target = assets / name
        if not target.exists():
            _chevron_image(32, color).save(str(target), "PNG")
    return png_path, ico_path


def icon_pixmap(size: int):
    from PySide6.QtGui import QPixmap

    return QPixmap.fromImage(_icon_image(size))
