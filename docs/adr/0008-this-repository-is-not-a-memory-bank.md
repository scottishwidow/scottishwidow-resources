# 8. This repository is not a memory bank

Date: 2026-09-03

## Status

Accepted

Supersedes [ADR-0007](./0007-autonomous-alert-dismissal-is-earned-per-rule.md).

## Context

The IaC triage pipeline was built on an assumption that never got stated plainly:
that an agent judging a finding needs *accumulated knowledge about this system*,
and that the repository is where such knowledge should live. Every design
decision downstream inherited it.

`context.py` read `docs/adr/` and `docs/design/` into every finding's prompt, and
`CONTEXT-MAP.md` called that "the pipeline's actual differentiator over a
suppression file". `fixtures/ground-truth.yaml` accumulated verdicts harvested
from past triage. `autonomy.json` held an allowlist of rules that had earned
standing authority. Three stores, three schemas, three exporters and guards to
keep them honest — `export_fixture.py` refusing to run once `runs/` was
non-empty, `verdict_author` provenance so a model could not score itself, the
`.agent-data/`-is-not-`runs/` separation in `run.sh`.

Two problems, and they compound.

The first is authority. `docs/design/` is where development thinking is worked
out; it is half-formed by design. Feeding it to an agent as settled truth
promotes drafts to facts, and it does so silently — nobody writing a design doc
is thinking about the verdict it will produce six months later.

The second is that every one of these stores exists *for the agent*. Each is a
thing that must be written, kept current, guarded against contamination, and
reasoned about when it goes stale. And each was compensating for the same
underlying starvation: the agent was shown only the handful of lines Trivy
quoted, and never the Terraform itself. It was being asked what a finding means
*here* while being shown almost nothing of here. The prose was standing in for
the code.

## Decision

**No persistent context exists in this repository for the benefit of an agent.**
The only context that may exist here is development context and domain context —
artifacts that would exist, unchanged, if no agent ever ran.

Each agent's inputs are fixed and exhaustive:

- The **triager** reads the infrastructure code (`**/*.tf`) and the GitHub
  Security findings. Nothing else.
- The **remediator** reads the GitHub Security findings, the triager's issue
  body, and the infrastructure code it is patching. Nothing else.

Anything supporting a registry of any kind is removed: the ground-truth fixture
and its scorer, schema, exporter and provenance tracking; the autonomy allowlist
and support floor; `context.py` and the document set it assembled. A single
read-only `**/*.tf` toolbox serves both agents, because the code is the truth
about this system and the only store that never goes stale.

Retiring the autonomy ratchet follows from the same rule rather than from a
change of mind about ADR-0007's reasoning, which still holds on its own terms: an
earned-authority mechanism is inherently an accumulating store, and computing it
from live API history rather than a file only hides the accumulation elsewhere.

The safety property it replaces is one sentence: **nothing merges and nothing is
dismissed without a human.** The human's label on an issue authorises
remediation; the human's merge accepts a patch; closing an issue `wontfix`
dismisses its alert.

## Considered alternatives

**A purpose-built decision register** — rule- and resource-keyed entries with
rationales, queried per finding — was the obvious replacement for the document
context, and is what this ADR was originally going to record. It is a memory bank
with a schema. It was rejected once the starvation it was compensating for could
be addressed directly.

**Keeping ADRs but dropping design docs** was rejected because it preserves the
premise. An ADR read as agent input is maintained partly for the agent, and the
line between "durable decision" and "current thinking" is not one a directory
name can hold.

**Read-only access scoped to include `CONTEXT.md`** was considered: domain
context is explicitly legitimate, and a glossary is not half-formed thinking. It
was rejected for the narrower scope because `**/*.tf` is a boundary anyone can
verify at a glance, and every widening of it is an argument that has to be had
again.

## Consequences

The pipeline's claim over a suppression file is now weaker and more honest. It no
longer knows what was decided; it reads what was built. A configuration that is
intentional but unremarkable in the code will read as a real finding, and the
human who labels the issue is where that is resolved. This is the cost, and it is
accepted: an agent that guesses from a snippet plus a prose document was not
better informed, only more confident.

`security-events: write` has no remaining structural justification, and nothing
in the pipeline should acquire it except the narrow issue-close-to-alert-dismiss
path, which carries a human decision rather than forming one.

Roughly 1,100 lines of measurement machinery and 630 of autonomy machinery leave
with this decision, along with six entries in the triage context's glossary.
