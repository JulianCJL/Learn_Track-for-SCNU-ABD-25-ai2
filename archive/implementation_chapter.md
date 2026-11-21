# Implementation Chapter Contribution: CLI and Input Validation

*Draft section for the implementation chapter co-written by Haorong Li and Senyu Xu.*

## Command-line user interface

The LearnTrack command-line interface provides menu options to add, list, view, update, and delete learning tasks; filter tasks; display progress statistics; and exit the application. The menu collects task details such as title, course, due date, priority, and subtasks. It sends each operation to the team's `TaskManager` instead of manipulating task data or JSON files directly. This keeps the interface separate from the task model and persistence responsibilities.

The list view presents each task's identifier, due date, priority, status, course, and title. The details view displays the selected task's subtasks. The update menu changes one field at a time, and deletion asks for a confirmation response before calling the manager. The filter menu delegates course, status, and overdue filters to the manager. The statistics option displays total tasks, counts by status, overdue count, and completion rate returned by the manager.

## Input validation and error handling

The CLI checks each interactive input before passing it to the task layer. Menu choices must match one of the displayed options. Task titles and course names cannot be empty. Due dates must be valid calendar dates in `YYYY-MM-DD` form; the date may be left empty when no deadline is known. Priority must be an integer from 1 to 4, with 1 representing the highest priority. Status is selected from `To Do`, `In Progress`, or `Completed`. Task identifiers are checked by requesting the selected task from the manager.

When an input is invalid, the CLI explains the expected format and asks again. `ValueError` messages raised by the manager are shown as action errors instead of terminating the menu. End-of-file and keyboard interruption close the CLI cleanly.

## Integration boundary

The menu expects the team's `TaskManager` to expose `add_task`, `get_task`, `get_tasks`, `update_task`, `delete_task`, `filter_tasks`, and `statistics` methods. Task objects returned by the manager expose an identifier, title, course, due date, priority, status, and subtasks. The module `learntrack_cli.py` documents this interface in `TaskManagerPort` and `TaskRecord` and exposes `run_cli(task_manager)` as its entry point.

Before final submission, align method and field names with the integrated source and include a screenshot or transcript from the team's actual application. The CLI does not implement task storage, CRUD behavior, filtering, or statistics; those belong to the other assigned modules.
