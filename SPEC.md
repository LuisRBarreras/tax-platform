# SPEC.md — Working guide (editable document)

> Note: `AGENTS.md` is treated as read-only by the agent tooling.
> This file (`SPEC.md`) is the canonical place to record the workflow and progress.

## 📏 Task size — mandatory rule

**One task = one small, verifiable change.**

- **Do NOT** make large changes in one go (e.g. implement three endpoints, update the plan
  and test everything at once).
- **DO** split it into mini-tasks:
  - Example 1: "Implement the upload-proof endpoint" -> test with curl -> update `PLAN.txt`
    -> stop.
  - Example 2: "Update `PLAN.txt` to reflect that Phase 0 is complete" -> check the file ->
    stop.
- After each mini-task, **update `PLAN.txt` or `SPEC.md`** and confirm with the user before
  continuing.

## 📋 Recommended workflow

1. **Understand the context** — read `PLAN.txt` and `SPEC.md` when relevant.
2. **Define the concrete task** — in one or two sentences.
3. **Plan the minimum steps** — a short, verifiable list (1-2 changes per iteration).
4. **Execute and verify** — implement, test, confirm.
5. **Update the plan** — record what was done and what is left in `PLAN.txt`/`SPEC.md`.
6. **Iterate** — only move on once the previous task is validated and documented.

## 🚫 Clear rules

- **Do not refactor** anything unrelated to the current task.
- **Do not mix** multiple features in one commit.
- **Do not delete** existing functionality without confirming first.
- **Do not modify** a file without reading it first.
- **Verify with tests or curl** every endpoint or relevant change.
- **Update `PLAN.txt`/`SPEC.md` when finishing a task** — even partially, note the progress.

## ✅ Definition of done

- The specific task is implemented.
- Tested and working (manual or automated).
- No unrelated changes.
- The plan (`PLAN.txt`/`SPEC.md`) was updated when applicable.
- It can be explained in a short summary.

---

Last updated: 2026-11-01
