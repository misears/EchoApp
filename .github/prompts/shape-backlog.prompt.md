sync 
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
- Prefer improvements that fit EchoApp's current task-hub structure: Ideas, Todos, Problems, Recently Completed, and the ordered build groups already laid out in TASK_HUB.md.

Return:

1. A one-sentence feature definition
2. User-visible behavior
3. Out-of-scope boundaries
4. Likely affected files/subsystems
5. Acceptance criteria
6. A suggested prompt the user can paste into `/phase-plan` or `/phase-implement`
   The suggested prompt should be 2–4 sentences, written in imperative form, referencing the feature definition and acceptance criteria from this brief.

If the idea is too ambiguous, ask only the smallest set of clarifying questions needed to remove implementation ambiguity. Wait for the user's answers before generating the implementation brief. Do not produce a partial brief alongside clarifying questions.
