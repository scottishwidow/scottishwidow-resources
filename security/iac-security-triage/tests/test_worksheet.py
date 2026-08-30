"""Tests for the labelling worksheet generator."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import normalise  # noqa: E402
import worksheet  # noqa: E402
from vocabulary import DIFFICULTIES, VERDICTS  # noqa: E402

BASELINE = Path(__file__).resolve().parents[1] / "fixtures" / "baseline-scan.json"


class Worksheet(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with open(BASELINE, encoding="utf-8") as handle:
            cls.normalised = normalise.normalise(json.load(handle))
        cls.entries = worksheet.build(cls.normalised)

    def test_one_entry_per_first_party_finding(self) -> None:
        self.assertEqual(len(self.entries), 12)
        self.assertEqual(
            set(self.entries),
            {record["fingerprint"] for record in self.normalised["first_party"]},
        )

    def test_vendored_findings_are_not_offered_for_labelling(self) -> None:
        vendored = {record["fingerprint"] for record in self.normalised["vendored"]}
        self.assertEqual(vendored & set(self.entries), set())

    def test_entries_are_pre_filled_with_the_context_needed_to_judge(self) -> None:
        for fingerprint, entry in self.entries.items():
            with self.subTest(fingerprint=fingerprint):
                for field in ("rule", "title", "severity", "module", "resource", "code"):
                    self.assertTrue(entry[field], msg=field)
                self.assertTrue(entry["location"]["declared_in"])
                self.assertTrue(entry["location"]["instantiated_in"])
                self.assertTrue(entry["remediation"])

    def test_no_human_field_is_pre_populated(self) -> None:
        for fingerprint, entry in self.entries.items():
            with self.subTest(fingerprint=fingerprint):
                self.assertIsNone(entry["verdict"])
                self.assertIsNone(entry["difficulty"])
                self.assertIsNone(entry["rationale"])
                self.assertEqual(entry["evidence"], [])

    def test_rendered_worksheet_round_trips_and_states_the_vocabulary(self) -> None:
        rendered = worksheet.header() + yaml.dump(
            self.entries, Dumper=worksheet._Dumper, sort_keys=False, default_flow_style=False
        )
        for term in list(VERDICTS) + list(DIFFICULTIES):
            self.assertIn(term, rendered)

        parsed = yaml.safe_load(rendered)
        self.assertEqual(parsed, self.entries)


if __name__ == "__main__":
    unittest.main()
