# Agentic IaC security triage and remediation — as built

Status: **implemented.** This document describes the pipeline that exists. It is
the behaviour contract, together with the two test suites; there is no separate
specification.

Note for whoever reads this next, human or otherwise: this file is **not** agent
input. `docs/design/` is where development thinking is worked out and is
half-formed by design. What the agents read is the Terraform, all of it, and
nothing else — see
[ADR-0008](../adr/0008-this-repository-is-not-a-memory-bank.md).

Goal: catch security misconfigurations in this repository's Terraform, decide
what each one *means here*, record a rationale for every decision, and — where a
human asks for it — propose a patch. The safety property is one sentence:
**nothing merges and nothing is dismissed without a human.**

## Shape of the thing

One loop, two agents, and a tracker item between them. Everything before the
first agent and everything after the second is deterministic. A patch reaches
the repository through exactly two human acts: the label that authorises it, and
the merge that accepts it.

```
                trivy config --format json .        v0.74.0, pinned
                            │
                            ▼
                      normalise.py                  one record per finding,
                            │                       keyed, then filtered twice
            ┌───────────────┼───────────────┐
            │               │               │
       ┌────▼────┐   ┌──────▼──────┐  ┌─────▼────┐
       │ eligible│   │below_thresh │  │ vendored │
       │    9    │   │      3      │  │    8     │
       └────┬────┘   └──────┬──────┘  └─────┬────┘
            │               │               │
            │          open alert,      recorded
            │          untriaged,       upstream,
            │          no issue         never prompted
            ▼
     outstanding.py                             eligible, minus every key the
            │                                   tracker already holds
            ▼
     taskflows/iac_triage                       ← a model step
            │                                   one branch per outstanding
            ▼                                   finding, no toolboxes at all
     collect_verdicts.py                        applies the discard rule
            │
            ▼
     file_issues.py                             one issue per triaged finding,
            │                                   under needs-triage
            ▼
  ═══════════════ a human reads the tracker item ═══════════════
            │                                           │
   labels it ready-for-remediation           closes it wontfix
            │                                           │
            ▼                                           ▼
     remediation_target.py                       reconcile_alert.py
            │   the finding, its item and the       dismisses the alert
            │   paths a patch may touch             the item names
            ▼
     taskflows/iac_remediate                    ← the other model step
            │                                   one unified diff, as text
            ▼
     collect_patch.py
            │
            ▼
     patch_gate.py                              a filter, not an acceptance
            │
      ┌─────┴─────┐
      │           │
   passed      rejected
      │           │
      ▼           ▼
 a pull request  a comment on the item
      │          naming the gate it failed
      ▼
  ═══════════════ a human merges it ═══════════════
```

`normalise.py` reads stdin or a report path, so the committed baseline replays
without a scanner and the whole deterministic half is testable with neither
Trivy nor AWS.

## Decisions that are load-bearing in the code

**Ownership first, severity second, and neither is a judgment.** Both filters are
path and enum comparisons; no model sees a finding before both have run. The
*order* is what matters: all 8 `CRITICAL` findings in this repository are
vendored, so a severity gate applied alone would admit exactly the eight findings
that cannot be fixed here and drop five first-party ones. Ownership is decided on
the **owner path** — the first `Occurrences[].Filename`, falling back to the Trivy
target — which is where the offending code is *instantiated* rather than where it
lives, because that is what says whether this repository can fix it.
`.terraform/modules/` is vendored, `live/` and `modules/` are first-party, and an
unrecognised path is treated as first-party so nothing escapes triage by being
somewhere unexpected.

**Identity is a readable composite key**, not a hash:

    AWS-0089:module.bootstrap:aws_s3_bucket.terraform_state_bucket

`ruleId:module_address:resource_type.resource_name`. It survives line-number
drift, distinguishes two instantiations of one module, and is readable because it
appears in the committed fixture and in issue bodies. There is no ordinal, so two
first-party findings could in principle collide; that case is *reported* as
`duplicate_first_party_keys` rather than absorbed, and a test holds it empty.

**Code scanning holds per-finding state; Issues hold the work.** Every triaged
finding becomes an issue whatever its verdict, because deciding a finding is not
worth acting on is precisely the judgment this pipeline exists to inform, and
burying it in a dismissal comment hides it from where work is reviewed. The
issue carries the alert's number, so a human decision can be rejoined to its
alert later without re-deriving a line number that has since moved.

**The agents read the code, and nothing else about this system.** Every
first-party `.tf` file is assembled by `terraform_corpus.py` and carried in each
agent's prompt: 24 files, 778 lines, about 20KB. There is no store — nothing in
this pipeline may consult what was decided about a *different* finding. The
remediator reading the tracker item for the finding it is patching is not a
loophole in that rule: an item is one finding's own record, and it is where the
verdict was written in the first place rather than a second copy of it.

