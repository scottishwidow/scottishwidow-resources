"""Tests for the finding normaliser, ownership partition and finding key.

Run from the repository root with `python3 -m unittest discover -s
security/iac_security/tests`.

The expected counts are the corpus described in `design.md - Context`: 20
findings across 11 rule IDs, 12 first-party and 8 vendored, of which the
severity gate leaves 7 triage-eligible and 5 below threshold.
"""

from __future__ import annotations

import collections
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import normalise  # noqa: E402
import vocabulary  # noqa: E402

BASELINE = Path(__file__).resolve().parents[1] / "fixtures" / "baseline-scan.json"


def first_party(normalised: dict) -> list[dict]:
    """The two filters run in order, so first-party is what either side of the gate holds."""
    return normalised["eligible"] + normalised["below_threshold"]


def all_records(normalised: dict) -> list[dict]:
    return first_party(normalised) + normalised["vendored"]


def synthetic_report(target: str, filename: str | None, start_line: int = 1) -> dict:
    """A one-finding Trivy report, for cases the baseline corpus does not cover."""
    occurrences = []
    if filename is not None:
        occurrences = [
            {
                "Resource": "aws_s3_bucket.example",
                "Filename": filename,
                "Location": {"StartLine": start_line, "EndLine": start_line + 2},
            }
        ]
    return {
        "Results": [
            {
                "Target": target,
                "Type": "terraform",
                "Misconfigurations": [
                    {
                        "ID": "AWS-0089",
                        "Title": "S3 Bucket Logging",
                        "Severity": "LOW",
                        "Status": "FAIL",
                        "CauseMetadata": {
                            "Resource": "module.example",
                            "StartLine": start_line,
                            "EndLine": start_line + 2,
                            "Code": {
                                "Lines": [
                                    {
                                        "Number": start_line,
                                        "Content": 'resource "aws_s3_bucket" "example" {',
                                    }
                                ]
                            },
                            "Occurrences": occurrences,
                        },
                    }
                ],
            }
        ]
    }


class BaselineCorpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with open(BASELINE, encoding="utf-8") as handle:
            cls.report = json.load(handle)
        cls.normalised = normalise.normalise(cls.report)
        cls.all_records = all_records(cls.normalised)

    def test_emits_one_record_per_finding(self) -> None:
        self.assertEqual(len(self.all_records), 20)

    def test_every_record_carries_its_identifying_fields(self) -> None:
        for record in self.all_records:
            with self.subTest(key=record["key"]):
                self.assertTrue(record["rule_id"])
                self.assertTrue(record["module_address"])
                self.assertTrue(record["resource_type"])
                self.assertTrue(record["resource_name"])
                self.assertTrue(record["owner_path"])

    def test_first_party_keys_are_distinct(self) -> None:
        """The only place a key carries a verdict, so the only place it must be unique."""
        keys = [record["key"] for record in first_party(self.normalised)]
        self.assertEqual(len(set(keys)), 12)
        self.assertEqual(self.normalised["duplicate_first_party_keys"], [])

    def test_every_colliding_aws_0104_finding_is_vendored(self) -> None:
        """The corpus's only key collision lies entirely in code we do not own.

        This is what retires the ordinal (`design.md - Decision 3`): the sibling
        egress rules that a rule-plus-resource key cannot separate are never
        triaged, so they never need separating.
        """
        colliding = [r for r in self.all_records if r["rule_id"] == "AWS-0104"]
        self.assertEqual(len(colliding), 8)
        self.assertTrue(all(r["ownership"] == normalise.VENDORED for r in colliding))
        self.assertTrue(all(".terraform/modules/" in r["owner_path"] for r in colliding))

    def test_ownership_partition(self) -> None:
        self.assertEqual(len(first_party(self.normalised)), 12)
        self.assertEqual(len(self.normalised["vendored"]), 8)
        self.assertEqual(self.normalised["unrecognised_locations"], [])

    def test_vendored_findings_all_lie_under_a_module_cache(self) -> None:
        for record in self.normalised["vendored"]:
            self.assertIn(".terraform/modules/", record["owner_path"])

    def test_keys_survive_line_number_drift(self) -> None:
        """A finding that moves down the file keeps the identity it had."""
        shifted = json.loads(json.dumps(self.report))
        for result in shifted["Results"]:
            for misconf in result.get("Misconfigurations") or []:
                cause = misconf["CauseMetadata"]
                cause["StartLine"] += 10
                cause["EndLine"] += 10
                for line in cause["Code"]["Lines"]:
                    line["Number"] += 10
                for occurrence in cause.get("Occurrences") or []:
                    occurrence["Location"]["StartLine"] += 10
                    occurrence["Location"]["EndLine"] += 10

        before = [record["key"] for record in self.all_records]
        after_normalised = normalise.normalise(shifted)
        after = [record["key"] for record in all_records(after_normalised)]
        self.assertEqual(before, after)

    def test_renaming_a_resource_changes_only_that_resources_keys(self) -> None:
        renamed = json.loads(json.dumps(self.report))
        for result in renamed["Results"]:
            for misconf in result.get("Misconfigurations") or []:
                for line in misconf["CauseMetadata"]["Code"]["Lines"]:
                    line["Content"] = line["Content"].replace(
                        '"aws_subnet" "public_zone_1"', '"aws_subnet" "public_zone_alpha"'
                    )

        after = normalise.normalise(renamed)
        before = {
            (record["key"], record["resource_address"]) for record in self.all_records
        }
        after_pairs = {
            (record["key"], record["resource_address"]) for record in all_records(after)
        }
        touched = {address for _, address in before ^ after_pairs}
        self.assertEqual(touched, {"aws_subnet.public_zone_1", "aws_subnet.public_zone_alpha"})


