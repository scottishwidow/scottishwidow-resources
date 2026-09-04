"""Tests for the fixture export, its schema and the scorer.

Run from the repository root with `python3 -m unittest discover -s
security/iac_security/tests`.

The corpus is the one in `design.md - Context`: 7 triage-eligible findings across
6 rule IDs, `AWS-0164` the only rule at n=2.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import export_fixture  # noqa: E402
import fixture_schema  # noqa: E402
import issue_body  # noqa: E402
import normalise  # noqa: E402
import score  # noqa: E402

BASELINE = Path(__file__).resolve().parents[1] / "fixtures" / "baseline-scan.json"

STATE_BUCKET = "module.bootstrap:aws_s3_bucket.terraform_state_bucket"
SUBNET_1 = "AWS-0164:module.vpc:aws_subnet.public_zone_1"
SUBNET_2 = "AWS-0164:module.vpc:aws_subnet.public_zone_2"


def normalised() -> dict:
    with open(BASELINE, encoding="utf-8") as handle:
        # Pinned to `HIGH`, the threshold this corpus was designed and measured
        # against, rather than read from `config.json`. The configured threshold
        # is meant to move — task 3.6 moved it to `MEDIUM` — and every count in
        # this file describes the baseline corpus, not wherever the gate sits
        # today. `ThresholdDropTest` in test_ground_truth.py is where moving it
        # is the subject rather than an accident.
        return normalise.normalise(json.load(handle), threshold="HIGH")


def issue(number: int, key: str, verdict: str, author: str = "human", **kwargs) -> dict:
    """An issue body in the template shape the exporter reads."""
    rationale = kwargs.get("rationale", "Because of the thing.")
    evidence = kwargs.get(
        "evidence", "docs/adr/0004-gitlab-downsized-2k-reference-architecture.md"
    )
    return {
        "number": number,
        "body": (
            f"| **Key** | `{key}` |\n"
            f"| **Verdict author** | `{author}` |\n\n"
            f"## Verdict\n\n{verdict}\n\n"
            f"## Rationale\n\n{rationale}\n\n"
            f"## Evidence\n\n{evidence}\n"
        ),
    }


def alert(number: int, rule_id: str, path: str, start_line: int, **kwargs) -> dict:
    return {
        "number": number,
        "state": kwargs.get("state", "open"),
        "dismissed_comment": kwargs.get("dismissed_comment"),
        "rule": {"id": rule_id},
        "most_recent_instance": {"location": {"path": path, "start_line": start_line}},
    }


VENDORED_INSTANCE = re.compile(r"/live/.*?/\.terraform/modules/[^/]+/")


def alert_path(code_path: str) -> str:
    """Spell a path the way code scanning does.

    Trivy composes the module instance into `Target`; the alert reports the
    module's source path. Collapsing it here is what makes the four vendored
    `AWS-0104` pairs collide in the fixture the way they collide for real.
    """
    return VENDORED_INSTANCE.sub("/", code_path)


def baseline_alerts() -> list[dict]:
    """One alert per finding, joined the way the real endpoint joins."""
    data = normalised()
    records = data["eligible"] + data["below_threshold"] + data["vendored"]
    return [
        alert(index + 1, r["rule_id"], alert_path(r["code_path"]), r["start_line"])
        for index, r in enumerate(records)
    ]


class IssueBodyTest(unittest.TestCase):
    def test_unanswered_template_yields_no_verdict(self):
        body = (
            f"| **Key** | `AWS-0086:{STATE_BUCKET}` |\n\n"
            "## Verdict\n\n<!-- one of: not-applicable | real-mechanical -->\n\n"
            "## Rationale\n\n<!-- why -->\n"
        )
        parsed = issue_body.parse(body)
        self.assertEqual(parsed["verdict"], "")
        self.assertEqual(parsed["rationale"], "")

    def test_missing_provenance_is_unknown_not_human(self):
        body = f"| **Key** | `AWS-0086:{STATE_BUCKET}` |\n\n## Verdict\n\nreal-mechanical\n"
        self.assertEqual(issue_body.parse(body)["verdict_author"], issue_body.UNKNOWN)

    def test_body_without_a_key_is_not_a_triage_issue(self):
        self.assertIsNone(issue_body.parse("Just an ordinary issue."))

    def test_evidence_collects_repo_relative_paths(self):
        parsed = issue_body.parse(
            f"| **Key** | `AWS-0086:{STATE_BUCKET}` |\n\n## Verdict\n\nnot-applicable\n\n"
            "## Evidence\n\ndocs/adr/0001-ansible-over-ssm.md\nmodules/vpc/main.tf\n"
        )
        self.assertEqual(
            parsed["evidence"], ["docs/adr/0001-ansible-over-ssm.md", "modules/vpc/main.tf"]
        )


class ExportTest(unittest.TestCase):
    """Task 3.2: the fixture covers exactly the findings the system triages."""

    def setUp(self):
        self.normalised = normalised()
        self.alerts = baseline_alerts()

    def test_full_export_has_one_entry_per_eligible_finding(self):
        issues = [
            issue(100 + i, r["key"], "real-mechanical")
            for i, r in enumerate(self.normalised["eligible"])
        ]
        fixture = export_fixture.build(self.normalised, self.alerts, issues)
        self.assertEqual(len(fixture["entries"]), 7)
        self.assertEqual(fixture["untriaged_keys"], [])
        self.assertEqual(fixture["unjoined_keys"], [])

    def test_every_exported_key_is_triage_eligible(self):
        eligible = {r["key"] for r in self.normalised["eligible"]}
        issues = [
            issue(100 + i, key, "not-applicable") for i, key in enumerate(sorted(eligible))
        ]
        fixture = export_fixture.build(self.normalised, self.alerts, issues)
        self.assertTrue({e["key"] for e in fixture["entries"]} <= eligible)

    def test_below_threshold_and_vendored_never_appear(self):
        excluded = {
            r["key"] for r in self.normalised["below_threshold"] + self.normalised["vendored"]
        }
        issues = [
            issue(100 + i, key, "not-applicable") for i, key in enumerate(sorted(excluded))
        ]
        fixture = export_fixture.build(self.normalised, self.alerts, issues)
        self.assertEqual(fixture["entries"], [])

    def test_a_triaged_below_threshold_finding_is_reported(self):
        """3.1 requires that none was triaged; silence would hide a contaminated corpus."""
        below = {r["key"] for r in self.normalised["below_threshold"]}
        issues = [issue(100 + i, key, "not-applicable") for i, key in enumerate(sorted(below))]
        fixture = export_fixture.build(self.normalised, self.alerts, issues)
        self.assertEqual(set(fixture["ineligible_verdicts"]), below)

    def test_a_dismissed_vendored_alert_is_not_an_error(self):
        """Decision 4 routes vendored findings to dismissal; that is the design, not drift."""
        vendored = self.normalised["vendored"][0]
        alerts = [
            alert(
                1,
                vendored["rule_id"],
                alert_path(vendored["code_path"]),
                vendored["start_line"],
                state="dismissed",
                dismissed_comment="Upstream module; fix belongs to the publisher.",
            )
        ]
        fixture = export_fixture.build(self.normalised, alerts, [])
        self.assertEqual(fixture["ineligible_verdicts"], [])
        self.assertEqual(fixture["entries"], [])

    def test_untriaged_findings_are_outstanding_not_invented(self):
        issues = [issue(100, f"AWS-0086:{STATE_BUCKET}", "real-mechanical")]
        fixture = export_fixture.build(self.normalised, self.alerts, issues)
        self.assertEqual(len(fixture["entries"]), 1)
        self.assertEqual(len(fixture["untriaged_keys"]), 6)

    def test_dismissed_alert_supplies_verdict_and_evidence(self):
        target = next(r for r in self.normalised["eligible"] if r["rule_id"] == "AWS-0132")
        alerts = [
            alert(
                1,
                target["rule_id"],
                target["code_path"],
                target["start_line"],
                state="dismissed",
                dismissed_comment="Accepted per docs/adr/0003-ebs-snapshot-backups-via-dlm.md",
            )
        ]
        fixture = export_fixture.build(self.normalised, alerts, [])
        entry = fixture["entries"][0]
        self.assertEqual(entry["verdict"], "not-applicable")
        self.assertEqual(entry["verdict_author"], "human")
        self.assertEqual(entry["recorded_on"], "alert")
        self.assertEqual(entry["evidence"], ["docs/adr/0003-ebs-snapshot-backups-via-dlm.md"])

    def test_issue_verdict_wins_over_an_open_alert(self):
        issues = [issue(100, f"AWS-0086:{STATE_BUCKET}", "real-judgment", author="model")]
        fixture = export_fixture.build(self.normalised, self.alerts, issues)
        entry = fixture["entries"][0]
        self.assertEqual(entry["recorded_on"], "issue")
        self.assertEqual(entry["verdict_author"], "model")
        self.assertEqual(entry["issue"], 100)

    def test_vendored_key_collisions_do_not_join(self):
        """The four AWS-0104 pairs share rule, path and line; none may be joined."""
        index = export_fixture.index_alerts(self.alerts)
        collided = [r for r in self.normalised["vendored"] if r["rule_id"] == "AWS-0104"]
        self.assertEqual(len(collided), 8)
        self.assertTrue(all(export_fixture.alert_for(r, index) is None for r in collided))

    def test_rendered_fixture_round_trips_and_validates(self):
        import yaml

        issues = [
            issue(100 + i, r["key"], "real-mechanical")
            for i, r in enumerate(self.normalised["eligible"])
        ]
        fixture = export_fixture.build(self.normalised, self.alerts, issues)
        reloaded = yaml.safe_load(export_fixture.render(fixture))
        self.assertEqual(fixture_schema.validate(reloaded), [])
        self.assertEqual(len(reloaded["entries"]), 7)



class ThresholdDropTest(unittest.TestCase):
    """Task 3.6: the export is a repeatable operation, not a one-off.

    Lowering the threshold is the only way the corpus grows before
    `live/gitlab/` lands, so the property that matters is that a re-export
    *extends* the fixture: the findings admitted by the drop gain entries, and
    the entries already recorded are neither rewritten nor invalidated. If a
    drop reset the corpus, every threshold move would cost the verdicts already
    spent on it.

    The two findings a drop to `MEDIUM` admits are the ones named in
    `design.md - Decision 5` as the corpus's most independent judgments —
    `AWS-0178` on the VPC and `AWS-0090` on the scratch bucket — and they are
    the only first-party findings the agent has not already been shown.
    """

    NEWLY_ELIGIBLE = {
        "AWS-0178:module.vpc:aws_vpc.main",
        "AWS-0090:module.ssm_scratch:aws_s3_bucket.this",
    }

    def setUp(self):
        with open(BASELINE, encoding="utf-8") as handle:
            self.report = json.load(handle)
        self.high = normalise.normalise(self.report, threshold="HIGH")
        self.medium = normalise.normalise(self.report, threshold="MEDIUM")
        self.alerts = baseline_alerts()

    def keys(self, normalised: dict, bucket: str) -> set:
        return {r["key"] for r in normalised[bucket]}

    def test_drop_admits_the_below_threshold_findings_and_loses_none(self):
        self.assertEqual(
            self.keys(self.medium, "eligible") - self.keys(self.high, "eligible"),
            self.NEWLY_ELIGIBLE,
        )
        self.assertTrue(
            self.keys(self.high, "eligible") <= self.keys(self.medium, "eligible")
        )
        # Ownership is decided before severity, so a severity move must not
        # disturb the vendored partition at all.
        self.assertEqual(self.keys(self.high, "vendored"), self.keys(self.medium, "vendored"))

    def test_keys_survive_the_drop_unchanged(self):
        """A finding carries the same identity at either threshold.

        This is what makes the corpus cumulative: the key in an entry recorded
        under `HIGH` still names the same finding under `MEDIUM`, so existing
        verdicts keep pointing at what they judged (`design.md - Decision 3`).
        """
        before = {r["key"]: r for r in self.high["eligible"] + self.high["below_threshold"]}
        after = {r["key"]: r for r in self.medium["eligible"] + self.medium["below_threshold"]}
        self.assertEqual(set(before), set(after))
        for key, record in before.items():
            self.assertEqual(record["rule_id"], after[key]["rule_id"])
            self.assertEqual(record["severity"], after[key]["severity"])

    def test_re_export_extends_the_fixture_without_rewriting_it(self):
        original = [
            issue(100 + i, r["key"], "real-mechanical")
            for i, r in enumerate(self.high["eligible"])
        ]
        first = export_fixture.build(self.high, self.alerts, original)

        # 3.1 re-run over the newly eligible findings, then 3.2 again.
        widened = original + [
            issue(200 + i, key, "not-applicable")
            for i, key in enumerate(sorted(self.NEWLY_ELIGIBLE))
        ]
        second = export_fixture.build(self.medium, self.alerts, widened)

        self.assertEqual(len(first["entries"]), 7)
        self.assertEqual(len(second["entries"]), 9)
        self.assertEqual(second["severity_threshold"], "MEDIUM")
        self.assertEqual(second["untriaged_keys"], [])

        carried = {e["key"]: e for e in second["entries"]}
        for entry in first["entries"]:
            self.assertIn(entry["key"], carried)
            self.assertEqual(entry, carried[entry["key"]])

    def test_the_newly_eligible_pair_is_an_error_before_the_drop_and_legal_after(self):
        """The same verdicts, judged by whether the finding was submitted for triage.

        Triaging these two under `HIGH` contaminates the corpus and is reported
        as such; the drop is precisely what makes recording them legitimate.
        """
        issues = [
            issue(200 + i, key, "not-applicable")
            for i, key in enumerate(sorted(self.NEWLY_ELIGIBLE))
        ]
        before = export_fixture.build(self.high, self.alerts, issues)
        self.assertEqual(set(before["ineligible_verdicts"]), self.NEWLY_ELIGIBLE)
        self.assertEqual(before["entries"], [])

        after = export_fixture.build(self.medium, self.alerts, issues)
        self.assertEqual(after["ineligible_verdicts"], [])
        self.assertEqual({e["key"] for e in after["entries"]}, self.NEWLY_ELIGIBLE)

    def test_a_widened_fixture_still_validates(self):
        import yaml

        issues = [
            issue(100 + i, r["key"], "real-judgment")
            for i, r in enumerate(self.medium["eligible"])
        ]
        fixture = export_fixture.build(self.medium, self.alerts, issues)
        reloaded = yaml.safe_load(export_fixture.render(fixture))
        self.assertEqual(fixture_schema.validate(reloaded), [])
        self.assertEqual(len(reloaded["entries"]), 9)


class SchemaTest(unittest.TestCase):
    """Task 3.3: the fixture is gated, not merely linted."""

    def fixture(self, **overrides) -> dict:
        entry = {
            "key": f"AWS-0086:{STATE_BUCKET}",
            "rule_id": "AWS-0086",
            "verdict": "real-mechanical",
            "verdict_author": "human",
            "rationale": "Because of the thing.",
            "evidence": [],
        }
        entry.update(overrides)
        return {
            "severity_threshold": "HIGH",
            "exported_at": "2026-09-02T00:00:00+00:00",
            "entries": [entry],
        }

    def test_valid_fixture_passes(self):
        self.assertEqual(fixture_schema.validate(self.fixture()), [])

    def test_misspelled_verdict_is_rejected(self):
        errors = fixture_schema.validate(self.fixture(verdict="real-mechanicl"))
        self.assertTrue(any("unknown verdict" in e for e in errors))

    def test_empty_rationale_is_rejected(self):
        errors = fixture_schema.validate(self.fixture(rationale="   "))
        self.assertTrue(any("empty rationale" in e for e in errors))

    def test_unknown_verdict_author_is_rejected(self):
        errors = fixture_schema.validate(self.fixture(verdict_author="the-intern"))
        self.assertTrue(any("unknown verdict_author" in e for e in errors))

    def test_duplicate_keys_are_rejected(self):
        fixture = self.fixture()
        fixture["entries"] = fixture["entries"] * 2
        self.assertTrue(any("duplicate key" in e for e in fixture_schema.validate(fixture)))

    def test_missing_field_is_reported(self):
        fixture = self.fixture()
        del fixture["entries"][0]["rationale"]
        self.assertTrue(
            any("missing field rationale" in e for e in fixture_schema.validate(fixture))
        )


class ScoreTest(unittest.TestCase):
    """Task 3.4: scored against a deliberately disagreeing run, not against itself."""

    def fixture(self) -> dict:
        def entry(key, rule, verdict, author="human"):
            return {
                "key": key,
                "rule_id": rule,
                "verdict": verdict,
                "verdict_author": author,
                "rationale": "Recorded.",
                "evidence": [],
            }

        return {
            "severity_threshold": "HIGH",
            "exported_at": "2026-09-02T00:00:00+00:00",
            "entries": [
                entry(f"AWS-0086:{STATE_BUCKET}", "AWS-0086", "real-mechanical"),
                entry(f"AWS-0087:{STATE_BUCKET}", "AWS-0087", "real-mechanical"),
                entry(SUBNET_1, "AWS-0164", "not-applicable"),
                entry(SUBNET_2, "AWS-0164", "real-judgment"),
            ],
        }

    def run_of(self, **verdicts) -> list[dict]:
        keys = {
            "a": (f"AWS-0086:{STATE_BUCKET}", "AWS-0086"),
            "b": (f"AWS-0087:{STATE_BUCKET}", "AWS-0087"),
            "s1": (SUBNET_1, "AWS-0164"),
            "s2": (SUBNET_2, "AWS-0164"),
        }
        return [
            {"key": keys[name][0], "rule_id": keys[name][1], "verdict": verdict}
            for name, verdict in verdicts.items()
        ]

    def test_perfect_run_agrees_everywhere(self):
        report = score.score(
            self.fixture(),
            self.run_of(
                a="real-mechanical",
                b="real-mechanical",
                s1="not-applicable",
                s2="real-judgment",
            ),
        )
        self.assertEqual(report["overall"], {"scored": 4, "agreed": 4, "agreement": 1.0})
        self.assertEqual(report["per_rule"]["AWS-0164"]["scored"], 2)

    def test_deliberately_disagreeing_run_reports_sub_100(self):
        """A scorer that returns 100% unconditionally must fail this."""
        report = score.score(
            self.fixture(),
            self.run_of(
                a="real-mechanical",
                b="not-applicable",
                s1="not-applicable",
                s2="not-applicable",
            ),
        )
        self.assertEqual(report["overall"], {"scored": 4, "agreed": 2, "agreement": 0.5})
        self.assertEqual(
            report["per_rule"]["AWS-0086"],
            {"scored": 1, "agreed": 1, "disagreements": [], "agreement": 1.0},
        )
        self.assertEqual(report["per_rule"]["AWS-0087"]["agreement"], 0.0)
        self.assertEqual(report["per_rule"]["AWS-0164"]["agreed"], 1)
        self.assertEqual(report["per_rule"]["AWS-0164"]["agreement"], 0.5)
        self.assertEqual(
            report["per_rule"]["AWS-0164"]["disagreements"],
            [{"key": SUBNET_2, "expected": "real-judgment", "got": "not-applicable"}],
        )

    def test_every_figure_carries_its_support(self):
        report = score.score(
            self.fixture(), self.run_of(a="real-mechanical", s1="not-applicable")
        )
        for bucket in report["per_rule"].values():
            self.assertIn("scored", bucket)
            self.assertEqual(bucket["scored"], bucket["agreed"] + len(bucket["disagreements"]))

    def test_model_authored_entry_is_excluded_from_agreement(self):
        fixture = self.fixture()
        fixture["entries"][0]["verdict_author"] = "model"
        report = score.score(fixture, self.run_of(a="real-mechanical", b="real-mechanical"))
        self.assertEqual(report["excluded_non_human"], [f"AWS-0086:{STATE_BUCKET}"])
        self.assertNotIn("AWS-0086", report["per_rule"])
        self.assertEqual(report["overall"]["scored"], 1)
        self.assertEqual(report["scorable_entries"], 3)

    def test_unknown_provenance_is_excluded_too(self):
        fixture = self.fixture()
        fixture["entries"][0]["verdict_author"] = "unknown"
        report = score.score(fixture, self.run_of(a="real-mechanical"))
        self.assertEqual(report["excluded_non_human"], [f"AWS-0086:{STATE_BUCKET}"])
        self.assertEqual(report["overall"]["agreement"], None)

    def test_fixture_entries_missing_from_the_run_are_reported(self):
        report = score.score(self.fixture(), self.run_of(a="real-mechanical"))
        self.assertEqual(
            report["not_covered_by_run"],
            sorted([f"AWS-0087:{STATE_BUCKET}", SUBNET_1, SUBNET_2]),
        )


class UnscoredRuleTest(unittest.TestCase):
    """Task 3.5: a rule absent from the fixture is flagged, never counted."""

    def fixture(self) -> dict:
        return {
            "severity_threshold": "HIGH",
            "exported_at": "2026-09-02T00:00:00+00:00",
            "entries": [
                {
                    "key": f"AWS-0086:{STATE_BUCKET}",
                    "rule_id": "AWS-0086",
                    "verdict": "real-mechanical",
                    "verdict_author": "human",
                    "rationale": "Recorded.",
                    "evidence": [],
                }
            ],
        }

    def test_finding_from_an_absent_rule_is_excluded_and_flagged(self):
        report = score.score(
            self.fixture(),
            [
                {
                    "key": f"AWS-0086:{STATE_BUCKET}",
                    "rule_id": "AWS-0086",
                    "verdict": "real-mechanical",
                },
                {
                    "key": "AWS-9999:module.new:aws_thing.new",
                    "rule_id": "AWS-9999",
                    "verdict": "not-applicable",
                },
            ],
        )
        self.assertEqual(report["unscored_rules"], ["AWS-9999"])
        self.assertEqual(report["unknown_keys"], ["AWS-9999:module.new:aws_thing.new"])
        self.assertNotIn("AWS-9999", report["per_rule"])
        # The unlabelled finding must not inflate the figure it is absent from.
        self.assertEqual(report["overall"], {"scored": 1, "agreed": 1, "agreement": 1.0})


if __name__ == "__main__":
    unittest.main()
