# LearnTrack — Test Report & Bug List

**Scope:** unit testing (`Task`, `TaskManager`, `json_storage_fixed`) and full-flow
integration testing of the CLI menus.
**Test owners:** Wenjie Shang, Zixuan Deng (Action: Unit testing and integration testing, Week 5)
**Test date:** 19 November 2026
**Source under test:** `task.py`, `task_manager.py`, `json_storage_fixed.py`, `learntrack_cli.py`
**Source changes made while testing:** **none**. No production file was edited, and no bug
below has been fixed yet — every item is left open for the team to triage.

---

## 1. Result summary

| Suite | File | Tests | Result |
|---|---|---|---|
| Task entity (validation + serialization) | `tests/test_task.py` | 43 | 43 passed |
| TaskManager business layer | `tests/test_task_manager.py` | 49 | 49 passed |
| JSON persistence layer | `tests/test_json_storage.py` | 33 | 31 passed, 2 expected failures (BUG-01, BUG-06) |
| CLI integration (all menus, real process) | `tests/test_cli_integration.py` | 49 | 44 passed, 5 expected failures (BUG-01, BUG-02, BUG-03, BUG-04, BUG-05) |
| **Total** | `tests/` | **174** | **167 passed, 7 expected failures** |

`python -m unittest discover -s tests -v` → `Ran 174 tests ... OK (expected failures=7)`

The 7 "expected failures" are `@unittest.expectedFailure` tests. They encode the
*correct* behaviour and currently fail because of the six defects in section 3.
Keeping them red is the guard rail: once a bug is fixed the test turns green and
unittest reports an "unexpected success", which is exactly the signal the fixer wants.

Coverage of the acceptance criteria:

| Acceptance criterion | Evidence |
|---|---|
| Core unit tests all pass | `TestTask*`, `TestAddTask`, `TestGetTasksOrdering`, `TestUpdateTask`, `TestDeleteTask`, `TestFilterTasks`, `TestStatistics`, `TestSaveTasks`, `TestLoadValidation` — all green |
| Every CLI menu tested | `TestMenuCoverage.test_every_menu_option_is_exercised_in_one_session` walks options 1–7 + 0 in one session and asserts the state at the end; `TestAddAndList`, `TestViewAndLongListBoundaries`, `TestUpdate`, `TestDelete`, `TestFilter`, `TestStatistics` cover each option again in isolation |
| Normal / illegal / boundary input | `TestIllegalInput` (13 cases), `TestEofHandling`, plus boundary cases in every menu class (blank date, blank subtasks, priority 1 & 4, due today, long course names, CJK text) |
| Bugs reproducible | Each bug below has a numbered repro with command, expected and actual output |

---

## 2. What was tested (traceability)

| ID range | Area | Layer |
|---|---|---|
| TC-T-01 … TC-T-36 | `Task` defaults, field validation, subtask copying, dict/JSON round trip, `validate()` | Unit |
| TC-M-01 … TC-M-45 | `TaskManager` construction, CRUD, snapshot isolation, sort order, filters, statistics | Unit |
| TC-S-01 … TC-S-16 | load/save contract, envelope format, invalid-record skipping, corruption recovery, I/O errors | Unit |
| TC-I-01 … TC-I-36 | add / list / view / update / delete / filter / statistics menus, retry prompts, EOF | Integration (in-process) |
| TC-I-37 … TC-I-41 | real process start → save → restart → delete, unreadable/BOM store at boot | Integration (subprocess) |

**Verified working (no defect found):** every field validator (`task_id`, `title`,
`course`, `due_date`, `priority`, `status`, `subtasks`); failed assignment leaves
the previous value intact; `update_task` is all-or-nothing; returned tasks are
snapshots (no shared mutable state); deadline → priority → id ordering; course /
status / overdue filters and their AND combination; `completion_rate` rounding;
atomic replace of `tasks.json` with no leftover `*.tmp` files; corrupt-file backup
(`*_corrupt_*.json`); invalid/duplicate record skipping at load; persistence of
add/update/delete across a restart; every CLI retry loop; graceful EOF (`LearnTrack closed.`).

