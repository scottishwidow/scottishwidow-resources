#!/usr/bin/env python3
"""Turn a triage run's manifest into a scoreable verdict list.

The taskflow's fan-out task publishes one branch per eligible finding. The
framework writes those branches into the run manifest as
``outputs.<id> = [{"model": ..., "item": ..., "result": ...}]``; this reads that
and emits the flat ``[{key, rule_id, verdict, rationale, evidence}]`` shape
``score.py`` and the issue step consume.

The whole point of this step is the discard rule (`spec.md - Scenario: Rationale
is unavailable`, `tasks.md` 4.5):

    A verdict produced without a rationale is discarded and the finding is
    recorded as `undetermined`.

This is where the shape of a verdict is checked, and the taskflow's `outputs`
schema no longer attempts it. A schema sitting on a captured *response* cannot:
the framework decodes it with a bare ``json.loads``, so a model that fences its
JSON fails the schema and its branch is recorded as ``result: null`` -- the
verdict destroyed rather than reported. The schema now checks only that a branch
produced something, which is the half it can enforce, and the shape is checked
here, where the text still exists to be reported.

Discarded is not dropped. A finding whose verdict was thrown away still appears
in the output as `undetermined`, carrying why it was discarded, because a
finding that vanishes from a run is invisible to both scoring and the tracker.

Usage::

    collect_verdicts.py --manifest .agent-data/artifacts/<id>/manifest.json
    collect_verdicts.py --latest -o ../runs/2026-09-02T12:00:00.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
TRIAGE_DIR = HERE.parent
AGENT_DATA = HERE / ".agent-data"
RUNS = TRIAGE_DIR / "runs"

sys.path.insert(0, str(TRIAGE_DIR))
import vocabulary  # noqa: E402

UNDETERMINED = "undetermined"

# Why a verdict was replaced by `undetermined`, recorded on the record itself.
DISCARD_MISSING_RATIONALE = "no rationale supplied"
DISCARD_BLANK_RATIONALE = "rationale was empty or whitespace"
DISCARD_UNKNOWN_VERDICT = "verdict not in the vocabulary"
DISCARD_NO_RESULT = "branch produced no result"
DISCARD_UNPARSEABLE = "branch result was not a JSON object"


def latest_manifest(root: pathlib.Path = AGENT_DATA) -> pathlib.Path:
    """The most recently written manifest under the agent data directory."""
    manifests = sorted(
        root.glob("artifacts/*/manifest.json"),
        key=lambda p: p.stat().st_mtime,
    )
    if not manifests:
        raise SystemExit(f"no manifest found under {root}; has a triage run happened?")
    return manifests[-1]


def unfence(text: str) -> str:
    """Strip a markdown code fence wrapping the whole of *text*, if there is one.

    Narrow on purpose. A fence around the entire reply is a presentation habit
    -- Sonnet applies one to JSON however plainly it is asked not to -- and
    costs nothing to see through. Anything else is not: prose with an object
    somewhere inside it is a model that answered a different question, and
    hunting for the first `{` would turn the discard rule into a scraper. Only
    an opening fence on the first line and a closing fence on the last are
    removed; text outside them leaves the reply unparseable, as it should.
    """
    lines = text.strip().splitlines()
    if len(lines) < 2 or not lines[0].startswith("```") or lines[-1].strip() != "```":
        return text
    # The opening line may carry a language tag (```json) and nothing else.
    if lines[0][3:].strip().isalnum() or not lines[0][3:].strip():
        return "\n".join(lines[1:-1])
    return text


def decode(result: Any) -> dict[str, Any] | None:
    """A branch result is a JSON object, or the text of one, or unusable."""
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            decoded = json.loads(unfence(result))
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None
    return None


def discard(record: dict[str, Any], reason: str) -> dict[str, Any]:
    """Replace a verdict with `undetermined`, keeping what was discarded."""
    record["discarded_verdict"] = record.get("verdict")
    record["verdict"] = UNDETERMINED
    record["discarded_because"] = reason
    return record


def branch_to_record(branch: dict[str, Any], finding_keys: dict[str, str]) -> dict[str, Any]:
    """One fan-out branch to one verdict record, applying the discard rule."""
    result = decode(branch.get("result"))
    item = branch.get("item")
    # The branch index is the fallback identity: a branch that produced nothing
    # cannot tell us which finding it was, but its position still can.
    fallback_key = ""
    if isinstance(item, int):
        fallback_key = list(finding_keys)[item] if item < len(finding_keys) else ""

    if result is None:
        record = {"key": fallback_key, "verdict": None, "rationale": "", "evidence": []}
        record["rule_id"] = finding_keys.get(fallback_key, "")
        return discard(record, DISCARD_NO_RESULT if branch.get("result") is None else DISCARD_UNPARSEABLE)

    key = str(result.get("key") or fallback_key)
    record: dict[str, Any] = {
        "key": key,
        "rule_id": finding_keys.get(key, ""),
        "verdict": result.get("verdict"),
        "rationale": result.get("rationale") or "",
        "evidence": result.get("evidence") or [],
        "model": branch.get("model"),
    }

    if not isinstance(record["evidence"], list):
        record["evidence"] = [str(record["evidence"])]

    rationale = result.get("rationale")
    if rationale is None:
        return discard(record, DISCARD_MISSING_RATIONALE)
    if not isinstance(rationale, str) or not rationale.strip():
        return discard(record, DISCARD_BLANK_RATIONALE)
    if record["verdict"] not in vocabulary.VERDICTS:
        return discard(record, DISCARD_UNKNOWN_VERDICT)

    return record


def collect(
    manifest: dict[str, Any],
    findings: dict[str, str],
    output_id: str = "verdicts",
) -> list[dict[str, Any]]:
    """Flatten the named fan-in output into verdict records."""
    outputs = manifest.get("outputs") or {}
    if output_id not in outputs:
        raise SystemExit(
            f"manifest has no output {output_id!r}; it has: "
            + (", ".join(sorted(outputs)) or "(none)")
        )
    branches = outputs[output_id]
    if not isinstance(branches, list):
        raise SystemExit(f"output {output_id!r} is not a fan-in list; got {type(branches).__name__}")

    return [branch_to_record(branch, findings) for branch in branches]


def finding_rule_ids(path: pathlib.Path | None) -> dict[str, str]:
    """Key -> rule ID for the eligible findings, so records carry their rule."""
    if path is None or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {f["key"]: f["rule_id"] for f in data.get("eligible", [])}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", help="path to a run manifest.json")
    source.add_argument(
        "--latest",
        action="store_true",
        help=f"use the newest manifest under {AGENT_DATA}",
    )
    parser.add_argument(
        "--findings",
        help="normalised findings JSON, to attach a rule ID to each verdict",
    )
    parser.add_argument("--output-id", default="verdicts", help="the taskflow task id to read")
    parser.add_argument("-o", "--output", help="write here instead of stdout")
    args = parser.parse_args(argv)

    path = latest_manifest() if args.latest else pathlib.Path(args.manifest)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    findings = finding_rule_ids(pathlib.Path(args.findings) if args.findings else None)

    records = collect(manifest, findings, args.output_id)

    discarded = [r for r in records if r.get("discarded_because")]
    if discarded:
        print(
            f"{len(discarded)} of {len(records)} verdicts discarded and recorded as "
            f"{UNDETERMINED}:",
            file=sys.stderr,
        )
        for record in discarded:
            print(f"  {record['key'] or '(unidentified)'}: {record['discarded_because']}", file=sys.stderr)

    rendered = json.dumps(records, indent=2)
    if args.output:
        out = pathlib.Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered + "\n", encoding="utf-8")
        print(f"wrote {len(records)} verdicts to {out}", file=sys.stderr)
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
