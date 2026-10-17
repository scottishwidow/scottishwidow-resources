# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT-MAP.md`** at the repo root — it points at one `CONTEXT.md` per context. Read each one relevant to the topic.
- **`docs/adr/`** — read ADRs that touch the area you're about to work in. Also check per-context `docs/adr/` directories for context-scoped decisions.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The producer skill (`/grill-with-docs`) creates them lazily when terms or decisions actually get resolved.

## File structure

This is a multi-context repo (monorepo). `CONTEXT-MAP.md` at the root points to per-context `CONTEXT.md` files:

```
/
├── CONTEXT-MAP.md
├── docs/adr/                          ← all decisions
└── live/
    ├── aws/management/CONTEXT.md      ← Management domain language
    └── hetzner/
        ├── ovpn/CONTEXT.md            ← OVPN domain language
        └── honeynet/CONTEXT.md        ← Honeynet domain language
```

No context has its own `docs/adr/` yet. Update the structure above when a context is
added or gets its own ADRs.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in the relevant `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/grill-with-docs`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders) — but worth reopening because…_
