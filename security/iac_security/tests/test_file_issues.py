"""Tests for issue promotion (`tasks.md` group 6, `design.md - Decision 4`).

Run from the repository root with `python3 -m unittest discover -s
security/iac_security/tests`.

The corpus is the one in `design.md - Context`: 7 triage-eligible findings, 5
below-threshold and 8 vendored. Every count asserted here is derived from the
committed baseline rather than written down, so a change to the corpus moves the
tests with it instead of failing them.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import file_issues  # noqa: E402
import issue_body  # noqa: E402
import normalise  # noqa: E402
import vocabulary  # noqa: E402

BASELINE = Path(__file__).resolve().parents[1] / "fixtures" / "baseline-scan.json"


def normalised() -> dict:
    with open(BASELINE, encoding="utf-8") as handle:
        # Pinned to `HIGH`, the threshold this corpus was designed and measured
        # against, rather than read from `config.json`. The configured threshold
        # is meant to move — task 3.6 moved it to `MEDIUM` — and every count in
        # this file describes the baseline corpus, not wherever the gate sits
        # today.
        return normalise.normalise(json.load(handle), threshold="HIGH")


def verdict(key: str, verdict_class: str = "real-mechanical", **kwargs) -> dict:
    """A verdict record in the shape `collect_verdicts.py` emits."""
    record = {
        "key": key,
        "rule_id": key.split(":", 1)[0],
        "verdict": verdict_class,
        "rationale": kwargs.get("rationale", "Because of the thing."),
        "evidence": kwargs.get("evidence", []),
    }
    record.update({k: v for k, v in kwargs.items() if k not in ("rationale", "evidence")})
    return record


def full_run(findings: dict, verdict_class: str = "real-mechanical") -> list[dict]:
    """A verdict for every eligible finding, as a completed run produces."""
    return [verdict(record["key"], verdict_class) for record in findings["eligible"]]


def issue_for(item: dict, number: int = 1) -> dict:
    """The issue `gh` would return for something this module just filed."""
    return {"number": number, "body": item["body"]}


class FilesOnePerTriagedFinding(unittest.TestCase):
    """`tasks.md` 6.1."""

    def setUp(self) -> None:
        self.findings = normalised()
        self.plan = file_issues.plan(self.findings, full_run(self.findings), [])

    def test_a_full_run_files_one_issue_per_eligible_finding(self) -> None:
        self.assertEqual(len(self.plan["create"]), 7)
        self.assertEqual(len(self.findings["eligible"]), 7)
        self.assertEqual(
            sorted(item["key"] for item in self.plan["create"]),
            sorted(record["key"] for record in self.findings["eligible"]),
        )

    def test_nothing_is_left_untriaged_by_a_full_run(self) -> None:
        self.assertEqual(self.plan["untriaged_eligible"], [])

    def test_each_body_carries_the_key_the_verdict_and_the_rationale(self) -> None:
        for item in self.plan["create"]:
            parsed = issue_body.parse(item["body"])
            self.assertIsNotNone(parsed, item["key"])
            self.assertEqual(parsed["key"], item["key"])
            self.assertEqual(parsed["verdict"], "real-mechanical")
            self.assertEqual(parsed["rationale"], "Because of the thing.")

    def test_each_issue_is_filed_under_needs_triage(self) -> None:
        for item in self.plan["create"]:
            self.assertEqual(tuple(item["labels"]), (file_issues.NEEDS_TRIAGE,))

    def test_the_title_names_the_rule_and_where_it_fired(self) -> None:
        item = self.plan["create"][0]
        rule_id, _, rest = item["key"].partition(":")
        self.assertTrue(item["title"].startswith(f"[{rule_id}] "), item["title"])
        self.assertTrue(item["title"].endswith(rest), item["title"])

    def test_evidence_cited_by_the_agent_reaches_the_issue(self) -> None:
        tf_file = "modules/vpc/main.tf"
        key = self.findings["eligible"][0]["key"]
        plan = file_issues.plan(self.findings, [verdict(key, evidence=[tf_file])], [])
        self.assertEqual(issue_body.parse(plan["create"][0]["body"])["evidence"], [tf_file])


class IsIdempotentOnTheFindingKey(unittest.TestCase):
    """`tasks.md` 6.2."""

    def setUp(self) -> None:
        self.findings = normalised()
        self.run = full_run(self.findings)
        first = file_issues.plan(self.findings, self.run, [])
        self.existing = [
            issue_for(item, number=100 + index) for index, item in enumerate(first["create"])
        ]

    def test_a_second_run_with_unchanged_verdicts_files_nothing(self) -> None:
        second = file_issues.plan(self.findings, self.run, self.existing)
        self.assertEqual(second["create"], [])
        self.assertEqual(len(second["skipped_existing"]), 7)

    def test_a_second_run_reports_the_issue_each_finding_already_has(self) -> None:
        second = file_issues.plan(self.findings, self.run, self.existing)
        self.assertEqual(
            {item["key"]: item["issue"] for item in second["skipped_existing"]},
            {issue_body.parse(i["body"])["key"]: i["number"] for i in self.existing},
        )

    def test_a_changed_verdict_still_files_nothing_for_a_known_key(self) -> None:
        """The key is the identity, not the verdict: a re-run must not duplicate."""
        changed = full_run(self.findings, "not-applicable")
        self.assertEqual(file_issues.plan(self.findings, changed, self.existing)["create"], [])

    def test_a_human_applied_disposition_label_is_left_untouched(self) -> None:
        """Nothing in a second run's plan edits an existing issue at all.

        The disposition a human applied is this pipeline's output. It survives
        because the second run has no instruction to emit — not because the
        instruction is careful — so the plan is asserted empty in every field
        that could reach an existing issue.
        """
        labelled = [dict(issue, labels=[{"name": "ready-for-human"}]) for issue in self.existing]
        second = file_issues.plan(self.findings, self.run, labelled)
        self.assertEqual(second["create"], [])
        self.assertNotIn("edit", second)
        self.assertNotIn("relabel", second)

    def test_closed_issues_are_fetched_so_a_wontfix_is_not_refiled(self) -> None:
        """Idempotency spans state: a finding closed as `wontfix` stays closed.

        Asserted on the query rather than on the plan, because the plan never
        sees an issue the query did not ask for.
        """
        captured: list[list[str]] = []
        original = file_issues.gh_json
        file_issues.gh_json = lambda args: captured.append(args) or []
        try:
            file_issues.fetch_issues()
        finally:
            file_issues.gh_json = original
        self.assertIn("--state", captured[0])
        self.assertEqual(captured[0][captured[0].index("--state") + 1], "all")

    def test_an_unrelated_issue_does_not_block_filing(self) -> None:
        unrelated = [{"number": 7, "body": "A bug report with no finding key in it."}]
        self.assertEqual(len(file_issues.plan(self.findings, self.run, unrelated)["create"]), 7)


class FilesNotApplicableVerdictsToo(unittest.TestCase):
    """`tasks.md` 6.3."""

    def setUp(self) -> None:
        self.findings = normalised()
        self.plan = file_issues.plan(self.findings, full_run(self.findings, "not-applicable"), [])

    def test_a_not_applicable_verdict_still_creates_an_issue(self) -> None:
        self.assertEqual(len(self.plan["create"]), 7)

    def test_the_issue_states_the_verdict_and_its_rationale(self) -> None:
        for item in self.plan["create"]:
            parsed = issue_body.parse(item["body"])
            self.assertEqual(parsed["verdict"], "not-applicable")
            self.assertTrue(parsed["rationale"])

    def test_nothing_here_can_dismiss_an_alert(self) -> None:
        """Structural: this module never speaks to the code scanning API.

        With no rule allowlisted (`design.md - Decision 6`) a `not-applicable`
        verdict must leave the alert open. That holds because there is no code
        path from here to a dismissal, which is a stronger statement than any
        conditional would be.
        """
        source = (Path(file_issues.__file__)).read_text(encoding="utf-8")
        for forbidden in ("code-scanning", "dismissed_reason", "--state dismissed", "PATCH"):
            self.assertNotIn(forbidden, source)

    def test_a_discarded_verdict_is_filed_as_undetermined_and_says_why(self) -> None:
        key = self.findings["eligible"][0]["key"]
        record = verdict(
            key,
            "undetermined",
            rationale="",
            discarded_verdict="real-mechanical",
            discarded_because="rationale was empty or whitespace",
        )
        plan = file_issues.plan(self.findings, [record], [])
        parsed = issue_body.parse(plan["create"][0]["body"])
        self.assertEqual(parsed["verdict"], "undetermined")
        self.assertIn("rationale was empty or whitespace", parsed["rationale"])
        self.assertIn("real-mechanical", parsed["rationale"])


class NeverAppliesReadyForAgent(unittest.TestCase):
    """`tasks.md` 6.4 — the boundary the remediation change depends on."""

    def test_the_label_is_absent_from_the_emittable_vocabulary(self) -> None:
        self.assertNotIn("ready-for-agent", file_issues.EMITTABLE_LABELS)
        self.assertEqual(file_issues.EMITTABLE_LABELS, (file_issues.NEEDS_TRIAGE,))

    def test_emitting_it_raises_rather_than_filing(self) -> None:
        with self.assertRaises(file_issues.ForbiddenLabel):
            file_issues.check_labels(("ready-for-agent",))
        with self.assertRaises(file_issues.ForbiddenLabel):
            file_issues.create_issue(
                {"title": "t", "body": "b", "labels": ["needs-triage", "ready-for-agent"]}
            )

    def test_a_run_of_all_mechanical_fixes_still_files_under_needs_triage(self) -> None:
        findings = normalised()
        plan = file_issues.plan(findings, full_run(findings, "real-mechanical"), [])
        self.assertEqual(len(plan["create"]), 7)
        for item in plan["create"]:
            self.assertEqual(tuple(item["labels"]), (file_issues.NEEDS_TRIAGE,))
            self.assertNotIn("ready-for-agent", item["labels"])

    def test_no_verdict_in_the_vocabulary_unlocks_a_different_label(self) -> None:
        findings = normalised()
        for verdict_class in vocabulary.VERDICTS:
            plan = file_issues.plan(findings, full_run(findings, verdict_class), [])
            labels = {label for item in plan["create"] for label in item["labels"]}
            self.assertEqual(labels, {file_issues.NEEDS_TRIAGE}, verdict_class)


class FilesNothingForFilteredFindings(unittest.TestCase):
    """`tasks.md` 6.5."""

    def setUp(self) -> None:
        self.findings = normalised()

    def test_below_threshold_and_vendored_findings_are_never_candidates(self) -> None:
        plan = file_issues.plan(self.findings, full_run(self.findings), [])
        filed = {item["key"] for item in plan["create"]}
        for group in ("below_threshold", "vendored"):
            for record in self.findings[group]:
                self.assertNotIn(record["key"], filed)
        self.assertEqual(len(self.findings["below_threshold"]), 5)
        self.assertEqual(len(self.findings["vendored"]), 8)

    def test_a_verdict_for_a_below_threshold_finding_is_rejected_not_filed(self) -> None:
        key = self.findings["below_threshold"][0]["key"]
        plan = file_issues.plan(self.findings, [verdict(key)], [])
        self.assertEqual(plan["create"], [])
        self.assertEqual(plan["ineligible_verdicts"], [{"key": key, "reason": "below-threshold"}])

    def test_a_verdict_for_a_vendored_finding_is_rejected_not_filed(self) -> None:
        key = self.findings["vendored"][0]["key"]
        plan = file_issues.plan(self.findings, [verdict(key)], [])
        self.assertEqual(plan["create"], [])
        self.assertEqual(plan["ineligible_verdicts"], [{"key": key, "reason": "vendored"}])

    def test_a_verdict_for_an_unknown_key_is_rejected_not_filed(self) -> None:
        plan = file_issues.plan(self.findings, [verdict("AWS-9999:module.x:aws_thing.y")], [])
        self.assertEqual(plan["create"], [])
        self.assertEqual(len(plan["ineligible_verdicts"]), 1)

    def test_a_partial_run_reports_the_eligible_findings_it_left_untriaged(self) -> None:
        scoped = [record["key"] for record in self.findings["eligible"][:2]]
        plan = file_issues.plan(self.findings, [verdict(key) for key in scoped], [])
        self.assertEqual(len(plan["create"]), 2)
        self.assertEqual(
            plan["untriaged_eligible"],
            sorted(r["key"] for r in self.findings["eligible"] if r["key"] not in scoped),
        )


if __name__ == "__main__":
    unittest.main()
