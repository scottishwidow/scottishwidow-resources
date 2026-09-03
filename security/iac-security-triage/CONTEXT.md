# IaC security triage

The pipeline that scans this repository's Terraform for misconfigurations,
decides what each finding means *here*, and records a rationale for every
decision. It spans no AWS environment — it reads the code that defines them all,
and needs no cloud credentials to do it.

Start at [the as-built design](../../docs/design/iac-security-triage.md).

## Language

**Finding**:
One misconfiguration result from Trivy about one resource, normalised into one
record by `normalise.py`. A finding is not a problem — whether it is one is the
verdict, decided later and separately.
_Avoid_: issue (that is the tracker item), alert (that is its state in code
scanning), vulnerability (these are configuration defects, not CVEs).

**Finding key**:
A finding's identity: `ruleId:module_address:resource_type.resource_name`, for
example `AWS-0086:module.bootstrap:aws_s3_bucket.terraform_state_bucket`. It
survives line-number drift, separates two instantiations of one module, and is
readable because it appears in the fixture and in issue bodies. It is the join
between every part of the pipeline.
_Avoid_: id, hash, fingerprint — it is deliberately none of those.

**Owner path** / **code path**:
Two different paths, and the distinction matters. The **code path** is where the
offending code lives (`modules/bootstrap/main.tf`); the **owner path** is where
it is instantiated (`live/management/bootstrap/main.tf`), taken from the
finding's first `Occurrences[].Filename`. **Ownership is decided on the owner
path**, because that is what says whether this repository can fix it.
_Avoid_: "the file" — say which one.

**Ownership** — *first-party* or *vendored*:
Whether a finding lies in code maintained here or in a third-party module pulled
into `.terraform/modules/`. Decided by path comparison, never by a model. An
unrecognised path is treated as first-party, so nothing escapes triage by being
somewhere unexpected.
_Avoid_: ours/theirs, internal/external.

**Triage status** — *eligible*, *below-threshold*, or *upstream*:
The outcome of the two deterministic filters, in that order. `upstream` is what
a vendored finding carries; it is a *status*, not a verdict, because ownership is
settled by path rather than by judgment.
_Avoid_: filtered, ignored, suppressed, excluded — see below.

**Below-threshold**:
A first-party finding under the configured severity threshold. It is **untriaged,
not dismissed**: its alert stays open, it gets no tracker item, and no verdict is
formed for it. It keeps its finding key, so lowering the threshold extends the
corpus rather than resetting it.
_Avoid_: suppressed, ignored, muted, closed — all of them assert a decision that
has not been made.

**Severity threshold**:
The `MEDIUM` in `config.json`. A recorded configuration value, applied *after*
ownership, so moving it is a reviewable diff rather than an edit to logic.

**Verdict**:
Exactly one of four classes from `vocabulary.py`, assigned only to eligible
findings: `not-applicable` (inapplicable here, or a knowingly accepted risk),
`real-mechanical` (real, fix needs no judgment about this system),
`real-judgment` (real, fix does), `undetermined` (not decidable from the context
available).
_Avoid_: false positive — it collapses "the scanner is wrong" into "this does not
apply here", which are different findings about different things. Say
`not-applicable` and give the rationale.

**Rationale**:
The prose accompanying a verdict, required for it to count. A verdict without one
is discarded, not stored bare.

**Discard rule**:
What happens to a verdict that arrives malformed or without a rationale: it is
dropped *as a verdict*, and the finding is recorded `undetermined` carrying
`discarded_verdict` and `discarded_because`. **Discarded is not dropped** — the
finding still appears in the run, because one that vanished would be invisible to
both scoring and the tracker.

**Alert** / **alert state**:
The finding's durable per-finding state in GitHub code scanning: open or
dismissed. This is where a *human* triage decision is recorded.
_Avoid_: using alert and finding interchangeably — the alert is the state, the
finding is the thing.

**Tracker item**:
The GitHub issue a triaged finding is promoted to, under `needs-triage`, carrying
the verdict and rationale in readable form. Code scanning holds state; Issues hold
work. Every triaged finding gets one, whatever its verdict.

**Ground truth** / **the corpus**:
`fixtures/ground-truth.yaml` — verdicts *exported* from recorded triage by
`export_fixture.py`, never authored by hand. It is a snapshot of alert and issue
state, not a second place a verdict can be written.
_Avoid_: labels, annotations, the answer key.

**Provenance** (`verdict_author`):
Whether an entry's verdict came from a `human`, a `model`, or an undeclared
`unknown`. Load-bearing: **only `human` entries may contribute to an agreement
figure**, because a verdict written by a model cannot score that model. Today
every entry is `model`, which is why there is no agreement figure.

**Agreement** and **support**:
Agreement is the rate at which automated verdicts match human ones for a rule.
Support is the number of findings behind that rate. **Neither is ever reported
without the other** — most rules here fire once, so an unsupported agreement
figure is a coin flip reported as a measurement.

**Support floor**:
The minimum scored findings a rule needs before full agreement can confer
dismissal authority (`k = 5`, in `autonomy.json`). A judgment, not a derivation.
It exists so unanimity over a single case never earns anything.

**Allowlist**:
The set of rules granted autonomous dismissal. Currently empty, and necessary
rather than sufficient — evidence is re-checked at run time, so it can only
narrow what the measurement permits, never widen it.

**Propose-only**:
The pipeline's current posture: it forms verdicts, files them as issues, and
touches no alert state. Everything is a proposal to a human until a rule earns
otherwise.
_Avoid_: read-only — it does write issues.
