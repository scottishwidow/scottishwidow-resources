"""The two workflows, and the boundary between them.

`design.md - Decision 11` rests on two claims that are one careless edit apart
from being false: triage is reachable only by a deliberate dispatch, and the
scan does not depend on triage. Both are properties of YAML, so both are
asserted here rather than left to a reviewer noticing.

The token argument is the reason this matters. `AI_API_TOKEN` is safe in a
public repository only because the sole workflow referencing it cannot be
triggered by a fork -- which is true only while that workflow's trigger list
stays exactly `workflow_dispatch`.
"""

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


class TriageIsDispatchOnly(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = load(TRIAGE)

    def test_workflow_dispatch_is_the_only_trigger(self) -> None:
        self.assertEqual(triggers(self.workflow), {"workflow_dispatch"})

    def test_no_event_trigger_can_reach_it(self) -> None:
        """Named explicitly, so adding one fails here and not in review."""
        for event in ("push", "pull_request", "pull_request_target", "schedule"):
            self.assertNotIn(event, triggers(self.workflow))

    def test_it_cannot_write_alert_state(self) -> None:
        """Propose-only is enforced by permissions, not only by good intent."""
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})

    def test_no_job_can_write_alert_state(self) -> None:
        """The workflow default is not the whole story once jobs widen it.

        `file-issues` needs `issues: write` and `security-events: read` --
        read, to resolve each finding's alert number, never write -- so the
        propose-only claim can no longer rest on the top-level block alone or
        on `security-events` being wholly absent. Every job is checked.
        """
        for name, job in self.workflow["jobs"].items():
            granted = job.get("permissions", self.workflow["permissions"])
            self.assertNotEqual(granted.get("security-events"), "write", name)


class IssuesAreFiledByAJobThatRunsNoModel(unittest.TestCase):
    """`design.md - Decision 4`, and the split that keeps it safe.

    A verdict travels to a human as an issue, so something in this workflow must
    hold `issues: write`. The separation asserted here is what keeps that from
    widening the model's authority: the job that runs the agent cannot open an
    issue, and the job that opens issues never sees the token.
    """

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
        """A `not-applicable` verdict files an issue; it does not dismiss.

        `security-events: read` is present -- resolving a finding's alert
        number needs it -- but there is no `write` anywhere in the grant.
        """
        self.assertEqual(
            self.granted(self.filer),
            {"contents": "read", "issues": "write", "security-events": "read"},
        )

    def test_issue_filing_waits_for_triage(self) -> None:
        self.assertEqual(self.filer["needs"], "triage")


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
    """A broken, unfunded or never-invoked triage must not stop publication."""

    def setUp(self) -> None:
        self.text = SCAN.read_text(encoding="utf-8")
        self.workflow = load(SCAN)

    def test_scan_does_not_invoke_or_chain_to_the_triage_workflow(self) -> None:
        """Every way one workflow can depend on another, checked by name.

        Not a bare substring search for the triage workflow's name: the scan
        mentions `security/iac_security/` in a comment about the baseline
        fixture, which is a path and not a dependency.
        """
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
        """The top-level block is not the whole story once a job overrides it."""
        for name, job in self.workflow["jobs"].items():
            granted = job.get("permissions", self.workflow["permissions"])
            self.assertEqual(
                granted, {"contents": "read", "security-events": "write"}, name
            )


class ScanNeedsNoCloudCredentials(unittest.TestCase):
    """Static HCL scanning reads files; it never reaches AWS.

    `proposal.md - Impact` turns on this: no OIDC role is needed by this change,
    and that holds only while the scan asks for nothing that could carry one.
    Asserted rather than inspected, because the cheapest way to debug a scanner
    is to give it credentials and the second cheapest is to notice you did.
    """

    def setUp(self) -> None:
        self.text = SCAN.read_text(encoding="utf-8")
        self.workflow = load(SCAN)

    def test_no_permission_can_mint_a_cloud_credential(self) -> None:
        """`id-token: write` is the whole OIDC handshake; without it there is none."""
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
        """Covers the static-key and assume-role spellings alike."""
        for name in (
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "role-to-assume",
        ):
            self.assertNotIn(name, self.text)

    def test_no_step_is_handed_a_secret(self) -> None:
        """Whatever a secret is called, it reaches a step through `env` or `with`."""
        for job in self.workflow["jobs"].values():
            for step in job["steps"]:
                for field in ("env", "with"):
                    supplied = yaml.safe_dump(step.get(field, {}))
                    self.assertNotIn("secrets.", supplied, step.get("name"))

    def test_the_checkout_leaves_no_token_on_disk(self) -> None:
        """The one credential a scan job gets for free, declined explicitly."""
        checkout = next(
            step for step in self.workflow["jobs"]["trivy"]["steps"]
            if "actions/checkout" in step.get("uses", "")
        )
        self.assertIs(checkout["with"]["persist-credentials"], False)


class ForkPullRequestDegradesSafely(unittest.TestCase):
    """The spec's fork scenario, as far as a file can carry it.

    A fork's `GITHUB_TOKEN` is read-only whatever the permissions block asks
    for, so the SARIF upload is rejected. What the workflow controls is what
    happens next: the scan still runs, its findings still reach the run's
    output, and the rejected upload does not fail the run. The last of those is
    one deleted line away from being false, so it is asserted and not trusted.
    """

    def setUp(self) -> None:
        self.workflow = load(SCAN)
        self.steps = self.workflow["jobs"]["trivy"]["steps"]

    def upload_steps(self) -> list[dict]:
        """Every step that publishes alert state, found by what it runs."""
        return [
            step
            for step in self.steps
            if "upload-sarif" in step.get("uses", "")
        ]

    def test_the_scan_runs_on_a_pull_request(self) -> None:
        self.assertIn("pull_request", triggers(self.workflow))

    def test_the_scan_step_does_not_fail_the_run_on_findings(self) -> None:
        """Findings reaching the output is the point; a non-zero exit hides them."""
        scan = next(step for step in self.steps if "trivy-action" in step.get("uses", ""))
        self.assertEqual(str(scan["with"]["exit-code"]), "0")

    def test_a_rejected_upload_does_not_fail_the_run(self) -> None:
        uploads = self.upload_steps()
        self.assertTrue(uploads, "no step uploads SARIF")
        for step in uploads:
            self.assertIs(step.get("continue-on-error"), True, step.get("name"))

    def test_the_upload_runs_even_after_an_earlier_failure(self) -> None:
        """`if: always()` is why a scan failure still reports what it found."""
        for step in self.upload_steps():
            self.assertEqual(step.get("if"), "always()")

    def test_uploading_is_the_only_way_the_scan_writes_alert_state(self) -> None:
        """So a fork writing nothing follows from that one step being rejected."""
        for step in self.steps:
            if step in self.upload_steps():
                continue
            self.assertNotIn("code-scanning", yaml.safe_dump(step))
            self.assertNotIn("sarifs", yaml.safe_dump(step))


if __name__ == "__main__":
    unittest.main()
