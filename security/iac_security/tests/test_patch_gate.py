from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import patch_gate  # noqa: E402

FINDING = {
    "key": "AWS-0086:module.bootstrap:aws_s3_bucket.terraform_state_bucket",
    "rule_id": "AWS-0086",
    "module_address": "module.bootstrap",
    "resource_address": "aws_s3_bucket.terraform_state_bucket",
    "code_path": "modules/bootstrap/main.tf",
    "owner_path": "live/management/bootstrap/main.tf",
}

PASSING_EVIDENCE = patch_gate.Evidence(applies=True, validate_passed=True, fmt_passed=True)
PASSED_REASON = f"{FINDING['key']} is removed and no new finding is introduced"


def misconfig(rule_id: str, module_address: str, resource_type: str, resource_name: str) -> dict:
    return {
        "ID": rule_id,
        "Status": "FAIL",
        "CauseMetadata": {
            "Resource": module_address,
            "Code": {
                "Lines": [
                    {"Number": 1, "Content": f'resource "{resource_type}" "{resource_name}" {{'}
                ]
            },
        },
    }


def scan(*misconfigs: dict) -> dict:
    return {"Results": [{"Target": "modules/bootstrap/main.tf", "Misconfigurations": list(misconfigs)}]}


TARGET_MISCONFIG = misconfig(
    "AWS-0086", "module.bootstrap", "aws_s3_bucket", "terraform_state_bucket"
)
OTHER_MISCONFIG = misconfig("AWS-0132", "module.bootstrap", "aws_subnet", "public_zone_1")

SCAN_BEFORE = scan(TARGET_MISCONFIG)
SCAN_AFTER_CLEAN = scan()
SCAN_AFTER_UNCHANGED = scan(TARGET_MISCONFIG)
SCAN_AFTER_NEW_FINDING = scan(OTHER_MISCONFIG)


def diff_for(path: str, *, new: bool = False, deleted: bool = False) -> str:
    header = f"diff --git a/{path} b/{path}\n"
    if new:
        return (
            header
            + "new file mode 100644\n"
            + "--- /dev/null\n"
            + f"+++ b/{path}\n"
            + "@@ -0,0 +1,1 @@\n"
            + "+resource_content\n"
        )
    if deleted:
        return (
            header
            + "deleted file mode 100644\n"
            + f"--- a/{path}\n"
            + "+++ /dev/null\n"
            + "@@ -1,1 +0,0 @@\n"
            + "-old\n"
        )
    return (
        header
        + f"--- a/{path}\n"
        + f"+++ b/{path}\n"
        + "@@ -1,1 +1,1 @@\n"
        + "-old\n"
        + "+new\n"
    )


# Git quotes a path holding a non-ASCII byte and escapes the byte in octal.
QUOTED_HEADER = r'diff --git "a/modules/bootstrap/pol\303\255tica.tf" "b/modules/bootstrap/pol\303\255tica.tf"'
QUOTED_PATH_DIFF = (
    QUOTED_HEADER + "\n"
    + "--- a/modules/bootstrap/pol\\303\\255tica.tf\n"
    + "+++ b/modules/bootstrap/pol\\303\\255tica.tf\n"
    + "@@ -1,1 +1,1 @@\n"
    + "-old\n"
    + "+new\n"
)


def rename_diff(old_path: str, new_path: str) -> str:
    return (
        f"diff --git a/{old_path} b/{new_path}\n"
        + "similarity index 100%\n"
        + f"rename from {old_path}\n"
        + f"rename to {new_path}\n"
    )


class CleanPatch(unittest.TestCase):
    def test_removes_its_target_and_introduces_nothing(self) -> None:
        decision = patch_gate.decide(
            diff_for(FINDING["code_path"]),
            FINDING,
            SCAN_BEFORE,
            SCAN_AFTER_CLEAN,
            PASSING_EVIDENCE,
        )
        self.assertTrue(decision.passed)
        self.assertEqual(decision.gate, patch_gate.PASSED)
        self.assertEqual(decision.reason, PASSED_REASON)


