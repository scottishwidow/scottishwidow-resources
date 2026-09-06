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
        # Pinned to `HIGH`: every count in this file describes the baseline corpus, not `config.json`'s current gate.
        return normalise.normalise(json.load(handle), threshold="HIGH")


def verdict(key: str, verdict_class: str = "real-mechanical", **kwargs) -> dict:
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
    return [verdict(record["key"], verdict_class) for record in findings["eligible"]]


def issue_for(item: dict, number: int = 1) -> dict:
    return {"number": number, "body": item["body"]}


class FilesOnePerTriagedFinding(unittest.TestCase):
    def setUp(self) -> None:
        self.findings = normalised()
        self.plan = file_issues.plan(self.findings, full_run(self.findings), [], [])

    def test_a_full_run_files_one_issue_per_eligible_finding(self) -> None:
        self.assertEqual(len(self.plan["create"]), 7)
        self.assertEqual(len(self.findings["eligible"]), 7)
        self.assertEqual(
            sorted(item["key"] for item in self.plan["create"]),
            sorted(record["key"] for record in self.findings["eligible"]),
        )

    def test_nothing_is_left_untriaged_by_a_full_run(self) -> None:
        self.assertEqual(self.plan["filed_without_a_verdict"], [])

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
        plan = file_issues.plan(self.findings, [verdict(key, evidence=[tf_file])], [], [])
        self.assertEqual(issue_body.parse(plan["create"][0]["body"])["evidence"], [tf_file])


class EvidenceOutsideTheCorpusIsMarkedInPlace(unittest.TestCase):
    def setUp(self) -> None:
        self.finding = {"rule_id": "AWS-0164", "title": "t", "severity": "HIGH"}
        self.record = {
            "key": "AWS-0164:module.vpc:aws_subnet.public_zone_1",
            "verdict": "real-judgment",
            "rationale": "why",
            "evidence": ["modules/vpc/main.tf", "live/nonexistent/main.tf"],
            "evidence_discrepancy": ["live/nonexistent/main.tf"],
        }

    def test_each_cited_path_appears_exactly_once(self) -> None:
        section = file_issues.evidence_section(self.record)
        for path in self.record["evidence"]:
            self.assertEqual(section.count(f"`{path}`"), 1, section)

    def test_only_the_discrepant_path_is_marked(self) -> None:
        section = file_issues.evidence_section(self.record)
        self.assertIn("- `live/nonexistent/main.tf` — **not in the Terraform corpus**", section)
        self.assertIn("- `modules/vpc/main.tf`\n", section)

    def test_a_verdict_with_no_discrepancy_says_nothing_about_one(self) -> None:
        del self.record["evidence_discrepancy"]
        section = file_issues.evidence_section(self.record)
        self.assertNotIn("not in the Terraform corpus", section)

    def test_the_marker_does_not_disturb_the_paths_read_back(self) -> None:
        body = file_issues.body(self.finding, self.record, None)
        self.assertEqual(issue_body.parse(body)["evidence"], self.record["evidence"])


class IsIdempotentOnTheFindingKey(unittest.TestCase):
    def setUp(self) -> None:
        self.findings = normalised()
        self.run = full_run(self.findings)
        first = file_issues.plan(self.findings, self.run, [], [])
        self.existing = [
            issue_for(item, number=100 + index) for index, item in enumerate(first["create"])
        ]

    def test_a_second_run_with_unchanged_verdicts_files_nothing(self) -> None:
        second = file_issues.plan(self.findings, self.run, self.existing, [])
        self.assertEqual(second["create"], [])
        self.assertEqual(len(second["skipped_existing"]), 7)

    def test_a_second_run_reports_the_issue_each_finding_already_has(self) -> None:
        second = file_issues.plan(self.findings, self.run, self.existing, [])
        self.assertEqual(
            {item["key"]: item["issue"] for item in second["skipped_existing"]},
            {issue_body.parse(i["body"])["key"]: i["number"] for i in self.existing},
        )

    def test_a_changed_verdict_still_files_nothing_for_a_known_key(self) -> None:
        changed = full_run(self.findings, "not-applicable")
        self.assertEqual(file_issues.plan(self.findings, changed, self.existing, [])["create"], [])

    def test_a_human_applied_disposition_label_is_left_untouched(self) -> None:
        labelled = [dict(issue, labels=[{"name": "ready-for-human"}]) for issue in self.existing]
        second = file_issues.plan(self.findings, self.run, labelled, [])
        self.assertEqual(second["create"], [])
        self.assertNotIn("edit", second)
        self.assertNotIn("relabel", second)

    def test_closed_issues_are_fetched_so_a_wontfix_is_not_refiled(self) -> None:
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
        self.assertEqual(len(file_issues.plan(self.findings, self.run, unrelated, [])["create"]), 7)


