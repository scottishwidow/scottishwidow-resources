"""Tests for the autonomy ratchet (`tasks.md` group 7, `design.md - Decision 6`).

Run from the repository root with `python3 -m unittest discover -s
security/iac-security-triage/tests`.

The property under test is a negative one — that alert state is *not* written —
so most of these assert an absence. The cases are the spec's three withholding
scenarios (never scored, scored below full agreement, agreed but below support)
plus the two the spec does not enumerate and the code must still handle: a rule
whose grant has gone stale, and a verdict that was never dismissible.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import autonomy  # noqa: E402
import normalise  # noqa: E402
import score  # noqa: E402
import vocabulary  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "fixtures" / "baseline-scan.json"
POLICY = ROOT / "autonomy.json"

RULE = "AWS-0164"
KEY = "AWS-0164:module.vpc:aws_subnet.public_zone_1"


def normalised() -> dict:
    with open(BASELINE, encoding="utf-8") as handle:
        return normalise.normalise(json.load(handle))


def policy(allowlist: list[str] | None = None, floor: int = 5) -> dict:
    return {
        "support_floor": floor,
        "allowlist": [{"rule_id": rule} for rule in (allowlist or [])],
    }


def evidence(rule: str = RULE, scored: int = 5, agreement: float = 1.0) -> dict:
    """A scoring report in the shape `score.py --json` emits."""
    return {
        "per_rule": {
            rule: {
                "scored": scored,
                "agreed": int(round(scored * agreement)),
                "agreement": agreement,
                "disagreements": [],
            }
        }
    }


def verdict(key: str = KEY, verdict_class: str = "not-applicable") -> dict:
    return {
        "key": key,
        "rule_id": key.split(":", 1)[0],
        "verdict": verdict_class,
        "rationale": "The subnets are public by design.",
        "evidence": [],
    }


def decide(verdicts, ev, pol, numbers=None):
    return autonomy.decide(verdicts, ev, pol, numbers if numbers is not None else {KEY: 12})


class TheAllowlistIsEmptyOnThisCorpus(unittest.TestCase):
    """`tasks.md` 7.1."""

    def setUp(self) -> None:
        self.policy = autonomy.load_policy(POLICY)

    def test_the_committed_allowlist_is_empty(self) -> None:
        self.assertEqual(self.policy["allowlist"], [])
        self.assertEqual(autonomy.allowlisted_rules(self.policy), [])

    def test_the_support_floor_is_five(self) -> None:
        self.assertEqual(self.policy["support_floor"], 5)

    def test_the_largest_eligible_rule_cannot_reach_the_floor(self) -> None:
        """The reason the allowlist is empty, derived rather than asserted.

        `AWS-0164` at n=2 is the largest rule in the eligible corpus, so even
        unanimous agreement on every eligible finding leaves every rule short.
        """
        eligible = normalised()["eligible"]
        largest = max(
            len([r for r in eligible if r["rule_id"] == rule])
            for rule in {r["rule_id"] for r in eligible}
        )
        self.assertEqual(largest, 2)
        self.assertLess(largest, self.policy["support_floor"])

    def test_a_floor_of_one_is_refused(self) -> None:
        """"Greater than one" is the spec's wording and is enforced, not assumed."""
        for floor in (1, 0, -1, "5", None):
            with self.subTest(floor=floor):
                path = Path(self.enterContext(tempfile.TemporaryDirectory()))
                config = path / "autonomy.json"
                config.write_text(json.dumps({"support_floor": floor, "allowlist": []}))
                with self.assertRaises(SystemExit):
                    autonomy.load_policy(config)

    def test_a_qualifying_rule_is_reported_and_not_granted(self) -> None:
        """Evidence never grants authority on its own; a human's diff does."""
        checks = autonomy.audit(policy(), evidence(scored=5, agreement=1.0))
        self.assertEqual(checks["qualifying_not_granted"], [RULE])
        self.assertEqual(checks["allowlist"], [])
        self.assertEqual(
            decide([verdict()], evidence(), policy())[0]["reason"], autonomy.NOT_GRANTED
        )