**The corpus is the cacheable prefix.** A cache prefix must be common to every
branch of the fan-out. The personality is common already; the corpus is common
only while nothing per-finding precedes it, so the prompt runs personality, then
corpus, then the finding. It is also the better ordering independently of the
cost, because the model answers about the last thing it read. What the caching
actually saves depends on how the framework schedules the fan-out — branches that
run fully in parallel all miss the cache together — so no figure is quoted here.

**Neither agent has any tools.** `toolboxes` is empty on both, deliberately.
Every fact arrives in the prompt, which buys a run reproducible from its inputs
and no structural path from a run to a dismissal, an issue or a commit whatever a
prompt says. It matters most on the remediator, where none of the framework's
own containment would do instead: its `confirm:` list prompts through a bare
`input()`, which in unattended CI raises rather than denies; `headless: true`
auto-allows every call; and `blocked_tools` blocks named tools rather than
granting none. An agent holding no toolbox needs none of that.

**Scanning is automatic and triage follows it; the money is spent on change
only.** Triage runs on the scan's completion, so a code change is triaged without
anyone asking. It costs nothing when nothing changed, because the fan-out runs
over the *outstanding* findings — the eligible set minus every key that already
has a tracker item — so a merge that touches no Terraform reaches no model and
files nothing. The rule lives in `taskflow/outstanding.py` and deliberately not
in `normalise.py`: `normalise.py` is pure and replayable against a committed
fixture, and "has a tracker item" is a property of the *tracker*, which changes
without the finding changing. It is not a fourth `triage_status` for the same
reason. Filing was already idempotent on the key, so this changes no filing
behaviour — it moves the saving to before the money is spent.

**`undetermined` is triaged again; a second verdict is a comment.** It is what
the discard rule records when a reply is unparseable, has no rationale, or never
arrives — a failure to judge, not a judgment — so excluding on it would let one
bad reply silence a finding permanently. A finding whose *open* item records it
is therefore triaged again, and because the item already exists the new verdict
is commented onto it and nothing is opened. One finding key owns one item, still.
`issue_body.py` reads a comment as a verdict as well as a body, which is what
stops the re-triage repeating forever. A *closed* item excludes its finding
whatever it records: a reintroduced finding reopens its alert, which is where
that state belongs.

**Remediation is invoked by a label, never by a verdict.** `real-mechanical` is
advice to whoever reads the issue and gates nothing. What starts a run is
`ready-for-remediation` on that issue — a dedicated label rather than the
repository-wide `ready-for-agent`, which is carried by issues that hold no
finding. `remediation_target.py` halts a run whose issue names no finding key,
in a job holding no token at all, so a mislabelled issue costs nothing.

**A finding the scan no longer holds is a stop, not a failure.** A key that
matches nothing eligible exits on a status of its own, apart from the defect
exits. The run spends no model token, says on the issue which finding is gone,
removes the label that authorised it and ends green. A red run then means a
defect, which is the only thing a red run should mean.

**The patch gate is a filter, and says so.** It applies the diff, confines it to
the paths the finding named, holds `terraform validate` and `terraform fmt
-check`, and confirms by re-scan that the target key is gone and that no new key
appeared. It claims nothing beyond that: no gate here can see that a patch
stranded a subnet's instances. A passed patch becomes a pull request naming the
key, the verdict and the rationale; a rejected one becomes a comment on the issue
naming the gate it failed, so a failure teaches something instead of
disappearing. What accepts a patch is the merge.

**Alert state is derived from what a human does on the tracker.** Closing an item
that carries `wontfix` dismisses the alert its **Alert** row names, with the
issue URL as the dismissal comment. It is keyed on the label rather than on the
close, because a merged remediation pull request closes its item as *completed*
and that alert closes on its own at the next scan. It is a derivation from a
decision, not a store: nothing accumulates and nothing is queried later.

## Hard constraints (violate these and it breaks)

- **No pull request from a fork may cause a run that reads `AI_API_TOKEN`.**
  Triage runs on `workflow_run` from the scan's completion, so the boundary is a
  job condition rather than the `on:` block: it pins `workflow_run.event ==
  'push'` and `head_branch == 'main'`. This is the more dangerous form of the
  constraint — a `workflow_run` handler runs from the default branch *with full
  secrets access*, and the scan runs on `pull_request` — so the test asserts the
  condition, not the trigger list. An assertion over the trigger list passes
  against the vulnerable version.
- **A finding is promoted to at most one tracker item, ever.** The exclusion and
  the filer must agree on what a tracker item records, or a re-triaged finding
  gets a second item and the key stops being a join. They agree by sharing
  `issue_body.py`, which is the one place a body and its comments are read back
  into a verdict.
- **The job that runs the model never holds a write permission; the job that
  writes never sees the token.** `taskflow/tests/test_workflows.py` asserts it
  per job.
  The tracker read widens the triage job to `issues: read` and no further — it
  decides what to triage and may not open what it decides on. It holds
  identically on the remediation side: the job running the model holds nothing,
  the job that applies a model-authored diff holds neither a write permission nor
  a push credential, and the job opening the pull request holds `contents: write`
  and `pull-requests: write` and no token.
