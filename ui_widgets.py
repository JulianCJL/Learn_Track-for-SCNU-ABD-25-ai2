"""Reusable widgets for the LearnTrack desktop UI."""

from __future__ import annotations

from datetime import date
from typing import Callable

from PySide6.QtCore import (
    QAbstractListModel, QEasingCurve, QModelIndex, QPoint, QPropertyAnimation,
    QRectF, QSize, Qt, QTimer, Signal,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QCompleter, QDateEdit,
    QDialog, QDialogButtonBox, QFrame, QGraphicsOpacityEffect, QHBoxLayout,
    QLabel, QLineEdit, QListView, QPlainTextEdit, QPushButton, QSizePolicy,
    QStyledItemDelegate, QStyle, QVBoxLayout, QWidget,
)

from learntrack_cli import split_subtasks

STATUS_LABEL = {"To Do": "To do", "In Progress": "In progress", "Completed": "Completed"}
STATUS_ORDER = ("To Do", "In Progress", "Completed")
PRIORITY_LABEL = {1: "P1", 2: "P2", 3: "P3", 4: "P4"}
PRIORITY_HINT = {
    1: "Highest priority",
    2: "High priority",
    3: "Normal priority",
    4: "Low priority",
}


def status_color(palette: dict[str, str], status: str) -> tuple[str, str]:
    """Return the (text colour, soft background) pair for a status value."""
    key = {"To Do": "muted", "In Progress": "info", "Completed": "ok"}.get(status, "muted")
    soft = {"To Do": "border", "In Progress": "info_soft", "Completed": "ok_soft"}.get(status, "border")
    return palette[key], palette[soft]


def priority_color(palette: dict[str, str], priority: int) -> str:
    return palette.get(f"p{max(1, min(4, int(priority)))}", palette["p4"])


def with_alpha(color_hex: str, alpha: int) -> str:
    """Return an rgba() string so translucent chips render the same everywhere."""
    color = QColor(color_hex)
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha})"


class TaskListModel(QAbstractListModel):
    """Task rows exposed as records so the delegate can paint rich cards."""

    TaskRole = int(Qt.ItemDataRole.UserRole) + 1

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict] = []

    def set_records(self, records: list[dict]) -> None:
        self.beginResetModel()
        self._rows = list(records)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        record = self._rows[index.row()]
        if role == int(Qt.ItemDataRole.DisplayRole):
            return record["title"]
        if role in (self.TaskRole, int(Qt.ItemDataRole.UserRole)):
            return record
        if role == int(Qt.ItemDataRole.ToolTipRole):
            parts = [record["title"], f"Course: {record['course']}",
                     f"Due: {record['due_date'] or 'not set'}",
                     f"Status: {STATUS_LABEL.get(record['status'], record['status'])}"]
            if record["subtasks"]:
                parts.append("Subtasks:\n" + "\n".join(
                    f"  {i}. {text}" for i, text in enumerate(record["subtasks"], 1)))
            return "\n".join(parts)
        return None

    def records(self) -> list[dict]:
        return list(self._rows)

    def record_at(self, row: int) -> dict | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def row_of(self, task_id: str) -> int:
        for row, record in enumerate(self._rows):
            if record["task_id"] == task_id:
                return row
        return -1


