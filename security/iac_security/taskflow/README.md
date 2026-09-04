# Triage taskflow

The agentic half of the pipeline: a `seclab-taskflow-agent` taskflow that reads
the eligible findings produced by `../normalise.py` and assigns each a verdict
with a rationale. Propose-only — it changes no alert and files no issue.

## Running it

```sh
export AI_API_TOKEN=<an Anthropic API key>
./run.sh                        # the reproducible, propose-only run
./run.sh --lint --strict        # validate offline: no model, no token, no network
./run.sh -g report=             # live Trivy scan instead of the baseline

python3 collect_verdicts.py --latest --findings <(./scan.sh) -o ../runs/local.json
```

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
findings   run:   ./scan.sh  ->  {eligible, below_threshold, vendored}       deterministic
corpus     run:   ./terraform_corpus.py  ->  {documents: [every .tf file]}  deterministic
verdicts   over:  outputs.findings.eligible   one branch per finding         the only model step
```

Only `eligible` is fanned out over, so the ownership-then-severity order of
`design.md - Decision 2` holds at the point where it costs money: a vendored or
below-threshold finding is never in a prompt.

## Why the agent has no tools

The `toolboxes` list is empty, deliberately. Every fact the agent may use
arrives in its prompt — the finding record and the Terraform corpus — so:

- a run is reproducible from its inputs, and the exact bytes the model saw are
  recoverable from the run manifest;
- there is no path from a run to a dismissal, an issue, or the network, whatever
  a prompt says. `tasks.md` 4.6 is then a structural property rather than a
  behaviour to be observed and hoped for;
- the agent cannot read alert state, and so cannot read a verdict it is about to
  be scored against. Read-only access would not be enough here.

The cost is that the corpus is pushed rather than pulled: every first-party
`.tf` file goes into every finding's prompt. ADR-0008 sizes that cost at 24
files, 770 lines — about 6k tokens per finding, cacheable, and affordable enough
that pull is not worth building until the corpus is roughly ten times larger.

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
| `taskflows/iac_triage.yaml` | the pipeline: two shell tasks and one fan-out |
| `personalities/iac_triage.yaml` | the system prompt: vocabulary, rationale requirement |
| `scan.sh` | scan or replay, then normalise. A `run:` field is not templated, so configuration arrives as `TRIVY_REPORT` |
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
