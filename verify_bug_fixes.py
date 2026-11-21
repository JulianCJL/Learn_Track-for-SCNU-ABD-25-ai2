"""Regression checks for the LearnTrack storage layer and CLI flows.

Every case runs in its own temporary directory, so the project's own
``tasks.json`` is never touched.

    python verify_bug_fixes.py

Exit code 0 means all checks passed; 1 means at least one failed.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unicodedata import east_asian_width
from unittest import mock

PROJECT = Path(__file__).resolve().parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from json_storage import create_manager, load_tasks  # noqa: E402
from learntrack_cli import run_cli, split_subtasks  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))


class Feed:
    """Scripted keyboard input for one CLI session."""

    def __init__(self, answers: list[object]) -> None:
        self.queue = list(answers)
        self.prompts: list[str] = []

    def __call__(self, prompt: str = "") -> str:
        self.prompts.append(prompt)
        if not self.queue:
            raise EOFError
        item = self.queue.pop(0)
        return item(prompt) if callable(item) else str(item)  # type: ignore[return-value]


def session(manager, answers: list[object]) -> tuple[str, Feed]:
    feed = Feed(answers)
    out = io.StringIO()
    with mock.patch("builtins.input", new=feed), contextlib.redirect_stdout(out):
        run_cli(manager)
    return out.getvalue(), feed


def cells(text: str) -> int:
    return sum(2 if east_asian_width(char) in "WF" else 1 for char in text)


def check_bom_loading(root: Path) -> None:
    """A UTF-8 BOM must not be mistaken for corruption."""
    path = root / "bom" / "tasks.json"
    path.parent.mkdir(parents=True)
    payload = [{"task_id": "a" * 32, "title": "Existing task", "course": "SE",
                "due_date": "2026-12-10", "priority": 2, "status": "To Do",
                "subtasks": ["Draft"]}]
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(payload, ensure_ascii=False).encode())
    loaded = load_tasks(path)
    no_backup = not any("_corrupt_" in item.name for item in path.parent.iterdir())
    record("UTF-8 BOM loads without a corrupt backup", len(loaded) == 1 and no_backup,
           f"loaded={len(loaded)}, corrupt_backup={not no_backup}")


def check_unicode_priority(root: Path) -> None:
    """A superscript digit must be rejected instead of crashing int()."""
    manager = create_manager(root / "prio" / "tasks.json")
    output, _ = session(manager, ["1", "Prio task", "SE", "", "\u00b2", "2", "", "0"])
    rejected = "Priority must be 1, 2, 3, or 4." in output
    no_crash = "Unable to complete that action" not in output
    saved = len(manager.get_tasks()) == 1 and manager.get_tasks()[0].priority == 2
    record("Superscript digit is rejected gracefully", rejected and no_crash and saved,
           f"rejected={rejected}, no_crash={no_crash}, saved={saved}")


def check_cjk_alignment(root: Path) -> None:
    """CJK course names must keep the Title column aligned."""
    manager = create_manager(root / "cjk" / "tasks.json")
    session(manager, ["1", "CJK course task", "软件工程", "2026-12-10", "1", "", "0"])
    session(manager, ["1", "Long CJK course", "计算机科学与技术学院软件工程导论课程", "", "2", "", "0"])
    session(manager, ["1", "Ascii course task", "Software Engineering", "2026-12-11", "2", "", "0"])
    output, _ = session(manager, ["2", "0"])
    header = next(line for line in output.splitlines() if line.startswith("ID"))
    target = cells(header[:header.index("Title")])
    aligned = True
    for title in ("CJK course task", "Long CJK course", "Ascii course task"):
        row = next(line for line in output.splitlines() if title in line)
        aligned &= cells(row[:row.index(title)]) == target
    record("CJK course names keep columns aligned", aligned, f"title_column={target}")


def check_fullwidth_comma(root: Path) -> None:
    """Full-width commas must split subtasks, in add and in update."""
    pure = (split_subtasks("读课本，做题，复习") == ["读课本", "做题", "复习"]
            and split_subtasks("A,B") == ["A", "B"]
            and split_subtasks("A，B,C") == ["A", "B", "C"]
            and split_subtasks("") == [])
    manager = create_manager(root / "comma" / "tasks.json")
    session(manager, ["1", "分隔符", "SE", "", "3", "读课本，做题，复习", "0"])
    added = manager.get_tasks()[0].subtasks == ["读课本", "做题", "复习"]
    session(manager, ["4", manager.get_tasks()[0].task_id, "6", "第一章，第二章", "0"])
    updated = manager.get_tasks()[0].subtasks == ["第一章", "第二章"]
    record("Full-width commas split subtasks", pure and added and updated,
           f"pure={pure}, add={added}, update={updated}")


def check_unreadable_store(root: Path) -> None:
    """An unreadable store must fail with a message, not a traceback."""
    work = root / "locked"
    work.mkdir(parents=True)
    (work / "tasks.json").mkdir()
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    result = subprocess.run(
        [sys.executable, str(PROJECT / "learntrack_cli.py")],
        input="0\n", cwd=str(work), text=True, encoding="utf-8",
        capture_output=True, timeout=30, env=env,
    )
    friendly = "LearnTrack cannot start" in result.stdout
    no_trace = "Traceback" not in result.stderr
    record("Unreadable store shows a friendly start-up message",
           result.returncode == 1 and friendly and no_trace,
           f"returncode={result.returncode}, message={friendly}, no_trace={no_trace}")


def check_concurrent_instance(root: Path) -> None:
    """A second instance must preserve the other version instead of losing it."""
    shared = root / "shared" / "tasks.json"
    first = create_manager(shared)
    second = create_manager(shared)
    first.add_task("Added by window A", "SE")
    second.add_task("Added by window B", "AI")
    conflicts = [item for item in shared.parent.iterdir() if "_conflict_" in item.name]
    kept = bool(conflicts) and "Added by window A" in conflicts[0].read_text(encoding="utf-8")
    detected = second.external_change and not first.external_change
    record("Concurrent write keeps a backup of the other version", detected and kept,
           f"detected={detected}, snapshot_kept={kept}")


def check_full_flow(root: Path) -> None:
    """The whole menu still works end to end and still persists."""
    manager = create_manager(root / "flow" / "tasks.json")
    answers: list[object] = []
    answers += ["1", "Finish SE proposal", "Software Engineering", "2026-12-10", "1", "Draft,Proofread"]
    answers += ["1", "Revise AI midterm", "Artificial Intelligence", "", "2", ""]
    answers += ["1", "Read queue chapter", "Data Structures", "2026-11-15", "3", "Ch2,Ch3"]
    answers += ["2"]
    answers += ["3", lambda p: manager.get_tasks()[0].task_id]
    answers += ["4", lambda p: manager.get_tasks()[0].task_id, "5", "2"]
    answers += ["6", "1", "Software Engineering", "6", "2", "3", "6", "3"]
    answers += ["7"]
    answers += ["5", lambda p: manager.get_tasks()[-1].task_id, "y"]
    answers += ["0"]
    output, feed = session(manager, answers)
    markers = ("1. Add task", "2. List tasks", "3. View task details", "4. Update task",
               "5. Delete task", "6. Filter tasks", "7. View statistics",
               "Added task", "Updating ", "Updated task", "Task deleted.",
               "Task statistics", "Goodbye.")
    ok = all(marker in output for marker in markers) and feed.queue == []
    reopened = create_manager(root / "flow" / "tasks.json")
    persisted = len(reopened.get_tasks()) == 2
    record("Full menu flow and persistence", ok and persisted, f"menus={ok}, persisted={persisted}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="learntrack_verify_") as tmp:
        root = Path(tmp)
        check_bom_loading(root)
        check_unicode_priority(root)
        check_cjk_alignment(root)
        check_fullwidth_comma(root)
        check_unreadable_store(root)
        check_concurrent_instance(root)
        check_full_flow(root)

    print("LearnTrack regression checks")
    print("=" * 52)
    for name, ok, detail in RESULTS:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    failed = [name for name, ok, _ in RESULTS if not ok]
    print("-" * 52)
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
