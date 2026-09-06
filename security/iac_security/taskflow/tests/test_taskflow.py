from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TASKFLOW_DIR = HERE.parent
TRIAGE_DIR = TASKFLOW_DIR.parent
REPO_ROOT = TRIAGE_DIR.parents[1]

sys.path.insert(0, str(TASKFLOW_DIR))
sys.path.insert(0, str(TRIAGE_DIR))

import yaml  # noqa: E402

import collect_verdicts  # noqa: E402
import terraform_corpus  # noqa: E402
import vocabulary  # noqa: E402

TASKFLOW_PATH = TASKFLOW_DIR / "taskflows" / "iac_triage.yaml"
PERSONALITY_PATH = TASKFLOW_DIR / "personalities" / "iac_triage.yaml"
MODEL_CONFIG_PATH = TASKFLOW_DIR / "model_configs" / "iac_triage.yaml"


def load(path: pathlib.Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


FINDING_KEYS = {"AWS-0164:module.vpc:aws_subnet.public_zone_1": "AWS-0164"}


def good_verdict(**overrides: object) -> dict:
    """A verdict that survives the discard rule, with fields overridden."""
    base = {
        "key": "AWS-0164:module.vpc:aws_subnet.public_zone_1",
        "verdict": "real-judgment",
        "rationale": "Public IPs on these subnets are load-bearing for the NAT-less design.",
        "evidence": ["modules/vpc/main.tf"],
    }
    base.update(overrides)
    return base


def script_paths(run: str) -> list[str]:
    """The paths a `run:` field names, recognised by extension and not by interpreter."""
    return [token for token in run.split() if token.endswith((".sh", ".py"))]


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
        self.assertEqual(ids, ["findings", "corpus", "verdicts"])

    def test_only_the_verdict_task_uses_a_model(self) -> None:
        """The deterministic half must stay deterministic."""
        for task_id in ("findings", "corpus"):
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


class RunFieldsResolveFromTheContainerWorkingDirectory(unittest.TestCase):
    """`run.sh` mounts the repository root at `/app` and works there, so a
    `run:` field naming a path relative to this directory resolves to nothing.

    `--lint` cannot catch that: it validates offline and executes no `run:`
    field, so a wrong path here surfaces only in a live run.
    """

    def test_every_run_field_names_a_path_that_exists_from_the_repository_root(self) -> None:
        for entry in load(TASKFLOW_PATH)["taskflow"]:
            task = entry["task"]
            if "run" not in task:
                continue
            named = script_paths(task["run"])
            self.assertTrue(named, f"{task['name']} names no .sh or .py path to run")
            for path in named:
                self.assertTrue((REPO_ROOT / path).is_file(), f"{task['name']}: {path}")


class VerdictVocabularyIsShared(unittest.TestCase):
    def test_personality_names_every_verdict(self) -> None:
        text = PERSONALITY_PATH.read_text(encoding="utf-8")
        for verdict in vocabulary.VERDICTS:
            self.assertIn(verdict, text, f"{verdict} is not described to the agent")

    def test_the_collector_judges_against_the_shared_vocabulary(self) -> None:
        self.assertIs(collect_verdicts.vocabulary.VERDICTS, vocabulary.VERDICTS)


class BranchSchemaChecksLivenessNotShape(unittest.TestCase):

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
        for name in self.config["models"]:
            settings = self.config["model_settings"][name]
            self.assertEqual(settings["endpoint"], "https://api.anthropic.com")

    def test_settings_name_only_configured_models(self) -> None:
        """The framework rejects the config outright otherwise."""
        self.assertLessEqual(
            set(self.config.get("model_settings", {})), set(self.config["models"])
        )


class DiscardRule(unittest.TestCase):

    findings = FINDING_KEYS

    def record(self, result: object, item: int = 0) -> dict:
        return collect_verdicts.branch_to_record(
            {"model": "test", "item": item, "result": result}, self.findings
        )

    def good(self, **overrides: object) -> dict:
        return good_verdict(**overrides)

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
        record = self.record(self.good(evidence="modules/vpc/main.tf"))
        self.assertEqual(record["evidence"], ["modules/vpc/main.tf"])


class EvidenceDiscrepancy(unittest.TestCase):
    """A cited path outside the corpus is recorded, not discarded (ADR-0008).

    The corpus is exhaustive, so a citation the corpus does not contain was
    never actually shown to the model. That is worth flagging -- but the verdict
    it accompanies may still be right, so it must survive, unlike a verdict that
    fails the discard rule.
    """

    findings = FINDING_KEYS
    corpus = {"modules/vpc/main.tf", "live/management/main.tf"}

    def record(self, evidence: list[str], corpus_paths: set[str] | None) -> dict:
        result = good_verdict(evidence=evidence)
        return collect_verdicts.branch_to_record(
            {"model": "test", "item": 0, "result": result}, self.findings, corpus_paths
        )

    def test_evidence_within_the_corpus_carries_no_discrepancy(self) -> None:
        record = self.record(["modules/vpc/main.tf"], self.corpus)
        self.assertNotIn("evidence_discrepancy", record)
        self.assertEqual(record["verdict"], "real-judgment")

    def test_evidence_outside_the_corpus_is_recorded_not_discarded(self) -> None:
        record = self.record(["modules/vpc/main.tf", "live/nonexistent/main.tf"], self.corpus)
        self.assertEqual(record["verdict"], "real-judgment")
        self.assertNotIn("discarded_because", record)
        self.assertEqual(record["evidence_discrepancy"], ["live/nonexistent/main.tf"])

    def test_no_corpus_paths_supplied_means_no_check_is_made(self) -> None:
        """`collect_verdicts.py` run without a `--findings`-style corpus source
        must not invent discrepancies it has no way to verify."""
        record = self.record(["live/nonexistent/main.tf"], None)
        self.assertNotIn("evidence_discrepancy", record)

    def test_corpus_paths_from_manifest_reads_the_corpus_task(self) -> None:
        manifest = {"outputs": {"corpus": {"documents": [{"path": "modules/vpc/main.tf", "text": "x"}]}}}
        self.assertEqual(collect_verdicts.corpus_paths_from_manifest(manifest), {"modules/vpc/main.tf"})

    def test_corpus_paths_from_manifest_is_none_without_a_corpus_task(self) -> None:
        self.assertIsNone(collect_verdicts.corpus_paths_from_manifest({"outputs": {}}))


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
        records = collect_verdicts.collect(manifest, FINDING_KEYS)
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
            collect_verdicts.collect({"outputs": {"findings": {}, "corpus": {}}}, {})

    def test_flags_evidence_the_corpus_task_never_carried(self) -> None:
        manifest = {
            "outputs": {
                "corpus": {"documents": [{"path": "modules/vpc/main.tf", "text": "x"}]},
                "verdicts": [
                    {
                        "model": "m",
                        "item": 0,
                        "result": {
                            "key": "AWS-0164:module.vpc:aws_subnet.public_zone_1",
                            "verdict": "not-applicable",
                            "rationale": "Recorded decision covers this.",
                            "evidence": ["live/nonexistent/main.tf"],
                        },
                    }
                ],
            }
        }
        records = collect_verdicts.collect(manifest, FINDING_KEYS)
        self.assertEqual(records[0]["verdict"], "not-applicable")
        self.assertEqual(records[0]["evidence_discrepancy"], ["live/nonexistent/main.tf"])

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
            FINDING_KEYS,
        )
        self.assertLessEqual({"key", "rule_id", "verdict"}, set(record))