class DismissalRequiresEvidenceAndAGrant(unittest.TestCase):
    """`tasks.md` 7.2."""

    def test_an_allowlisted_rule_with_support_dismisses(self) -> None:
        decision = decide([verdict()], evidence(scored=5), policy([RULE]))[0]
        self.assertEqual(decision["action"], autonomy.DISMISS)
        self.assertEqual(decision["alert"], 12)

    def test_the_rationale_is_recorded_on_the_alert(self) -> None:
        comment = autonomy.dismissal_comment(verdict())
        self.assertIn("The subnets are public by design.", comment)
        self.assertIn(KEY, comment)
        self.assertIn("Reopen", comment)

    def test_the_dismissal_states_a_reason_github_accepts(self) -> None:
        """A finding that does not apply here is not a scanner error."""
        self.assertEqual(autonomy.DISMISSED_REASON, "won't fix")
        self.assertIn(autonomy.DISMISSED_REASON, {"false positive", "won't fix", "used in tests"})

    def test_dismissal_patches_the_alert_rather_than_deleting_anything(self) -> None:
        """A dismissed alert stays visible: the record is edited, never removed."""
        calls: list[list[str]] = []
        original = autonomy.gh_json
        autonomy.gh_json = lambda args: calls.append(args)
        try:
            autonomy.dismiss_alert(12, "because")
        finally:
            autonomy.gh_json = original
        self.assertEqual(calls[0][:4], ["gh", "api", "--method", "PATCH"])
        self.assertIn("state=dismissed", calls[0])
        self.assertIn("dismissed_comment=because", calls[0])
        self.assertNotIn("DELETE", calls[0])

    def test_a_dismissal_can_be_reopened(self) -> None:
        calls: list[list[str]] = []
        original = autonomy.gh_json
        autonomy.gh_json = lambda args: calls.append(args)
        try:
            autonomy.reopen_alert(12)
        finally:
            autonomy.gh_json = original
        self.assertIn("state=open", calls[0])
        self.assertEqual(calls[0][4], f"{autonomy.ALERTS_ENDPOINT}/12")

    def test_a_finding_that_joins_to_no_alert_is_not_dismissed(self) -> None:
        decision = decide([verdict()], evidence(), policy([RULE]), numbers={})[0]
        self.assertEqual(decision["action"], autonomy.PROPOSE)
        self.assertEqual(decision["reason"], autonomy.NO_ALERT)


