from __future__ import annotations

import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = pathlib.Path(__file__).resolve().parent
TRIAGE_DIR = HERE.parent

sys.path.insert(0, str(TRIAGE_DIR))

import issue_body  # noqa: E402
import patch_gate  # noqa: E402
import remediation_target  # noqa: E402
import vocabulary  # noqa: E402

KEY = "AWS-0164:module.vpc:aws_subnet.public_zone_1"

FINDING = {
    "key": KEY,
    "rule_id": "AWS-0164",
    "severity": "HIGH",
    "code_path": "modules/vpc/main.tf",
    "owner_path": "live/management/vpc/main.tf",
    "triage_status": "eligible",
}

UNANSWERED_VERDICT = "<!-- one of: not-applicable, real-mechanical, real-judgment, undetermined -->"


def body(key: str = KEY, verdict: str = "real-mechanical", alert: int = 12) -> str:
    return (
        "## Finding\n\n| | |\n|---|---|\n"
        f"| **Key** | `{key}` |\n"
        f"| **Alert** | [#{alert}](https://example.invalid/{alert}) |\n\n"
        f"## Verdict\n\n{verdict}\n\n"
        "## Rationale\n\nThe subnet assigns public IPs on purpose.\n\n"
        "## Evidence\n\n- `modules/vpc/main.tf`\n"
    )


def item(**overrides: object) -> dict:
    base = {"number": 42, "body": body(), "comments": []}
    base.update(overrides)
    return base


def findings(*records: dict) -> dict:
    return {"eligible": list(records or (FINDING,))}


