#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
TRIAGE_DIR = HERE.parent

RUNS = TRIAGE_DIR / "runs"

sys.path.insert(0, str(TRIAGE_DIR))
import vocabulary  # noqa: E402

UNDETERMINED = "undetermined"

DISCARD_MISSING_RATIONALE = "no rationale supplied"
DISCARD_BLANK_RATIONALE = "rationale was empty or whitespace"
DISCARD_UNKNOWN_VERDICT = "verdict not in the vocabulary"
DISCARD_NO_RESULT = "branch produced no result"
DISCARD_UNPARSEABLE = "branch result was not a JSON object"

EVIDENCE_DISCREPANCY = "evidence_discrepancy"


def latest_manifest(root: pathlib.Path = RUNS) -> pathlib.Path:
    manifests = sorted(
        root.glob("artifacts/*/manifest.json"),
        key=lambda p: p.stat().st_mtime,
    )
    if not manifests:
        raise SystemExit(f"no manifest found under {root}; has a triage run happened?")
    return manifests[-1]


def unfence(text: str) -> str:
    lines = text.strip().splitlines()
    if len(lines) < 2 or not lines[0].startswith("```") or lines[-1].strip() != "```":
        return text
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
    record["discarded_verdict"] = record.get("verdict")
    record["verdict"] = UNDETERMINED
    record["discarded_because"] = reason
    return record


class EligibleFindings:
    """The eligible list in scan order, plus the rule ID of each finding key.

    Two eligible findings can carry one finding key, so the order matters
    separately from the map: a branch is attributed by its position in the list,
    which the map cannot express once it has collapsed a duplicate.
    """

    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        records = records or []
        self._keys = [record["key"] for record in records]
        self._rule_ids = {record["key"]: record["rule_id"] for record in records}

    def key_at(self, item: int) -> str:
        """The finding key of the branch at this position, or empty if there is none."""
        return self._keys[item] if 0 <= item < len(self._keys) else ""

    def rule_id(self, key: str) -> str:
        return self._rule_ids.get(key, "")


def corpus_paths_from_manifest(manifest: dict[str, Any]) -> set[str] | None:
    corpus = (manifest.get("outputs") or {}).get("corpus")
    if not isinstance(corpus, dict):
        return None
    return {doc["path"] for doc in corpus.get("documents", [])}


def branch_to_record(
    branch: dict[str, Any],
    findings: EligibleFindings,
    corpus_paths: set[str] | None = None,
) -> dict[str, Any]:
    """One fan-out branch to one verdict record, applying the discard rule."""
    result = decode(branch.get("result"))
    item = branch.get("item")
    fallback_key = findings.key_at(item) if isinstance(item, int) else ""

    if result is None:
        record = {"key": fallback_key, "verdict": None, "rationale": "", "evidence": []}
        record["rule_id"] = findings.rule_id(fallback_key)
        return discard(record, DISCARD_NO_RESULT if branch.get("result") is None else DISCARD_UNPARSEABLE)

    key = str(result.get("key") or fallback_key)
    record: dict[str, Any] = {
        "key": key,
        "rule_id": findings.rule_id(key),
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

    if corpus_paths is not None:
        unknown = [path for path in record["evidence"] if path not in corpus_paths]
        if unknown:
            record[EVIDENCE_DISCREPANCY] = unknown

    return record


def collect(
    manifest: dict[str, Any],
    findings: EligibleFindings,
    output_id: str = "verdicts",
) -> list[dict[str, Any]]:
    outputs = manifest.get("outputs") or {}
    if output_id not in outputs:
        raise SystemExit(
            f"manifest has no output {output_id!r}; it has: "
            + (", ".join(sorted(outputs)) or "(none)")
        )
    branches = outputs[output_id]
    if not isinstance(branches, list):
        raise SystemExit(f"output {output_id!r} is not a fan-in list; got {type(branches).__name__}")

    paths = corpus_paths_from_manifest(manifest)
    return [branch_to_record(branch, findings, paths) for branch in branches]


def eligible_findings(path: pathlib.Path | None) -> EligibleFindings:
    if path is None or not path.exists():
        return EligibleFindings()
    data = json.loads(path.read_text(encoding="utf-8"))
    return EligibleFindings(data.get("eligible", []))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Turn a triage run's manifest into a verdict list.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", help="path to a run manifest.json")
    source.add_argument(
        "--latest",
        action="store_true",
        help=f"use the newest manifest under {RUNS}",
    )
    parser.add_argument(
        "--findings",
        help="normalised findings JSON, to attach a finding key and rule ID to each verdict",
    )
    parser.add_argument("--output-id", default="verdicts", help="the taskflow task id to read")
    parser.add_argument("-o", "--output", help="write here instead of stdout")
    args = parser.parse_args(argv)

    path = latest_manifest() if args.latest else pathlib.Path(args.manifest)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    findings = eligible_findings(pathlib.Path(args.findings) if args.findings else None)

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

    discrepant = [r for r in records if r.get(EVIDENCE_DISCREPANCY)]
    for record in discrepant:
        print(
            f"warning: {record['key']} cites evidence not in the Terraform corpus: "
            + ", ".join(record[EVIDENCE_DISCREPANCY]),
            file=sys.stderr,
        )

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
