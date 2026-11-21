# LearnTrack PoC Demonstration Script

**Length:** about 4 minutes  
**Presenter:** Haorong Li with Zhaoliang Zhuang  
**Setup:** Use the team's integrated application after the main program calls `run_cli(task_manager)`. The CLI contribution is an interface module and is not a standalone application. Use group-approved demo data; the CLI itself does not create, reset, or manage the team's data file.

## Workflow and talk track

### 1. Introduce the prototype (20 seconds)

**Say:** “LearnTrack is a lightweight student task manager. It keeps course tasks, due dates, priorities, progress status, and subtasks in one place. I will show task entry, deadline and course views, progress updates, and summary statistics.”

### 2. Add a task with subtasks (60 seconds)

Choose `1. Add task` and enter:

- Title: `Prepare software engineering demo slides`
- Course: `Software Engineering`
- Due date: `2026-11-20`
- Priority: `1`
- Subtasks: `Draft outline, Create slides, Rehearse demo`

Point out that the program returns a generated task ID and saves the task locally. Note the ID for the details and update steps.

### 3. Add a second course task and list tasks (45 seconds)

Add another task:

- Title: `Review data structures notes`
- Course: `Data Structures`
- Due date: `2026-11-18`
- Priority: `2`
- Subtasks: leave blank

Choose `2. List tasks`. Explain that tasks with dates appear first, with priority shown beside each row.

### 4. Show details and update progress (55 seconds)

Choose `3. View task details` and enter the ID for the software engineering task. Show its course, deadline, priority, status, and subtasks.

Choose `4. Update task`, enter the same ID, select `5. Status`, then choose `2. In Progress`. Explain that the task record is saved immediately.

### 5. Show filtering and statistics (45 seconds)

Choose `6. Filter tasks`, then `1. By course`, and enter `Software Engineering`. Show that the filtered list contains the matching task.

Choose `7. View statistics`. Briefly point out the total, status counts, overdue count, and completion rate.

### 6. Demonstrate validation and close (35 seconds)

Choose `6. Filter tasks`, then enter an invalid menu choice such as `9`; show that the CLI explains the valid choices and asks again. If time permits, start adding a task and enter an invalid date once, then correct it using `YYYY-MM-DD` format.

Choose `0. Exit`.

**Close with:** “The current PoC demonstrates centralized recording, course filtering, deadline ordering, task decomposition, and progress summaries. Calendar notifications and shared accounts are future extensions.”

## Recording checklist

- Keep the terminal readable and close unrelated windows.
- Use the same sample values and menu flow so the report and demo remain consistent.
- Pause briefly after each menu action so the audience can read the result.
- Confirm with the teammate responsible for storage that the chosen demo data is ready.
- All group members should appear on camera for the required group video; the recording itself still needs to be made by the team.
