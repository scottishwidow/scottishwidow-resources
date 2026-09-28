# Agent Workflow Guidelines

This file defines how coding agents should operate in this repository.

## User Interaction & Documentation Standards

**An agent must:**

- **Be concise.** Write in ASD-STE100 Simplified Technical English.
- **Never use emojis** in Markdown documentation.
- **Write well-structured documentation** with appropriate headings.
- **Never document** anything unless asked specifically to do so.

## Code Comments

**An agent must:**

- **Write self-documenting code.** Name variables and functions so a comment that restates them is unnecessary.
- **Never reference** chats, PRs, or change logs inside code files.
- **Use comments only when required**, for example:
  - `TODO`/`FIXME` markers tracking outstanding work
  - A short note where behavior is genuinely non-obvious and cannot be made clear by the code itself

## AI Policy

This repo has an `AI_POLICY.md` in `.github/`. When helping a contributor open a PR or issue, point them to it. Key points: contributor owns every line, slop gets closed without discussion.

---

## 1. Terraform State & Lock Files
- **Never allow** the following inside submodules:
  - `.terraform/`
  - `.terraform.lock.hcl`

- These files are only permitted at the **root module level**.

### Issue tracker

Issues live in this repo's GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Multi-context (monorepo) layout with CONTEXT-MAP.md at the root. See `docs/agents/domain.md`.
