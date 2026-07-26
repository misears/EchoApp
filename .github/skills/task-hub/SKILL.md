---
name: 'task-hub'
description: 'Use when working on EchoApp tasks, backlog items, follow-up fixes, or implementation planning that should read from and update TASK_HUB.md.'
---

# EchoApp Task Hub

Use this skill whenever the user asks to:
- capture or review ideas,
- show or update todos,
- track problems or blockers,
- shape backlog items into executable work,
- or keep the repository task hub current after implementation.

## Primary file

- [TASK_HUB.md](../../../TASK_HUB.md)

## Required behavior

1. Read [TASK_HUB.md](../../../TASK_HUB.md) before planning or implementing task-oriented work.
2. Treat it as the default human-readable source of truth for:
   - Ideas
   - Todos
   - Problems
   - Recently Completed
3. When changes materially affect project direction, open items, or known issues, update [TASK_HUB.md](../../../TASK_HUB.md) in the same change.
4. Keep entries short, concrete, and easy to scan.
5. Prefer moving items between sections over duplicating them.

## Section guidance

### Ideas

Use for rough or partially shaped thoughts. These should not assume a final design yet.

### Todos

Use for specific, actionable work items. Prefer checklist entries and clear verbs.

### Problems

Use for active bugs, friction points, environment issues, or known limitations that affect planning or execution.

### Recently Completed

Use for freshly completed items that should stay visible for a while. Prune old entries when they stop being useful.

## Updating rules

- If a task is completed, remove it from **Todos** and add a concise note to **Recently Completed**.
- If a bug is fixed, remove it from **Problems** or reword it as a follow-up if risk remains.
- If a rough idea becomes concrete, move it from **Ideas** to **Todos**.
- If the user asks for the backlog, summarize from [TASK_HUB.md](../../../TASK_HUB.md) first.
