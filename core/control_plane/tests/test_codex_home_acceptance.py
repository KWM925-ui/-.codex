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


ACCEPTANCE_SCRIPT = THIS_DIR.parent / "scripts/run_codex_home_acceptance.py"


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

    def run_acceptance(self, root: Path, *extra: str):
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
        )

    def test_acceptance_dry_run_lists_default_checks_without_real_smoke(self):
        tmpdir, root = self._fixture_root()
        with tmpdir:
            result = self.run_acceptance(root, "--dry-run", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["dry_run"])
            self.assertFalse(payload["include_real_smoke"])
            self.assertEqual(
                [step["name"] for step in payload["steps"]],
                [
                    "layout_audit",
                    "context_firewall_audit",
                    "agent_e2e_offline",
                    "project_task_workflow_smoke",
                ],
            )

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
                ],
            )

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
            args = mock.Mock(
                root=str(root),
                include_real_smoke=True,
                codex_bin="codex",
                real_timeout_seconds=1,
                dry_run=False,
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


if __name__ == "__main__":
    unittest.main()
