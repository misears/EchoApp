---
name: task-hub
description: Review, update, or reshape EchoApp ideas, todos, and problems using TASK_HUB.md as the default source of truth.
argument-hint: Ask to show backlog, add an idea, update todos, move completed work, or summarize current problems.
agent: ask
---

Use [TASK_HUB.md](../../TASK_HUB.md) as the default EchoApp backlog file.

When invoked:

1. Read [TASK_HUB.md](../../TASK_HUB.md) first. If [TASK_HUB.md](../../TASK_HUB.md) cannot be found or read, notify the user immediately and do not proceed with any updates.
2. Treat it as the primary source for:
   - Ideas
   - Todos
   - Problems
   - Recently Completed
3. If the user asks to add or change backlog content, update [TASK_HUB.md](../../TASK_HUB.md) directly.
4. Keep the file concise and easy to scan:
   - short bullets for ideas and problems
   - checklist-style bullets for todos
   - concise completion notes for recent work

Return the requested result in EchoApp-specific terms.

If the user asks for:

- **show backlog**: summarize the active sections from [TASK_HUB.md](../../TASK_HUB.md)
- **add idea**: place it in **Ideas** unless it has a clear, actionable next step and an implicit owner or assignee, in which case place it in **Todos**
- **add todo**: place it in **Todos** as a checklist item
- **report a blocker or bug**: place it in **Problems**
- **close work**: move it to **Recently Completed**
- **remove item**: delete it from its current section without moving it to **Recently Completed**, only after confirming with the user

If an item is too vague, ask the smallest clarifying question needed before updating the file.
