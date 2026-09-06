from __future__ import annotations

import pathlib
import sys
import unittest

import yaml

HERE = pathlib.Path(__file__).resolve().parent
TRIAGE_DIR = HERE.parents[1]
REPO_ROOT = HERE.parents[3]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
SCAN = WORKFLOWS / "iac-security-scan.yml"
TRIAGE = WORKFLOWS / "iac-security-triage.yml"
REMEDIATE = WORKFLOWS / "iac-security-remediate.yml"

sys.path.insert(0, str(TRIAGE_DIR))

import file_issues  # noqa: E402

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

    def on(self) -> dict:
        return self.workflow[ON] if ON in self.workflow else self.workflow["on"]

    def test_it_triggers_on_the_scan_workflow_completing(self) -> None:
        self.assertEqual(triggers(self.workflow), {"workflow_run", "workflow_dispatch"})
        self.assertEqual(self.on()["workflow_run"]["workflows"], ["IaC security scan"])
        self.assertIn("completed", self.on()["workflow_run"]["types"])

    def test_a_dispatch_can_reach_the_job(self) -> None:
        """The manual path is what re-triages a finding the tracker already holds."""
        self.assertIn("github.event_name == 'workflow_dispatch'", self.triage["if"])

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

    def test_every_workflow_that_scans_pins_the_same_trivy(self) -> None:
        """A patch is judged against the scanner that raised the finding, or it is judged against nothing."""
        pins = {path.name: trivy_step(load(path)) for path in (SCAN, TRIAGE, REMEDIATE)}
        for name, step in pins.items():
            self.assertEqual(step["uses"], pins[SCAN.name]["uses"], name)
            self.assertEqual(
                step["with"]["version"], pins[SCAN.name]["with"]["version"], name
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
        """It reads the tracker to decide what to triage, and may do no more than read it."""
        self.assertEqual(self.granted(self.triage).get("issues"), "read")

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


class TokenIsConfinedToTheWorkflowsThatRunAModel(unittest.TestCase):
    def test_no_other_workflow_references_the_token(self) -> None:
        referencing = [
            path.name
            for path in sorted(WORKFLOWS.glob("*.yml"))
            if TOKEN in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(referencing, sorted([REMEDIATE.name, TRIAGE.name]))

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


class ATrackerItemIsNotTriagedTwice(unittest.TestCase):
    """Triage costs nothing when nothing changed.

    The exclusion needs the tracker, and the tracker is read on the host: the
    published image carries neither `gh` nor a token, and the taskflow reaches no
    network of its own.
    """

    def setUp(self) -> None:
        self.workflow = load(TRIAGE)
        self.triage = self.workflow["jobs"]["triage"]
        self.steps = self.triage["steps"]

    def step(self, name: str) -> dict:
        return next(step for step in self.steps if step.get("name") == name)

    def index_of(self, name: str) -> int:
        return self.steps.index(self.step(name))

    def test_the_tracker_is_read_before_the_taskflow_that_excludes_on_it(self) -> None:
        self.assertLess(self.index_of("Read the tracker"), self.index_of("Run triage taskflow"))

    def test_the_snapshot_carries_what_the_exclusion_reads(self) -> None:
        """State says whether an item is closed; comments say whether it has since been judged."""
        run = self.step("Read the tracker")["run"]
        self.assertIn("--state all", run)
        for field in ("number", "state", "body", "comments"):
            self.assertIn(field, run)

    def test_the_snapshot_is_named_to_the_container_from_the_repository_root(self) -> None:
        self.assertIn(
            "-g tracker=security/iac_security/runs/tracker.json",
            self.step("Run triage taskflow")["run"],
        )

    def test_the_step_reading_the_tracker_never_sees_the_model_token(self) -> None:
        self.assertNotIn(TOKEN, yaml.safe_dump(self.step("Read the tracker")))

    def test_the_step_running_the_model_never_sees_the_tracker_token(self) -> None:
        self.assertNotIn("GH_TOKEN", yaml.safe_dump(self.step("Run triage taskflow")))


class ADispatchedRunIsDeliberate(unittest.TestCase):
    """Two inputs, both defaulting to the cautious answer.

    The bypass exists only on the dispatch path, and filing is off by default so
    testing verdicts costs tokens and artifacts but no tracker churn.
    """

    def setUp(self) -> None:
        self.workflow = load(TRIAGE)
        on = self.workflow[ON] if ON in self.workflow else self.workflow["on"]
        self.inputs = on["workflow_dispatch"]["inputs"]
        self.triage = self.workflow["jobs"]["triage"]
        self.filer = self.workflow["jobs"]["file-issues"]

    def step(self, job: dict, name: str) -> dict:
        return next(step for step in job["steps"] if step.get("name") == name)

    def test_both_inputs_default_to_off(self) -> None:
        for name in ("retriage_tracked", "file_issues"):
            self.assertIs(self.inputs[name]["default"], False, name)
            self.assertEqual(self.inputs[name]["type"], "boolean", name)

    def test_the_bypass_never_fires_on_the_automatic_path(self) -> None:
        supplied = self.step(self.triage, "Run triage taskflow")["env"]["BYPASS"]
        self.assertIn("github.event_name == 'workflow_dispatch'", supplied)
        self.assertIn("inputs.retriage_tracked", supplied)

    def test_the_bypass_reaches_the_taskflow_as_a_global(self) -> None:
        self.assertIn("-g bypass=", self.step(self.triage, "Run triage taskflow")["run"])

    def test_a_dispatched_run_files_nothing_unless_asked(self) -> None:
        filing = self.step(self.filer, "File issues")
        self.assertIn("github.event_name == 'workflow_dispatch'", filing["env"]["DRY_RUN"])
        self.assertIn("inputs.file_issues != true", filing["env"]["DRY_RUN"])
        self.assertIn("--dry-run", filing["run"])

    def test_a_run_off_the_scan_still_files(self) -> None:
        """`DRY_RUN` is false on the automatic path, and the flag is passed only when it is true."""
        run = self.step(self.filer, "File issues")["run"]
        self.assertIn('if [ "$DRY_RUN" = \'true\' ]; then', run)


class RemediationIsInvokedByALabel(unittest.TestCase):
    """A human reads the tracker item and asks for a patch; nothing else starts a run."""

    def setUp(self) -> None:
        self.workflow = load(REMEDIATE)
        self.target = self.workflow["jobs"]["target"]
        self.remediate = self.workflow["jobs"]["remediate"]

    def on(self) -> dict:
        return self.workflow[ON] if ON in self.workflow else self.workflow["on"]

    def test_it_triggers_on_an_issue_being_labelled(self) -> None:
        self.assertEqual(triggers(self.workflow), {"issues"})
        self.assertEqual(self.on()["issues"]["types"], ["labeled"])

    def test_the_trigger_is_filtered_to_the_dedicated_label(self) -> None:
        self.assertIn(
            f"github.event.label.name == '{file_issues.READY_FOR_REMEDIATION}'",
            self.target["if"],
        )

    def test_the_repository_wide_afk_label_starts_no_run(self) -> None:
        """`ready-for-agent` is carried by issues that hold no finding at all.

        Asserted against what runs rather than against the file, which names the
        label in a comment saying why it is not the trigger.
        """
        self.assertNotIn("ready-for-agent", yaml.safe_dump(self.on()))
        for name, job in self.workflow["jobs"].items():
            self.assertNotIn("ready-for-agent", job.get("if", ""), name)

    def test_the_pipeline_cannot_apply_the_label_that_triggers_it(self) -> None:
        self.assertNotIn(file_issues.READY_FOR_REMEDIATION, file_issues.EMITTABLE_LABELS)
        with self.assertRaises(file_issues.ForbiddenLabel):
            file_issues.check_labels((file_issues.READY_FOR_REMEDIATION,))

    def test_two_issues_labelled_at_once_are_remediated_independently(self) -> None:
        concurrency = self.workflow["concurrency"]
        self.assertIn("github.event.issue.number", concurrency["group"])
        self.assertIs(concurrency["cancel-in-progress"], False)

    def test_both_jobs_check_out_main_rather_than_whatever_the_issue_says(self) -> None:
        for name, job in self.workflow["jobs"].items():
            checkout = next(
                step for step in job["steps"] if "actions/checkout" in step.get("uses", "")
            )
            self.assertEqual(checkout["with"]["ref"], "main", name)
            self.assertIs(checkout["with"]["persist-credentials"], False, name)


class AMislabelledIssueCostsNothing(unittest.TestCase):
    """The first job is deterministic, holds no token, and exits unless the body yields a finding key."""

    def setUp(self) -> None:
        self.workflow = load(REMEDIATE)
        self.target = self.workflow["jobs"]["target"]
        self.remediate = self.workflow["jobs"]["remediate"]

    def step(self, job: dict, name: str) -> dict:
        return next(step for step in job["steps"] if step.get("name") == name)

    def test_it_holds_no_token_of_either_kind(self) -> None:
        rendered = yaml.safe_dump(self.target)
        self.assertNotIn(TOKEN, rendered)
        self.assertNotIn("secrets.", rendered)
        self.assertNotIn("GH_TOKEN", rendered)

    def test_it_runs_no_model_and_no_scanner(self) -> None:
        for step in self.target["steps"]:
            rendered = yaml.safe_dump(step)
            self.assertNotIn("trivy", rendered)
            self.assertNotIn("run.sh", rendered)

    def test_it_reads_the_key_off_the_body_the_event_carried(self) -> None:
        """The payload rather than the API: reading the issue back would need a token."""
        step = self.step(self.target, "Read the finding key")
        self.assertEqual(step["env"]["ISSUE_BODY"], "${{ github.event.issue.body }}")
        self.assertIn("--key-only", step["run"])

    def test_the_body_is_never_interpolated_into_the_script(self) -> None:
        """An issue body is written by whoever opened the issue."""
        self.assertNotIn(
            "github.event.issue.body", self.step(self.target, "Read the finding key")["run"]
        )

    def test_the_job_that_costs_money_runs_only_when_a_key_was_found(self) -> None:
        self.assertEqual(self.remediate["needs"], "target")
        self.assertIn("needs.target.outputs.key != ''", self.remediate["if"])

    def test_the_key_is_what_the_first_job_hands_the_second(self) -> None:
        self.assertIn("steps.finding.outputs.key", self.target["outputs"]["key"])


class TheRemediatorHoldsNoWritePermission(unittest.TestCase):
    """The job running the model holds the token, so it holds nothing else."""

    def setUp(self) -> None:
        self.workflow = load(REMEDIATE)
        self.remediate = self.workflow["jobs"]["remediate"]

    def granted(self, job: dict) -> dict:
        return job.get("permissions", self.workflow["permissions"])

    def step(self, name: str) -> dict:
        return next(step for step in self.remediate["steps"] if step.get("name") == name)

    def test_the_workflow_grants_nothing_but_read(self) -> None:
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})

    def test_no_job_holds_a_write_permission_of_any_kind(self) -> None:
        for name, job in self.workflow["jobs"].items():
            for scope, level in self.granted(job).items():
                self.assertNotEqual(level, "write", f"{name}: {scope}")

    def test_the_job_running_the_model_may_read_the_issue_and_no_more(self) -> None:
        self.assertEqual(self.granted(self.remediate), {"contents": "read", "issues": "read"})

    def test_the_step_reading_the_issue_never_sees_the_model_token(self) -> None:
        self.assertNotIn(TOKEN, yaml.safe_dump(self.step("Read the tracker item")))

    def test_the_step_running_the_model_never_sees_the_tracker_token(self) -> None:
        self.assertNotIn("GH_TOKEN", yaml.safe_dump(self.step("Run remediation taskflow")))

    def test_the_patch_leaves_as_an_artifact_rather_than_as_a_commit(self) -> None:
        upload = next(
            step for step in self.remediate["steps"]
            if "upload-artifact" in step.get("uses", "")
        )
        self.assertTrue(upload["with"]["path"].endswith("${{ github.run_id }}.patch"))