class UnrecognisedLocation(unittest.TestCase):
    def test_unknown_prefix_is_first_party_and_surfaced(self) -> None:
        report = synthetic_report(target="sandbox/main.tf", filename="sandbox/main.tf")
        normalised = normalise.normalise(report)

        self.assertEqual(len(first_party(normalised)), 1)
        self.assertEqual(normalised["vendored"], [])
        self.assertFalse(first_party(normalised)[0]["ownership_recognised"])
        self.assertEqual(normalised["unrecognised_locations"], ["sandbox/main.tf"])

    def test_missing_occurrence_falls_back_to_the_scan_target(self) -> None:
        report = synthetic_report(target="modules/vpc/main.tf", filename=None)
        normalised = normalise.normalise(report)

        self.assertEqual(first_party(normalised)[0]["owner_path"], "modules/vpc/main.tf")
        self.assertTrue(first_party(normalised)[0]["ownership_recognised"])


class DuplicateFirstPartyKey(unittest.TestCase):
    """Without an ordinal, two first-party findings could share a key.

    That would silently apply one verdict to two judgments, so it is reported
    rather than absorbed. It does not occur in the current corpus.
    """

    def test_shared_key_is_surfaced(self) -> None:
        report = synthetic_report(target="modules/x/main.tf", filename="modules/x/main.tf")
        misconfs = report["Results"][0]["Misconfigurations"]
        misconfs.append(json.loads(json.dumps(misconfs[0])))
        misconfs[1]["CauseMetadata"]["StartLine"] = 40

        normalised = normalise.normalise(report)

        self.assertEqual(len(first_party(normalised)), 2)
        self.assertEqual(
            normalised["duplicate_first_party_keys"],
            ["AWS-0089:module.example:aws_s3_bucket.example"],
        )

    def test_vendored_shared_key_is_not_reported(self) -> None:
        """Vendored siblings sharing a key is the expected case, not a fault."""
        path = "live/management/.terraform/modules/x/main.tf"
        report = synthetic_report(target=path, filename=path)
        misconfs = report["Results"][0]["Misconfigurations"]
        misconfs.append(json.loads(json.dumps(misconfs[0])))

        normalised = normalise.normalise(report)

        self.assertEqual(len(normalised["vendored"]), 2)
        self.assertEqual(normalised["duplicate_first_party_keys"], [])


