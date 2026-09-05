from __future__ import annotations

import pathlib
import unittest

import yaml

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[3]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
SCAN = WORKFLOWS / "iac-security-scan.yml"
TRIAGE = WORKFLOWS / "iac-security-triage.yml"

TOKEN = "AI_API_TOKEN"
# `on` is YAML 1.1's boolean true, which is what safe_load makes of the key.
ON = True


def load(path: pathlib.Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def triggers(workflow: dict) -> set[str]:
    on = workflow[ON] if ON in workflow else workflow["on"]
    if isinstance(on, str):
        return {on}
    return set(on)


class TriageFiresOffTheScan(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = load(TRIAGE)
        self.triage = self.workflow["jobs"]["triage"]

    def test_it_triggers_on_the_scan_workflow_completing(self) -> None:
        self.assertEqual(triggers(self.workflow), {"workflow_run"})
        on = self.workflow[ON] if ON in self.workflow else self.workflow["on"]
        self.assertEqual(on["workflow_run"]["workflows"], ["IaC security scan"])
        self.assertIn("completed", on["workflow_run"]["types"])

    def test_no_pull_request_from_a_fork_can_reach_the_job(self) -> None:
        # A trigger-list check alone cannot see this: `workflow_run` is not one
        # of the events a fork can raise directly, but its completion fires for
        # every pull request the scan workflow runs against, forks included.
        # The boundary is this job condition, so that is what must be asserted
        # -- a workflow missing it would pass a check that only inspected `on:`.
        condition = self.triage["if"]
        self.assertIn("github.event.workflow_run.event == 'push'", condition)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", condition)

    def test_it_checks_out_main_explicitly_rather_than_the_triggering_commit(self) -> None:
        checkout = next(
            step for step in self.triage["steps"]
            if "actions/checkout" in step.get("uses", "")
        )
        self.assertEqual(checkout["with"]["ref"], "main")

    def test_it_cannot_write_alert_state(self) -> None:
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})

    def test_no_job_can_write_alert_state(self) -> None:
        for name, job in self.workflow["jobs"].items():
            granted = job.get("permissions", self.workflow["permissions"])
            self.assertNotEqual(granted.get("security-events"), "write", name)