class TerraformCorpus(unittest.TestCase):
    """`terraform_corpus.py`, ADR-0008's replacement for `context.py`.

    The assembler may hold code and never prose (ADR-0008 -- Consequences), and
    that is enforced structurally: it only ever globs `.tf`. What is tested here
    is derived from the tree at test time rather than restated as a fixed list
    or count, so it fails the moment the corpus actually changes shape -- a
    twenty-fifth file, or one under `.terraform/` -- rather than only when
    someone remembers to update a number.
    """

    def independently_walked_tf_paths(self, root: pathlib.Path) -> set[str]:
        """The first-party `.tf` files on disk, computed without using the
        module under test, so the comparison is not circular."""
        found: set[str] = set()
        for prefix in ("live", "modules"):
            directory = root / prefix
            if not directory.is_dir():
                continue
            for path in directory.rglob("*.tf"):
                relative = path.relative_to(root)
                if ".terraform" in relative.parts:
                    continue
                found.add(str(relative))
        return found

    def test_matches_exactly_the_first_party_tf_files_on_disk(self) -> None:
        collected = terraform_corpus.collect(REPO_ROOT)
        paths = {d["path"] for d in collected["documents"]}
        self.assertEqual(paths, self.independently_walked_tf_paths(REPO_ROOT))
        self.assertTrue(all(d["text"] for d in collected["documents"]))

    def test_documents_are_ordered_stably(self) -> None:
        """Two runs must present the same corpus in the same order."""
        first = [d["path"] for d in terraform_corpus.collect(REPO_ROOT)["documents"]]
        second = [d["path"] for d in terraform_corpus.collect(REPO_ROOT)["documents"]]
        self.assertEqual(first, second)
        self.assertEqual(first, sorted(first))

    def test_globs_only_tf_and_nothing_under_dot_terraform(self) -> None:
        """A resolved module cache can land inside `live/` or `modules/` once
        `terraform init` has run; it must stay out of the corpus exactly as it
        stays out of triage in `normalise.py`."""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            first_party = root / "live" / "management"
            first_party.mkdir(parents=True)
            (first_party / "main.tf").write_text('resource "x" "y" {}\n', encoding="utf-8")
            (first_party / "README.md").write_text("not terraform\n", encoding="utf-8")

            vendored = first_party / ".terraform" / "modules" / "some_module"
            vendored.mkdir(parents=True)
            (vendored / "main.tf").write_text('resource "a" "b" {}\n', encoding="utf-8")

            collected = terraform_corpus.collect(root)
            paths = [d["path"] for d in collected["documents"]]

        self.assertEqual(paths, [str(pathlib.Path("live/management/main.tf"))])

    def test_a_missing_directory_is_reported_not_silent(self) -> None:
        collected = terraform_corpus.collect(pathlib.Path("/nonexistent"))
        self.assertEqual(collected["documents"], [])
        self.assertEqual(sorted(collected["missing_dirs"]), sorted(terraform_corpus.CORPUS_DIRS))