class FilesNotApplicableVerdictsToo(unittest.TestCase):
    def setUp(self) -> None:
        self.findings = normalised()
        run = full_run(self.findings, "not-applicable")
        self.plan = file_issues.plan(self.findings, run, [], [])

    def test_a_not_applicable_verdict_still_creates_an_issue(self) -> None:
        self.assertEqual(len(self.plan["create"]), 7)

    def test_the_issue_states_the_verdict_and_its_rationale(self) -> None:
        for item in self.plan["create"]:
            parsed = issue_body.parse(item["body"])
            self.assertEqual(parsed["verdict"], "not-applicable")
            self.assertTrue(parsed["rationale"])

    def test_nothing_here_can_dismiss_an_alert(self) -> None:
        source = (Path(file_issues.__file__)).read_text(encoding="utf-8")
        for forbidden in ("dismissed_reason", "--state dismissed", "PATCH", "POST", "DELETE"):
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
        plan = file_issues.plan(self.findings, [record], [], [])
        item = next(entry for entry in plan["create"] if entry["key"] == key)
        parsed = issue_body.parse(item["body"])
        self.assertEqual(parsed["verdict"], "undetermined")
        self.assertIn("rationale was empty or whitespace", parsed["rationale"])
        self.assertIn("real-mechanical", parsed["rationale"])


ALERT_URL = "https://github.com/o/r/security/code-scanning"


def alert(number: int, rule_id: str, path: str, start_line: int) -> dict:
    return {
        "number": number,
        "html_url": f"{ALERT_URL}/{number}",
        "rule": {"id": rule_id},
        "most_recent_instance": {"location": {"path": path, "start_line": start_line}},
    }


class RecordsTheAlertItWasFiledFor(unittest.TestCase):
    def setUp(self) -> None:
        self.findings = normalised()
        self.finding = self.findings["eligible"][0]

    def matching(self, number: int = 42) -> dict:
        return alert(
            number,
            self.finding["rule_id"],
            self.finding["code_path"],
            self.finding["start_line"],
        )

    def test_a_matching_alert_is_resolved(self) -> None:
        found = file_issues.find_alert(self.finding, [self.matching()])
        self.assertEqual(found["number"], 42)

    def test_an_ambiguous_match_resolves_to_none(self) -> None:
        self.assertIsNone(
            file_issues.find_alert(self.finding, [self.matching(41), self.matching(42)])
        )

    def test_an_ambiguous_match_is_filed_with_no_alert_row(self) -> None:
        plan = file_issues.plan(
            self.findings, full_run(self.findings), [], [self.matching(41), self.matching(42)]
        )
        item = next(i for i in plan["create"] if i["key"] == self.finding["key"])
        self.assertIsNone(item["alert"])
        self.assertNotIn("**Alert**", item["body"])

    def test_the_alert_row_links_to_the_alert_and_not_to_an_issue(self) -> None:
        plan = file_issues.plan(self.findings, full_run(self.findings), [], [self.matching()])
        item = next(i for i in plan["create"] if i["key"] == self.finding["key"])
        self.assertIn(f"| **Alert** | [#42]({ALERT_URL}/42) |", item["body"])
        self.assertNotIn("| **Alert** | #42 |", item["body"])

    def test_an_alert_with_no_url_is_written_as_a_code_span(self) -> None:
        self.assertEqual(file_issues.alert_cell({"number": 42}), "`#42`")
        parsed = issue_body.parse("| **Key** | `k` |\n| **Alert** | `#42` |")
        self.assertEqual(parsed["alert"], 42)

    def test_an_alert_for_a_different_rule_does_not_match(self) -> None:
        alerts = [alert(42, "AWS-9999", self.finding["code_path"], self.finding["start_line"])]
        self.assertIsNone(file_issues.find_alert(self.finding, alerts))

    def test_an_alert_at_a_different_location_does_not_match(self) -> None:
        alerts = [alert(42, self.finding["rule_id"], "live/other/main.tf", 1)]
        self.assertIsNone(file_issues.find_alert(self.finding, alerts))

    def test_no_alerts_resolves_to_none(self) -> None:
        self.assertIsNone(file_issues.find_alert(self.finding, []))

    def test_round_trip_through_filer_and_reader(self) -> None:
        plan = file_issues.plan(self.findings, full_run(self.findings), [], [self.matching()])
        item = next(i for i in plan["create"] if i["key"] == self.finding["key"])
        self.assertEqual(item["alert"], 42)
        self.assertEqual(issue_body.parse(item["body"])["alert"], 42)

    def test_a_body_with_no_resolved_alert_carries_no_alert_row(self) -> None:
        plan = file_issues.plan(self.findings, full_run(self.findings), [], alerts=[])
        item = next(i for i in plan["create"] if i["key"] == self.finding["key"])
        self.assertIsNone(item["alert"])
        self.assertNotIn("**Alert**", item["body"])
        self.assertIsNone(issue_body.parse(item["body"])["alert"])

    def test_a_body_with_no_alert_row_is_read_without_error(self) -> None:
        parsed = issue_body.parse("| **Key** | `AWS-0086:module.x:aws_s3_bucket.y` |")
        self.assertIsNotNone(parsed)
        self.assertIsNone(parsed["alert"])


