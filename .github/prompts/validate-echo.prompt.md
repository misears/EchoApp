---
name: validate-echo
description: Run EchoApp-focused validation after a change and report what passed, failed, and what still needs manual checking.
argument-hint: Describe what changed so validation can be targeted.
agent: agent
---

Validate a recent EchoApp change efficiently.

Validation rules:

- Use existing repo checks only.
- Prefer the narrowest checks that still cover the changed behavior.
- Include [`.vscode/tasks.json`](../../.vscode/tasks.json) task-based validation when relevant.
- If no automated check covers the change, say so clearly and propose concise manual verification steps.

In the final report, include:

1. Validation scope chosen
2. Commands or tasks run
3. Pass/fail outcome
4. Any failures or gaps
5. Recommended next action
