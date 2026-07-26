---
name: shape-backlog
description: Turn a rough EchoApp idea into a scoped implementation brief the coding agent can execute.
argument-hint: Paste a rough idea, backlog bullet, or feature note.
agent: ask
---

Turn the user's rough EchoApp idea into a build-ready implementation brief.

Use EchoApp-specific framing:

- Focus on local desktop audio workflows.
- Account for likely surfaces such as timeline editing, track controls, recording/takes, playback/rendering, model/runtime assets, and persistence.
- Prefer improvements that fit the current structure in [README.md](../../README.md).

Return:

1. A one-sentence feature definition
2. User-visible behavior
3. Out-of-scope boundaries
4. Likely affected files/subsystems
5. Acceptance criteria
6. A suggested prompt the user can paste into `/phase-plan` or `/phase-implement`

If the idea is too ambiguous, ask only the smallest set of clarifying questions needed to remove implementation ambiguity.
