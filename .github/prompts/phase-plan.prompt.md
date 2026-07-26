---
name: phase-plan
description: Create a scoped implementation plan for an EchoApp phase or backlog item.
argument-hint: Describe the phase goal, constraints, and what done looks like.
agent: plan
---

You are planning work for EchoApp / Echo Pro.

Use these repo-specific expectations while planning:

- Read [README.md](../../README.md) for product/workflow context before proposing changes.
- Treat EchoApp as a local desktop audio production application built around Python and PySide6.
- Assume feature work often spans multiple surfaces: UI, persistence, playback/rendering, install/runtime setup, and validation helpers.
- Prefer incremental changes that fit the current structure:
  - shared UI in [app/](../../app/)
  - main application flow in [echo_pro_app.py](../../echo_pro_app.py)
  - dev helpers in [tools/dev/](../../tools/dev/)

Produce a plan with these sections:

1. Goal
2. Scope boundaries
3. Affected files or subsystems
4. Implementation steps
5. Verification steps using existing repo checks only
6. Risks or open questions

If the request is still a rough idea, first reshape it into a concrete implementation target with explicit acceptance criteria before planning.
