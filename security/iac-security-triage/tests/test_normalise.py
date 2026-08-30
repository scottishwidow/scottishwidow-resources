"""Tests for the finding normaliser, ownership partition and fingerprint.

Run from the repository root with `python3 -m unittest discover -s
security/iac-security-triage/tests`.

The expected counts are the corpus described in `design.md - Context`: 20
findings across 11 rule IDs, 12 first-party and 8 vendored.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import normalise  # noqa: E402

BASELINE = Path(__file__).resolve().parents[1] / "fixtures" / "baseline-scan.json"


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
        cls.all_records = cls.normalised["first_party"] + cls.normalised["vendored"]

    def test_emits_one_record_per_finding(self) -> None:
        self.assertEqual(len(self.all_records), 20)

    def test_every_record_carries_its_identifying_fields(self) -> None:
        for record in self.all_records:
            with self.subTest(fingerprint=record["fingerprint"]):
                self.assertTrue(record["rule_id"])
                self.assertTrue(record["module_address"])
                self.assertTrue(record["resource_type"])
                self.assertTrue(record["resource_name"])
                self.assertTrue(record["owner_path"])

    def test_fingerprints_are_distinct(self) -> None:
        fingerprints = [record["fingerprint"] for record in self.all_records]
        self.assertEqual(len(set(fingerprints)), 20)

    def test_colliding_aws_0104_findings_are_separated(self) -> None:
        """Four AWS-0104 findings share rule, file and line; identity must not."""
        colliding = [
            record
            for record in self.all_records
            if record["rule_id"] == "AWS-0104"
            and record["resource_address"] == "aws_security_group_rule.egress_rules"
        ]
        self.assertEqual(len(colliding), 4)
        self.assertEqual(len({record["fingerprint"] for record in colliding}), 4)

    def test_ownership_partition(self) -> None:
        self.assertEqual(len(self.normalised["first_party"]), 12)
        self.assertEqual(len(self.normalised["vendored"]), 8)
        self.assertEqual(self.normalised["unrecognised_locations"], [])

    def test_vendored_findings_all_lie_under_a_module_cache(self) -> None:
        for record in self.normalised["vendored"]:
            self.assertIn(".terraform/modules/", record["owner_path"])

    def test_fingerprints_survive_line_number_drift(self) -> None:
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

        before = [record["fingerprint"] for record in self.all_records]
        after_normalised = normalise.normalise(shifted)
        after = [
            record["fingerprint"]
            for record in after_normalised["first_party"] + after_normalised["vendored"]
        ]
        self.assertEqual(before, after)

    def test_renaming_a_resource_changes_only_that_resources_fingerprints(self) -> None:
        renamed = json.loads(json.dumps(self.report))
        for result in renamed["Results"]:
            for misconf in result.get("Misconfigurations") or []:
                for line in misconf["CauseMetadata"]["Code"]["Lines"]:
                    line["Content"] = line["Content"].replace(
                        '"aws_subnet" "public_zone_1"', '"aws_subnet" "public_zone_alpha"'
                    )

        after = normalise.normalise(renamed)
        before = {
            (record["fingerprint"], record["resource_address"]) for record in self.all_records
        }
        after_pairs = {
            (record["fingerprint"], record["resource_address"])
            for record in after["first_party"] + after["vendored"]
        }
        touched = {address for _, address in before ^ after_pairs}
        self.assertEqual(touched, {"aws_subnet.public_zone_1", "aws_subnet.public_zone_alpha"})


class UnrecognisedLocation(unittest.TestCase):
    def test_unknown_prefix_is_first_party_and_surfaced(self) -> None:
        report = synthetic_report(target="sandbox/main.tf", filename="sandbox/main.tf")
        normalised = normalise.normalise(report)

        self.assertEqual(len(normalised["first_party"]), 1)
        self.assertEqual(normalised["vendored"], [])
        self.assertFalse(normalised["first_party"][0]["ownership_recognised"])
        self.assertEqual(normalised["unrecognised_locations"], ["sandbox/main.tf"])

    def test_missing_occurrence_falls_back_to_the_scan_target(self) -> None:
        report = synthetic_report(target="modules/vpc/main.tf", filename=None)
        normalised = normalise.normalise(report)

        self.assertEqual(normalised["first_party"][0]["owner_path"], "modules/vpc/main.tf")
        self.assertTrue(normalised["first_party"][0]["ownership_recognised"])


if __name__ == "__main__":
    unittest.main()
