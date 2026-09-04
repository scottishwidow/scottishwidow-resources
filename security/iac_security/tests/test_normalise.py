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
    return normalised["eligible"] + normalised["below_threshold"]


def all_records(normalised: dict) -> list[dict]:
    return first_party(normalised) + normalised["vendored"]


def synthetic_report(target: str, filename: str | None, start_line: int = 1) -> dict:
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
        keys = [record["key"] for record in first_party(self.normalised)]
        self.assertEqual(len(set(keys)), 12)
        self.assertEqual(self.normalised["duplicate_first_party_keys"], [])

    def test_every_colliding_aws_0104_finding_is_vendored(self) -> None:
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
        path = "live/management/.terraform/modules/x/main.tf"
        report = synthetic_report(target=path, filename=path)
        misconfs = report["Results"][0]["Misconfigurations"]
        misconfs.append(json.loads(json.dumps(misconfs[0])))

        normalised = normalise.normalise(report)

        self.assertEqual(len(normalised["vendored"]), 2)
        self.assertEqual(normalised["duplicate_first_party_keys"], [])


class SeverityGate(unittest.TestCase):
    # Pinned to `HIGH` so moving the configured threshold is a diff to one file, not a wave of test failures.
    BASELINE_THRESHOLD = "HIGH"

    @classmethod
    def setUpClass(cls) -> None:
        with open(BASELINE, encoding="utf-8") as handle:
            cls.report = json.load(handle)
        cls.normalised = normalise.normalise(cls.report, threshold=cls.BASELINE_THRESHOLD)

    def test_threshold_is_configuration_not_a_literal(self) -> None:
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
        report = synthetic_report(target="modules/x/main.tf", filename="modules/x/main.tf")
        report["Results"][0]["Misconfigurations"][0]["Severity"] = "SEVERE"

        normalised = normalise.normalise(report)

        self.assertEqual(len(normalised["eligible"]), 1)


class BelowThresholdFindingsSurvive(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with open(BASELINE, encoding="utf-8") as handle:
            # Pinned to the baseline threshold for the reason given in `SeverityGate`.
            cls.normalised = normalise.normalise(json.load(handle), threshold="HIGH")

    def test_present_in_the_output(self) -> None:
        below = self.normalised["below_threshold"]
        self.assertEqual(len(below), 5)
        self.assertEqual(
            collections.Counter(r["severity"] for r in below),
            collections.Counter({"LOW": 3, "MEDIUM": 2}),
        )

    def test_carry_no_verdict(self) -> None:
        for record in all_records(self.normalised):
            with self.subTest(key=record["key"]):
                self.assertNotIn("verdict", record)
                self.assertNotIn(record["triage_status"], vocabulary.VERDICTS)

    def test_marked_so_that_nothing_downstream_files_an_issue(self) -> None:
        for record in self.normalised["below_threshold"]:
            with self.subTest(key=record["key"]):
                self.assertEqual(record["ownership"], normalise.FIRST_PARTY)
                self.assertEqual(record["triage_status"], normalise.BELOW_THRESHOLD)
                self.assertNotIn(record, self.normalised["eligible"])

    def test_retain_the_identity_they_would_be_triaged_under(self) -> None:
        for record in self.normalised["below_threshold"]:
            with self.subTest(key=record["key"]):
                self.assertTrue(record["key"])
                self.assertTrue(record["resource_address"])


if __name__ == "__main__":
    unittest.main()
