# Review of Two Task-Management Tools

## Purpose

This review compares Todoist and Microsoft To Do against the LearnTrack proposal's needs: one place to record coursework deadlines, break larger work into smaller steps, prioritize tasks, and review progress. The notes below describe features documented by the vendors as of November 13, 2026.

## Comparison

| Area | Todoist | Microsoft To Do | Relevance to LearnTrack |
|---|---|---|---|
| Organization | Tasks can be grouped into projects and sections. Today and Upcoming views collect dated tasks across projects. [1] | Tasks can be grouped into lists. Planned collects tasks with dates, while My Day gives a focused daily view. [3][4] | A course field and deadline-sorted list provide the core course-oriented organization for the prototype. |
| Prioritization | Offers four priority levels; high-priority tasks are surfaced in Today and Upcoming. [1] | Lists can be sorted by importance or due date. [5] | Store a priority value and include it in list ordering or filters. |
| Breaking down work | Sections can represent project stages, and tasks can be organized within a project. [1] | Task details can include steps, notes, due dates, and reminders. [6] | LearnTrack records a task's subtasks so a long assignment can be split into manageable actions. |
| Deadline support | Supports scheduling by date and time, including recurring dates. [1] | Supports due dates, reminders, and recurring due dates; dated tasks appear in Planned. [3] | The prototype validates and stores a due date, then highlights overdue work. |
| Search and views | Saved filters can combine dates, priority, labels, projects, and other task attributes. [2] | Lists support search and sorting by importance, due date, and other fields. [5] | The CLI offers course, status, and overdue filters as a small, understandable subset. |

## Findings for the prototype

Both products show the value of keeping task organization, dates, and review views connected. Todoist is a useful reference for course/project grouping, priority levels, and saved filters. Microsoft To Do is a useful reference for a simple daily focus view, due dates, reminders, and task steps.

LearnTrack adopts the smallest features that fit the proposal and the PoC scope: course, title, due date, priority, status, and subtasks, with list, filter, and statistics views. The CLI contribution presents those functions through a menu and delegates the underlying task operations and storage to the team's `TaskManager` and JSON-storage modules. Automated notifications and calendar synchronization are outside the CLI contribution and can be considered as future extensions.

## References

See `references.md` for the full IEEE-style entries and access dates.
