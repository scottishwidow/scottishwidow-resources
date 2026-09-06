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


def trivy_step(workflow: dict) -> dict:
    return next(
        step
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if "trivy-action" in step.get("uses", "")
    )


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
        # The trigger list cannot carry this boundary: a fork raises no `workflow_run`
        # itself, but the scan it completes ran against that fork's pull request.
        condition = self.triage["if"]
        self.assertIn("github.event.workflow_run.event == 'push'", condition)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", condition)

    def test_a_failed_scan_does_not_start_a_triage_run(self) -> None:
        self.assertIn("github.event.workflow_run.conclusion == 'success'", self.triage["if"])

    def test_it_checks_out_main_explicitly_rather_than_the_triggering_commit(self) -> None:
        checkout = next(
            step for step in self.triage["steps"]
            if "actions/checkout" in step.get("uses", "")
        )
        self.assertEqual(checkout["with"]["ref"], "main")

    def test_both_workflows_pin_the_same_trivy(self) -> None:
        pins = {path.name: trivy_step(load(path)) for path in (SCAN, TRIAGE)}
        self.assertEqual(pins[SCAN.name]["uses"], pins[TRIAGE.name]["uses"])
        self.assertEqual(
            pins[SCAN.name]["with"]["version"], pins[TRIAGE.name]["with"]["version"]
        )

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
        self.assertIn("needs.triage.result != 'skipped'", self.filer["if"])

    def test_a_failed_triage_still_files_the_verdicts_it_produced(self) -> None:
        # A condition carrying no status function has an implicit `success()`,
        # which a string comparison alone cannot displace.
        condition = self.filer["if"]
        self.assertTrue(
            any(call in condition for call in ("always()", "failure()", "!cancelled()")),
            condition,
        )

    def test_it_checks_out_main_explicitly_rather_than_the_triggering_commit(self) -> None:
        checkout = next(
            step for step in self.filer["steps"]
            if "actions/checkout" in step.get("uses", "")
        )
        self.assertEqual(checkout["with"]["ref"], "main")

    def test_the_verdicts_it_reads_are_the_only_file_the_artifact_holds(self) -> None:
        upload = next(
            step for step in self.triage["steps"]
            if "upload-artifact" in step.get("uses", "")
            and step["with"]["name"].startswith("triage-verdicts-")
        )
        self.assertTrue(upload["with"]["path"].endswith("${{ github.run_id }}.json"))
        filing = next(step for step in self.filer["steps"] if step.get("name") == "File issues")
        self.assertIn("/tmp/verdicts/${{ github.run_id }}.json", filing["run"])


class PathsCrossTheContainerBoundary(unittest.TestCase):
    """`run.sh` works in `/app`, the repository root; the host steps do not."""

    def setUp(self) -> None:
        self.triage = load(TRIAGE)["jobs"]["triage"]

    def step(self, name: str) -> dict:
        return next(step for step in self.triage["steps"] if step.get("name") == name)

    def test_the_report_the_container_reads_is_named_from_the_repository_root(self) -> None:
        self.assertIn(
            "-g report=security/iac_security/runs/trivy-report.json",
            self.step("Run triage taskflow")["run"],
        )

    def test_the_host_step_stays_relative_to_its_own_working_directory(self) -> None:
        collect = self.step("Collect verdicts")
        self.assertEqual(collect["working-directory"], "security/iac_security/taskflow")
        self.assertEqual(collect["env"]["TRIVY_REPORT"], "../runs/trivy-report.json")


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


class TriageVendorsModulesBeforeItScans(unittest.TestCase):
    """`terraform init` is what makes an upstream module recognisable as vendored.

    `normalise.py` reads ownership off the marker `.terraform/modules/`. Without
    an init, Trivy reports an upstream module at its source path, the finding is
    classified first-party, and the pipeline triages and files code this
    repository does not own.
    """

    def setUp(self) -> None:
        self.workflow = load(TRIAGE)
        self.triage = self.workflow["jobs"]["triage"]
        self.steps = self.triage["steps"]

    def init_step(self) -> dict:
        return next(step for step in self.steps if "terraform init" in step.get("run", ""))

    def index_of(self, step: dict) -> int:
        return self.steps.index(step)

    def test_the_triage_job_initialises_terraform(self) -> None:
        self.assertIn("terraform init", self.init_step()["run"])

    def test_it_initialises_the_directory_that_instantiates_vendored_modules(self) -> None:
        step = self.init_step()
        self.assertEqual(step.get("working-directory"), "live/management")

    def test_it_initialises_without_a_backend(self) -> None:
        """A backend is the only part of init that would want a cloud credential."""
        self.assertIn("-backend=false", self.init_step()["run"])

    def test_it_runs_before_the_scan_it_exists_to_inform(self) -> None:
        self.assertLess(self.index_of(self.init_step()), self.index_of(trivy_step(self.workflow)))

    def test_an_unreachable_registry_does_not_fail_the_run(self) -> None:
        """An uninitialised scan is a degraded run, not a failed one."""
        self.assertTrue(self.init_step().get("continue-on-error"))

    def test_a_run_that_vendored_nothing_says_so(self) -> None:
        """`continue-on-error` alone would hide the degradation it permits."""
        run = self.init_step()["run"]
        self.assertIn("test -d .terraform/modules", run)
        self.assertIn("::warning::", run)

    def test_the_scan_workflow_does_not_initialise_terraform(self) -> None:
        """An init there would publish a code scanning alert for every vendored finding."""
        for job in load(SCAN)["jobs"].values():
            for step in job["steps"]:
                self.assertNotIn("terraform init", step.get("run", ""))


if __name__ == "__main__":
    unittest.main()
