# LearnTrack — Test Suite

Unit + integration tests for the LearnTrack PoC (Week 5 deliverable,
owners: Wenjie Shang, Zixuan Deng).

Standard library only (`unittest`); no `pip install` required. Python 3.10+.

## Run

```powershell
Set-Location "C:\Users\JulianCJL\Desktop\软工作业"
python -m unittest discover -s tests -v        # whole suite (174 tests)
python -m unittest tests.test_task -v          # one module
python -m unittest tests.test_cli_integration  # menu / end-to-end flows only
```

Run from the project root so the modules under test (`task`, `task_manager`,
`json_storage_fixed`, `learntrack_cli`) are importable. The test files also add
the project root to `sys.path` themselves, so running a file directly works too.

## Layout

| File | Layer | What it pins down |
|---|---|---|
| `test_task.py` | Unit | `Task` defaults, every field validator, subtask copy semantics, `to_dict`/`from_dict`/`to_json`/`from_json` round trips, `validate()` |
| `test_task_manager.py` | Unit | construction, `add/get/update/delete`, snapshot isolation, sort order (deadline → priority → id), course/status/overdue filters, statistics |
| `test_json_storage.py` | Unit | `load_tasks`/`save_tasks` contract, envelope `{"tasks": [...]}`, invalid/duplicate record skipping, corruption backup, `OSError` propagation, `PersistentTaskManager` write-through |
| `test_cli_integration.py` | Integration | every menu option (1–7 + exit), all prompts with illegal / boundary input, EOF handling, and real-process runs (`python learntrack_cli.py`) including restart persistence |
| `BUG_LIST.md` | Report | six reproducible defects with steps, expected vs actual output, and severity |

Tests never touch the project's own `tasks.json`: each case creates a manager in
its own `tempfile.TemporaryDirectory()`, and subprocess cases use that directory
as the working directory.

## Conventions

* Test IDs in the docstrings (`TC-T-…`, `TC-M-…`, `TC-S-…`, `TC-I-…`) map to
  `BUG_LIST.md` section 2.
* `@unittest.expectedFailure` marks a case that encodes the **correct** behaviour
  but currently fails on an existing defect (BUG-01 … BUG-06). When the bug is
  fixed the runner reports "unexpected success" — that is the signal to delete
  the decorator and move the test to the normal set.
* Dates used in overdue tests are computed from `date.today()`, so the suite does
  not expire.

## Latest result (19 Nov 2026)

```
Ran 174 tests in 3.4s
OK (expected failures=7)
```

167 passed, 7 expected failures covering the six open bugs listed in
`BUG_LIST.md`. No production file was modified by the test work.
