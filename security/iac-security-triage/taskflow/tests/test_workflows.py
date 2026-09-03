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

        `file-issues` needs `issues: write`, so the propose-only claim can no
        longer rest on the top-level block alone. Every job is checked.
        """
        for name, job in self.workflow["jobs"].items():
            granted = job.get("permissions", self.workflow["permissions"])
            self.assertNotIn("security-events", granted, name)


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
        """A `not-applicable` verdict files an issue; it does not dismiss."""
        self.assertEqual(self.granted(self.filer), {"contents": "read", "issues": "write"})

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
        mentions `security/iac-security-triage/` in a comment about the baseline
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


if __name__ == "__main__":
    unittest.main()
