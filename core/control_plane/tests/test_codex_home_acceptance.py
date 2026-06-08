import argparse
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
SCRIPTS_DIR = THIS_DIR.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from codex_home_test_fixtures import (
    PROD_MANIFEST,
    _materialize_layout,
    _write_config,
    _write_root_index,
)
from run_codex_home_acceptance import _check_hygiene
from run_codex_home_acceptance import _check_real_auth_preflight
from run_codex_home_acceptance import _run_acceptance
from run_codex_home_acceptance import _summarize_command_output
from run_codex_home_acceptance import StepResult


ACCEPTANCE_SCRIPT = SCRIPTS_DIR / "run_codex_home_acceptance.py"
PUBLIC_EXPORT_AUDIT_SCRIPT = SCRIPTS_DIR / "audit_codex_public_export.py"


class CodexHomeAcceptanceTests(unittest.TestCase):
    def _fixture_root(self):
        tmpdir = tempfile.TemporaryDirectory()
        root = Path(tmpdir.name) / ".codex"
        root.mkdir()
        manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
        manifest["home_root"] = root.as_posix()
        _materialize_layout(root, manifest)
        _write_config(root / "config.toml")
        _write_root_index(root)
        return tmpdir, root

    def run_acceptance(self, root: Path, *extra: str, env=None):
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(ACCEPTANCE_SCRIPT),
                "--root",
                str(root),
                *extra,
            ],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

    def run_public_export_audit(self, export_root: Path):
        return subprocess.run(
            [
                sys.executable,
                "-B",
                str(PUBLIC_EXPORT_AUDIT_SCRIPT),
                "--export-root",
                str(export_root),
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def create_export_root(self, root: Path) -> Path:
        export_root = root / "export"
        for relpath in [
            "core/control_plane/scripts",
            "core/control_plane/tests",
            "core/control_plane/templates",
            "core/skills",
        ]:
            (export_root / relpath).mkdir(parents=True, exist_ok=True)
        for relpath in [
            "core/control_plane/scripts/run_codex_home_acceptance.py",
            "core/control_plane/scripts/project_task_workflow.py",
            "core/control_plane/tests/test_project_task_workflow.py",
            "core/control_plane/templates/repo_AGENTS.template.md",
            "core/skills/project-bootstrap/SKILL.md",
        ]:
            (export_root / relpath).parent.mkdir(parents=True, exist_ok=True)
            (export_root / relpath).write_text("fixture\n", encoding="utf-8")
        return export_root

    def test_acceptance_dry_run_lists_default_checks_without_real_smoke(self):
        tmpdir, root = self._fixture_root()
        with tmpdir:
            result = self.run_acceptance(root, "--dry-run", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["gate_profile"], "quick")
            self.assertFalse(payload["include_real_smoke"])
            self.assertGreater(payload["total_budget_seconds"], 0)
            self.assertEqual(
                [step["name"] for step in payload["steps"]],
                [
                    "layout_audit",
                    "context_firewall_audit",
                    "agent_e2e_offline",
                    "project_task_workflow_smoke",
                    "hygiene",
                ],
            )
            for step in payload["steps"]:
                self.assertGreater(step["budget_seconds"], 0)
                self.assertIn(step["cost_class"], ["cheap", "medium", "real"])

    def test_acceptance_standard_profile_adds_full_unit_suite(self):
        tmpdir, root = self._fixture_root()
        with tmpdir:
            result = self.run_acceptance(
                root,
                "--dry-run",
                "--gate-profile",
                "standard",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["gate_profile"], "standard")
            self.assertFalse(payload["include_real_smoke"])
            self.assertEqual(
                [step["name"] for step in payload["steps"]],
                [
                    "layout_audit",
                    "context_firewall_audit",
                    "agent_e2e_offline",
                    "project_task_workflow_smoke",
                    "control_plane_unittests",
                    "hygiene",
                ],
            )

    def test_acceptance_full_profile_adds_offline_profile_sweeps(self):
        tmpdir, root = self._fixture_root()
        with tmpdir:
            result = self.run_acceptance(
                root,
                "--dry-run",
                "--gate-profile",
                "full",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["gate_profile"], "full")
            step_names = [step["name"] for step in payload["steps"]]
            self.assertIn("agent_e2e_offline_strict", step_names)
            self.assertIn("agent_e2e_offline_exploratory", step_names)
            self.assertEqual(step_names[-1], "hygiene")

    def test_acceptance_release_profile_adds_public_export_hygiene(self):
        tmpdir, root = self._fixture_root()
        with tmpdir:
            export_root = self.create_export_root(Path(tmpdir.name))
            result = self.run_acceptance(
                root,
                "--dry-run",
                "--gate-profile",
                "release",
                "--export-root",
                str(export_root),
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["gate_profile"], "release")
            self.assertEqual(payload["export_root"], str(export_root))
            step_names = [step["name"] for step in payload["steps"]]
            self.assertIn("public_export_hygiene", step_names)
            self.assertNotIn("real_current_full", step_names)

    def test_acceptance_dry_run_adds_real_smoke_only_when_explicit(self):
        tmpdir, root = self._fixture_root()
        with tmpdir:
            result = self.run_acceptance(
                root,
                "--dry-run",
                "--include-real-smoke",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["include_real_smoke"])
            self.assertEqual(
                [step["name"] for step in payload["steps"]],
                [
                    "layout_audit",
                    "context_firewall_audit",
                    "agent_e2e_offline",
                    "project_task_workflow_smoke",
                    "real_auth_preflight",
                    "real_patch_smoke",
                    "real_noop_smoke",
                    "real_ambiguous_smoke",
                    "hygiene",
                ],
            )

    def test_acceptance_real_profile_implies_real_smoke(self):
        tmpdir, root = self._fixture_root()
        with tmpdir:
            result = self.run_acceptance(
                root,
                "--dry-run",
                "--gate-profile",
                "real",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["gate_profile"], "real")
            self.assertFalse(payload["include_real_smoke"])
            self.assertEqual(
                [step["name"] for step in payload["steps"][-5:-1]],
                [
                    "real_auth_preflight",
                    "real_patch_smoke",
                    "real_noop_smoke",
                    "real_ambiguous_smoke",
                ],
            )

    def test_acceptance_saturation_profile_uses_current_full_batch(self):
        tmpdir, root = self._fixture_root()
        with tmpdir:
            result = self.run_acceptance(
                root,
                "--dry-run",
                "--gate-profile",
                "saturation",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["gate_profile"], "saturation")
            step_names = [step["name"] for step in payload["steps"]]
            self.assertIn("real_current_full", step_names)
            self.assertIn("shell_autoadvance_regression", step_names)
            self.assertIn("shell_worktree_remap_regression", step_names)
            self.assertIn("shell_repeatability_widening_regression", step_names)
            self.assertIn("shell_repo_scale_regression", step_names)

    def test_public_export_audit_accepts_function_only_tree(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_root = self.create_export_root(Path(tmpdir))
            result = self.run_public_export_audit(export_root)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"], payload)

    def test_public_export_audit_rejects_local_private_surfaces(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            export_root = self.create_export_root(Path(tmpdir))
            (export_root / "sessions").mkdir()
            (export_root / "config.toml").write_text("secret config\n", encoding="utf-8")
            result = self.run_public_export_audit(export_root)
            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            details = "\n".join(check["details"] for check in payload["checks"])
            self.assertIn("sessions", details)
            self.assertIn("config.toml", details)

    def test_acceptance_dry_run_can_plan_live_provider_real_smoke(self):
        tmpdir, root = self._fixture_root()
        with tmpdir:
            result = self.run_acceptance(
                root,
                "--dry-run",
                "--include-real-smoke",
                "--real-use-live-provider-config",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["real_use_live_provider_config"])
            real_commands = [
                step["command"]
                for step in payload["steps"]
                if step["name"].startswith("real_")
                and step["name"] != "real_auth_preflight"
            ]
            self.assertTrue(real_commands)
            for command in real_commands:
                self.assertIn("--real-use-live-provider-config", command)

    def test_real_auth_preflight_blocks_without_safe_env_auth(self):
        result = _check_real_auth_preflight({})
        self.assertEqual(result.name, "real_auth_preflight")
        self.assertFalse(result.ok)
        self.assertTrue(result.details["blocked_without_model_call"])
        self.assertFalse(result.details["copied_live_config"])
        self.assertFalse(result.details["copied_live_auth"])
        self.assertEqual(result.details["present_auth_env_vars"], [])

    def test_real_auth_preflight_reports_only_env_name_not_value(self):
        result = _check_real_auth_preflight({"OPENAI_API_KEY": "sk-test-secret"})
        self.assertTrue(result.ok)
        self.assertFalse(result.details["blocked_without_model_call"])
        self.assertEqual(result.details["present_auth_env_vars"], ["OPENAI_API_KEY"])
        self.assertNotIn("sk-test-secret", result.summary)
        self.assertNotIn("sk-test-secret", json.dumps(result.details))

    def test_real_auth_preflight_can_use_live_provider_without_reporting_secret(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            (root / "config.toml").write_text(
                (
                    'model_provider = "example_provider"\n'
                    'model = "gpt-5.1-codex"\n'
                    '\n'
                    '[model_providers.example_provider]\n'
                    'name = "Example Provider"\n'
                    'base_url = "https://provider.example.test/codex"\n'
                    'wire_api = "responses"\n'
                    'experimental_bearer_token = "SECRET_SHOULD_NOT_REPORT"\n'
                ),
                encoding="utf-8",
            )
            result = _check_real_auth_preflight(
                {},
                root,
                use_live_provider_config=True,
            )
            self.assertTrue(result.ok)
            self.assertFalse(result.details["blocked_without_model_call"])
            self.assertTrue(result.details["copied_live_provider_fragment"])
            self.assertFalse(result.details["copied_live_config"])
            self.assertNotIn("SECRET_SHOULD_NOT_REPORT", result.summary)
            self.assertNotIn("SECRET_SHOULD_NOT_REPORT", json.dumps(result.details))

    def test_acceptance_hygiene_fails_on_bytecode_residue(self):
        tmpdir, root = self._fixture_root()
        with tmpdir:
            residue = root / "core/control_plane/scripts/__pycache__/x.pyc"
            residue.parent.mkdir(parents=True, exist_ok=True)
            residue.write_bytes(b"x")
            hygiene = _check_hygiene(root)
            self.assertEqual(hygiene.name, "hygiene")
            self.assertFalse(hygiene.ok)
            self.assertIn(
                "core/control_plane/scripts/__pycache__",
                "\n".join(hygiene.details["bytecode_paths"]),
            )

    def test_acceptance_hygiene_ignores_foreign_eval_temp_when_owner_set(self):
        tmpdir, root = self._fixture_root()
        with tmpdir, tempfile.TemporaryDirectory(
            prefix="codex-agent-e2e-foreign-",
            dir="/tmp",
        ) as foreign_tmp:
            hygiene = _check_hygiene(root, temp_owner_id="owner-123")
            self.assertTrue(hygiene.ok, hygiene.details)
            self.assertEqual(hygiene.details["temporary_eval_dirs"], [])
            self.assertIn(foreign_tmp, hygiene.details["other_temporary_eval_dirs"])

    def test_acceptance_hygiene_flags_owned_eval_temp_when_owner_set(self):
        tmpdir, root = self._fixture_root()
        with tmpdir, tempfile.TemporaryDirectory(
            prefix="codex-agent-e2e-owner-123-",
            dir="/tmp",
        ) as owned_tmp:
            hygiene = _check_hygiene(root, temp_owner_id="owner-123")
            self.assertFalse(hygiene.ok)
            self.assertIn(owned_tmp, hygiene.details["temporary_eval_dirs"])

    def test_acceptance_reports_hygiene_after_real_auth_preflight_block(self):
        tmpdir, root = self._fixture_root()
        with tmpdir:
            args = argparse.Namespace(
                root=str(root),
                gate_profile="quick",
                include_real_smoke=True,
                codex_bin="codex",
                real_timeout_seconds=1,
                dry_run=False,
                fail_on_budget_overrun=False,
            )
            with mock.patch(
                "run_codex_home_acceptance._planned_commands",
                return_value=[StepResult(name="real_auth_preflight", ok=True)],
            ), mock.patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
                payload = _run_acceptance(args)
            step_names = [step["name"] for step in payload["steps"]]
            self.assertIn("real_auth_preflight", step_names)
            self.assertEqual(step_names[-1], "hygiene")
            preflight = next(
                step for step in payload["steps"] if step["name"] == "real_auth_preflight"
            )
            self.assertFalse(preflight["ok"])
            self.assertTrue(preflight["details"]["blocked_without_model_call"])
            self.assertEqual(payload["steps"][-1]["name"], "hygiene")

    def test_acceptance_can_fail_on_budget_overrun_when_requested(self):
        tmpdir, root = self._fixture_root()
        with tmpdir:
            args = argparse.Namespace(
                root=str(root),
                gate_profile="quick",
                include_real_smoke=False,
                codex_bin="codex",
                real_timeout_seconds=1,
                dry_run=False,
                fail_on_budget_overrun=True,
            )
            planned = [
                StepResult(
                    name="slow_step",
                    ok=True,
                    command=["slow"],
                    budget_seconds=1.0,
                    cost_class="cheap",
                )
            ]
            slow_result = StepResult(
                name="slow_step",
                ok=True,
                command=["slow"],
                budget_seconds=1.0,
                duration_seconds=2.0,
                budget_ok=False,
            )
            clean_hygiene = StepResult(
                name="hygiene",
                ok=True,
                budget_seconds=3.0,
                duration_seconds=0.1,
                budget_ok=True,
            )
            with mock.patch(
                "run_codex_home_acceptance._planned_commands",
                return_value=planned,
            ), mock.patch(
                "run_codex_home_acceptance._run_command",
                return_value=slow_result,
            ), mock.patch(
                "run_codex_home_acceptance._check_hygiene",
                return_value=clean_hygiene,
            ):
                payload = _run_acceptance(args)
            self.assertFalse(payload["ok"])
            self.assertTrue(payload["functional_ok"])
            self.assertFalse(payload["budget_ok"])

    def test_agent_e2e_summary_reads_current_payload_shape(self):
        stdout = json.dumps(
            {
                "evals": [
                    {
                        "id": "controlled_ab",
                        "strategies": {
                            "current_full_codex": {
                                "passed": 12,
                                "tasks": 12,
                            }
                        },
                    }
                ]
            }
        )
        self.assertEqual(
            _summarize_command_output("agent_e2e_offline", 0, stdout, ""),
            "通过，离线端到端 current_full_codex=12/12",
        )
        self.assertEqual(
            _summarize_command_output("agent_e2e_offline_strict", 0, stdout, ""),
            "通过，离线端到端 current_full_codex=12/12",
        )


if __name__ == "__main__":
    unittest.main()