---

## 3. Bug list

| ID | Title | Area | Severity | Status | Reproduced by |
|---|---|---|---|---|---|
| BUG-01 | A UTF-8 BOM in `tasks.json` is treated as corruption; the task list is replaced by an empty one | storage | **Medium** | Open | `TestLoadTasks.test_utf8_bom_file_is_loaded`, `TestRealProcess.test_utf8_bom_store_is_loaded_at_startup` |
| BUG-02 | A superscript/Unicode digit at the priority prompt raises an uncaught `ValueError`, aborting the add flow | CLI | **Low** | Open | `TestBugPriorityUnicodeDigit` |
| BUG-03 | Table columns are padded by code point, not display width, so CJK course names shift the Title column | CLI (display) | **Low** | Open | `TestBugCjkAlignment` |
| BUG-04 | Full-width comma (`，`) does not split subtasks; three steps become one | CLI (input) | **Low** | Open | `TestBugChineseCommaSubtasks` |
| BUG-05 | An unreadable `tasks.json` makes the program die with a raw Python traceback and no guidance | CLI start-up | **Medium** | Open | `TestRealProcess.test_unreadable_store_should_not_print_a_raw_traceback` |
| BUG-06 | Two running copies overwrite each other's tasks (no file locking) | storage | **Low** | Open (known limitation) | `TestKnownLimitationConcurrentInstances` |

Severity key: **High** = data loss / crash on a normal path; **Medium** = data loss
or unusable start-up on a plausible path, with a workaround; **Low** = wrong or
confusing behaviour on an unusual path, no data loss.

---

### BUG-01 — UTF-8 BOM in `tasks.json` wipes the visible task list

* **Severity:** Medium (data loss risk, recoverable only because a backup is kept)
* **Location:** `json_storage_fixed.py`, `load_tasks()` lines 92–105
  (`text = raw.decode("utf-8").strip()` then `json.loads(text)` → `_rebuild_empty()`)
* **Environment:** Windows 10/11, Python 3.13, any file saved with a BOM

**Steps to reproduce**

```powershell
$dir = Join-Path $env:TEMP "bom-repro"; New-Item -ItemType Directory -Force $dir | Out-Null
$json = '[{"task_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","title":"Existing task","course":"SE","due_date":"2026-12-10","priority":2,"status":"To Do","subtasks":[]}]'
# Any Windows tool that writes UTF-8 with a BOM produces this (Notepad "UTF-8 with BOM",
# PowerShell 5.1 `Set-Content -Encoding utf8`):
$bytes = [byte[]](0xEF,0xBB,0xBF) + [Text.Encoding]::UTF8.GetBytes($json)
[IO.File]::WriteAllBytes((Join-Path $dir "tasks.json"), $bytes)
Set-Location $dir; python "C:\Users\JulianCJL\Desktop\软工作业\learntrack_cli.py"
# choose menu 2
```

* **Expected:** the existing task is listed; the file is loaded normally.
* **Actual:** `Warning: ...解析失败；原文件已另存为 ...tasks_corrupt_2026....json，重建空表。`
  then `No tasks to show.` and `tasks.json` is rewritten as `[]`.
* **Evidence (captured):**

```
file starts with BOM: efbbbf
tasks visible after load: 0
file rewritten to: []
backups: ['tasks.json', 'tasks_corrupt_20261119_160638_120393.json']
```

* **Impact:** the user opens the program and their whole list is gone from the UI.
  The bytes survive only in a `*_corrupt_*.json` file the user must find by hand.
  `_backup_beside()` also returns `None` on write failure and the rebuild still
  proceeds, which would make this unrecoverable.
* **Suggested fix (not applied):** strip the BOM before parsing
  (`text = raw.decode("utf-8-sig").strip()`), and refuse to rebuild when the
  backup could not be written.

