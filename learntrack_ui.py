"""LearnTrack desktop application built on PySide6.

The window is a presentation layer only: every read and write goes through the
persistent manager from ``json_storage`` so the JSON file stays authoritative.
"""

from __future__ import annotations

import sys
import traceback
from datetime import date
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QFrame,
    QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QStackedLayout, QVBoxLayout, QWidget,
)

import json_storage
import ui_theme
import ui_widgets
from ui_widgets import (
    STATUS_LABEL, EmptyState, StatCard, TaskCardDelegate, TaskDialog,
    TaskListModel, Toast, priority_color, status_color, with_alpha,
)

WEEKDAY_LABEL = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def app_base_dir() -> Path:
    """Directory the program lives in, so ``tasks.json`` sits beside the app."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def asset_path(name: str) -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", app_base_dir()))
    return bundle_root / "assets" / name


class MainWindow(QMainWindow):
    """Single-window task board: summary, filter bar, card list, detail pane."""

    def __init__(self, manager, data_path: Path, theme_name: str = "light") -> None:
        super().__init__()
        self.manager = manager
        self.data_path = data_path
        self._theme_name = "dark" if theme_name == "dark" else "light"
        self._filter = "all"
        self._selected_id: str | None = None
        self._settings = QSettings()

        self.setWindowTitle("LearnTrack · Academic Task Manager")
        self.setWindowIcon(QIcon(str(asset_path("learn_track.png"))))
        self.resize(1280, 820)
        self.setMinimumSize(1120, 700)

        self._build_ui()
        self._apply_theme(first=True)
        self._install_shortcuts()
        self._refresh(reset_selection=True)

        saved = self._settings.value("window/geometry")
        restored = bool(saved) and self.restoreGeometry(saved)
        if not restored or not self._on_screen():
            self.resize(1280, 820)
            available = QGuiApplication.primaryScreen().availableGeometry()
            self.move(available.center() - self.rect().center())

    def _on_screen(self) -> bool:
        frame = self.frameGeometry()
        return any(screen.availableGeometry().intersects(frame)
                   for screen in QGuiApplication.screens())

    # ------------------------------------------------------------------ layout

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self._root = root
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(20, 18, 20, 12)
        outer.setSpacing(14)

        outer.addWidget(self._build_header())

        content = QHBoxLayout()
        content.setSpacing(14)
        content.addWidget(self._build_sidebar())
        content.addWidget(self._build_main_column(), 1)
        content.addWidget(self._build_detail_panel())
        outer.addLayout(content, 1)

        self.toast = Toast(root, lambda: ui_theme.theme(self._theme_name))

        status = self.statusBar()
        status.setSizeGripEnabled(False)
        status.showMessage(f"Data file: {self.data_path}")
        status.setToolTip(str(self.data_path))

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("Header")
        header.setFixedHeight(96)
        shadow = QGraphicsDropShadowEffect(header)
        shadow.setBlurRadius(34)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(13, 60, 56, 46))
        header.setGraphicsEffect(shadow)

        row = QHBoxLayout(header)
        row.setContentsMargins(26, 16, 22, 16)
        row.setSpacing(16)

        icon = QLabel()
        icon.setPixmap(ui_theme.icon_pixmap(52))
        icon.setFixedSize(52, 52)
        row.addWidget(icon)

        text_column = QVBoxLayout()
        text_column.setSpacing(3)
        title = QLabel("LearnTrack")
        title.setObjectName("HeaderTitle")
        subtitle = QLabel("Academic task manager · all your coursework in one place")
        subtitle.setObjectName("HeaderSub")
        text_column.addWidget(title)
        text_column.addWidget(subtitle)
        row.addLayout(text_column)
        row.addStretch(1)

        today = date.today()
        badge = QLabel(f"{today.isoformat()}  {WEEKDAY_LABEL[today.weekday()]}")
        badge.setObjectName("HeaderBadge")
        row.addWidget(badge)

        self.theme_button = QPushButton("Dark mode")
        self.theme_button.setProperty("kind", "heroGhost")
        self.theme_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_button.setToolTip("Switch between light and dark themes")
        self.theme_button.clicked.connect(self._toggle_theme)
        row.addWidget(self.theme_button)

        self.new_button = QPushButton("+  New task")
        self.new_button.setProperty("kind", "hero")
        self.new_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_button.setToolTip("Create a new task (Ctrl+N)")
        self.new_button.clicked.connect(self.create_task)
        row.addWidget(self.new_button)

        return header

    def _build_sidebar(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setFixedWidth(268)

        column = QVBoxLayout(panel)
        column.setContentsMargins(18, 18, 18, 16)
        column.setSpacing(12)

        section = QLabel("OVERVIEW")
        section.setObjectName("SectionTitle")
        column.addWidget(section)

        grid = QGridLayout()
        grid.setSpacing(9)
        self.card_total = StatCard("Total tasks", "accent", self._palette)
        self.card_total.clicked.connect(lambda: self._set_filter("all"))
        self.card_progress = StatCard("In progress", "info", self._palette)
        self.card_progress.clicked.connect(lambda: self._set_filter("progress"))
        self.card_done = StatCard("Completed", "ok", self._palette)
        self.card_done.clicked.connect(lambda: self._set_filter("done"))
        self.card_overdue = StatCard("Overdue", "danger", self._palette)
        self.card_overdue.clicked.connect(lambda: self._set_filter("overdue"))
        grid.addWidget(self.card_total, 0, 0)
        grid.addWidget(self.card_progress, 0, 1)
        grid.addWidget(self.card_done, 1, 0)
        grid.addWidget(self.card_overdue, 1, 1)
        column.addLayout(grid)

        column.addSpacing(4)
        rate_row = QHBoxLayout()
        rate_caption = QLabel("Completion")
        rate_caption.setObjectName("Muted")
        self.rate_value = QLabel("0%")
        self.rate_value.setObjectName("Muted")
        self.rate_value.setStyleSheet("font-weight:700;")
        rate_row.addWidget(rate_caption)
        rate_row.addStretch(1)
        rate_row.addWidget(self.rate_value)
        column.addLayout(rate_row)

        self.rate_bar = QProgressBar()
        self.rate_bar.setRange(0, 100)
        self.rate_bar.setValue(0)
        self.rate_bar.setTextVisible(False)
        self.rate_bar.setFixedHeight(8)
        column.addWidget(self.rate_bar)

        column.addSpacing(10)
        filter_title = QLabel("FILTERS")
        filter_title.setObjectName("SectionTitle")
        column.addWidget(filter_title)

        self.filter_buttons: dict[str, QPushButton] = {}
        for key, label in (("all", "All tasks"), ("todo", "To do"),
                           ("progress", "In progress"), ("done", "Completed"),
                           ("overdue", "Overdue")):
            button = QPushButton(label)
            button.setProperty("kind", "nav")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, value=key: self._set_filter(value))
            self.filter_buttons[key] = button
            column.addWidget(button)
        self.filter_buttons["all"].setChecked(True)

        column.addStretch(1)

        hint = QLabel("Every change is written to tasks.json")
        hint.setObjectName("Subtle")
        hint.setWordWrap(True)
        column.addWidget(hint)

        return panel

    def _build_main_column(self) -> QWidget:
        wrapper = QWidget()
        column = QVBoxLayout(wrapper)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(12)

        toolbar = QFrame()
        toolbar.setObjectName("Toolbar")
        toolbar.setFixedHeight(62)
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(14, 10, 16, 10)
        bar.setSpacing(10)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search titles, courses or subtasks…")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(150)
        self.search.textChanged.connect(self._schedule_refresh)
        bar.addWidget(self.search, 1)

        self.course_box = QComboBox()
        self.course_box.setFixedWidth(136)
        self.course_box.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.course_box.setMinimumContentsLength(6)
        self.course_box.setToolTip("Filter by course")
        self.course_box.currentIndexChanged.connect(self._schedule_refresh)
        bar.addWidget(self.course_box)

        self.sort_box = QComboBox()
        self.sort_box.setFixedWidth(124)
        self.sort_box.addItem("By due date", "deadline")
        self.sort_box.addItem("By priority", "priority")
        self.sort_box.addItem("By course", "course")
        self.sort_box.addItem("By title", "title")
        self.sort_box.setToolTip("Sort order")
        self.sort_box.currentIndexChanged.connect(self._schedule_refresh)
        bar.addWidget(self.sort_box)

        column.addWidget(toolbar)

        list_area = QWidget()
        list_layout = QVBoxLayout(list_area)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(0)

        self.model = TaskListModel(self)
        self.delegate = TaskCardDelegate(lambda: ui_theme.theme(self._theme_name), self)
        self.view = ui_widgets.make_task_list_view(lambda: ui_theme.theme(self._theme_name))
        self.view.setModel(self.model)
        self.view.setItemDelegate(self.delegate)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.doubleClicked.connect(lambda _index: self.edit_task())
        self.view.selectionModel().currentChanged.connect(self._on_selection_changed)
        list_layout.addWidget(self.view, 1)

        self.empty_state = EmptyState(lambda: ui_theme.theme(self._theme_name))
        list_layout.addWidget(self.empty_state, 1)
        self.empty_state.hide()

        column.addWidget(list_area, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(8, 0, 8, 0)
        self.count_label = QLabel("0 tasks")
        self.count_label.setObjectName("Subtle")
        footer.addWidget(self.count_label)
        footer.addStretch(1)
        self.hint_label = QLabel("Double-click a card to edit · Delete to remove")
        self.hint_label.setObjectName("Subtle")
        footer.addWidget(self.hint_label)
        column.addLayout(footer)

        return wrapper

    def _build_detail_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("DetailPanel")
        panel.setFixedWidth(352)

        column = QVBoxLayout(panel)
        column.setContentsMargins(20, 18, 20, 18)
        column.setSpacing(12)

        caption = QLabel("DETAILS")
        caption.setObjectName("SectionTitle")
        column.addWidget(caption)

        self.detail_stack = QStackedLayout()
        column.addLayout(self.detail_stack, 1)

        placeholder = QWidget()
        placeholder_layout = QVBoxLayout(placeholder)
        placeholder_layout.setSpacing(8)
        placeholder_layout.addStretch(1)
        icon = QLabel("◌")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size:34px;")
        icon.setObjectName("Subtle")
        placeholder_layout.addWidget(icon)
        tip = QLabel("Select a task from the list\nto see the full details")
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip.setObjectName("Muted")
        placeholder_layout.addWidget(tip)
        placeholder_layout.addStretch(1)
        self.detail_stack.addWidget(placeholder)

        self.detail_body = QWidget()
        body = QVBoxLayout(self.detail_body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)

        self.detail_title = QLabel("")
        self.detail_title.setObjectName("DetailTitle")
        self.detail_title.setWordWrap(True)
        body.addWidget(self.detail_title)

        chips = QHBoxLayout()
        chips.setSpacing(8)
        self.detail_priority = QLabel("")
        self.detail_priority.setObjectName("Chip")
        self.detail_status = QLabel("")
        self.detail_status.setObjectName("Chip")
        chips.addWidget(self.detail_priority)
        chips.addWidget(self.detail_status)
        chips.addStretch(1)
        body.addLayout(chips)

        meta = QGridLayout()
        meta.setHorizontalSpacing(12)
        meta.setVerticalSpacing(7)
        self.meta_values: dict[str, QLabel] = {}
        for row, (key, caption_text) in enumerate((("course", "Course"),
                                                   ("due", "Due date"),
                                                   ("subtasks", "Subtasks"),
                                                   ("id", "Task ID"))):
            key_label = QLabel(caption_text)
            key_label.setObjectName("MetaKey")
            value_label = QLabel("")
            value_label.setObjectName("MetaValue" if key != "id" else "Mono")
            value_label.setWordWrap(True)
            meta.addWidget(key_label, row, 0, Qt.AlignmentFlag.AlignTop)
            meta.addWidget(value_label, row, 1)
            self.meta_values[key] = value_label
        meta.setColumnStretch(1, 1)
        body.addLayout(meta)

        divider = QFrame()
        divider.setObjectName("Divider")
        divider.setFixedHeight(1)
        body.addWidget(divider)

        subtask_caption = QLabel("SUBTASKS")
        subtask_caption.setObjectName("SectionTitle")
        body.addWidget(subtask_caption)

        self.subtask_scroll = QScrollArea()
        self.subtask_scroll.setWidgetResizable(True)
        self.subtask_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.subtask_host = QWidget()
        self.subtask_host.setObjectName("SubtaskHost")
        self.subtask_layout = QVBoxLayout(self.subtask_host)
        self.subtask_layout.setContentsMargins(0, 0, 4, 0)
        self.subtask_layout.setSpacing(8)
        self.subtask_layout.addStretch(1)
        self.subtask_scroll.setWidget(self.subtask_host)
        body.addWidget(self.subtask_scroll, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.edit_button = QPushButton("Edit")
        self.edit_button.setProperty("kind", "primary")
        self.edit_button.clicked.connect(self.edit_task)
        self.toggle_button = QPushButton("Mark done")
        self.toggle_button.setProperty("kind", "ghost")
        self.toggle_button.clicked.connect(self.toggle_status)
        self.delete_button = QPushButton("Delete")
        self.delete_button.setProperty("kind", "danger")
        self.delete_button.clicked.connect(self.delete_task)
        actions.addWidget(self.edit_button)
        actions.addWidget(self.toggle_button)
        actions.addWidget(self.delete_button)
        body.addLayout(actions)

        self.detail_stack.addWidget(self.detail_body)
        self.detail_stack.setCurrentIndex(0)
        return panel

    def _install_shortcuts(self) -> None:
        bindings = (
            ("Ctrl+N", self.create_task),
            ("Ctrl+F", self._focus_search),
            ("Ctrl+R", lambda: self._refresh(force=True)),
            ("F2", self.edit_task),
            ("Delete", self.delete_task),
        )
        self._shortcuts = []
        for sequence, handler in bindings:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(handler)
            self._shortcuts.append(shortcut)

    # ------------------------------------------------------------------- state

    def _palette(self) -> dict[str, str]:
        return ui_theme.theme(self._theme_name)

    def _toggle_theme(self) -> None:
        self._theme_name = "dark" if self._theme_name == "light" else "light"
        self._apply_theme()
        self._settings.setValue("theme", self._theme_name)
        self.toast.show_message(
            "Switched to the dark theme" if self._theme_name == "dark" else "Switched to the light theme", "ok", 1800)

    def _apply_theme(self, first: bool = False) -> None:
        palette = ui_theme.theme(self._theme_name)
        chevron_file = asset_path("chevron_dark.png" if self._theme_name == "dark"
                                  else "chevron_light.png")
        chevron = str(chevron_file).replace("\\", "/") if chevron_file.exists() else ""
        application = QApplication.instance()
        application.setPalette(ui_theme.build_palette(palette))
        application.setStyleSheet(ui_theme.build_qss(palette, chevron))
        self.theme_button.setText("Light mode" if self._theme_name == "dark" else "Dark mode")

        for card in (self.card_total, self.card_progress, self.card_done, self.card_overdue):
            card.refresh_palette()
        self.empty_state.refresh_palette()
        record = self._current_record() if self._selected_id else None
        if record:
            self._update_detail(record)
        else:
            self._paint_subtasks()
        self.view.viewport().update()
        if not first:
            self.update()

    def _set_filter(self, key: str) -> None:
        self._filter = key
        for name, button in self.filter_buttons.items():
            button.setChecked(name == key)
        self._refresh(reset_selection=False)

    def _focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def _schedule_refresh(self) -> None:
        if not hasattr(self, "_refresh_timer"):
            self._refresh_timer = QTimer(self)
            self._refresh_timer.setSingleShot(True)
            self._refresh_timer.timeout.connect(lambda: self._refresh(reset_selection=False))
        self._refresh_timer.start(160)

    # -------------------------------------------------------------------- data

    def _all_records(self) -> list[dict]:
        return [task.to_dict() for task in self.manager.get_tasks()]

    def _current_record(self) -> dict | None:
        if not self._selected_id:
            return None
        for record in self._all_records():
            if record["task_id"] == self._selected_id:
                return record
        return None

    def _refresh(self, reset_selection: bool = False, force: bool = False) -> None:
        today = date.today().isoformat()
        records = self._all_records()
        stats = self.manager.statistics()

        self.card_total.set_value(int(stats["total"]))
        self.card_progress.set_value(int(stats["in_progress"]))
        self.card_done.set_value(int(stats["completed"]))
        self.card_overdue.set_value(int(stats["overdue"]))
        rate = float(stats["completion_rate"])
        self.rate_bar.setValue(int(round(rate)))
        self.rate_value.setText(f"{rate:.0f}%")

        self._sync_courses(records)

        if self._filter == "todo":
            records = [r for r in records if r["status"] == "To Do"]
        elif self._filter == "progress":
            records = [r for r in records if r["status"] == "In Progress"]
        elif self._filter == "done":
            records = [r for r in records if r["status"] == "Completed"]
        elif self._filter == "overdue":
            records = [r for r in records
                       if r["due_date"] and r["due_date"] < today and r["status"] != "Completed"]

        course = self.course_box.currentData()
        if course:
            records = [r for r in records if r["course"] == course]

        query = self.search.text().strip().casefold()
        if query:
            records = [r for r in records
                       if query in r["title"].casefold()
                       or query in r["course"].casefold()
                       or any(query in item.casefold() for item in r["subtasks"])]

        sort_key = self.sort_box.currentData()
        if sort_key == "priority":
            records.sort(key=lambda r: (r["priority"], r["due_date"] or "9999-12-31"))
        elif sort_key == "course":
            records.sort(key=lambda r: (r["course"].casefold(), r["due_date"] or "9999-12-31"))
        elif sort_key == "title":
            records.sort(key=lambda r: r["title"].casefold())

        keep = None if reset_selection else self._selected_id
        self.model.set_records(records)
        self.count_label.setText(f"{len(records)} tasks")
        has_rows = bool(records)
        self.view.setVisible(has_rows)
        self.empty_state.set_variant(len(self._all_records()) > 0)
        self.empty_state.setVisible(not has_rows)

        if keep:
            row = self.model.row_of(keep)
            if row >= 0:
                self.view.setCurrentIndex(self.model.index(row, 0))
                return
        if reset_selection or not keep:
            self.view.clearSelection()
            self._selected_id = None
            self._update_detail(None)
        elif has_rows:
            self.view.setCurrentIndex(self.model.index(0, 0))
        else:
            self._selected_id = None
            self._update_detail(None)

        if force:
            self.toast.show_message("Reloaded from tasks.json", "ok", 1600)

    def _sync_courses(self, records: list[dict]) -> None:
        current = self.course_box.currentData()
        courses = sorted({r["course"] for r in records}, key=str.casefold)
        self.course_box.blockSignals(True)
        self.course_box.clear()
        self.course_box.addItem("All courses", None)
        for course in courses:
            self.course_box.addItem(course, course)
        index = self.course_box.findData(current) if current else 0
        self.course_box.setCurrentIndex(index if index >= 0 else 0)
        self.course_box.blockSignals(False)

    def _on_selection_changed(self, current, _previous) -> None:
        record = self.model.record_at(current.row()) if current.isValid() else None
        self._selected_id = record["task_id"] if record else None
        self._update_detail(record)

    def _update_detail(self, record: dict | None) -> None:
        if not record:
            self.detail_stack.setCurrentIndex(0)
            return
        self.detail_stack.setCurrentIndex(1)
        self.detail_title.setText(record["title"])
        palette = self._palette()
        color = priority_color(palette, record["priority"])
        self.detail_priority.setText(f"P{record['priority']}")
        self.detail_priority.setStyleSheet(
            f"background: {with_alpha(color, 34)}; color: {color};"
            f" border: 1px solid {with_alpha(color, 85)};"
            " border-radius: 9px; padding: 2px 10px; font-size: 11px; font-weight: 700;")
        fg, bg = status_color(palette, record["status"])
        self.detail_status.setText(STATUS_LABEL.get(record["status"], record["status"]))
        self.detail_status.setStyleSheet(
            f"background: {bg}; color: {fg}; border: 1px solid {with_alpha(fg, 68)};"
            " border-radius: 9px; padding: 2px 10px; font-size: 11px; font-weight: 700;")

        self.meta_values["course"].setText(record["course"])
        due = record["due_date"]
        overdue = bool(due) and due < date.today().isoformat() and record["status"] != "Completed"
        self.meta_values["due"].setText((due or "Not set") + ("  ·  overdue" if overdue else ""))
        self.meta_values["due"].setStyleSheet(
            f"color: {palette['danger']}; font-weight: 600;" if overdue else "")
        self.meta_values["subtasks"].setText(
            f"{len(record['subtasks'])} subtasks" if record["subtasks"] else "No subtasks")
        self.meta_values["id"].setText(record["task_id"][:12] + "…")
        self.meta_values["id"].setToolTip(record["task_id"])

        completed = record["status"] == "Completed"
        self.toggle_button.setText("Reopen" if completed else "Mark done")
        self._selected_snapshot = record
        self._paint_subtasks()

    def _paint_subtasks(self) -> None:
        while self.subtask_layout.count() > 1:
            item = self.subtask_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        record = getattr(self, "_selected_snapshot", None)
        if not record:
            return
        palette = self._palette()
        if not record["subtasks"]:
            label = QLabel("No subtasks yet for this task")
            label.setObjectName("Subtle")
            label.setWordWrap(True)
            self.subtask_layout.insertWidget(0, label)
            return
        for number, text in enumerate(record["subtasks"], 1):
            row_widget = QWidget()
            row = QHBoxLayout(row_widget)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(9)
            index_label = QLabel(str(number))
            index_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            index_label.setFixedSize(18, 18)
            index_label.setStyleSheet(
                f"background: {palette['accent_soft']}; color: {palette['accent']};"
                " border-radius: 9px; font-size: 10px; font-weight: 700;")
            text_label = QLabel(text)
            text_label.setWordWrap(True)
            text_label.setStyleSheet(f"color: {palette['text']}; font-size: 12px;")
            row.addWidget(index_label, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(text_label, 1)
            self.subtask_layout.insertWidget(self.subtask_layout.count() - 1, row_widget)

    # ------------------------------------------------------------------ actions

    def create_task(self) -> None:
        dialog = TaskDialog(self._palette, None,
                            [r["course"] for r in self._all_records()], self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            task = self.manager.add_task(
                values["title"], values["course"], values["due_date"],
                values["priority"], values["subtasks"])
            if values["status"] != task.status:
                self.manager.update_task(task.task_id, status=values["status"])
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot save task", str(exc))
            return
        if self._filter not in ("all", "todo"):
            self._set_filter("all")
        if self.search.text():
            self.search.clear()
        self._selected_id = task.task_id
        self._refresh()
        self._notify_saved("Task created")

    def edit_task(self) -> None:
        record = self._current_record()
        if not record:
            self.toast.show_message("Select a task first", "warn", 1600)
            return
        dialog = TaskDialog(self._palette, record,
                            [r["course"] for r in self._all_records()], self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        changes = {key: value for key, value in values.items() if record.get(key) != value}
        if not changes:
            return
        try:
            self.manager.update_task(record["task_id"], **changes)
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot update task", str(exc))
            return
        self._refresh()
        self._notify_saved("Task updated")

    def toggle_status(self) -> None:
        record = self._current_record()
        if not record:
            self.toast.show_message("Select a task first", "warn", 1600)
            return
        target = "To Do" if record["status"] == "Completed" else "Completed"
        try:
            self.manager.update_task(record["task_id"], status=target)
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot update status", str(exc))
            return
        self._refresh()
        self._notify_saved("Marked as completed" if target == "Completed" else "Reopened")

    def delete_task(self) -> None:
        if isinstance(QApplication.focusWidget(), (QLineEdit, QPlainTextEdit)):
            return
        record = self._current_record()
        if not record:
            self.toast.show_message("Select a task first", "warn", 1600)
            return
        box = QMessageBox(self)
        box.setWindowTitle("Delete task")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(f"Delete \u201c{record['title']}\u201d?")
        box.setInformativeText("This cannot be undone: the task is removed from tasks.json immediately.")
        confirm = box.addButton("Delete", QMessageBox.ButtonRole.DestructiveRole)
        confirm.setProperty("kind", "danger")
        cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        cancel.setProperty("kind", "ghost")
        box.exec()
        if box.clickedButton() is not confirm:
            return
        try:
            self.manager.delete_task(record["task_id"])
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot delete task", str(exc))
            return
        self._selected_id = None
        self._refresh(reset_selection=True)
        self._notify_saved("Task deleted")

    def _notify_saved(self, message: str) -> None:
        if getattr(self.manager, "last_save_failed", False):
            self.toast.show_message(
                "Changes are kept in memory only: tasks.json could not be written (check file permissions)", "error", 4200)
            return
        if getattr(self.manager, "external_change", False):
            self.manager.external_change = False
            self.toast.show_message(
                f"{message}; another instance changed the file, so the older version was backed up as tasks_conflict_*.json", "warn", 4200)
            return
        self.toast.show_message(message, "ok")

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if getattr(self, "toast", None):
            self.toast.reposition()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._settings.setValue("window/geometry", self.saveGeometry())
        super().closeEvent(event)


def open_manager(preferred: Path):
    """Create the persistent manager, falling back to the user profile."""
    try:
        return json_storage.create_manager(preferred), preferred
    except (OSError, ValueError):
        fallback = Path.home() / "LearnTrack" / "tasks.json"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        return json_storage.create_manager(fallback), fallback


def _install_exception_hook(log_path: Path) -> None:
    def hook(kind, value, tb):
        text = "".join(traceback.format_exception(kind, value, tb))
        try:
            with open(log_path, "a", encoding="utf-8") as handle:
                handle.write(text + "\n")
        except OSError:
            pass
        QMessageBox.critical(None, "LearnTrack hit an error",
                             f"Something went wrong; details were written to:\n{log_path}\n\n{value}")

    sys.excepthook = hook


def main() -> int:
    QApplication.setOrganizationName("LearnTrack")
    QApplication.setApplicationName("LearnTrack")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(asset_path("learn_track.png"))))

    base = app_base_dir()
    if not getattr(sys, "frozen", False):
        try:
            ui_theme.ensure_assets(base)
        except OSError:
            pass
    _install_exception_hook(base / "learntrack_error.log")

    manager, data_path = open_manager(base / "tasks.json")
    saved_theme = str(QSettings().value("theme", "light"))
    window = MainWindow(manager, data_path, saved_theme)

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