class AnEmptyCorpusIsAnError(unittest.TestCase):
    """The prompt promises the agent a complete corpus, so it must be one.

    The template says the corpus is exhaustive and the personality withdraws
    "I was not shown enough" as a reason on the strength of that. A bad mount or
    a wrong root would otherwise triage every finding against zero files while
    still claiming to have shown everything -- a silent failure that produces
    confident verdicts formed on nothing. `must_complete: true` on the `corpus`
    task turns a non-zero exit here into a halted run.
    """

    def run_main_against(self, root: pathlib.Path) -> str:
        original = terraform_corpus.REPO_ROOT
        terraform_corpus.REPO_ROOT = root
        try:
            with self.assertRaises(SystemExit) as raised:
                terraform_corpus.main([])
        finally:
            terraform_corpus.REPO_ROOT = original
        return str(raised.exception)

    def test_a_missing_corpus_directory_halts_the_run(self) -> None:
        message = self.run_main_against(pathlib.Path("/nonexistent"))
        self.assertIn("no such corpus directory", message)

    def test_a_corpus_of_no_files_halts_the_run(self) -> None:
        """Both roots present and both empty: nothing is missing, yet there is
        nothing to show the agent either."""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for prefix in terraform_corpus.CORPUS_DIRS:
                (root / prefix).mkdir()
            message = self.run_main_against(root)
        self.assertIn("corpus is empty", message)

    def test_a_populated_corpus_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for prefix in terraform_corpus.CORPUS_DIRS:
                (root / prefix).mkdir()
            (root / "modules" / "main.tf").write_text('resource "x" "y" {}\n', encoding="utf-8")

            output = root / "corpus.json"
            original = terraform_corpus.REPO_ROOT
            terraform_corpus.REPO_ROOT = root
            try:
                self.assertEqual(terraform_corpus.main(["-o", str(output)]), 0)
            finally:
                terraform_corpus.REPO_ROOT = original

            written = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual([d["path"] for d in written["documents"]], ["modules/main.tf"])


if __name__ == "__main__":
    unittest.main()
