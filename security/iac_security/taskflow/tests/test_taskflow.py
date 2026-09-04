"""Tests for the triage taskflow's deterministic parts.

Everything here runs offline against the committed baseline: no Docker, no
model, no network. What cannot be tested this way -- that the model returns a
verdict at all -- is not tested here, on purpose. What *is* tested is every
place a bad model response is supposed to be caught.
"""

from __future__ import annotations

import json
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TASKFLOW_DIR = HERE.parent
TRIAGE_DIR = TASKFLOW_DIR.parent
REPO_ROOT = TRIAGE_DIR.parents[1]

sys.path.insert(0, str(TASKFLOW_DIR))
sys.path.insert(0, str(TRIAGE_DIR))

import yaml  # noqa: E402

import collect_verdicts  # noqa: E402
import context  # noqa: E402
import vocabulary  # noqa: E402

TASKFLOW_PATH = TASKFLOW_DIR / "taskflows" / "iac_triage.yaml"
PERSONALITY_PATH = TASKFLOW_DIR / "personalities" / "iac_triage.yaml"
MODEL_CONFIG_PATH = TASKFLOW_DIR / "model_configs" / "iac_triage.yaml"


def load(path: pathlib.Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def task_by_id(taskflow: dict, task_id: str) -> dict:
    for entry in taskflow["taskflow"]:
        if entry["task"].get("id") == task_id:
            return entry["task"]
    raise AssertionError(f"no task with id {task_id!r}")


class TaskflowShape(unittest.TestCase):
    def setUp(self) -> None:
        self.taskflow = load(TASKFLOW_PATH)

    def test_declares_the_expected_three_tasks(self) -> None:
        ids = [entry["task"].get("id") for entry in self.taskflow["taskflow"]]
        self.assertEqual(ids, ["findings", "context", "verdicts"])

    def test_only_the_verdict_task_uses_a_model(self) -> None:
        """The deterministic half must stay deterministic."""
        for task_id in ("findings", "context"):
            task = task_by_id(self.taskflow, task_id)
            self.assertIn("run", task, f"{task_id} should be a shell task")
            self.assertNotIn("agents", task)

    def test_the_agent_has_no_toolboxes(self) -> None:
        """No toolbox is the reason a run cannot touch alert state (4.6)."""
        verdicts = task_by_id(self.taskflow, "verdicts")
        self.assertNotIn("toolboxes", verdicts)
        self.assertNotIn("toolboxes", load(PERSONALITY_PATH))

    def test_fans_out_over_eligible_findings_only(self) -> None:
        """Vendored and below-threshold findings never reach a prompt."""
        over = task_by_id(self.taskflow, "verdicts")["over"]
        self.assertIn("outputs.findings.eligible", over)
        self.assertNotIn("below_threshold", over)
        self.assertNotIn("vendored", over)


class VerdictVocabularyIsShared(unittest.TestCase):
    """The prompt and vocabulary.py must not drift apart.

    The taskflow schema was the third copy and is no longer one: it describes
    the verdict object nowhere, so there is nothing there to drift. What the
    model is told and what the collector accepts are now the only two
    statements of the vocabulary, and `collect_verdicts` reads `vocabulary.py`
    rather than restating it -- leaving the prompt as the one place a class
    could go missing.
    """

    def test_personality_names_every_verdict(self) -> None:
        text = PERSONALITY_PATH.read_text(encoding="utf-8")
        for verdict in vocabulary.VERDICTS:
            self.assertIn(verdict, text, f"{verdict} is not described to the agent")

    def test_the_collector_judges_against_the_shared_vocabulary(self) -> None:
        """Not a restatement of it: the same object, so drift is impossible."""
        self.assertIs(collect_verdicts.vocabulary.VERDICTS, vocabulary.VERDICTS)


class BranchSchemaChecksLivenessNotShape(unittest.TestCase):
    """Why the `outputs` schema stopped describing the verdict object.

    The framework decodes a captured response with a bare `json.loads`, so a
    fenced reply is a string. An object schema therefore failed every real
    verdict Sonnet produced and recorded the branch as `result: null` --
    destroying the answer instead of reporting it, which is the opposite of
    what 4.5 asks for. The schema keeps the half it can enforce on a prose
    channel: that the branch said something.
    """

    def setUp(self) -> None:
        self.schema = task_by_id(load(TASKFLOW_PATH), "verdicts")["outputs"]

    def test_the_schema_accepts_the_text_of_a_reply(self) -> None:
        self.assertEqual(self.schema["type"], "string")

    def test_the_schema_still_rejects_a_branch_that_said_nothing(self) -> None:
        self.assertEqual(self.schema["minLength"], 1)

    def test_the_schema_does_not_restate_the_verdict_object(self) -> None:
        """Two guards on one property is where they drift; this leaves one."""
        self.assertNotIn("properties", self.schema)
        self.assertNotIn("required", self.schema)


class ModelSelection(unittest.TestCase):
    """The model config is load-bearing in two ways a reviewer would not see.

    The framework defaults to Copilot, so an unreferenced model config leaves
    the run wanting a GitHub PAT; and a task with no `model:` silently falls
    back to the framework's own default rather than to anything named here.
    """

    def setUp(self) -> None:
        self.taskflow = load(TASKFLOW_PATH)
        self.config = load(MODEL_CONFIG_PATH)

    def test_the_taskflow_references_the_model_config(self) -> None:
        self.assertEqual(
            self.taskflow["model_config"],
            "security.iac_security.taskflow.model_configs.iac_triage",
        )

    def test_the_verdict_task_names_a_configured_model(self) -> None:
        """A `model:` absent here resolves to the framework's DEFAULT_MODEL."""
        model = task_by_id(self.taskflow, "verdicts").get("model")
        self.assertIn(model, self.config["models"])

    def test_the_backend_is_the_anthropic_messages_api(self) -> None:
        self.assertEqual(self.config["backend"], "anthropic_sdk")

    def test_every_model_is_sent_to_an_unregistered_endpoint(self) -> None:
        """The endpoint is what selects `x-api-key` over a bearer token.

        `capi.get_provider()` returns `bearer_auth=False` only for a host it
        does not recognise, and the Anthropic backend sends the token natively
        only then. A registered host here would ship the key as a bearer token
        to an API that expects neither.
        """
        for name in self.config["models"]:
            settings = self.config["model_settings"][name]
            self.assertEqual(settings["endpoint"], "https://api.anthropic.com")

    def test_settings_name_only_configured_models(self) -> None:
        """The framework rejects the config outright otherwise."""
        self.assertLessEqual(
            set(self.config.get("model_settings", {})), set(self.config["models"])
        )


class DiscardRule(unittest.TestCase):
    """A verdict without a rationale is discarded, not accepted (4.5)."""

    findings = {"AWS-0164:module.vpc:aws_subnet.public_zone_1": "AWS-0164"}

    def record(self, result: object, item: int = 0) -> dict:
        return collect_verdicts.branch_to_record(
            {"model": "test", "item": item, "result": result}, self.findings
        )

    def good(self, **overrides: object) -> dict:
        base = {
            "key": "AWS-0164:module.vpc:aws_subnet.public_zone_1",
            "verdict": "real-judgment",
            "rationale": "Public IPs on these subnets are load-bearing for the NAT-less design.",
            "evidence": ["docs/adr/0002-self-host-nextcloud-on-t4g-small.md"],
        }
        base.update(overrides)
        return base

    def test_a_complete_verdict_survives(self) -> None:
        record = self.record(self.good())
        self.assertEqual(record["verdict"], "real-judgment")
        self.assertNotIn("discarded_because", record)
        self.assertEqual(record["rule_id"], "AWS-0164")

    def test_missing_rationale_becomes_undetermined(self) -> None:
        result = self.good()
        del result["rationale"]
        record = self.record(result)
        self.assertEqual(record["verdict"], "undetermined")
        self.assertEqual(record["discarded_because"], collect_verdicts.DISCARD_MISSING_RATIONALE)
        self.assertEqual(record["discarded_verdict"], "real-judgment")

    def test_whitespace_rationale_becomes_undetermined(self) -> None:
        """A rationale of spaces is a string of length 3, and JSON-legal."""
        record = self.record(self.good(rationale="   \n\t "))
        self.assertEqual(record["verdict"], "undetermined")
        self.assertEqual(record["discarded_because"], collect_verdicts.DISCARD_BLANK_RATIONALE)

    def test_verdict_outside_the_vocabulary_becomes_undetermined(self) -> None:
        record = self.record(self.good(verdict="probably-fine"))
        self.assertEqual(record["verdict"], "undetermined")
        self.assertEqual(record["discarded_because"], collect_verdicts.DISCARD_UNKNOWN_VERDICT)

    def test_a_branch_that_produced_nothing_becomes_undetermined(self) -> None:
        record = self.record(None)
        self.assertEqual(record["verdict"], "undetermined")
        self.assertEqual(record["discarded_because"], collect_verdicts.DISCARD_NO_RESULT)

    def test_a_non_json_response_becomes_undetermined(self) -> None:
        record = self.record("I think this one is fine, honestly.")
        self.assertEqual(record["verdict"], "undetermined")
        self.assertEqual(record["discarded_because"], collect_verdicts.DISCARD_UNPARSEABLE)

    def test_a_discarded_finding_is_still_reported(self) -> None:
        """Discarding a verdict must not make the finding disappear."""
        record = self.record(None)
        self.assertEqual(record["key"], "AWS-0164:module.vpc:aws_subnet.public_zone_1")

    def test_a_json_string_response_is_decoded(self) -> None:
        record = self.record(json.dumps(self.good()))
        self.assertEqual(record["verdict"], "real-judgment")

    def test_a_fenced_response_is_decoded(self) -> None:
        """The reply Sonnet actually sends, on every run, however it is asked."""
        record = self.record("```json\n" + json.dumps(self.good()) + "\n```")
        self.assertEqual(record["verdict"], "real-judgment")
        self.assertNotIn("discarded_because", record)

    def test_a_fence_without_a_language_tag_is_decoded(self) -> None:
        record = self.record("```\n" + json.dumps(self.good()) + "\n```")
        self.assertEqual(record["verdict"], "real-judgment")

    def test_prose_around_an_object_is_still_discarded(self) -> None:
        """The line the fence tolerance must not cross.

        Seeing through a fence reads a reply that answered the question in the
        shape asked for. Digging an object out of commentary would accept one
        that did not, and the discard rule would quietly become a scraper.
        """
        record = self.record("Here is my verdict:\n" + json.dumps(self.good()))
        self.assertEqual(record["verdict"], "undetermined")
        self.assertEqual(record["discarded_because"], collect_verdicts.DISCARD_UNPARSEABLE)

    def test_a_fence_with_a_trailing_remark_is_still_discarded(self) -> None:
        record = self.record(
            "```json\n" + json.dumps(self.good()) + "\n```\nLet me know if that helps."
        )
        self.assertEqual(record["verdict"], "undetermined")
        self.assertEqual(record["discarded_because"], collect_verdicts.DISCARD_UNPARSEABLE)

    def test_evidence_is_always_a_list(self) -> None:
        record = self.record(self.good(evidence="docs/adr/0001-ansible-over-ssm.md"))
        self.assertEqual(record["evidence"], ["docs/adr/0001-ansible-over-ssm.md"])


class CollectFromManifest(unittest.TestCase):
    def test_reads_the_named_fan_in_output(self) -> None:
        manifest = {
            "outputs": {
                "verdicts": [
                    {
                        "model": "m",
                        "item": 0,
                        "result": {
                            "key": "AWS-0164:module.vpc:aws_subnet.public_zone_1",
                            "verdict": "not-applicable",
                            "rationale": "Recorded decision covers this.",
                            "evidence": [],
                        },
                    },
                    {"model": "m", "item": 1, "result": None},
                ]
            }
        }
        records = collect_verdicts.collect(manifest, DiscardRule.findings)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["verdict"], "not-applicable")
        self.assertEqual(records[1]["verdict"], "undetermined")

    def test_a_manifest_without_the_output_fails_loudly(self) -> None:
        """A run that produced no verdicts must not look like a run that did.

        This is the shape of a run that failed before the model step -- the
        degradation case of 4.7. It has to raise rather than return an empty
        list, so a failed run is reported as a failure rather than silently
        collected as zero verdicts.
        """
        with self.assertRaises(SystemExit):
            collect_verdicts.collect({"outputs": {"findings": {}, "context": {}}}, {})

    def test_records_carry_the_fields_a_verdict_consumer_needs(self) -> None:
        """key, rule_id and verdict are the fields file_issues.py reads."""
        record = collect_verdicts.branch_to_record(
            {
                "model": "m",
                "item": 0,
                "result": {
                    "key": "AWS-0164:module.vpc:aws_subnet.public_zone_1",
                    "verdict": "real-mechanical",
                    "rationale": "why",
                },
            },
            DiscardRule.findings,
        )
        self.assertLessEqual({"key", "rule_id", "verdict"}, set(record))


