# Triage taskflow

The agentic half of the pipeline: a `seclab-taskflow-agent` taskflow that reads
the eligible findings produced by `../normalise.py`, drops the ones the tracker
already holds, and assigns each of the rest a verdict with a rationale.
Propose-only — it changes no alert and files no issue.

## Running it

```sh
export AI_API_TOKEN=<an Anthropic API key>
./run.sh                                                              # live Trivy scan, propose-only
./run.sh --lint --strict                                              # validate offline: no model, no token, no network
./run.sh -g report=security/iac_security/fixtures/baseline-scan.json  # replay the committed baseline instead
./run.sh -g tracker=security/iac_security/runs/tracker.json           # exclude on a tracker snapshot read here
./run.sh -g bypass=true                                               # triage every eligible finding again

python3 collect_verdicts.py --latest -o ../runs/local.json
```

Every run needs a tracker, because the exclusion halts rather than triaging
everything by accident. A snapshot is what the `outstanding` task reads when
`tracker` names one, and it is read on the host because the published image
carries neither `gh` nor a token:

```sh
gh issue list --state all --limit 500 --json number,state,body,comments \
  > ../runs/tracker.json
```

Named without one, the task runs `gh` itself and fails where the image has none.
`-g bypass=true` needs no tracker at all: it reads none.

The token can instead go in a `.env` file at the repository root, which the
framework reads itself (`load_dotenv(find_dotenv(usecwd=True))`) and which
`.gitignore` excludes:

    AI_API_TOKEN=<an Anthropic API key>

`run.sh` forwards a token with a bare `-e AI_API_TOKEN`, and only when the host
has one. That detail matters: `load_dotenv` does not override a variable already
present in the environment, and an empty string counts as present, so passing
`-e AI_API_TOKEN=""` would shadow the `.env` and fail with "AI_API_TOKEN
environment variable is not set" while the file holding it sat right here.

## The model

`model_configs/iac_triage.yaml` selects Anthropic's Messages API, and
`taskflows/iac_triage.yaml` names its logical model on the `verdicts` task.

The framework's own documentation asks for a GitHub PAT with Copilot access,
which is a fact about its *default* rather than a requirement: `capi.py`
registers `api.githubcopilot.com` as the default provider, and the engine also
ships an Anthropic backend driving `/v1/messages` through the official SDK.
Selecting it is two fields — `backend: anthropic_sdk` and an `endpoint` — and it
is the `endpoint` that makes authentication right: `get_provider()` does not
recognise `api.anthropic.com`, so the token goes out as `x-api-key` rather than
as a bearer token an Anthropic endpoint would reject.

The token keeps the framework's own variable name, `AI_API_TOKEN`, and holds an
Anthropic API key. A provider-specific name would read better and cost more: the
fork boundary asserted in `tests/test_workflows.py` is written around one
variable, and a second name is a second thing that has to stay confined.

Swapping models is a one-line edit to `models:` in the model config. Reverting
to Copilot is deleting the `model_config:` line from the taskflow and supplying
a PAT.

`run.sh` mounts the repository root into the published image and stays there,
passing the taskflow's full dotted name,
`-t security.iac_security.taskflow.taskflows.iac_triage`. The framework
resolves that with `importlib.resources.files()`, which requires every
component of a dotted name to be a legal Python identifier — the reason this
package is `iac_security` rather than `iac-security-triage`.

## Shape

```
findings     run:   scan.sh                       ->  {eligible, below_threshold, vendored}  deterministic
outstanding  run:   scan.sh | outstanding.py      ->  {findings: eligible minus tracked}     deterministic
corpus       run:   terraform_corpus.py           ->  {documents: every .tf file}            deterministic
verdicts     over:  outputs.outstanding.findings  ->  one branch per finding                 the only model step
```

The fan-out reads `outstanding`, which reads `eligible`, so the
ownership-then-severity order of `design.md - Decision 2` holds at the point
where it costs money: a vendored or below-threshold finding is never in a prompt.

`run:` is not templated, so `outstanding` cannot read `outputs.findings` and
names the report again through `TRIVY_REPORT`. A named report is replayed rather
than rescanned, so the two tasks partition one report; only a live local run pays
for a second scan.

## The tracker exclusion

Triage costs nothing when nothing changed. A merge that touches no Terraform
found the same findings as the merge before it, and every one of them already has
a tracker item — so `outstanding.py` drops them before the fan-out reaches a
model, and a run whose findings are all tracked reaches no model at all.

| the tracker holds | what happens |
|---|---|
| nothing for this key | triaged |
| an open item recording `undetermined` | triaged again; the verdict arrives as a comment on that item |
| an open item recording any other verdict | not triaged |
| a closed item, whatever it records | not triaged |

Three things about the rule:

- **It is not in `normalise.py` and is not a fourth `triage_status`.**
  `normalise.py` is pure and replayable against a committed fixture, and its
  value is that it makes no network call. `triage_status` is the outcome of the
  two deterministic filters, and both are properties of the *finding*; "has a
  tracker item" is a property of the *tracker*, and it changes without the
  finding changing.
- **It changes no filing behaviour.** `file_issues.py` already listed issues
  `--state all` and skipped a key that was present. The exclusion moves the
  saving to before the money is spent.
- **A closed item keeps its finding excluded.** A reintroduced finding reopens
  its code scanning alert, which is where that state belongs.

