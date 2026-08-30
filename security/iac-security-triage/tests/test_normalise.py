"""Tests for the finding normaliser, ownership partition and finding key.

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
            with self.subTest(key=record["key"]):
                self.assertTrue(record["rule_id"])
                self.assertTrue(record["module_address"])
                self.assertTrue(record["resource_type"])
                self.assertTrue(record["resource_name"])
                self.assertTrue(record["owner_path"])

    def test_first_party_keys_are_distinct(self) -> None:
        """The only place a key carries a verdict, so the only place it must be unique."""
        keys = [record["key"] for record in self.normalised["first_party"]]
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
        self.assertEqual(len(self.normalised["first_party"]), 12)
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
        after = [
            record["key"]
            for record in after_normalised["first_party"] + after_normalised["vendored"]
        ]
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
            (record["key"], record["resource_address"])
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

        self.assertEqual(len(normalised["first_party"]), 2)
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


if __name__ == "__main__":
    unittest.main()