class TheDeadSpecPathIsGone(unittest.TestCase):
    def test_the_issue_body_names_no_openspec_path(self) -> None:
        source = Path(file_issues.__file__).read_text(encoding="utf-8")
        self.assertNotIn("openspec/", source)

    def test_no_module_or_document_in_the_package_names_one(self) -> None:
        # This file is excluded: it is the only one that must name the dead path.
        root = Path(file_issues.__file__).parent
        guard = Path(__file__).resolve()
        named = [
            str(path.relative_to(root))
            for path in sorted(list(root.rglob("*.py")) + list(root.rglob("*.md")))
            if path.resolve() != guard and "openspec/" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(named, [])


class NeverAppliesAnAuthorisingLabel(unittest.TestCase):
    """Neither `ready-for-agent` nor `ready-for-remediation`.

    An agent able to apply one would be authorising its own downstream work:
    `ready-for-remediation` is what triggers the remediation workflow, and
    `ready-for-agent` is the repository's general AFK-ready label.
    """

    authorising = ("ready-for-agent", file_issues.READY_FOR_REMEDIATION)

    def test_neither_label_is_in_the_emittable_vocabulary(self) -> None:
        self.assertEqual(file_issues.EMITTABLE_LABELS, (file_issues.NEEDS_TRIAGE,))
        for label in self.authorising:
            self.assertNotIn(label, file_issues.EMITTABLE_LABELS, label)
            self.assertIn(label, file_issues.FORBIDDEN_LABELS, label)

    def test_emitting_either_raises_rather_than_filing(self) -> None:
        for label in self.authorising:
            with self.subTest(label=label):
                with self.assertRaises(file_issues.ForbiddenLabel):
                    file_issues.check_labels((label,))
                with self.assertRaises(file_issues.ForbiddenLabel):
                    file_issues.create_issue(
                        {"title": "t", "body": "b", "labels": ["needs-triage", label]}
                    )

    def test_the_issue_says_which_label_asks_the_pipeline_for_a_patch(self) -> None:
        """A label nobody knows about authorises nothing, so the item names it."""
        findings = normalised()
        item = file_issues.plan(findings, full_run(findings), [], [])["create"][0]
        self.assertIn(file_issues.READY_FOR_REMEDIATION, item["body"])

    def test_a_label_outside_the_vocabulary_raises_whether_or_not_it_is_named(self) -> None:
        """The forbidden list is a statement of intent; the vocabulary is the check."""
        with self.assertRaises(file_issues.ForbiddenLabel):
            file_issues.check_labels(("some-label-nobody-listed",))

    def test_a_run_of_all_mechanical_fixes_still_files_under_needs_triage(self) -> None:
        findings = normalised()
        plan = file_issues.plan(findings, full_run(findings, "real-mechanical"), [], [])
        self.assertEqual(len(plan["create"]), 7)
        for item in plan["create"]:
            self.assertEqual(tuple(item["labels"]), (file_issues.NEEDS_TRIAGE,))
            self.assertNotIn("ready-for-agent", item["labels"])

    def test_no_verdict_in_the_vocabulary_unlocks_a_different_label(self) -> None:
        findings = normalised()
        for verdict_class in vocabulary.VERDICTS:
            plan = file_issues.plan(findings, full_run(findings, verdict_class), [], [])
            labels = {label for item in plan["create"] for label in item["labels"]}
            self.assertEqual(labels, {file_issues.NEEDS_TRIAGE}, verdict_class)


class FilesNothingForFilteredFindings(unittest.TestCase):
    def setUp(self) -> None:
        self.findings = normalised()

    def test_below_threshold_and_vendored_findings_are_never_candidates(self) -> None:
        plan = file_issues.plan(self.findings, full_run(self.findings), [], [])
        filed = {item["key"] for item in plan["create"]}
        for group in ("below_threshold", "vendored"):
            for record in self.findings[group]:
                self.assertNotIn(record["key"], filed)
        self.assertEqual(len(self.findings["below_threshold"]), 5)
        self.assertEqual(len(self.findings["vendored"]), 8)

    def filed(self, plan: dict) -> set[str]:
        return {item["key"] for item in plan["create"]}

    def test_a_verdict_for_a_below_threshold_finding_is_rejected_not_filed(self) -> None:
        key = self.findings["below_threshold"][0]["key"]
        plan = file_issues.plan(self.findings, [verdict(key)], [], [])
        self.assertNotIn(key, self.filed(plan))
        self.assertEqual(plan["ineligible_verdicts"], [{"key": key, "reason": "below-threshold"}])

    def test_a_verdict_for_a_vendored_finding_is_rejected_not_filed(self) -> None:
        key = self.findings["vendored"][0]["key"]
        plan = file_issues.plan(self.findings, [verdict(key)], [], [])
        self.assertNotIn(key, self.filed(plan))
        self.assertEqual(plan["ineligible_verdicts"], [{"key": key, "reason": "vendored"}])

    def test_a_verdict_for_an_unknown_key_is_rejected_not_filed(self) -> None:
        key = "AWS-9999:module.x:aws_thing.y"
        plan = file_issues.plan(self.findings, [verdict(key)], [], [])
        self.assertNotIn(key, self.filed(plan))
        self.assertEqual(len(plan["ineligible_verdicts"]), 1)


class EveryEligibleFindingBecomesATrackerItem(unittest.TestCase):
    def setUp(self) -> None:
        self.findings = normalised()
        self.scoped = [record["key"] for record in self.findings["eligible"][:2]]
        self.missing = sorted(
            r["key"] for r in self.findings["eligible"] if r["key"] not in self.scoped
        )
        self.plan = file_issues.plan(
            self.findings, [verdict(key) for key in self.scoped], [], []
        )

    def test_a_partial_run_still_files_every_eligible_finding(self) -> None:
        self.assertEqual(
            sorted(item["key"] for item in self.plan["create"]),
            sorted(record["key"] for record in self.findings["eligible"]),
        )

    def test_it_reports_which_findings_no_verdict_reached(self) -> None:
        self.assertEqual(self.plan["filed_without_a_verdict"], self.missing)

    def test_a_finding_no_verdict_reached_is_recorded_undetermined(self) -> None:
        for item in self.plan["create"]:
            expected = "real-mechanical" if item["key"] in self.scoped else file_issues.UNDETERMINED
            self.assertEqual(item["verdict"], expected, item["key"])

    def test_its_body_says_no_verdict_was_produced(self) -> None:
        item = next(item for item in self.plan["create"] if item["key"] in self.missing)
        parsed = issue_body.parse(item["body"])
        self.assertEqual(parsed["verdict"], file_issues.UNDETERMINED)
        self.assertIn(file_issues.DISCARDED_NO_RECORD, parsed["rationale"])

    def test_a_finding_already_filed_is_not_filed_again_without_a_verdict(self) -> None:
        item = next(item for item in self.plan["create"] if item["key"] in self.missing)
        second = file_issues.plan(
            self.findings, [verdict(key) for key in self.scoped], [issue_for(item, 42)], []
        )
        self.assertNotIn(item["key"], {entry["key"] for entry in second["create"]})
        self.assertIn({"key": item["key"], "issue": 42}, second["skipped_existing"])


class TwoVerdictsForOneKeyInOneRun(unittest.TestCase):
    """Filing is idempotent within one run as well as across runs.

    One finding key can reach the verdict list more than once, because two
    eligible findings can carry it. Only the first record for a key is filed.
    """

    def setUp(self) -> None:
        self.findings = normalised()
        self.key = self.findings["eligible"][0]["key"]

    def plan_for(self, records: list[dict]) -> dict:
        return file_issues.plan(self.findings, records, [], [])

    def filed_for_the_key(self, plan: dict) -> list[dict]:
        return [item for item in plan["create"] if item["key"] == self.key]

    def test_the_second_record_for_a_key_is_not_filed(self) -> None:
        plan = self.plan_for([verdict(self.key), verdict(self.key, "not-applicable")])
        self.assertEqual(len(self.filed_for_the_key(plan)), 1)

    def test_the_first_record_for_a_key_is_the_one_filed(self) -> None:
        plan = self.plan_for([verdict(self.key), verdict(self.key, "not-applicable")])
        self.assertEqual(self.filed_for_the_key(plan)[0]["verdict"], "real-mechanical")

    def test_the_second_record_is_reported_rather_than_dropped(self) -> None:
        plan = self.plan_for([verdict(self.key), verdict(self.key, "not-applicable")])
        self.assertEqual([item["key"] for item in plan["skipped_duplicate_in_run"]], [self.key])

    def test_a_run_with_no_duplicate_reports_none(self) -> None:
        plan = self.plan_for(full_run(self.findings))
        self.assertEqual(plan["skipped_duplicate_in_run"], [])
        self.assertEqual(len(plan["create"]), 7)

    def test_a_key_a_previous_run_filed_is_still_skipped_as_existing(self) -> None:
        """The across-run guard is reached first, so both records skip as existing."""
        first = self.plan_for([verdict(self.key)])
        existing = [issue_for(self.filed_for_the_key(first)[0], number=100)]
        second = file_issues.plan(self.findings, [verdict(self.key), verdict(self.key)], existing, [])
        self.assertEqual(self.filed_for_the_key(second), [])
        self.assertEqual({item["key"] for item in second["skipped_existing"]}, {self.key})
        self.assertEqual(second["skipped_duplicate_in_run"], [])

    def test_an_eligible_finding_without_a_verdict_is_still_filed_once(self) -> None:
        """A duplicated verdict must not make its key look untriaged as well."""
        plan = self.plan_for([verdict(self.key), verdict(self.key)])
        self.assertNotIn(self.key, plan["filed_without_a_verdict"])


class ATrackerItemAwaitingAVerdictIsCommentedOn(unittest.TestCase):
    """`undetermined` is a failure to judge, not a judgment, so its finding is
    triaged again — and the new verdict must reach the item that already exists.

    Opening a second item for one finding key would break the idempotency the
    whole tracker join rests on.
    """

    def setUp(self) -> None:
        self.findings = normalised()
        self.key = self.findings["eligible"][0]["key"]
        first = file_issues.plan(
            self.findings, [verdict(self.key, file_issues.UNDETERMINED)], [], []
        )
        self.item = issue_for(self.filed(first), number=77)
        self.item["state"] = "OPEN"

    def filed(self, plan: dict) -> dict:
        return next(item for item in plan["create"] if item["key"] == self.key)

    def plan_with(self, records: list[dict], item: dict | None = None) -> dict:
        return file_issues.plan(self.findings, records, [item or self.item], [])

    def test_the_new_verdict_arrives_as_a_comment(self) -> None:
        plan = self.plan_with([verdict(self.key, "real-judgment")])
        self.assertEqual([entry["key"] for entry in plan["comment"]], [self.key])
        self.assertEqual(plan["comment"][0]["issue"], 77)

    def test_it_opens_no_second_item_for_that_key(self) -> None:
        plan = self.plan_with([verdict(self.key, "real-judgment")])
        self.assertNotIn(self.key, {entry["key"] for entry in plan["create"]})

    def test_the_comment_carries_the_verdict_and_the_rationale(self) -> None:
        plan = self.plan_with(
            [verdict(self.key, "real-mechanical", rationale="The bucket is unversioned.")]
        )
        body = plan["comment"][0]["body"]
        self.assertEqual(issue_body.comment_verdict(body), "real-mechanical")
        self.assertIn("The bucket is unversioned.", body)

    def test_the_comment_is_what_the_next_run_reads_the_item_as(self) -> None:
        """Otherwise the re-triage never ends: the issue body still says `undetermined`."""
        plan = self.plan_with([verdict(self.key, "real-judgment")])
        answered = dict(self.item, comments=[{"body": plan["comment"][0]["body"]}])
        self.assertFalse(issue_body.awaits_a_verdict(issue_body.tracker_items([answered])[self.key]))

    def test_a_second_undetermined_is_not_commented(self) -> None:
        """The item says `undetermined` already; a comment per push would bury it."""
        plan = self.plan_with([verdict(self.key, file_issues.UNDETERMINED)])
        self.assertEqual(plan["comment"], [])
        self.assertIn({"key": self.key, "issue": 77}, plan["skipped_existing"])

    def test_a_finding_no_verdict_reached_is_not_commented_either(self) -> None:
        plan = self.plan_with([])
        self.assertEqual(plan["comment"], [])
        self.assertNotIn(self.key, plan["filed_without_a_verdict"])

    def test_only_the_first_of_two_records_for_one_key_is_commented(self) -> None:
        plan = self.plan_with([verdict(self.key, "real-judgment"), verdict(self.key, "not-applicable")])
        self.assertEqual([entry["verdict"] for entry in plan["comment"]], ["real-judgment"])

    def test_an_item_recording_a_real_verdict_is_skipped_not_commented(self) -> None:
        judged = file_issues.plan(self.findings, [verdict(self.key, "real-judgment")], [], [])
        item = issue_for(self.filed(judged), number=88)
        item["state"] = "OPEN"
        plan = self.plan_with([verdict(self.key, "not-applicable")], item)
        self.assertEqual(plan["comment"], [])
        self.assertIn({"key": self.key, "issue": 88}, plan["skipped_existing"])

    def test_a_closed_item_is_skipped_however_it_was_left(self) -> None:
        """A reintroduced finding reopens its alert, which is where that state belongs."""
        plan = self.plan_with(
            [verdict(self.key, "real-judgment")], dict(self.item, state="CLOSED")
        )
        self.assertEqual(plan["comment"], [])
        self.assertIn({"key": self.key, "issue": 77}, plan["skipped_existing"])

    def test_an_item_of_unknown_state_is_treated_as_open(self) -> None:
        """A snapshot from before the state field was fetched re-triages rather than drops."""
        plan = self.plan_with([verdict(self.key, "real-judgment")], issue_for(self.filed(
            file_issues.plan(self.findings, [verdict(self.key, file_issues.UNDETERMINED)], [], [])
        ), number=77))
        self.assertEqual([entry["issue"] for entry in plan["comment"]], [77])

    def test_the_tracker_read_fetches_state_and_comments(self) -> None:
        captured: list[list[str]] = []
        original = file_issues.gh_json
        file_issues.gh_json = lambda args: captured.append(args) or []
        try:
            file_issues.fetch_issues()
        finally:
            file_issues.gh_json = original
        fields = captured[0][captured[0].index("--json") + 1]
        self.assertEqual(set(fields.split(",")), {"number", "state", "body", "comments"})


class AnEligibleFindingAlreadyTrackedIsNotReportedUntriaged(unittest.TestCase):
    """A finding that already has an item is not filed, so it was not left untriaged."""

    def setUp(self) -> None:
        self.findings = normalised()
        self.run = full_run(self.findings)
        first = file_issues.plan(self.findings, self.run, [], [])
        self.existing = [
            issue_for(item, number=100 + index) for index, item in enumerate(first["create"])
        ]

    def test_a_run_that_triaged_nothing_files_nothing_and_reports_nothing_missing(self) -> None:
        plan = file_issues.plan(self.findings, [], self.existing, [])
        self.assertEqual(plan["create"], [])
        self.assertEqual(plan["comment"], [])
        self.assertEqual(plan["filed_without_a_verdict"], [])

    def test_every_excluded_finding_is_still_reported_against_its_item(self) -> None:
        plan = file_issues.plan(self.findings, [], self.existing, [])
        self.assertEqual(
            {entry["key"]: entry["issue"] for entry in plan["skipped_existing"]},
            {issue_body.parse(i["body"])["key"]: i["number"] for i in self.existing},
        )


if __name__ == "__main__":
    unittest.main()