class TaskCardDelegate(QStyledItemDelegate):
    """Paints one rounded task card per row."""

    ROW_HEIGHT = 88

    def __init__(self, palette_getter: Callable[[], dict[str, str]],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._palette = palette_getter

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        width = option.rect.width()
        return QSize(width if width > 0 else 620, self.ROW_HEIGHT)

    def paint(self, painter: QPainter, option, index) -> None:
        record = index.data(TaskListModel.TaskRole)
        if not record:
            return
        palette = self._palette()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        card = QRectF(option.rect).adjusted(10, 5, -10, -5)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if selected:
            fill = QColor(palette["accent_soft"])
            stroke = QColor(palette["accent"])
        elif hovered:
            fill = QColor(palette["card_hover"])
            stroke = QColor(palette["border_strong"])
        else:
            fill = QColor(palette["card"])
            stroke = QColor(palette["border"])

        path = QPainterPath()
        path.addRoundedRect(card, 14, 14)
        painter.fillPath(path, fill)
        painter.setPen(QPen(stroke, 2 if selected else 1))
        painter.drawPath(path)

        if selected:
            bar = QRectF(card.left() + 1, card.top() + 18, 3, card.height() - 36)
            painter.fillRect(bar, QColor(palette["accent"]))

        inner_left = card.left() + 18
        right_edge = card.right() - 18

        # Status chip, measured before the title so the title can elide.
        status_text = STATUS_LABEL.get(record["status"], record["status"])
        status_fg, status_bg = status_color(palette, record["status"])
        chip_font = QFont(painter.font())
        chip_font.setPointSizeF(8.6)
        chip_font.setBold(True)
        chip_width = QFontMetrics(chip_font).horizontalAdvance(status_text) + 22
        chip_rect = QRectF(right_edge - chip_width, card.top() + 14, chip_width, 24)
        self._draw_chip(painter, chip_rect, status_text, chip_font,
                        QColor(status_bg), QColor(status_fg))

        title_font = QFont(painter.font())
        title_font.setPointSizeF(11.2)
        title_font.setBold(True)
        title_width = int(chip_rect.left() - 14 - inner_left)
        painter.setFont(title_font)
        painter.setPen(QColor(palette["text"]))
        title = QFontMetrics(title_font).elidedText(
            record["title"], Qt.TextElideMode.ElideRight, title_width)
        painter.drawText(QRectF(inner_left, card.top() + 13, title_width, 26),
                         int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), title)

        # Priority pill and meta line.
        pill_rect = QRectF(inner_left, card.top() + 46, 40, 22)
        pill_font = QFont(painter.font())
        pill_font.setPointSizeF(8.4)
        pill_font.setBold(True)
        color = QColor(priority_color(palette, record["priority"]))
        pill_bg = QColor(color)
        pill_bg.setAlpha(28 if palette["bg"].startswith("#F") else 52)
        self._draw_chip(painter, pill_rect, PRIORITY_LABEL.get(record["priority"], "P3"),
                        pill_font, pill_bg, color)

        meta_font = QFont(painter.font())
        meta_font.setPointSizeF(9.0)
        meta_font.setBold(False)
        painter.setFont(meta_font)
        metrics = QFontMetrics(meta_font)
        due = record["due_date"]
        overdue = bool(due) and due < date.today().isoformat() and record["status"] != "Completed"
        pieces = [(record["course"], palette["muted"])]
        if due:
            pieces.append((due + ("  overdue" if overdue else ""),
                           palette["danger"] if overdue else palette["muted"]))
        else:
            pieces.append(("No due date", palette["subtle"]))
        if record["subtasks"]:
            pieces.append((f"{len(record['subtasks'])} subtasks", palette["subtle"]))

        x = pill_rect.right() + 12
        limit = right_edge - 6
        labels = [("\u00b7 " if i else "") + text for i, (text, _c) in enumerate(pieces)]
        widths = [metrics.horizontalAdvance(label) for label in labels]
        gap = 12
        available = limit - x
        total = sum(widths) + gap * (len(labels) - 1)
        if total > available and len(labels) > 1:
            reserved = sum(widths[1:]) + gap * (len(labels) - 1)
            widths[0] = max(46, available - reserved - gap)
            labels[0] = metrics.elidedText(labels[0], Qt.TextElideMode.ElideRight, int(widths[0]))
            widths[0] = metrics.horizontalAdvance(labels[0])

        for index_piece, label in enumerate(labels):
            if x >= limit:
                break
            rect_width = min(widths[index_piece], limit - x)
            painter.setPen(QColor(pieces[index_piece][1]))
            painter.drawText(QRectF(x, card.top() + 46, max(0, rect_width), 22),
                             int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                             label)
            x += widths[index_piece] + gap

        painter.restore()

    @staticmethod
    def _draw_chip(painter: QPainter, rect: QRectF, text: str, font: QFont,
                   background: QColor, foreground: QColor) -> None:
        path = QPainterPath()
        path.addRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        painter.fillPath(path, background)
        painter.setFont(font)
        painter.setPen(foreground)
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), text)


