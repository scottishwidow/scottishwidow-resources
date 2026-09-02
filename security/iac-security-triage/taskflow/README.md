# Triage taskflow

The agentic half of the pipeline: a `seclab-taskflow-agent` taskflow that reads
the eligible findings produced by `../normalise.py` and assigns each a verdict
with a rationale. Propose-only — it changes no alert and files no issue.

## Running it

```sh
export AI_API_TOKEN=<an Anthropic API key>
./run.sh                        # the scoped, reproducible, propose-only run
./run.sh --lint --strict        # validate offline: no model, no token, no network
./run.sh -g scope_keys=         # every eligible finding
./run.sh -g report=             # live Trivy scan instead of the baseline

python3 collect_verdicts.py --latest --findings <(./scan.sh) -o ../runs/local.json
python3 ../score.py --run ../runs/local.json
```

The token can instead go in a `.env` file in this directory, which the framework
reads itself (`load_dotenv(find_dotenv(usecwd=True))`) and which `.gitignore`
excludes:

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

`run.sh` mounts the repository root into the published image and enters this
directory, because the framework resolves `-t taskflows.iac_triage` with
`importlib.resources.files()` — every component of a dotted name has to be a
legal Python identifier, and `iac-security-triage` is not one. Entering below
the hyphen is what makes these assets addressable.

## Shape

```
findings   run:   ./scan.sh  ->  {eligible, below_threshold, vendored}   deterministic
context    run:   ./context.py  ->  {documents: [ADRs, design docs]}     deterministic
verdicts   over:  outputs.findings.eligible   one branch per finding     the only model step
```

Only `eligible` is fanned out over, so the ownership-then-severity order of
`design.md - Decision 2` holds at the point where it costs money: a vendored or
below-threshold finding is never in a prompt.

## Why the agent has no tools

The `toolboxes` list is empty, deliberately. Every fact the agent may use
arrives in its prompt — the finding record and the decision records — so:

- a run is reproducible from its inputs, and the exact bytes the model saw are
  recoverable from the run manifest;
- there is no path from a run to a dismissal, an issue, or the network, whatever
  a prompt says. `tasks.md` 4.6 is then a structural property rather than a
  behaviour to be observed and hoped for;
- the agent cannot read alert state, and so cannot read a verdict it is about to
  be scored against. Read-only access would not be enough here.

The cost is that context is pushed rather than pulled: every document goes into
every finding's prompt. That is affordable only because the deterministic
filters cut twenty findings to seven.

## The discard rule

A verdict without a rationale is discarded and the finding recorded as
`undetermined` (`spec.md - Scenario: Rationale is unavailable`). It is enforced
twice, on purpose:

- the taskflow's `outputs` schema rejects the branch (`rationale` is required,
  `minLength: 1`), so a non-compliant response never becomes a value;
- `collect_verdicts.py` applies the rule again over every branch, catching what
  a schema cannot — a whitespace-only rationale, a branch that failed for an
  unrelated reason, a verdict outside the vocabulary, a reply that was not JSON.

The second is not redundancy for its own sake. The schema is a config file, and
the property should not depend on one line of YAML staying right.

Discarded is not dropped: the finding still appears in the output as
`undetermined`, carrying `discarded_verdict` and `discarded_because`. A finding
that vanished from a run would be invisible to both scoring and the tracker.

## Scope

`globals.scope_keys` confines a run to named findings. It currently holds the
two `AWS-0164` subnet findings, and the reason is ordering rather than cost.

A finding the agent has judged can no longer be given an *independent* human
verdict — whoever labels it afterwards has seen the answer. So the run is
confined to findings whose ground truth is already recorded, and the other five
stay clean until they are triaged in code scanning. Widening the scope after
labelling more of them is what `tasks.md` 3.6 asks to be shown, exercised rather
than argued.

## Files

| | |
|---|---|
| `taskflows/iac_triage.yaml` | the pipeline: two shell tasks and one fan-out |
| `personalities/iac_triage.yaml` | the system prompt: vocabulary, rationale requirement |
| `scan.sh` | scan or replay, then normalise. A `run:` field is not templated, so configuration arrives as `TRIVY_REPORT` |
| `context.py` | the decision records, as JSON. `--without-context` is the control arm of the comparison deferred in 5.2 |
| `collect_verdicts.py` | run manifest → scoreable verdict records, applying the discard rule |
| `model_configs/iac_triage.yaml` | the model and the API behind it: Anthropic, not the framework's Copilot default |
| `run.sh` | the Docker invocation, with the mounts the above needs |
| `.agent-data/` | gitignored. The agent's data directory, bound out of the container so the run manifest survives it |

`.agent-data/` is deliberately not `../runs/`: `export_fixture.py` treats a
non-empty `runs/` as proof that a triage run has already happened and refuses to
write ground truth afterwards. Scratch state landing there would spend that
guard without a run ever having happened.

## Tests

```sh
python3 -m unittest discover -s security/iac-security-triage/taskflow/tests
```

Offline — no Docker, no model, no network. They cover the discard rule against
deliberately non-compliant responses, the scope expression against the baseline
corpus, the vocabulary staying shared between `vocabulary.py`, the schema and
the prompt, and the workflow boundary that keeps `AI_API_TOKEN` out of reach of
a fork.
