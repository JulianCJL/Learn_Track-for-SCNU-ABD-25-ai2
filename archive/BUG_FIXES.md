# LearnTrack — Bug Fix Record

**Input:** the six defects listed in `tests/BUG_LIST.md` (unit + integration
testing, Week 5, Wenjie Shang & Zixuan Deng).
**Fixed by:** Jialiang Cheng (bug handling folder).
**Fixed on:** 19 November 2026.
**Base code:** the unmodified prototype copy (`task.py`, `task_manager.py`,
`learntrack_cli.py`, `json_storage_fixed.py`) — same SHA-256 as the tested version.
**Scope:** only this folder was touched. `task.py` and `task_manager.py` were not
modified at all; their public API is unchanged.

Quick check:

```powershell
Set-Location "…\6程家梁（bug处理）"
python verify_bug_fixes.py       # 7/7 checks must pass
python json_storage_fixed.py     # storage self-test, items 1–14 must be True
```

---

## 1. Fix summary

| ID | Severity | Status | File / lines | What changed |
|---|---|---|---|---|
| BUG-01 | Medium | **Fixed** | `json_storage_fixed.py` 113, 87–92 | read with `utf-8-sig`; refuse to rebuild a damaged file when the backup cannot be written |
| BUG-02 | Low | **Fixed** | `learntrack_cli.py` 273–280 | `isdigit()` → `isdecimal()` so `²` is rejected instead of raising |
| BUG-03 | Low | **Fixed** | `learntrack_cli.py` 163–215 | columns measured/padded/truncated in terminal cells (`east_asian_width`) |
| BUG-04 | Low | **Fixed** | `learntrack_cli.py` 20–25, 114–115, 137–139 | one `split_subtasks()` helper for add and update, splitting on `,` and `，` |
| BUG-05 | Medium | **Fixed** | `learntrack_cli.py` 314–325 | start-up wraps `create_manager()`; friendly message + exit code 1, no traceback |
| BUG-06 | Low | **Mitigated** (documented limitation) | `json_storage_fixed.py` 170–200 | stale-file detection: the other instance's version is saved as `tasks_conflict_*.json` and a warning is printed before overwriting |

Verification: `verify_bug_fixes.py` → **7/7 PASS** (six bug checks + one full
menu regression check). Storage self-test → **14/14 True**.

---

## 2. Per-bug detail

### BUG-01 — UTF-8 BOM no longer destroys the task list

`load_tasks()` decoded with `"utf-8"`, so a BOM-prefixed file failed `json.loads`
and was "repaired" into an empty list.

```diff
-        text = raw.decode("utf-8").strip()
+        text = raw.decode("utf-8-sig").strip()   # utf-8-sig 顺带去掉 BOM
```

Second half of the fix (`_rebuild_empty`, lines 87–92): a damaged file is only
replaced after a copy has actually been written. If the copy fails, the rebuild
is abandoned and an `OSError` is raised, so the program stops instead of erasing
the user's data.

```diff
     backup = _backup_beside(path, "corrupt")
+    if backup is None:
+        raise OSError(f"cannot back up {path} before rebuilding it")
```

Saved files are still written as plain UTF-8 (no BOM), so load → save → load
stays stable.

### BUG-02 — Superscript digit at the priority prompt

```diff
-            if value.isdigit() and int(value) in {1, 2, 3, 4}:
+            # BUG-02: isdigit() is True for "²" but int("²") raises ValueError.
+            # isdecimal() only accepts characters int() can actually convert.
+            if value.isdecimal() and int(value) in {1, 2, 3, 4}:
```

The legitimate case is preserved: full-width digits (`１` … `４`) are still
`isdecimal()` and still convert, so Chinese-IME numeric input keeps working.
`²`, `²³`, roman numerals and similar now fall into the normal
`Priority must be 1, 2, 3, or 4.` retry message and the add flow continues
instead of aborting.

### BUG-03 — CJK column alignment

`len()`-based widths became terminal-cell widths:

* `_cells(text)` — `unicodedata.east_asian_width`, wide/full-width = 2 cells;
* `_pad(text, width)` — pads to a cell budget instead of a character count;
* `_fit(text, width)` — truncates a course name to the cell budget without ever
  splitting a character;
* `_list_tasks` builds the header and every row from those three helpers, and the
  separator line uses `_cells(header)`.

Verified layout (all three Title fields start at the same column):

```
ID                               Due date    P  Status       Course                       Title
-----------------------------------------------------------------------------------------------
57441bc0a6464ea5acd2c5380877ba55 2026-11-15  3  To Do        计算机科学与技术学院软件工程 审阅第三章
e4361fb8129a44c9aa9fb7b5e3a1a4dc 2026-12-10  1  To Do        软件工程                     Finish SE proposal
```

ASCII-only data produces exactly the same table as before the fix.

### BUG-04 — Full-width comma splits subtasks

```python
SUBTASK_SEPARATORS = re.compile(r"[,，]")

def split_subtasks(text: str) -> list[str]:
    return [item.strip() for item in SUBTASK_SEPARATORS.split(text) if item.strip()]
```

Both `_add_task()` and `_update_task()` now call it, so the two prompts cannot
disagree. `A,B`, `A，B`, `A，B,C`, `读课本，做题，复习` and a blank line all behave as
expected; blank pieces are dropped, so `A,,B` still yields two subtasks.