---

### BUG-02 — Unicode digit at the priority prompt raises an uncaught `ValueError`

* **Severity:** Low (no data loss, but the add flow is aborted and the already
  typed title/course/date are thrown away)
* **Location:** `learntrack_cli.py`, `_priority_input()` line 234
  (`if value.isdigit() and int(value) in {1, 2, 3, 4}:`)

**Steps to reproduce**

```powershell
Set-Location "C:\Users\JulianCJL\Desktop\软工作业"; python learntrack_cli.py
# 1 (add) → title "Prio task" → course "SE" → blank due date → type the superscript two (²)
```

* **Expected:** `Priority must be 1, 2, 3, or 4.` and the prompt repeats, as for `abc`.
* **Actual:** the exception escapes `_priority_input()` and is caught only by the
  menu-level handler, so the whole add action dies and the task is not created:

```
Unable to complete that action: invalid literal for int() with base 10: '²'
```

* **Why:** `"²".isdigit()` is `True` (it is a Unicode *digit* but has no numeric
  value for `int()`), so the guard passes and `int(value)` raises.
* **Reproduced with:** `tests/test_cli_integration.py::TestBugPriorityUnicodeDigit`
* **Suggested fix (not applied):** validate with `value.isascii() and value.isdigit()`
  (or `value in {"1", "2", "3", "4"}`), so non-ASCII digits fall through to the
  normal rejection message.

---

### BUG-03 — CJK text shifts the table columns

* **Severity:** Low (cosmetic; no data affected)
* **Location:** `learntrack_cli.py`, `_list_tasks()` lines 158–173 — widths come from
  `len(...)` and padding from f-string field widths, which count code points.

**Steps to reproduce**

```powershell
Set-Location "C:\Users\JulianCJL\Desktop\软工作业"; python learntrack_cli.py
# add: title "CJK course task", course "软件工程"
# add: title "Course task",     course "Software Engineering"
# menu 2
```

* **Expected:** the Title column starts at the same screen column in the header and
  in every row.
* **Actual:** the row with the Chinese course starts its Title field 4 cells
  further right than the header, because `软件工程` counts 4 code points but occupies
  8 screen cells:

```
ID                               Due date    P  Status       Course               Title
f701caf399854e6db2c298c2fecaa2cd 2026-12-10  1  To Do        软件工程                 CJK course task
                                                             ^ 4 cells too wide ↑
```

* **Reproduced with:** `tests/test_cli_integration.py::TestBugCjkAlignment`
  (compares display width via `unicodedata.east_asian_width`)
* **Suggested fix (not applied):** pad with a width helper that counts East-Asian
  wide characters as 2 cells.

---

### BUG-04 — Full-width comma does not split subtasks

* **Severity:** Low (silently wrong data on a very common Chinese input habit)
* **Location:** `learntrack_cli.py` lines 103–104 (`_add_task`) and 127–128
  (`_update_task`), both `text.split(",")`

**Steps to reproduce**

```powershell
Set-Location "C:\Users\JulianCJL\Desktop\软工作业"; python learntrack_cli.py
# 1 (add) → title "分隔符" → course "SE" → blank date → priority 3
# subtasks: 读课本，做题，复习        (Chinese full-width comma, as produced by a Chinese IME)
# then menu 3 to view
```

* **Expected:** three subtasks: `读课本`, `做题`, `复习`.
* **Actual:** one subtask `读课本，做题，复习` — the punctuation stays inside the text:
  `subtasks stored: ['读课本，做题，复习']`
* **Reproduced with:** `tests/test_cli_integration.py::TestBugChineseCommaSubtasks`
* **Suggested fix (not applied):** split on both `,` and `，` (a character class:
  `re.split(r"[,，]", text)`), in both prompts.

---

### BUG-05 — Unreadable `tasks.json` kills the program with a raw traceback

