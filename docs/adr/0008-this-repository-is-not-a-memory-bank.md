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

- The **triager** reads the Terraform corpus and the GitHub Security findings.
  Nothing else.
- The **remediator** reads the GitHub Security findings, the triager's issue
  body, the Terraform corpus, and the set of paths it may touch. Nothing else.

Anything supporting a registry of any kind is removed: the ground-truth fixture
and its scorer, schema, exporter and provenance tracking; the autonomy allowlist
and support floor; `context.py` and the document set it assembled. The
**Terraform corpus** — every first-party `.tf` file in this repository, assembled
deterministically and carried in the prompt — serves both agents, because the
code is the truth about this system and the only store that never goes stale.

What counts as a store, precisely, because the remediator reads a verdict written
during triage and that must not be a loophole: **a store is consulted about
findings other than the one at hand.** A **tracker item** is one finding's own
record — the place its verdict is written in the first place rather than a second
copy of it — and reading the issue you labelled, about the finding being patched,
is not consulting a registry. Nothing in this pipeline may query what was decided
about a *different* finding.

Retiring the autonomy ratchet follows from the same rule rather than from a
change of mind about ADR-0007's reasoning, which still holds on its own terms: an
earned-authority mechanism is inherently an accumulating store, and computing it
from live API history rather than a file only hides the accumulation elsewhere.

The safety property it replaces is one sentence: **nothing merges and nothing is
dismissed without a human.** A human's `ready-for-remediation` label on an issue
authorises a patch attempt; a human's merge accepts the patch; closing an issue
`wontfix` dismisses its alert. The patch gate that stands between the label and
the merge filters what reaches review — it does not accept anything.

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

**A corpus widened to include `CONTEXT.md`** was considered: domain context is
explicitly legitimate, and a glossary is not half-formed thinking. It was
rejected for the narrower scope because first-party `.tf` is a boundary a test
can enumerate, and every widening of it is an argument that has to be had again.

## Consequences

The pipeline's claim over a suppression file is now weaker and more honest. It no
longer knows what was decided; it reads what was built. A configuration that is
intentional but unremarkable in the code will read as a real finding, and the
human who labels the issue is where that is resolved. This is the cost, and it is
accepted: an agent that guesses from a snippet plus a prose document was not
better informed, only more confident.

`security-events: write` has no remaining structural justification, and nothing
in the pipeline should acquire it except the narrow issue-close-to-alert-dismiss
path, which carries a human decision rather than forming one. The issue filer
does acquire `security-events: read`, to record the alert's number on the issue
it files — a read, and the thing that lets a human decision be rejoined to an
alert later without re-deriving a line number.

**The corpus assembler may contain code and never prose, and this is the
consequence most likely to be undone.** The assembler is structurally the same
shape as the `context.py` this decision deletes: a deterministic task that
gathers files and pushes them into every prompt. The distinction is not the
mechanism but what it may hold, and it is enforced by only ever globbing `.tf`.
It is named `terraform_corpus.py` rather than anything resembling *context*, and
a test asserts both its extension filter and the exact file set it produces. A
future reader who adds "just the ADRs" to it has reversed this ADR without
touching it.

2,033 lines leave with this decision — the scorer, fixture schema, exporter,
autonomy module and policy, `context.py`, and the 544-line ground-truth test
module and 183-line fixture that go with them — along with six entries in the
context's glossary.

## Amendment, 2026-09-04

The decision above originally read that "a single read-only `**/*.tf` toolbox
serves both agents". That is now the pushed Terraform corpus, and the reasoning
for the reversal belongs here because it corrects facts this ADR relied on rather
than a preference it expressed.

The toolbox rested on three claims about `seclab-taskflow-agent`, of which one
holds. It does not ship a filesystem MCP server (`memcache`, `logbook`,
`github_official`, `echo`, `codeql`), so the toolbox meant writing and mounting
custom server code. Its run manifest does not record which files an agent
opened — it carries per-task status, models, timing, token usage and named
outputs, and no tool calls — so the audit argument for pulling context was
false. And it does ship a push-context mechanism: `user_prompt` is Jinja over
task outputs, which is how the finding record reaches both agents and how
`context.py` reached them too. `context.py` was not using a mechanism the
framework lacks; it was using the ordinary one for something this ADR objects to.

What decided it was the size of the thing being argued over: the first-party
corpus is 24 files, 770 lines, 20,249 bytes — about 6k tokens per finding, 55k
for a full run, and cacheable. Pull was avoiding a cost that does not exist.
Pushing it also puts the vendored tree — 1,205 files — out of reach rather than
merely outside a glob, and gives the remediator the exact bytes a diff has to
apply against. Pull becomes worth building at roughly ten times today's corpus,
which is what `live/gitlab/` landing would do.