`undetermined` is the exception because it is what the discard rule records when
a reply is unparseable, has no rationale, or never arrives. It is a failure to
judge, not a judgment, so excluding on it would let one bad reply silence a
finding permanently, curable only by deleting an issue by hand. Because the item
exists, the second verdict is commented onto it and nothing is opened —
`issue_body.py` then reads that comment as the verdict the item records, so the
finding is not triaged a third time.

An unreadable tracker halts the run (`must_complete: true`) rather than
excluding nothing: triaging everything is the bill this task exists to remove,
and it should not be paid by accident.

## The bypass

`-g bypass=true` triages the whole eligible set, tracker item or not. In CI it is
set only by a dispatched run — `workflow_dispatch` carries a `retriage_tracked`
input — and it never fires on the automatic `workflow_run` path. A dispatched run
also passes `--dry-run` at the filing step unless a second input asks otherwise,
so testing verdicts costs tokens and artifacts but no tracker churn.

## Why the agent has no tools

The `toolboxes` list is empty, deliberately. Every fact the agent may use
arrives in its prompt — the finding record and the Terraform corpus — so:

- a run is reproducible from its inputs, and the exact bytes the model saw are
  recoverable from the run manifest;
- there is no path from a run to a dismissal, an issue, or the network, whatever
  a prompt says. `tasks.md` 4.6 is then a structural property rather than a
  behaviour to be observed and hoped for. It is the *agent's* reach that is
  empty, not the deterministic tasks': those run the scanner and read the
  tracker, and neither is reachable from a prompt;
- the agent cannot read alert state, and so cannot read a verdict it is about to
  be scored against. Read-only access would not be enough here.

The cost is that the corpus is pushed rather than pulled: every first-party
`.tf` file goes into every finding's prompt. ADR-0008 sizes that cost at 24
files, 770 lines — about 6k tokens per finding, cacheable, and affordable enough
that pull is not worth building until the corpus is roughly ten times larger.

Cacheable only if the prompt is ordered for it. A cache prefix must be common to
every branch of the fan-out: the personality is common already, and the corpus is
common only while nothing per-finding precedes it. So the prompt runs personality,
then corpus, then the finding and the instruction to reply — which is also the
better prompt, because the model answers about the last thing it read. How much
this actually saves depends on how the framework schedules the fan-out: branches
that run fully in parallel all miss the cache together. Establish that before
quoting a figure.

The prompt tells the agent the corpus is complete, and the personality withdraws
"I was not shown enough" as a reason on that promise. `terraform_corpus.py`
therefore exits non-zero when a corpus root is missing or the corpus is empty,
and `must_complete: true` halts the run. A bad mount stops the pipeline instead
of triaging every finding against nothing while claiming to show everything.

## The discard rule

A verdict without a rationale is discarded and the finding recorded as
`undetermined` (`spec.md - Scenario: Rationale is unavailable`). Two things
enforce it, and they check different halves:

- the taskflow's `outputs` schema requires the branch to have produced a
  non-empty string, so a branch that said nothing fails at the framework
  boundary;
- `collect_verdicts.py` checks the shape — that the reply parses, that the
  verdict is in the vocabulary, that the rationale is not absent, empty or
  whitespace.

The schema used to describe the verdict object too, and it could not. The
framework decodes a captured response with a bare `json.loads`
(`results.py`), so a fenced reply is a string — and Sonnet fences its JSON on
every run, however plainly the personality asks it not to. An object schema
therefore failed every real verdict and recorded the branch as `result: null`,
which is worse than rejecting it: the text is not persisted anywhere, so
`collect_verdicts.py` could no longer say *what* had been discarded or why, and
"discarded is not dropped" quietly became "dropped".

A schema sitting on a prose channel cannot tell a formatting slip from a
refusal. So it checks the one thing it can, and the shape is checked where the
text still exists to be reported.

`collect_verdicts.py` sees through a fence around the whole reply, and nothing
more. Prose with an object somewhere inside it stays unparseable and is
discarded, because hunting for the first `{` would turn the discard rule into a
scraper — accepting a reply that answered a different question in a different
shape.

Discarded is not dropped: the finding still appears in the output as
`undetermined`, carrying `discarded_verdict` and `discarded_because`. A finding
that vanished from a run would be invisible to both scoring and the tracker.

## Files

| | |
|---|---|
| `taskflows/iac_triage.yaml` | the pipeline: three shell tasks and one fan-out |
| `personalities/iac_triage.yaml` | the system prompt: vocabulary, rationale requirement |
| `scan.sh` | scan or replay, then normalise. A `run:` field is not templated, so configuration arrives as `TRIVY_REPORT` |
| `outstanding.py` | the eligible set minus what the tracker already holds, on `TRACKER_ITEMS` and `TRIAGE_BYPASS_TRACKER` |
| `terraform_corpus.py` | every first-party `.tf` file, as JSON (ADR-0008) |
| `collect_verdicts.py` | run manifest → verdict records, applying the discard rule |
| `model_configs/iac_triage.yaml` | the model and the API behind it: Anthropic, not the framework's Copilot default |
| `run.sh` | the Docker invocation, with the mounts the above needs |
| `../runs/` | gitignored. The agent's data directory, bound out of the container so the run manifest survives it, alongside the verdicts collected from it |

## Tests

```sh
python3 -m unittest discover -s security/iac_security/taskflow/tests
```

Offline — no Docker, no model, no network. They cover the discard rule against
deliberately non-compliant responses, the vocabulary staying shared between
`vocabulary.py`, the schema and the prompt, and the workflow boundary that keeps
`AI_API_TOKEN` out of reach of a fork.
