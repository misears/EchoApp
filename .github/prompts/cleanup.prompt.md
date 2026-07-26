---
name: cleanup
description: Inspect EchoApp reference documents, identify obsolete or cluttering files, and move inactive material into an archive folder.
argument-hint: Describe the cleanup scope, such as project root clutter, obsolete docs, or outdated support files.
agent: agent
---

Clean up the requested EchoApp area without deleting active project assets by mistake.

Repository-specific rules:

- Read [README.md](../../README.md) first for current product and folder conventions.
- Read [TASK_HUB.md](../../TASK_HUB.md) next for the actively maintained backlog and known current-state issues.
- Treat current repo-root launchers, active app code, `.github/` assets, and referenced documentation as active unless inspection proves otherwise.
- Prefer moving obsolete or superseded files into an [archive/](../../archive/) folder instead of deleting them.
- If [archive/](../../archive/) does not exist, create it in the repository root before moving archived material.
- Keep the project root focused: move obsolete docs, stale exports, unused backup variants, and other non-active clutter out of the root when they are not part of the current workflow.
- Update any references that would break because of files being moved.
- If a file looks ambiguous or may still be in active use, stop and ask before archiving it.

Execution checklist:

1. Restate the cleanup scope briefly.
2. Inspect the relevant reference documents and the target folder before changing anything.
3. Identify which files are active, obsolete, or ambiguous.
4. Move clearly obsolete items into [archive/](../../archive/) using a structure that preserves context.
5. Remove obvious root clutter from the active path by relocating it rather than deleting it.
6. Update broken references if any moved files were linked from active docs.
7. Summarize:
   - files moved
   - archive location used
   - references updated
   - any ambiguous items left in place for confirmation

Do not delete important project assets or widen scope into unrelated feature work.