* **Severity:** Medium (program cannot start; no data loss, but no recovery advice)
* **Location:** `learntrack_cli.py` `__main__` lines 266–270 calling
  `create_manager()` → `json_storage_fixed.load_tasks()` line 92
  (`raw = path.read_bytes()`) — the `OSError` is deliberately propagated by storage
  and never handled by the entry point.

**Steps to reproduce**

```powershell
$dir = Join-Path $env:TEMP "locked-repro"; New-Item -ItemType Directory -Force $dir | Out-Null
New-Item -ItemType Directory -Force (Join-Path $dir "tasks.json") | Out-Null   # file replaced by a directory
Set-Location $dir; python "C:\Users\JulianCJL\Desktop\软工作业\learntrack_cli.py"
```

* **Expected:** a one-line message such as `Cannot read tasks.json (...). Fix the
  file or delete it, then restart.` with a non-zero or clean exit — no stack dump.
* **Actual:** exit code 1 and an unpackaged traceback:

```
PermissionError: [Errno 13] Permission denied: 'tasks.json'
```

  `Tasks.json` replaced by a directory forces the case; a file held by another
process with a deny-read lock reaches the same `load_tasks` line and the same
unhandled `PermissionError`.
* **Reproduced with:** `tests/test_cli_integration.py::TestRealProcess::test_unreadable_store_should_not_print_a_raw_traceback`
* **Suggested fix (not applied):** wrap `create_manager()` in `try/except OSError`
  at the entry point, print the path and a recovery hint, exit with code 1.

---

### BUG-06 — Two running copies overwrite each other (no locking)

* **Severity:** Low (single-user prototype assumption; still a real lost-update)
* **Location:** `json_storage_fixed.py`, `PersistentTaskManager._persist()` / `_write_json()`
  — each process keeps the whole table in memory and rewrites the entire file,
  with no lock, no mtime check, no merge.

**Steps to reproduce**

```powershell
# terminal 1 and terminal 2, same folder:
Set-Location "C:\Users\JulianCJL\Desktop\软工作业"
#  T1: add "Added by window A"   (both windows started before either adds)
#  T2: add "Added by window B"
```

* **Expected:** both tasks in `tasks.json`.
* **Actual:** only the last writer's snapshot survives:

```
titles in file: ['Added by window B']
window A still holds: ['Added by window A']
```

* **Reproduced with:** `tests/test_json_storage.TestKnownLimitationConcurrentInstances`
* **Suggested fix (not applied):** document "one instance at a time" in the user
  manual, or re-check the file's mtime/size before writing and warn the user
  (`tasks.json changed on disk — reload before saving`).

---

## 4. Notes for the team (not defects)

1. `TaskManager.update_task()` cannot reject `task_id` through its own
   `allowed` set, because `task_id` is the parameter name: calling
   `update_task(id, task_id="x")` raises `TypeError` before the body runs. The ID
   is still protected, so this is an API-shape quirk, not a bug
   (see `TestUpdateTask.test_task_id_cannot_be_changed`).
2. `learntrack_cli.STATUSES` (line 14) duplicates `Task.STATUSES` and is never
   read — dead constant, harmless but drifts over time.
3. Course/status filtering is case-sensitive and exact by design; the CLI can
   therefore return "No tasks to show." for `se` when the stored course is `SE`.
4. `_list_tasks()` truncates course names longer than 28 characters without an
   ellipsis; the detail view always shows the full name.
5. Tests never touch the project's own `tasks.json`: every case builds its manager
   in a `tempfile.TemporaryDirectory()`, and subprocess cases run with that
   directory as the working directory.

---

## 5. How to run

```powershell
Set-Location "C:\Users\JulianCJL\Desktop\软工作业"
python -m unittest discover -s tests -v            # full suite, verbose
python -m unittest tests.test_task -v              # one module
python -m unittest tests.test_cli_integration      # menus only
```

Standard library only (`unittest`) — no `pip install` needed on any machine with
Python 3.10+.
