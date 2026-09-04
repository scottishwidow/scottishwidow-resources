# 7. Autonomous alert dismissal is earned per rule, on agreement *and* support

Date: 2026-09-03

## Status

Superseded by [ADR-0008](./0008-this-repository-is-not-a-memory-bank.md).

Not overturned on its own terms — the reasoning below still holds, and ADR-0008
says so explicitly. What retires it is the rule that no persistent context exists
here for an agent's benefit: an earned-authority mechanism is inherently an
accumulating store, and computing it from live API history rather than a file only
moves the accumulation. Autonomous dismissal is now out of scope permanently
rather than unearned.

## Context

The IaC triage pipeline (`security/iac_security/`) has a model assign a verdict to
each security finding this repository's own code produces. Four verdicts are possible, and
one of them — `not-applicable` — is a claim that the finding need not be looked at again.
Acting on that claim automatically means closing a code scanning alert with no human
between the model and the closure.

That is the one place in this pipeline where a mistake is worse than having built nothing.
A triage agent that wrongly dismisses a real finding does not merely fail to help; it
**manufactures confidence**. The alert is closed, the queue looks clean, and the finding is
now invisible in a way it was not before the scanner ran. Every other failure in this
system degrades to "a human still has to look at it", which is where we started.

So the question is not whether the model is good at triage. It is: what evidence would
justify letting it close an alert unattended, and how much of it?

The obvious answer — measure agreement against human verdicts and set a threshold — is not
sufficient here, and the reason is visible in the corpus rather than theoretical. Of the
seven triage-eligible findings, **five of the six rules fire exactly once**. The largest,
`AWS-0164`, is n=2:

```
  5  bootstrap state bucket   AWS-0086/0087/0091/0093/0132   (n=1 each)
  2  public subnets           AWS-0164 x2                    (n=2)
```

An agreement-only gate at 100% would therefore hand five of the six rules permanent
unsupervised dismissal authority on the strength of **a single case going the right way**.
A coin landing well twice in a row would unlock most of the ruleset. The measurement would
be real, the figure would be "100%", and it would mean nothing.

## Decision

Autonomous dismissal is granted **per rule ID**, and requires all three of:

| | bar | why |
|---|---|---|
| **Agreement** | 100% against the human-assigned corpus | one wrong dismissal is the failure this exists to prevent; there is no acceptable error rate for closing an alert unattended |
| **Support** | scored over **`k = 5`** findings for that rule | so that unanimity is not cheap |
| **Grant** | the rule ID present in `security/iac_security/autonomy.json` | evidence never grants authority on its own; a human's reviewable diff does |

**The support floor is the load-bearing half.** The agreement bar is the one that looks
strict and is in fact almost free — it is trivially met at n=1, which is precisely the
situation the corpus is in. The floor is what makes the agreement figure mean something,
and it is the number to argue about. `k = 5` is a judgment rather than a derivation: small
enough to be reachable as the corpus widens, large enough that unanimity across five
independent findings is not luck. It is deliberately greater than one, so that full
agreement over a single case can never confer authority no matter how the rest is
configured; `autonomy.py` refuses to load a policy with a floor of 1 or less rather than
treating that as a valid setting.

The allowlist is **necessary and not sufficient**. Evidence is re-checked at run time
against the scoring report, so a rule that was granted authority and has since disagreed
loses it without anyone remembering to edit the file. The allowlist can only ever narrow
what the evidence permits, never widen it — a grant that outlives its evidence is reported
as an error, not honoured.

Everything else is **proposed, not applied**: the verdict travels to a human as a GitHub
issue under `needs-triage` and the alert stays open behind it. That covers a rule never
scored, a rule scored below full agreement, a rule agreed on every case but over too few
findings, and a rule that would qualify but has not been granted.

### The evidence behind the current allowlist

**The allowlist is empty**, and on the current corpus no rule could qualify for it:

- The largest eligible rule is `AWS-0164` at n=2, against a floor of 5. Even unanimous
  agreement on every eligible finding leaves every rule short — this is asserted by a test
  derived from the corpus rather than written down, so it moves when the corpus does.
- The ground-truth fixture is not yet complete (1 of 7 entries), and the single entry that
  exists was written by a model, not a human. It carries `verdict_author: model` and the
  scorer excludes it, so the corpus currently supports **no** agreement figure at all.

Phase 2 of the ratchet is therefore unreachable today. That is the correct outcome and a
better claim than an auto-dismissal justified by n=1.

The corpus becomes able to carry this once `live/gitlab/` exists and contributes RDS,
ElastiCache and load balancer findings, and once the severity threshold is lowered to
readmit the two `MEDIUM` findings that were the most independent judgments in the original
set.

### Reversibility

A dismissal is an edit, never a deletion. The alert remains listed under
`--state dismissed`, the rationale and the finding key are written onto it as the
dismissal comment, and `autonomy.py --reopen <alert>` puts it back. Withdrawing a grant is
a one-line diff to `autonomy.json`; withdrawing the evidence behind it does the same thing
on its own.

## Consequences

- **Autonomy is a ratchet, not a setting.** It widens only as measured evidence
  accumulates, and it narrows automatically when the evidence stops supporting it.
- **The pipeline is useful before any rule is allowlisted.** Phase 1 — propose everything,
  a human applies it — is the whole system minus the closing act, and it is where the
  system lives today.
- **This is the transferable part.** "We let a model triage" is not a case anyone can take
  to a security review. "Here is per-rule agreement, here is the support behind each
  figure, and here is the policy gating autonomy on both" is.
- **Someone will want to lower `k`.** The pressure will come when a rule sits at n=3 with
  perfect agreement and the queue is annoying. The answer is to widen the corpus, not the
  gate — that is what this record exists to say to whoever asks later, including us.
- **The floor cannot be met by repetition.** Five findings of one rule against five copies
  of the same resource is one judgment counted five times. The corpus's diversity, not just
  its size, is what the figure rests on, and that caveat travels with every agreement
  number this pipeline reports.