class AuthorityIsWithheldEverywhereElse(unittest.TestCase):
    """`tasks.md` 7.3 — the spec's three scenarios, and two more."""

    def assert_withheld(self, decision: dict, reason: str) -> None:
        self.assertEqual(decision["action"], autonomy.PROPOSE)
        self.assertEqual(decision["reason"], reason)

    def test_a_never_scored_rule_leaves_alert_state_unchanged(self) -> None:
        self.assert_withheld(
            decide([verdict()], {"per_rule": {}}, policy())[0], autonomy.NEVER_SCORED
        )

    def test_a_rule_scored_below_full_agreement_leaves_alert_state_unchanged(self) -> None:
        self.assert_withheld(
            decide([verdict()], evidence(scored=10, agreement=0.9), policy())[0],
            autonomy.BELOW_AGREEMENT,
        )

    def test_a_fully_agreed_rule_below_the_support_floor_is_withheld(self) -> None:
        """The load-bearing half: 100% over n=2 confers nothing."""
        permitted, why = autonomy.qualifies(RULE, evidence(scored=2), 5)
        self.assertFalse(permitted)
        self.assertEqual(why, autonomy.BELOW_SUPPORT)
        self.assert_withheld(
            decide([verdict()], evidence(scored=2), policy())[0], autonomy.BELOW_SUPPORT
        )

    def test_a_stale_grant_loses_its_authority_without_anyone_editing_the_file(self) -> None:
        """The allowlist can only narrow what the evidence permits, never widen it."""
        stale = policy([RULE])
        self.assert_withheld(
            decide([verdict()], evidence(scored=10, agreement=0.8), stale)[0],
            autonomy.UNSUPPORTED_GRANT,
        )
        self.assertEqual(
            autonomy.audit(stale, evidence(scored=10, agreement=0.8))["unsupported_grants"], [RULE]
        )

    def test_no_verdict_other_than_not_applicable_can_dismiss(self) -> None:
        for verdict_class in vocabulary.VERDICTS:
            if verdict_class == autonomy.DISMISSIBLE_VERDICT:
                continue
            with self.subTest(verdict=verdict_class):
                self.assert_withheld(
                    decide([verdict(verdict_class=verdict_class)], evidence(), policy([RULE]))[0],
                    autonomy.NOT_DISMISSIBLE,
                )

    def test_the_current_corpus_dismisses_nothing_whatever_the_agent_says(self) -> None:
        """The end-to-end statement of 7.1 and 7.3 together.

        Every eligible finding judged `not-applicable`, scored at 100% agreement
        on every rule, against the committed policy: nothing is dismissed,
        because no rule reaches n=5 and the allowlist is empty.
        """
        eligible = normalised()["eligible"]
        run = [verdict(record["key"]) for record in eligible]
        per_rule = {}
        for record in eligible:
            bucket = per_rule.setdefault(
                record["rule_id"], {"scored": 0, "agreed": 0, "agreement": 1.0, "disagreements": []}
            )
            bucket["scored"] += 1
            bucket["agreed"] += 1
        decisions = autonomy.decide(
            run,
            {"per_rule": per_rule},
            autonomy.load_policy(POLICY),
            {record["key"]: index + 1 for index, record in enumerate(eligible)},
        )
        self.assertEqual(len(decisions), 7)
        self.assertEqual([d["action"] for d in decisions], [autonomy.PROPOSE] * 7)
        self.assertEqual(
            {d["reason"] for d in decisions}, {autonomy.BELOW_SUPPORT}
        )


class TheGateAgreesWithTheScorer(unittest.TestCase):
    """The evidence the ratchet reads is the report the scorer writes.

    Asserted against a real `score.py` report rather than a hand-built dict, so
    a change to the report's shape fails here instead of silently making every
    rule unqualifiable — which would fail safe, but silently.
    """

    def test_a_real_score_report_drives_the_gate(self) -> None:
        fixture = {
            "entries": [
                {
                    "key": f"{RULE}:module.vpc:aws_subnet.n{index}",
                    "rule_id": RULE,
                    "verdict": "not-applicable",
                    "verdict_author": "human",
                    "rationale": "Public by design.",
                }
                for index in range(5)
            ]
        }
        run = [
            {"key": entry["key"], "rule_id": RULE, "verdict": "not-applicable"}
            for entry in fixture["entries"]
        ]
        report = score.score(fixture, run)
        self.assertEqual(report["per_rule"][RULE]["scored"], 5)
        self.assertTrue(autonomy.qualifies(RULE, report, 5)[0])
        self.assertFalse(autonomy.qualifies(RULE, report, 6)[0])

    def test_one_disagreement_removes_the_authority(self) -> None:
        fixture = {
            "entries": [
                {
                    "key": f"{RULE}:module.vpc:aws_subnet.n{index}",
                    "rule_id": RULE,
                    "verdict": "not-applicable",
                    "verdict_author": "human",
                    "rationale": "Public by design.",
                }
                for index in range(5)
            ]
        }
        run = [
            {
                "key": entry["key"],
                "rule_id": RULE,
                "verdict": "real-judgment" if index == 0 else "not-applicable",
            }
            for index, entry in enumerate(fixture["entries"])
        ]
        report = score.score(fixture, run)
        permitted, why = autonomy.qualifies(RULE, report, 5)
        self.assertFalse(permitted)
        self.assertEqual(why, autonomy.BELOW_AGREEMENT)


if __name__ == "__main__":
    unittest.main()