class RemediationPathsCrossTheContainerBoundary(unittest.TestCase):
    """`run.sh` works in `/app`, the repository root; the host steps do not."""

    def setUp(self) -> None:
        self.remediate = load(REMEDIATE)["jobs"]["remediate"]

    def step(self, name: str) -> dict:
        return next(step for step in self.remediate["steps"] if step.get("name") == name)

    def index_of(self, name: str) -> int:
        return self.remediate["steps"].index(self.step(name))

    def test_the_taskflow_it_runs_is_the_remediation_one(self) -> None:
        self.assertEqual(
            self.step("Run remediation taskflow")["env"]["TASKFLOW"],
            "security.iac_security.taskflow.taskflows.iac_remediate",
        )

    def test_the_files_the_container_reads_are_named_from_the_repository_root(self) -> None:
        run = self.step("Run remediation taskflow")["run"]
        self.assertIn("-g report=security/iac_security/runs/trivy-report.json", run)
        self.assertIn("-g issue=security/iac_security/runs/issue.json", run)

    def test_the_issue_is_read_before_the_taskflow_that_patches_it(self) -> None:
        self.assertLess(
            self.index_of("Read the tracker item"), self.index_of("Run remediation taskflow")
        )

    def test_the_snapshot_carries_the_body_and_the_comments(self) -> None:
        """A human's comment on the item is one of the remediator's inputs."""
        run = self.step("Read the tracker item")["run"]
        for field in ("number", "body", "comments"):
            self.assertIn(field, run)

    def test_the_host_step_collecting_the_patch_stays_relative_to_its_own_directory(self) -> None:
        collect = self.step("Collect the patch")
        self.assertEqual(collect["working-directory"], "security/iac_security/taskflow")
        self.assertIn("collect_patch.py", collect["run"])


class RemediationVendorsModulesBeforeItScans(unittest.TestCase):
    """The same reason as in triage: without an init, an upstream module reads as first-party.

    A remediation run scans to find the finding it was labelled for, so a
    vendored finding that reads as first-party here would be patched in code
    this repository does not own.
    """

    def setUp(self) -> None:
        self.steps = load(REMEDIATE)["jobs"]["remediate"]["steps"]

    def init_step(self) -> dict:
        return next(step for step in self.steps if "terraform init" in step.get("run", ""))

    def test_it_initialises_the_directory_that_instantiates_vendored_modules(self) -> None:
        self.assertEqual(self.init_step().get("working-directory"), "live/management")

    def test_it_initialises_without_a_backend(self) -> None:
        self.assertIn("-backend=false", self.init_step()["run"])

    def test_it_runs_before_the_scan_it_exists_to_inform(self) -> None:
        self.assertLess(
            self.steps.index(self.init_step()),
            self.steps.index(trivy_step(load(REMEDIATE))),
        )

    def test_an_unreachable_registry_does_not_fail_the_run(self) -> None:
        self.assertTrue(self.init_step().get("continue-on-error"))