class PermittedPaths(unittest.TestCase):
    def test_an_unrelated_path_is_rejected(self) -> None:
        decision = patch_gate.decide(
            diff_for("live/gitlab/network/main.tf"),
            FINDING,
            SCAN_BEFORE,
            SCAN_AFTER_CLEAN,
            PASSING_EVIDENCE,
        )
        self.assertFalse(decision.passed)
        self.assertEqual(decision.gate, patch_gate.PERMITTED_PATHS)
        self.assertEqual(
            decision.reason,
            f"`live/gitlab/network/main.tf` is outside the permitted set for {FINDING['key']}",
        )

    def test_an_existing_sibling_of_the_code_path_is_rejected(self) -> None:
        # The module directory is too loose to be "the finding named it", so only a *new* file there is permitted.
        decision = patch_gate.decide(
            diff_for("modules/bootstrap/outputs.tf"),
            FINDING,
            SCAN_BEFORE,
            SCAN_AFTER_CLEAN,
            PASSING_EVIDENCE,
        )
        self.assertFalse(decision.passed)
        self.assertEqual(decision.gate, patch_gate.PERMITTED_PATHS)
        self.assertEqual(
            decision.reason,
            f"`modules/bootstrap/outputs.tf` is outside the permitted set for {FINDING['key']}",
        )

    def test_the_owner_path_is_permitted(self) -> None:
        decision = patch_gate.decide(
            diff_for(FINDING["owner_path"]),
            FINDING,
            SCAN_BEFORE,
            SCAN_AFTER_CLEAN,
            PASSING_EVIDENCE,
        )
        self.assertTrue(decision.passed)
        self.assertEqual(decision.gate, patch_gate.PASSED)
        self.assertEqual(decision.reason, PASSED_REASON)

    def test_a_new_file_beside_the_code_path_is_permitted(self) -> None:
        # The AWS-0132 shape: the fix adds a variable to `modules/` and threads it from `live/`.
        decision = patch_gate.decide(
            diff_for(FINDING["code_path"]) + diff_for("modules/bootstrap/variables.tf", new=True),
            FINDING,
            SCAN_BEFORE,
            SCAN_AFTER_CLEAN,
            PASSING_EVIDENCE,
        )
        self.assertTrue(decision.passed)
        self.assertEqual(decision.gate, patch_gate.PASSED)
        self.assertEqual(decision.reason, PASSED_REASON)

    def test_deleting_the_code_path_is_rejected(self) -> None:
        decision = patch_gate.decide(
            diff_for(FINDING["code_path"], deleted=True),
            FINDING,
            SCAN_BEFORE,
            SCAN_AFTER_CLEAN,
            PASSING_EVIDENCE,
        )
        self.assertFalse(decision.passed)
        self.assertEqual(decision.gate, patch_gate.PERMITTED_PATHS)
        self.assertEqual(
            decision.reason,
            f"`{FINDING['code_path']}` is deleted, which no remediation permits",
        )


class DoesNotApply(unittest.TestCase):
    def test_a_patch_that_does_not_apply_is_rejected(self) -> None:
        decision = patch_gate.decide(
            diff_for(FINDING["code_path"]),
            FINDING,
            SCAN_BEFORE,
            SCAN_AFTER_CLEAN,
            patch_gate.Evidence(applies=False, validate_passed=True, fmt_passed=True),
        )
        self.assertFalse(decision.passed)
        self.assertEqual(decision.gate, patch_gate.APPLY)
        self.assertEqual(decision.reason, "the diff does not apply cleanly")

    def test_a_patch_that_changes_nothing_is_rejected(self) -> None:
        decision = patch_gate.decide(
            "",
            FINDING,
            SCAN_BEFORE,
            SCAN_AFTER_CLEAN,
            PASSING_EVIDENCE,
        )
        self.assertFalse(decision.passed)
        self.assertEqual(decision.gate, patch_gate.APPLY)
        self.assertEqual(decision.reason, "the diff changes nothing")


class TerraformOutcomes(unittest.TestCase):
    def test_a_patch_leaving_validate_failing_is_rejected(self) -> None:
        decision = patch_gate.decide(
            diff_for(FINDING["code_path"]),
            FINDING,
            SCAN_BEFORE,
            SCAN_AFTER_CLEAN,
            patch_gate.Evidence(applies=True, validate_passed=False, fmt_passed=True),
        )
        self.assertFalse(decision.passed)
        self.assertEqual(decision.gate, patch_gate.TERRAFORM_VALIDATE)
        self.assertEqual(decision.reason, "terraform validate fails after the patch")

    def test_a_patch_leaving_fmt_failing_is_rejected(self) -> None:
        decision = patch_gate.decide(
            diff_for(FINDING["code_path"]),
            FINDING,
            SCAN_BEFORE,
            SCAN_AFTER_CLEAN,
            patch_gate.Evidence(applies=True, validate_passed=True, fmt_passed=False),
        )
        self.assertFalse(decision.passed)
        self.assertEqual(decision.gate, patch_gate.TERRAFORM_FMT)
        self.assertEqual(decision.reason, "terraform fmt -check fails after the patch")


