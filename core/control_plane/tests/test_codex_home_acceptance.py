import json
import subprocess
import sys
import tempfile
import unittest
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
from run_codex_home_acceptance import _summarize_command_output


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
                    "real_patch_smoke",
                    "real_noop_smoke",
                ],
            )

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
