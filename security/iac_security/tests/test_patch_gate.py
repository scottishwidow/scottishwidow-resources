from __future__ import annotations

import sys
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


if __name__ == "__main__":
    unittest.main()
