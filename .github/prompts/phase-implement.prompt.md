---
name: phase-implement
description: Implement a scoped EchoApp feature or phase with explicit boundaries and verification.
argument-hint: Provide the feature goal, boundaries, and done-when criteria.
agent: agent
---

Implement the requested EchoApp change end to end.

Repository-specific rules:

- Read [README.md](../../README.md) first for product and folder conventions.
- Reuse existing project patterns and modules before adding new structures.
- Keep end-user install and launcher behavior coherent with repo-root scripts.
- If persistence changes are required, update both load and save behavior together.
- If the work touches recording, timeline, mixer, playback, or runtime bootstrap behavior, look for existing related helpers before adding new logic.

Execution checklist:

1. Restate the goal, boundaries, and done-when criteria briefly.
2. Inspect the relevant code paths before editing.
3. Make the minimum complete set of changes needed across all affected surfaces.
4. Run the most relevant existing validation:
   - targeted tests when available
   - the existing repo task(s) when relevant
5. Summarize:
   - files changed
   - checks run
   - remaining manual validation recommended

Do not widen scope to unrelated cleanup unless it is required to make the requested change work correctly.