class ScanComparison(unittest.TestCase):
    def test_a_patch_leaving_its_target_present_is_rejected(self) -> None:
        decision = patch_gate.decide(
            diff_for(FINDING["code_path"]),
            FINDING,
            SCAN_BEFORE,
            SCAN_AFTER_UNCHANGED,
            PASSING_EVIDENCE,
        )
        self.assertFalse(decision.passed)
        self.assertEqual(decision.gate, patch_gate.TARGET_REMOVAL)
        self.assertEqual(decision.reason, f"{FINDING['key']} is still present after the patch")

    def test_a_patch_that_introduces_a_new_finding_is_rejected(self) -> None:
        decision = patch_gate.decide(
            diff_for(FINDING["code_path"]),
            FINDING,
            SCAN_BEFORE,
            SCAN_AFTER_NEW_FINDING,
            PASSING_EVIDENCE,
        )
        self.assertFalse(decision.passed)
        self.assertEqual(decision.gate, patch_gate.NEW_FINDINGS)
        self.assertEqual(
            decision.reason,
            f"the patch introduces a new finding: {OTHER_MISCONFIG['ID']}:module.bootstrap:aws_subnet.public_zone_1",
        )


class UnreadablePaths(unittest.TestCase):
    """A header the gate cannot read a path from must fail, not be skipped.

    Skipping it let the path past the permitted-paths check entirely, and the
    apply gate does not catch it either — such a diff applies cleanly.
    """

    def test_a_quoted_path_is_rejected(self) -> None:
        decision = patch_gate.decide(
            QUOTED_PATH_DIFF,
            FINDING,
            SCAN_BEFORE,
            SCAN_AFTER_CLEAN,
            PASSING_EVIDENCE,
        )
        self.assertFalse(decision.passed)
        self.assertEqual(decision.gate, patch_gate.PERMITTED_PATHS)
        self.assertEqual(
            decision.reason, f"`{QUOTED_HEADER}` names no path this gate can read"
        )

    def test_a_quoted_path_beside_a_permitted_one_is_rejected(self) -> None:
        decision = patch_gate.decide(
            diff_for(FINDING["code_path"]) + QUOTED_PATH_DIFF,
            FINDING,
            SCAN_BEFORE,
            SCAN_AFTER_CLEAN,
            PASSING_EVIDENCE,
        )
        self.assertFalse(decision.passed)
        self.assertEqual(decision.gate, patch_gate.PERMITTED_PATHS)


class Renames(unittest.TestCase):
    """A rename removes the old path while naming neither a deletion nor a new file."""

    def test_renaming_the_code_path_onto_the_owner_path_is_rejected(self) -> None:
        decision = patch_gate.decide(
            rename_diff(FINDING["code_path"], FINDING["owner_path"]),
            FINDING,
            SCAN_BEFORE,
            SCAN_AFTER_CLEAN,
            PASSING_EVIDENCE,
        )
        self.assertFalse(decision.passed)
        self.assertEqual(decision.gate, patch_gate.PERMITTED_PATHS)
        self.assertEqual(
            decision.reason,
            f"`{FINDING['code_path']}` is renamed away, which no remediation permits",
        )


class TheCommandLineTheWorkflowCalls(unittest.TestCase):
    """The workflow does the I/O; this is where it hands the outcomes over."""

    def setUp(self) -> None:
        self.scratch = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.scratch)

    def write(self, name: str, content: str | dict) -> str:
        path = self.scratch / name
        path.write_text(
            content if isinstance(content, str) else json.dumps(content), encoding="utf-8"
        )
        return str(path)

    def run_gate(self, *, diff: str, post_scan: dict | None, **observed: bool) -> dict:
        evidence = {"applies": True, "validate_passed": True, "fmt_passed": True} | observed
        argv = [
            "--diff", self.write("patch.diff", diff),
            "--target", self.write("target.json", {"finding": FINDING}),
            "--pre-scan", self.write("pre.json", SCAN_BEFORE),
            "--evidence", self.write("evidence.json", evidence),
            "-o", str(self.scratch / "decision.json"),
        ]
        if post_scan is not None:
            argv += ["--post-scan", self.write("post.json", post_scan)]
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(patch_gate.main(argv), 0)
        return json.loads((self.scratch / "decision.json").read_text(encoding="utf-8"))

    def test_it_writes_the_decision_the_workflow_reads_back(self) -> None:
        decision = self.run_gate(
            diff=diff_for(FINDING["code_path"]), post_scan=SCAN_AFTER_CLEAN
        )
        self.assertEqual(decision, {"passed": True, "gate": patch_gate.PASSED, "reason": PASSED_REASON})

    def test_it_names_the_gate_a_rejected_patch_failed(self) -> None:
        decision = self.run_gate(
            diff=diff_for(FINDING["code_path"]),
            post_scan=SCAN_AFTER_UNCHANGED,
        )
        self.assertFalse(decision["passed"])
        self.assertEqual(decision["gate"], patch_gate.TARGET_REMOVAL)

    def test_a_diff_that_did_not_apply_needs_no_post_scan(self) -> None:
        """The workflow runs nothing after a failed apply, so there is none to hand over."""
        decision = self.run_gate(
            diff=diff_for(FINDING["code_path"]), post_scan=None, applies=False
        )
        self.assertFalse(decision["passed"])
        self.assertEqual(decision["gate"], patch_gate.APPLY)


if __name__ == "__main__":
    unittest.main()