class IssuesAreFiledByAJobThatRunsNoModel(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = load(TRIAGE)
        self.triage = self.workflow["jobs"]["triage"]
        self.filer = self.workflow["jobs"]["file-issues"]

    def granted(self, job: dict) -> dict:
        return job.get("permissions", self.workflow["permissions"])

    def test_the_job_running_the_model_cannot_open_an_issue(self) -> None:
        self.assertNotIn("issues", self.granted(self.triage))

    def test_the_job_opening_issues_never_sees_the_token(self) -> None:
        self.assertNotIn(TOKEN, yaml.safe_dump(self.filer))

    def test_the_job_opening_issues_cannot_write_alert_state(self) -> None:
        self.assertEqual(
            self.granted(self.filer),
            {"contents": "read", "issues": "write", "security-events": "read"},
        )

    def test_issue_filing_waits_for_triage(self) -> None:
        self.assertEqual(self.filer["needs"], "triage")

    def test_issue_filing_does_not_run_when_triage_was_skipped(self) -> None:
        self.assertEqual(self.filer["if"], "needs.triage.result != 'skipped'")


class TokenIsConfinedToTriage(unittest.TestCase):
    def test_only_the_triage_workflow_references_the_token(self) -> None:
        referencing = [
            path.name
            for path in sorted(WORKFLOWS.glob("*.yml"))
            if TOKEN in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(referencing, [TRIAGE.name])

    def test_the_scan_workflow_uses_no_secret(self) -> None:
        self.assertNotIn("secrets.", SCAN.read_text(encoding="utf-8"))


class ScanDoesNotDependOnTriage(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SCAN.read_text(encoding="utf-8")
        self.workflow = load(SCAN)

    def test_scan_does_not_invoke_or_chain_to_the_triage_workflow(self) -> None:
        self.assertNotIn(TRIAGE.name, self.text)
        self.assertNotIn("workflow_call", self.text)
        self.assertNotIn("workflow_run", self.text)
        self.assertNotIn("workflow-dispatch", self.text)
        self.assertNotIn("gh workflow run", self.text)

    def test_scan_still_runs_on_code_changes(self) -> None:
        self.assertEqual(triggers(self.workflow), {"pull_request", "push"})

    def test_scan_needs_no_job_from_triage(self) -> None:
        for job in self.workflow["jobs"].values():
            self.assertNotIn("needs", job)

    def test_scan_publishes_with_only_the_permission_it_needs(self) -> None:
        self.assertEqual(
            self.workflow["permissions"],
            {"contents": "read", "security-events": "write"},
        )

    def test_no_job_widens_the_scan_beyond_that(self) -> None:
        for name, job in self.workflow["jobs"].items():
            granted = job.get("permissions", self.workflow["permissions"])
            self.assertEqual(
                granted, {"contents": "read", "security-events": "write"}, name
            )


class ScanNeedsNoCloudCredentials(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SCAN.read_text(encoding="utf-8")
        self.workflow = load(SCAN)

    def test_no_permission_can_mint_a_cloud_credential(self) -> None:
        self.assertNotIn("id-token", self.workflow["permissions"])
        for name, job in self.workflow["jobs"].items():
            self.assertNotIn("id-token", job.get("permissions", {}), name)

    def test_no_cloud_credential_action_is_used(self) -> None:
        for action in (
            "aws-actions/configure-aws-credentials",
            "google-github-actions/auth",
            "azure/login",
        ):
            self.assertNotIn(action, self.text)

    def test_no_credential_is_passed_by_name(self) -> None:
        for name in (
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "role-to-assume",
        ):
            self.assertNotIn(name, self.text)

    def test_no_step_is_handed_a_secret(self) -> None:
        for job in self.workflow["jobs"].values():
            for step in job["steps"]:
                for field in ("env", "with"):
                    supplied = yaml.safe_dump(step.get(field, {}))
                    self.assertNotIn("secrets.", supplied, step.get("name"))

    def test_the_checkout_leaves_no_token_on_disk(self) -> None:
        checkout = next(
            step for step in self.workflow["jobs"]["trivy"]["steps"]
            if "actions/checkout" in step.get("uses", "")
        )
        self.assertIs(checkout["with"]["persist-credentials"], False)


class ForkPullRequestDegradesSafely(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = load(SCAN)
        self.steps = self.workflow["jobs"]["trivy"]["steps"]

    def upload_steps(self) -> list[dict]:
        return [
            step
            for step in self.steps
            if "upload-sarif" in step.get("uses", "")
        ]

    def test_the_scan_runs_on_a_pull_request(self) -> None:
        self.assertIn("pull_request", triggers(self.workflow))

    def test_the_scan_step_does_not_fail_the_run_on_findings(self) -> None:
        scan = next(step for step in self.steps if "trivy-action" in step.get("uses", ""))
        self.assertEqual(str(scan["with"]["exit-code"]), "0")

    def test_a_rejected_upload_does_not_fail_the_run(self) -> None:
        uploads = self.upload_steps()
        self.assertTrue(uploads, "no step uploads SARIF")
        for step in uploads:
            self.assertIs(step.get("continue-on-error"), True, step.get("name"))

    def test_the_upload_runs_even_after_an_earlier_failure(self) -> None:
        for step in self.upload_steps():
            self.assertEqual(step.get("if"), "always()")

    def test_uploading_is_the_only_way_the_scan_writes_alert_state(self) -> None:
        for step in self.steps:
            if step in self.upload_steps():
                continue
            self.assertNotIn("code-scanning", yaml.safe_dump(step))
            self.assertNotIn("sarifs", yaml.safe_dump(step))


if __name__ == "__main__":
    unittest.main()