class TriageContext(unittest.TestCase):
    def test_collects_the_decision_records(self) -> None:
        collected = context.collect(REPO_ROOT)
        paths = [d["path"] for d in collected["documents"]]
        self.assertTrue(collected["included"])
        self.assertEqual(collected["missing_dirs"], [])
        self.assertTrue(any(p.startswith("docs/adr/") for p in paths))
        self.assertTrue(all(d["text"] for d in collected["documents"]))

    def test_documents_are_ordered_stably(self) -> None:
        """Two runs must present the same context in the same order."""
        first = [d["path"] for d in context.collect(REPO_ROOT)["documents"]]
        second = [d["path"] for d in context.collect(REPO_ROOT)["documents"]]
        self.assertEqual(first, second)
        self.assertEqual(first, sorted(first))

    def test_without_context_yields_no_documents(self) -> None:
        collected = context.collect(REPO_ROOT, include=False)
        self.assertEqual(collected["documents"], [])
        self.assertFalse(collected["included"])

    def test_a_missing_directory_is_reported_not_silent(self) -> None:
        collected = context.collect(pathlib.Path("/nonexistent"), include=True)
        self.assertEqual(collected["documents"], [])
        self.assertEqual(sorted(collected["missing_dirs"]), sorted(context.CONTEXT_DIRS))


if __name__ == "__main__":
    unittest.main()