class SeverityGate(unittest.TestCase):
    """The second deterministic filter (`design.md - Decision 2`).

    It runs *after* the ownership partition and does not replace it, which is
    what the CRITICAL case below holds: every CRITICAL finding in this corpus is
    vendored, so a severity gate applied alone would admit exactly the eight
    findings this repository cannot fix.
    """

    # The corpus every count here describes is the one at `HIGH`, the threshold
    # this capability was designed and measured against. It is pinned rather
    # than read from `config.json` so that moving the configured threshold —
    # which task 3.6 did, to `MEDIUM` — is a reviewable diff to one file and not
    # a wave of unrelated test failures. What the configured value currently is
    # gets its own assertion below.
    BASELINE_THRESHOLD = "HIGH"

    @classmethod
    def setUpClass(cls) -> None:
        with open(BASELINE, encoding="utf-8") as handle:
            cls.report = json.load(handle)
        cls.normalised = normalise.normalise(cls.report, threshold=cls.BASELINE_THRESHOLD)

    def test_threshold_is_configuration_not_a_literal(self) -> None:
        """Raising or lowering the gate is a diff to config.json, not to the logic.

        Asserted as membership of the ladder rather than as one value: pinning
        the configured threshold here would make it two diffs to move, which is
        the opposite of what `design.md - Decision 2` wants from it.
        """
        configured = normalise.load_threshold()
        self.assertIn(configured, normalise.SEVERITY_ORDER)
        self.assertEqual(
            normalise.normalise(self.report)["severity_threshold"], configured
        )

    def test_baseline_partition(self) -> None:
        self.assertEqual(len(self.normalised["eligible"]), 7)
        self.assertEqual(len(self.normalised["below_threshold"]), 5)
        self.assertEqual(len(self.normalised["vendored"]), 8)

    def test_eligible_findings_span_six_rules_with_one_at_n_equals_two(self) -> None:
        """The corpus's narrowness, asserted rather than described."""
        counts = collections.Counter(r["rule_id"] for r in self.normalised["eligible"])
        self.assertEqual(len(counts), 6)
        self.assertEqual(counts["AWS-0164"], 2)
        self.assertEqual(
            sorted(rule for rule, n in counts.items() if n > 1), ["AWS-0164"]
        )

    def test_every_critical_finding_is_excluded_on_ownership(self) -> None:
        criticals = [r for r in all_records(self.normalised) if r["severity"] == "CRITICAL"]
        self.assertEqual(len(criticals), 8)
        for record in criticals:
            with self.subTest(key=record["key"]):
                self.assertEqual(record["ownership"], normalise.VENDORED)
                self.assertEqual(record["triage_status"], normalise.UPSTREAM)

    def test_severity_never_overrides_ownership(self) -> None:
        """A CRITICAL vendored finding is excluded on ownership alone."""
        path = "live/management/.terraform/modules/x/main.tf"
        report = synthetic_report(target=path, filename=path)
        report["Results"][0]["Misconfigurations"][0]["Severity"] = "CRITICAL"

        normalised = normalise.normalise(report)

        self.assertEqual(normalised["eligible"], [])
        self.assertEqual(normalised["vendored"][0]["triage_status"], normalise.UPSTREAM)

    def test_lowering_the_threshold_admits_previously_excluded_findings(self) -> None:
        lowered = normalise.normalise(self.report, threshold="LOW")

        self.assertEqual(len(lowered["eligible"]), 12)
        self.assertEqual(lowered["below_threshold"], [])
        self.assertEqual(len(lowered["vendored"]), 8)

    def test_an_unknown_severity_is_not_silently_excluded(self) -> None:
        """Unexpected input escapes neither triage nor attention, as with paths."""
        report = synthetic_report(target="modules/x/main.tf", filename="modules/x/main.tf")
        report["Results"][0]["Misconfigurations"][0]["Severity"] = "SEVERE"

        normalised = normalise.normalise(report)

        self.assertEqual(len(normalised["eligible"]), 1)


class BelowThresholdFindingsSurvive(unittest.TestCase):
    """Below threshold means untriaged, not discarded (`design.md - Decision 2`).

    Dismissal is a verdict; no verdict has been formed for these, so they stay
    in the output as open, unlabelled findings that nothing downstream files.
    """

    @classmethod
    def setUpClass(cls) -> None:
        with open(BASELINE, encoding="utf-8") as handle:
            # Pinned to the baseline threshold for the reason given in
            # `SeverityGate`: this class is about what happens to a
            # below-threshold finding, not about where the gate currently sits.
            cls.normalised = normalise.normalise(json.load(handle), threshold="HIGH")

    def test_present_in_the_output(self) -> None:
        below = self.normalised["below_threshold"]
        self.assertEqual(len(below), 5)
        self.assertEqual(
            collections.Counter(r["severity"] for r in below),
            collections.Counter({"LOW": 3, "MEDIUM": 2}),
        )

    def test_carry_no_verdict(self) -> None:
        """The normaliser assigns dispositions; verdicts come from triage alone."""
        for record in all_records(self.normalised):
            with self.subTest(key=record["key"]):
                self.assertNotIn("verdict", record)
                self.assertNotIn(record["triage_status"], vocabulary.VERDICTS)

    def test_marked_so_that_nothing_downstream_files_an_issue(self) -> None:
        """An issue is filed per *eligible* finding, so the mark is the whole gate."""
        for record in self.normalised["below_threshold"]:
            with self.subTest(key=record["key"]):
                self.assertEqual(record["ownership"], normalise.FIRST_PARTY)
                self.assertEqual(record["triage_status"], normalise.BELOW_THRESHOLD)
                self.assertNotIn(record, self.normalised["eligible"])

    def test_retain_the_identity_they_would_be_triaged_under(self) -> None:
        """So that lowering the threshold extends the corpus rather than resetting it."""
        for record in self.normalised["below_threshold"]:
            with self.subTest(key=record["key"]):
                self.assertTrue(record["key"])
                self.assertTrue(record["resource_address"])


if __name__ == "__main__":
    unittest.main()