class StatCard(QFrame):
    """Small clickable counter used in the summary column."""

    clicked = Signal()

    def __init__(self, title: str, color_key: str,
                 palette_getter: Callable[[], dict[str, str]]) -> None:
        super().__init__()
        self.setObjectName("StatCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._palette = palette_getter
        self._color_key = color_key

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(2)

        row = QHBoxLayout()
        row.setSpacing(6)
        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color:{palette_getter()[color_key]};font-size:9px;")
        row.addWidget(self._dot)
        caption = QLabel(title)
        caption.setObjectName("StatLabel")
        row.addWidget(caption)
        row.addStretch(1)
        layout.addLayout(row)

        self._value = QLabel("0")
        self._value.setObjectName("StatValue")
        layout.addWidget(self._value)

    def set_value(self, value: int) -> None:
        self._value.setText(str(value))

    def refresh_palette(self) -> None:
        self._dot.setStyleSheet(f"color:{self._palette()[self._color_key]};font-size:9px;")

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class Toast(QFrame):
    """Transient message shown at the bottom of the window."""

    def __init__(self, parent: QWidget,
                 palette_getter: Callable[[], dict[str, str]]) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setProperty("kind", "ok")
        self._palette = palette_getter
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 10, 18, 10)
        row.setSpacing(9)
        self._dot = QLabel("●")
        self._text = QLabel("")
        self._text.setObjectName("ToastText")
        row.addWidget(self._dot)
        row.addWidget(self._text)

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(1.0)
        self.setGraphicsEffect(self._effect)
        self._fade = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.finished.connect(self._after_fade)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self._visible = False
        self.hide()

    def show_message(self, text: str, kind: str = "ok", msec: int = 2800) -> None:
        palette = self._palette()
        color = {"ok": palette["ok"], "warn": palette["warn"], "error": palette["danger"]}.get(
            kind, palette["ok"])
        self._dot.setStyleSheet(f"color:{color};font-size:10px;")
        self._text.setStyleSheet(f"color:{color};")
        self._text.setText(text)
        self.setProperty("kind", kind)
        self.style().unpolish(self)
        self.style().polish(self)
        self.adjustSize()
        self._place()
        self.show()
        self.raise_()
        self._visible = True

        self._fade.stop()
        self._fade.setDuration(180)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()
        self._timer.start(msec)

    def _place(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        x = (parent.width() - self.width()) // 2
        y = parent.height() - self.height() - 52
        self.move(QPoint(max(0, x), max(0, y)))

    def reposition(self) -> None:
        """Keep the toast centred after the window is resized."""
        if self._visible:
            self._place()

    def _fade_out(self) -> None:
        self._fade.stop()
        self._fade.setDuration(220)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.start()

    def _after_fade(self) -> None:
        if self._effect.opacity() <= 0.01:
            self.hide()
            self._visible = False


class EmptyState(QWidget):
    """Placeholder shown when the current filter has no results."""

    def __init__(self, palette_getter: Callable[[], dict[str, str]]) -> None:
        super().__init__()
        self._palette = palette_getter
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 40, 24, 40)
        layout.setSpacing(10)
        layout.addStretch(1)

        glyph = QLabel("🗒")
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glyph.setStyleSheet(f"font-size:44px;color:{palette_getter()['subtle']};")
        layout.addWidget(glyph)

        headline = QLabel("No tasks yet")
        headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        headline.setStyleSheet("font-size:15px;font-weight:700;")
        self.headline = headline
        layout.addWidget(headline)

        hint = QLabel("Use \u201cNew task\u201d in the top right to add your coursework")
        hint.setObjectName("Muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint = hint
        layout.addWidget(hint)

        layout.addStretch(1)

    def set_variant(self, has_any_task: bool) -> None:
        """Distinguish an empty board from an empty filter result."""
        if has_any_task:
            self.headline.setText("No tasks match this view")
            self.hint.setText("Try another filter on the left, or clear the search box")
        else:
            self.headline.setText("No tasks yet")
            self.hint.setText("Use \u201cNew task\u201d in the top right to add your coursework")

    def refresh_palette(self) -> None:
        for label in self.findChildren(QLabel):
            if label.text() == "🗒":
                label.setStyleSheet(f"font-size:44px;color:{self._palette()['subtle']};")


class PriorityPicker(QWidget):
    """Exclusive pill selector for the four priority levels."""

    changed = Signal(int)

    def __init__(self, palette_getter: Callable[[], dict[str, str]]) -> None:
        super().__init__()
        self._palette = palette_getter
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self.buttons: dict[int, QPushButton] = {}
        for level in (1, 2, 3, 4):
            button = QPushButton(f"P{level}")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(PRIORITY_HINT[level])
            button.setFixedHeight(32)
            button.clicked.connect(lambda _checked=False, value=level: self.changed.emit(value))
            self._group.addButton(button, level)
            self.buttons[level] = button
            row.addWidget(button)
        row.addStretch(1)
        self.set_value(3)
        self.refresh_palette()

    def set_value(self, level: int) -> None:
        level = max(1, min(4, int(level)))
        self.buttons[level].setChecked(True)

    def value(self) -> int:
        for level, button in self.buttons.items():
            if button.isChecked():
                return level
        return 3

    def refresh_palette(self) -> None:
        palette = self._palette()
        for level, button in self.buttons.items():
            accent = priority_color(palette, level)
            alpha = QColor(accent)
            alpha.setAlpha(38)
            soft = f"rgba({alpha.red()}, {alpha.green()}, {alpha.blue()}, {alpha.alpha()})"
            button.setStyleSheet(
                "QPushButton {"
                f" background: transparent; border: 1px solid {palette['border_strong']};"
                f" color: {palette['muted']}; border-radius: 16px; padding: 6px 16px;"
                " font-weight: 600; }"
                f"QPushButton:hover {{ border-color: {accent}; color: {accent}; }}"
                f"QPushButton:checked {{ background: {soft}; border-color: {accent};"
                f" color: {accent}; }}"
            )


class TaskDialog(QDialog):
    """Create or edit a task with the same validation rules as the data model."""

    def __init__(self, palette_getter: Callable[[], dict[str, str]],
                 record: dict | None = None, courses: list[str] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._palette = palette_getter
        self._record = record
        self.setWindowTitle("Edit task" if record else "New task")
        self.setModal(True)
        self.setMinimumWidth(540)

        shell = QVBoxLayout(self)
        shell.setContentsMargins(12, 12, 12, 12)

        body = QFrame()
        body.setObjectName("DialogBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(26, 22, 26, 20)
        layout.setSpacing(14)
        shell.addWidget(body)

        title = QLabel("Edit task" if record else "New task")
        title.setObjectName("DialogTitle")
        layout.addWidget(title)

        subtitle = QLabel("Fields marked * are required")
        subtitle.setObjectName("Muted")
        layout.addWidget(subtitle)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("e.g. Finish the Software Engineering group proposal")
        self._add_field(layout, "Task title *", self.title_edit)

        self.course_edit = QLineEdit()
        self.course_edit.setPlaceholderText("e.g. Introduction to Software Engineering")
        if courses:
            completer = QCompleter(list(dict.fromkeys(courses)), self.course_edit)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            palette = palette_getter()
            completer.popup().setStyleSheet(
                f"QListView {{ background: {palette['panel']}; color: {palette['text']};"
                f" border: 1px solid {palette['border_strong']}; border-radius: 8px;"
                " padding: 4px; outline: 0; }"
                f"QListView::item {{ padding: 5px 8px; border-radius: 6px; }}"
                f"QListView::item:selected {{ background: {palette['accent_soft']};"
                f" color: {palette['accent']}; }}")
            self.course_edit.setCompleter(completer)
        self._add_field(layout, "Course *", self.course_edit)

        date_row = QHBoxLayout()
        date_row.setSpacing(12)
        self.no_date = QCheckBox("No due date yet")
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(date.today())
        self.no_date.toggled.connect(self.date_edit.setDisabled)
        date_row.addWidget(self.date_edit, 1)
        date_row.addWidget(self.no_date)
        self._add_row(layout, "Due date", date_row)

        self.priority = PriorityPicker(palette_getter)
        self._add_field(layout, "Priority", self.priority)

        self.status_box = QComboBox()
        for status in STATUS_ORDER:
            self.status_box.addItem(STATUS_LABEL[status], status)
        self._add_field(layout, "Status", self.status_box)

        self.subtasks_edit = QPlainTextEdit()
        self.subtasks_edit.setPlaceholderText(
            "One subtask per line; commas or semicolons split too\ne.g. Research, Outline, Slides")
        self.subtasks_edit.setFixedHeight(96)
        self._add_field(layout, "Subtasks", self.subtasks_edit)

        self.error_label = QLabel("")
        self.error_label.setObjectName("ErrorText")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        buttons = QDialogButtonBox()
        cancel = buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        cancel.setProperty("kind", "ghost")
        save = buttons.addButton("Save task", QDialogButtonBox.ButtonRole.AcceptRole)
        save.setProperty("kind", "primary")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self._on_accept)
        layout.addWidget(buttons)

        self._fill(record)

    @staticmethod
    def _add_field(layout: QVBoxLayout, caption: str, widget: QWidget) -> None:
        label = QLabel(caption)
        label.setObjectName("FormLabel")
        layout.addWidget(label)
        layout.addWidget(widget)

    def _add_row(self, layout: QVBoxLayout, caption: str, row: QHBoxLayout) -> None:
        label = QLabel(caption)
        label.setObjectName("FormLabel")
        layout.addWidget(label)
        layout.addLayout(row)

    def _fill(self, record: dict | None) -> None:
        if not record:
            return
        self.title_edit.setText(record["title"])
        self.course_edit.setText(record["course"])
        if record["due_date"]:
            self.date_edit.setDate(date.fromisoformat(record["due_date"]))
        else:
            self.no_date.setChecked(True)
        self.priority.set_value(record["priority"])
        index = self.status_box.findData(record["status"])
        self.status_box.setCurrentIndex(index if index >= 0 else 0)
        self.subtasks_edit.setPlainText("\n".join(record["subtasks"]))
        self.title_edit.setFocus()
        self.title_edit.selectAll()

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def _on_accept(self) -> None:
        title = self.title_edit.text().strip()
        course = self.course_edit.text().strip()
        if not title:
            self._show_error("Task title cannot be empty.")
            self.title_edit.setFocus()
            return
        if not course:
            self._show_error("Course cannot be empty.")
            self.course_edit.setFocus()
            return

        due = "" if self.no_date.isChecked() else self.date_edit.date().toString("yyyy-MM-dd")
        if due:
            try:
                parsed = date.fromisoformat(due)
            except ValueError:
                self._show_error("Invalid date format.")
                return
            if parsed.isoformat() != due:
                self._show_error("Due date must use YYYY-MM-DD.")
                return

        subtasks: list[str] = []
        for line in self.subtasks_edit.toPlainText().splitlines():
            subtasks.extend(split_subtasks(line))

        self.accept()

    def values(self) -> dict:
        due = "" if self.no_date.isChecked() else self.date_edit.date().toString("yyyy-MM-dd")
        subtasks: list[str] = []
        for line in self.subtasks_edit.toPlainText().splitlines():
            subtasks.extend(split_subtasks(line))
        return {
            "title": self.title_edit.text().strip(),
            "course": self.course_edit.text().strip(),
            "due_date": due,
            "priority": self.priority.value(),
            "status": self.status_box.currentData(),
            "subtasks": subtasks,
        }


def make_task_list_view(palette_getter: Callable[[], dict[str, str]]) -> QListView:
    view = QListView()
    view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    view.setUniformItemSizes(True)
    view.setMouseTracking(True)
    view.setSpacing(0)
    view.setFrameShape(QFrame.Shape.NoFrame)
    view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return view
