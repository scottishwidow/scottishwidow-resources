## Agent skills

### Issue tracker

Issues live in this repo's GitHub Issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Multi-context (monorepo) layout with CONTEXT-MAP.md at the root. See `docs/agents/domain.md`.

## Guidelines

### Writing & user interaction

- Be concise. Talk in ASD-STE100 Simplified Technical English, and use the ubiquitous language from CONTEXT.md (follow CONTEXT-MAP.md to the right one if the repo has more than one).
- Never use emojis in any Markdown documentation.
- Documentation must be free of informal or decorative elements.

### Code comments

- Write self-documenting code: name variables and functions so a comment restating them is unnecessary.
- Write a comment only for a non-obvious constraint, a workaround, or why a simpler approach failed.
- Keep a comment to one line. If the explanation needs more, refactor the names instead.
- Never reference chats, PRs, or change logs inside code files.
