from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import issue_body  # noqa: E402


class EvidencePathPattern(unittest.TestCase):
    def test_matches_a_tf_file_under_live(self) -> None:
        self.assertEqual(
            issue_body.parse_evidence("- `live/management/bootstrap/main.tf`"),
            ["live/management/bootstrap/main.tf"],
        )

    def test_matches_a_tf_file_under_modules(self) -> None:
        self.assertEqual(
            issue_body.parse_evidence("- `modules/vpc/main.tf`"),
            ["modules/vpc/main.tf"],
        )

    def test_does_not_match_a_decision_record(self) -> None:
        self.assertEqual(
            issue_body.parse_evidence("- `docs/adr/0008-this-repository-is-not-a-memory-bank.md`"),
            [],
        )

    def test_does_not_match_a_design_document(self) -> None:
        self.assertEqual(
            issue_body.parse_evidence("- `docs/design/iac-security-triage.md`"),
            [],
        )

    def test_does_not_match_a_non_tf_file_under_a_corpus_root(self) -> None:
        self.assertEqual(
            issue_body.parse_evidence("- `live/management/README.md`"),
            [],
        )


class AlertRow(unittest.TestCase):
    def test_parses_the_alert_number_from_the_link_the_filer_writes(self) -> None:
        body = (
            "| **Key** | `AWS-0086:module.x:aws_s3_bucket.y` |\n"
            "| **Alert** | [#42](https://github.com/o/r/security/code-scanning/42) |\n"
        )
        self.assertEqual(issue_body.parse(body)["alert"], 42)

    def test_parses_the_alert_number_from_a_code_span(self) -> None:
        body = "| **Key** | `AWS-0086:module.x:aws_s3_bucket.y` |\n| **Alert** | `#42` |\n"
        self.assertEqual(issue_body.parse(body)["alert"], 42)

    def test_parses_a_bare_alert_number(self) -> None:
        body = "| **Key** | `AWS-0086:module.x:aws_s3_bucket.y` |\n| **Alert** | #42 |\n"
        self.assertEqual(issue_body.parse(body)["alert"], 42)

    def test_a_body_with_no_alert_row_reports_it_absent(self) -> None:
        body = "| **Key** | `AWS-0086:module.x:aws_s3_bucket.y` |\n"
        parsed = issue_body.parse(body)
        self.assertIsNotNone(parsed)
        self.assertIsNone(parsed["alert"])


if __name__ == "__main__":
    unittest.main()
