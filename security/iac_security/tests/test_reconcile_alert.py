from __future__ import annotations

import io
import json
import pathlib
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = pathlib.Path(__file__).resolve().parent
TRIAGE_DIR = HERE.parent

sys.path.insert(0, str(TRIAGE_DIR))

import reconcile_alert  # noqa: E402

KEY = "AWS-0164:module.vpc:aws_subnet.public_zone_1"
URL = "https://example.invalid/issues/41"


def body(key: str = KEY, alert: int | None = 12) -> str:
    rows = f"| **Key** | `{key}` |\n"
    if alert is not None:
        rows += f"| **Alert** | [#{alert}](https://example.invalid/alerts/{alert}) |\n"
    return (
        "## Finding\n\n| | |\n|---|---|\n"
        f"{rows}\n"
        "## Verdict\n\n`not-applicable`\n\n"
        "## Rationale\n\nThe bucket holds no data that survives a run.\n"
    )


def issue(
    labels: list | None = None,
    state_reason: str = "not_planned",
    text: str | None = None,
) -> dict:
    return {
        "number": 41,
        "html_url": URL,
        "state": "CLOSED",
        "state_reason": state_reason,
        "labels": [{"name": name} for name in labels or ["wontfix"]],
        "body": body() if text is None else text,
    }


class FakeAlerts:
    """The code scanning API as this module uses it, and nothing more."""

    def __init__(self) -> None:
        self.dismissed: list[dict] = []

    def dismiss(self, alert: int, reason: str, comment: str) -> None:
        self.dismissed.append({"alert": alert, "reason": reason, "comment": comment})


class AWontfixCloseDismissesTheAlert(unittest.TestCase):
    def setUp(self) -> None:
        self.alerts = FakeAlerts()

    def test_it_dismisses_the_alert_the_body_names(self) -> None:
        taken = reconcile_alert.reconcile(issue(), self.alerts)
        self.assertTrue(taken["dismiss"])
        self.assertEqual(taken["alert"], 12)
        self.assertEqual([call["alert"] for call in self.alerts.dismissed], [12])

    def test_the_comment_is_the_issue_url_and_the_reason_is_wont_fix(self) -> None:
        reconcile_alert.reconcile(issue(), self.alerts)
        self.assertEqual(self.alerts.dismissed[0]["comment"], URL)
        self.assertEqual(self.alerts.dismissed[0]["reason"], "won't fix")

    def test_the_label_is_read_whichever_shape_it_arrives_in(self) -> None:
        """A webhook renders a label as an object; a `gh` snapshot renders it as a string."""
        item = issue()
        item["labels"] = ["needs-triage", "wontfix"]
        self.assertTrue(reconcile_alert.reconcile(item, self.alerts)["dismiss"])

    def test_a_dry_run_decides_and_dismisses_nothing(self) -> None:
        taken = reconcile_alert.reconcile(issue(), self.alerts, dry_run=True)
        self.assertTrue(taken["dismiss"])
        self.assertEqual(self.alerts.dismissed, [])


class EveryOtherCloseDismissesNothing(unittest.TestCase):
    def setUp(self) -> None:
        self.alerts = FakeAlerts()

    def refuses(self, item: dict) -> dict:
        taken = reconcile_alert.reconcile(item, self.alerts)
        self.assertFalse(taken["dismiss"])
        self.assertEqual(self.alerts.dismissed, [])
        return taken

    def test_a_close_without_the_label_dismisses_nothing(self) -> None:
        taken = self.refuses(issue(labels=["needs-triage"]))
        self.assertIn("wontfix", taken["reason"])

    def test_a_close_as_completed_dismisses_nothing(self) -> None:
        """A merged remediation pull request closes its issue this way, and that alert closes at the next scan."""
        taken = self.refuses(issue(labels=["wontfix", "ready-for-remediation"], state_reason="completed"))
        self.assertIn("completed", taken["reason"])

    def test_a_body_with_no_alert_row_dismisses_nothing_and_says_so(self) -> None:
        taken = self.refuses(issue(text=body(alert=None)))
        self.assertIn("names no alert", taken["reason"])

    def test_a_body_carrying_no_finding_at_all_dismisses_nothing_and_says_so(self) -> None:
        taken = self.refuses(issue(text="This issue is about something else entirely."))
        self.assertIn("names no alert", taken["reason"])


class TheCommandLineReportsWhatItDid(unittest.TestCase):
    def run_main(self, item: dict, *args: str) -> tuple[str, dict, FakeAlerts]:
        alerts = FakeAlerts()
        with tempfile.TemporaryDirectory() as scratch:
            snapshot = pathlib.Path(scratch) / "issue.json"
            snapshot.write_text(json.dumps(item), encoding="utf-8")
            report = pathlib.Path(scratch) / "report.json"
            printed = io.StringIO()
            with redirect_stdout(printed):
                code = reconcile_alert.main(
                    ["--issue", str(snapshot), "-o", str(report), *args], client=alerts
                )
            self.assertEqual(code, 0)
            return printed.getvalue(), json.loads(report.read_text(encoding="utf-8")), alerts

    def test_a_dismissal_names_the_alert_and_the_reason(self) -> None:
        printed, report, alerts = self.run_main(issue())
        self.assertIn("dismissed alert #12", printed)
        self.assertEqual(report["alert"], 12)
        self.assertEqual(len(alerts.dismissed), 1)

    def test_a_body_with_no_alert_row_is_reported_rather_than_raised(self) -> None:
        printed, report, alerts = self.run_main(issue(text=body(alert=None)))
        self.assertIn("nothing dismissed", printed)
        self.assertFalse(report["dismiss"])
        self.assertEqual(alerts.dismissed, [])

    def test_a_missing_snapshot_stops_the_run(self) -> None:
        with self.assertRaises(SystemExit):
            reconcile_alert.main(["--issue", "/nonexistent/issue.json"], client=FakeAlerts())


if __name__ == "__main__":
    unittest.main()
