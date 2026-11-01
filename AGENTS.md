# AGENTS.md — Working guide for coding agents

## 🎯 General principles

1. **Be pragmatic and methodical.**
   - Prefer simple, direct solutions.
   - Avoid over-engineering.

2. **Split work into small, simple tasks.**
   - One task at a time.
   - Before starting, state what you are going to do and how.

3. **If something is complex, plan first.**
   - Break it into verifiable steps.
   - Verify each step before moving on.
   - Do not assume something worked until you have checked it.

4. **Do not try to do many things in one pass.**
   - Large changes = many small steps.
   - Every change should be reviewable and reversible.

## 📋 Recommended workflow
1. **Understand the context** — read `PLAN.txt` and `SPEC.md` when relevant.
2. **Define the concrete task** — in one or two sentences.
3. **Plan the minimum steps** — a short, verifiable list.
4. **Execute and verify** — implement, test, confirm.
5. **Iterate** — only move to the next task once the previous one is validated.

## 🚫 Clear rules

- **Do not refactor** anything unrelated to the current task.
- **Do not mix** multiple features in one commit.
- **Do not delete** existing functionality without confirming first.
- **Do not modify** a file without reading it first.
- **Verify with tests or curl** every endpoint or relevant change.

## 🔍 Before making changes

- Ask when the scope or direction is unclear.
- Read the target file before editing it.
- Confirm the impact on other modules.

## ✅ Definition of done

- The specific task is implemented.
- Tested and working (manual or automated).
- No unrelated changes.
- The plan (`PLAN.txt`) was updated when applicable.
- It can be explained in a short summary.