### BUG-05 — Start-up failure without a traceback

```python
try:
    manager = create_manager()
except OSError as exc:
    print(f"LearnTrack cannot start: the task file is unreadable ({exc})")
    print("Close the program holding it, or fix/remove tasks.json, then retry.")
    raise SystemExit(1)
run_cli(manager)
```

Exit code **1** (a failed start must be detectable by a wrapper script), message
on stdout, nothing on stderr. Normal start-up is unchanged, and the handler covers
the case added by BUG-01's backup refusal as well, because both raise `OSError`.

### BUG-06 — Two instances no longer lose data silently

`PersistentTaskManager` records the file signature `(mtime_ns, size)` after load
and after every successful save. Before saving it re-reads the signature; if the
file changed underneath, it copies the on-disk version to
`tasks_conflict_YYYYMMDD_HHMMSS_µs.json`, sets `external_change = True`, prints a
warning and then writes its own snapshot.

```diff
+    def _snapshot_external_change(self) -> None:
+        current = _file_signature(self.storage_path)
+        if current is None or self._signature is None or current == self._signature:
+            return
+        backup = _backup_beside(self.storage_path, "conflict")
+        self.external_change = True
+        print(f"Warning: tasks.json 已被其他实例修改；磁盘版本另存为 {backup}…")
```

Why not a true merge: the data model has no per-record timestamps or version
field, so merging two snapshots would mean guessing which side of a conflicting
record to keep. For a single-user prototype the honest fix is "detect, preserve,
tell the user" — no silent loss — and the limitation stays documented. A merge
would need a schema change and should be a separate, planned task.

---

## 3. Compatibility fixes (cross-module)

| # | Issue | Resolution |
|---|---|---|
| 1 | `load_tasks()` may now raise `OSError` from the backup guard as well as from `read_bytes()`; previously the CLI's `__main__` had no handler at all | the only production caller, `learntrack_cli.__main__`, now handles `OSError`; `create_manager()` keeps propagating it (storage must never pretend an empty list) |
| 2 | `learntrack_cli.STATUSES` (line 16) was a dead constant while `_status_input()` hard-coded the same three strings — a drift trap between CLI and `Task.STATUSES` | `_status_input()` now derives both its legend and its mapping from `STATUSES`; printed output is byte-identical and the public name is kept, so other members' imports still work |
| 3 | BOM tolerance must not re-introduce BOM on write, or every load would rewrite `tasks.json` | the atomic writer still encodes plain UTF-8; verified by round-tripping a BOM file through add/update |
| 4 | Conflict snapshots sit next to the store and are matched by `_backup_beside` naming | they reuse the same `path.stem + tag + timestamp` scheme (`tasks_conflict_*`), never shadowing `tasks.json` |
| 5 | `TaskManagerPort` / `TaskRecord` protocol purity | `task.py` and `task_manager.py` untouched; no new required attribute on `Task`, only two optional flags on `PersistentTaskManager` (`external_change`, plus the internal `_signature`) |
| 6 | Tests instantiate `PersistentTaskManager(None, blocked_path)` and expect `last_save_failed` | preserved: `__init__` signature unchanged, signature tracking is silent when the file does not exist |

Deliberately **not** changed (would alter agreed behaviour or other members' work):

* `DATA_FILE` remains working-directory relative — the demo and README both start
  the program from the project folder;
* course/status filters stay exact and case-sensitive (documented behaviour);
* user-facing messages keep their current mix of English (CLI) and Chinese
  (storage warnings); translating them would touch text the report already quotes.

---

## 4. Effect on the existing test suite

The suite in `6程家梁（测试专用）/tests` was re-run unchanged against this folder
(in a temporary copy, so neither folder was modified):

```
Ran 174 tests in 3.0s
FAILED (expected failures=2, unexpected successes=5)
```

* **167 tests still pass** — the four fixed modules changed nothing else.
* **5 bug tests now report "unexpected success"** (BUG-01 ×2, BUG-02, BUG-03,
  BUG-04): that is unittest's signal that an `@expectedFailure` case started
  passing. The testing owner should delete those decorators during the final
  regression pass.
* **2 cases remain "expected failures"**, and both encode an *older* expectation
  rather than a defect:
  1. `TestRealProcess.test_unreadable_store_should_not_print_a_raw_traceback`
     asserts `returncode == 0`; the fix intentionally exits with 1. Suggested
     change: assert `returncode == 1` and `"Traceback" not in stderr`.
  2. `TestKnownLimitationConcurrentInstances.test_two_managers_over_one_file_keep_both_tasks`
     asserts that both tasks end up in `tasks.json` (a real merge). The fix
     preserves the other version in `tasks_conflict_*.json` instead. Suggested
     change: keep the case as a documented limitation and assert that the
     snapshot file contains the other instance's task.

---

## 5. Files in this folder

| File | Role |
|---|---|
| `task.py` | unchanged |
| `task_manager.py` | unchanged |
| `json_storage_fixed.py` | BUG-01, BUG-06 |
| `learntrack_cli.py` | BUG-02, BUG-03, BUG-04, BUG-05, compatibility #2 |
| `verify_bug_fixes.py` | new: 7 automated checks, exit code 0/1 |
| `启动LearnTrack.bat` | new: double-click launcher - `cd`s to its own folder, runs the CLI, keeps the window open after exit |
| `BUG_FIXES.md` | this record |
