# Haorong Li's LearnTrack Contributions

This pack is limited to Haorong Li's listed assignments in the proposal:

- Investigate two task-management tools.
- Build the CLI menu and input validation.
- Co-write the implementation chapter with Senyu Xu.
- Unify the references format.
- Co-write the PoC demo script and workflow with Zhaoliang Zhuang.

The `软工group3` chat showed the proposal and asked members to keep their assigned sections in sync. The project-related messages visible there did not provide the team's source code, a `TaskManager` API, or a citation-style rule. No project source or report draft was present in this workspace.

## CLI integration

`learntrack_cli.py` contains the menu and input validation only. It delegates task operations to the team's `TaskManager` and does not implement the task model, JSON storage, CRUD logic, filtering, or statistics. The team application should construct its manager and call:

```python
from learntrack_cli import run_cli

run_cli(task_manager)
```

The manager should provide the methods and task fields defined by `TaskManagerPort` and `TaskRecord` in the file. If the team code uses different names, adapt this boundary when the shared source is available.

## Documents

- `tool_comparison.md` — research note for Todoist and Microsoft To Do.
- `implementation_chapter.md` — draft section limited to the CLI and input validation.
- `references.md` — references normalized to IEEE numeric style as a working default.
- `demo_script.md` — PoC presentation workflow and talk track.

The proposal gives deadlines by project week. Dates in the demo are illustrative sample data, not course deadlines.