class TheIssueSaysWhichFinding(unittest.TestCase):
    def test_a_body_carrying_a_key_names_its_finding(self) -> None:
        target = remediation_target.target(findings(), item())
        self.assertEqual(target["finding"], FINDING)
        self.assertEqual(target["issue"]["key"], KEY)
        self.assertEqual(target["issue"]["number"], 42)
        self.assertEqual(target["issue"]["alert"], 12)

    def test_a_body_carrying_no_key_yields_no_tracker_item(self) -> None:
        self.assertIsNone(remediation_target.tracker_item({"body": "A bug report."}))

    def test_a_body_carrying_no_key_halts_the_run(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            remediation_target.target(findings(), {"body": "A bug report."})
        self.assertIn("no finding key", str(raised.exception))

    def test_a_key_that_is_not_an_eligible_finding_halts_the_run(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            remediation_target.target(findings(), item(body=body(key="AWS-0001:m:r.n")))
        self.assertIn("not an eligible finding", str(raised.exception))

    def test_a_key_naming_two_eligible_findings_halts_the_run(self) -> None:
        """A finding key can be claimed twice, and then it identifies no single thing to patch."""
        with self.assertRaises(SystemExit) as raised:
            remediation_target.target(findings(FINDING, dict(FINDING)), item())
        self.assertIn("no single one", str(raised.exception))

    def test_the_body_and_its_comments_are_carried_verbatim(self) -> None:
        """The human's own words are an input, so they reach the prompt unedited."""
        note = "The bucket is public on purpose, but the logging is not."
        target = remediation_target.target(findings(), item(comments=[{"body": note}]))
        self.assertEqual(target["issue"]["body"], body())
        self.assertEqual(target["issue"]["comments"], [note])


class AnUnansweredVerdictIsNotAVerdict(unittest.TestCase):
    """The label authorises the patch; it does not judge the finding."""

    def test_a_recorded_verdict_is_carried_as_it_stands(self) -> None:
        target = remediation_target.target(findings(), item())
        self.assertEqual(target["issue"]["verdict"], "real-mechanical")
        self.assertTrue(target["issue"]["verdict_recorded"])

    def test_an_unanswered_template_prompt_reads_as_undetermined(self) -> None:
        target = remediation_target.target(
            findings(), item(body=body(verdict=UNANSWERED_VERDICT))
        )
        self.assertEqual(target["issue"]["verdict"], vocabulary.UNDETERMINED)
        self.assertFalse(target["issue"]["verdict_recorded"])

    def test_a_verdict_outside_the_vocabulary_reads_as_undetermined(self) -> None:
        target = remediation_target.target(findings(), item(body=body(verdict="`probably-fine`")))
        self.assertEqual(target["issue"]["verdict"], vocabulary.UNDETERMINED)
        self.assertFalse(target["issue"]["verdict_recorded"])

    def test_a_later_verdict_comment_supersedes_the_body(self) -> None:
        comment = f"## {issue_body.NEW_VERDICT}\n\n`real-judgment`\n\n## Rationale\n\nx\n"
        target = remediation_target.target(
            findings(),
            item(body=body(verdict=f"`{vocabulary.UNDETERMINED}`"), comments=[{"body": comment}]),
        )
        self.assertEqual(target["issue"]["verdict"], "real-judgment")


class PermittedPathsComeFromTheGate(unittest.TestCase):
    """Named for the prompt out of the rule `patch_gate.path_is_permitted` applies.

    Two statements of one rule is where they drift, so what is asserted here is
    that every path named to the agent is one the gate accepts, and that the
    gate rejects what is not named -- rather than a fixed list.
    """

    def touching(self, path: str, is_new: bool = False) -> patch_gate.TouchedFile:
        return patch_gate.TouchedFile(
            path=path, source_path=path, is_new=is_new, is_deleted=False, is_renamed=False
        )

    def setUp(self) -> None:
        self.permitted = remediation_target.permitted_paths(FINDING)

    def test_every_editable_path_passes_the_gate(self) -> None:
        for path in self.permitted["editable"]:
            with self.subTest(path=path):
                self.assertTrue(patch_gate.path_is_permitted(self.touching(path), FINDING))

    def test_the_code_path_and_the_owner_path_are_both_editable(self) -> None:
        self.assertEqual(
            self.permitted["editable"], sorted({FINDING["code_path"], FINDING["owner_path"]})
        )

    def test_a_new_file_in_the_named_directory_passes_the_gate(self) -> None:
        new = f"{self.permitted['new_files_under']}/logging.tf"
        self.assertTrue(patch_gate.path_is_permitted(self.touching(new, is_new=True), FINDING))

    def test_a_file_the_target_names_nowhere_is_rejected_by_the_gate(self) -> None:
        self.assertFalse(
            patch_gate.path_is_permitted(self.touching("modules/other/main.tf"), FINDING)
        )


class TheKeyOnlyModeCostsNothing(unittest.TestCase):
    """The first job of the workflow: no scan, no token, no model."""

    def run_key_only(self, item_record: dict) -> str:
        captured = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = pathlib.Path(tmp) / "issue.json"
            snapshot.write_text(json.dumps(item_record), encoding="utf-8")
            with redirect_stdout(captured):
                self.assertEqual(
                    remediation_target.main(["--key-only", "--issue", str(snapshot)]), 0
                )
        return captured.getvalue().strip()

    def test_it_prints_the_key_the_body_carries(self) -> None:
        self.assertEqual(self.run_key_only(item()), KEY)

    def test_it_prints_nothing_for_an_issue_that_holds_no_finding(self) -> None:
        self.assertEqual(self.run_key_only({"number": 7, "body": "A bug report."}), "")

    def test_it_reads_no_findings_at_all(self) -> None:
        """It runs before the scan, so stdin holds nothing to read."""
        sys.stdin = io.StringIO("")
        try:
            self.assertEqual(self.run_key_only(item()), KEY)
        finally:
            sys.stdin = sys.__stdin__


class TheIssueSnapshotIsOptional(unittest.TestCase):
    def test_the_body_can_arrive_in_the_environment_instead(self) -> None:
        """The workflow's first job holds no token, so it reads the event payload."""
        os.environ[remediation_target.BODY_ENV] = body()
        try:
            loaded = remediation_target.load_item(None)
        finally:
            del os.environ[remediation_target.BODY_ENV]
        self.assertEqual(remediation_target.tracker_item(loaded)["key"], KEY)

    def test_a_named_snapshot_that_does_not_exist_halts_the_run(self) -> None:
        with self.assertRaises(SystemExit):
            remediation_target.load_item("/nonexistent/issue.json")


if __name__ == "__main__":
    unittest.main()