- **`security-events: write` is held by the reconciliation path and nowhere
  else.** `iac-security-reconcile.yml` dismisses an alert when its issue is
  closed `wontfix`, carrying a human decision rather than forming one. The issue
  filer holds `security-events: read`, to record the alert's number on the issue.
  The scan holds the permission too and is not a second writer: GitHub accepts
  nothing narrower for publishing a SARIF report, so the test enumerates both
  holders and asserts the scan reaches no alert.
- **The pipeline never applies the label that authorises remediation.** An agent
  able to apply it would be authorising its own downstream work.
  `ready-for-remediation` and `ready-for-agent` are both absent from the
  emittable vocabulary, and a label outside that vocabulary raises rather than
  being filed.
- **The scan workflow must not reference the triage workflow.** Triage being
  broken, unfunded or unrun must never stop a finding being published. Declaring
  the `workflow_run` trigger on the triage side is what keeps this true.
- **Below threshold means untriaged, never dismissed.** Dismissal is a verdict
  and none has been formed. Those findings keep their key, so lowering the
  threshold extends what has been judged rather than resetting it — as it did at
  MEDIUM.
- **A patch is filtered, never accepted, by anything other than a human.** The
  gate makes review cheap; it does not make review unnecessary, and the pull
  request body says so where the reviewer will read it.
- **A verdict without a rationale is discarded, and discarded is not dropped.**
  The finding survives as `undetermined` carrying `discarded_verdict` and
  `discarded_because`. A finding that vanished from a run would be invisible to
  the tracker. An eligible finding that no verdict record reached is discarded on
  the same rule and filed as `undetermined`, since only `file_issues.py` compares
  the verdicts against the whole eligible set.

## What the pipeline claims

**It routes and reasons; it does not claim to be measurably right.** There is no
agreement figure and there will not be one for this corpus. The eligible findings
were released to the agent untriaged, at the repository owner's instruction, for
speed — so every verdict this corpus has ever carried was written by the model,
and a verdict cannot score the model that wrote it. The forfeit is one-way: a
finding the agent has judged can no longer be given an independent human verdict.

The corpus is also too narrow to carry an accuracy claim even once clean: 9
findings over 8 rules, 7 of which fire exactly once, reducing to roughly four
distinct judgment calls. That is the direct reason autonomy was dropped rather
than tuned — an earned-authority gate needs support that this corpus cannot
supply, and ADR-0008 puts autonomous dismissal out of scope permanently rather
than unearned.

## Deferred

- **Plan-JSON scanning.** Static HCL only today.
- **Non-Terraform IaC** — Ansible, shell, `user_data`.

Both are deferred without a mechanism: nothing is staged for them, and taking
either on is a design change rather than a configuration one.

## Boundaries worth keeping

Everything under `security/iac_security/` is stdlib Python: no framework, no
network, no cloud credentials. `taskflow/` is the single exception and the
boundary is deliberate — it holds the only part needing
`seclab-taskflow-agent`, Docker and a model token, so replacing the orchestration
engine touches that directory and nothing else. The scanner, the identity scheme,
the fixture, the gate and the reconciler do not know it exists.

`vocabulary.py` defines the four verdict classes once, shared by both
personalities, so they cannot drift apart. `upstream` is kept out of that set:
ownership is decided by path, not by triage, so it is not a verdict.
`real-mechanical` is advice to whoever labels the issue: nothing enforces it,
because routing is the label and never the verdict.

The corpus assembler may contain code and never prose, enforced by only ever
globbing `.tf`. It is structurally the same shape as the document-context
assembler ADR-0008 deleted, and the distinction is what it may hold rather than
what it does. A test asserts both its extension filter and the exact file set it
produces.

Each agent selects its model in its own file under `taskflow/model_configs/`,
one for triage and one for remediation, so a model swap for one flow cannot
silently swap the other. Both name Anthropic's Messages API through
`backend: anthropic_sdk` rather than the framework's Copilot default.
The `endpoint` field is what makes authentication correct: the framework's
`get_provider()` does not recognise `api.anthropic.com`, so the token goes out as
`x-api-key` rather than as a bearer token that endpoint would reject. Swapping
models is a one-line edit to `models:`.

## Verification

    python3 -m unittest discover -s security/iac_security/tests           # 147
    python3 -m unittest discover -s security/iac_security/taskflow/tests  # 221

Both suites are offline — no Trivy, no AWS, no Docker, no model token, no
network, and no Terraform. They run against the committed baseline, and the tests
that matter most *derive* their expectations from it rather than restating them,
so they move when the findings do: that no first-party key is claimed twice, and
that the fork boundary holds per job. `fixtures/baseline-scan.json` is what the
suites scan instead of Trivy, and is no run's default report.

## Sources

- `security/iac_security/CONTEXT.md` — the domain language this document uses
- `security/iac_security/README.md` — the deterministic half, in operating detail
- `security/iac_security/taskflow/README.md` — the agentic half, ditto
- `docs/adr/0008-this-repository-is-not-a-memory-bank.md` — why there is no store,
  and why the corpus is the code
