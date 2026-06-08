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

from codex_home_test_fixtures import (
    CURATED_SUGGEST_SCRIPT,
    LIFECYCLE_REVIEW_SCRIPT,
    PROD_MANIFEST,
    _materialize_layout,
    _write_config,
    _write_file,
    _write_root_index,
)


class LifecycleAndContextSmokeTests(unittest.TestCase):
    def _fixture_root(self):
        tmpdir = tempfile.TemporaryDirectory()
        root = Path(tmpdir.name) / ".codex"
        root.mkdir()
        manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
        manifest["home_root"] = root.as_posix()
        _materialize_layout(root, manifest)
        _write_config(root / "config.toml")
        _write_root_index(root)
        return tmpdir, root, manifest

    def test_lifecycle_review_smoke_is_report_only(self):
        tmpdir, root, manifest = self._fixture_root()
        with tmpdir:
            _write_file(root / ".tmp/smoke.tmp", "x")
            result = subprocess.run(
                [
                    sys.executable,
                    str(LIFECYCLE_REVIEW_SCRIPT),
                    "--root",
                    str(root),
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["layout_version"], manifest["layout_version"])
            self.assertTrue(payload["privacy"]["report_only"])
            self.assertFalse(payload["privacy"]["mutated_files"])

    def test_curated_suggestion_smoke_is_redacted(self):
        tmpdir, root, manifest = self._fixture_root()
        with tmpdir:
            secret = "SMOKE_SECRET_SHOULD_NOT_APPEAR"
            input_path = root / "context.json"
            input_path.write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "id": "repo",
                                "source_class": "repo_state",
                                "content": "repo " + secret,
                                "relevance_score": 0.9,
                                "freshness_days": 0,
                                "memory_kind": "project_fact",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(CURATED_SUGGEST_SCRIPT),
                    "--root",
                    str(root),
                    "--input",
                    str(input_path),
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(secret, result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["layout_version"], manifest["layout_version"])
            self.assertTrue(payload["privacy"]["soft_integration"])
            self.assertFalse(payload["privacy"]["raw_content_emitted"])

    def test_real_regression_scripts_retry_rate_limits_and_accept_pass_variants(self):
        scripts = [
            "run_autoadvance_regression.sh",
            "run_worktree_remap_regression.sh",
            "run_repeatability_widening_regression.sh",
            "run_repo_scale_autoadvance_regression.sh",
        ]
        for script in scripts:
            script_text = (SCRIPTS_DIR / script).read_text(encoding="utf-8")
            self.assertIn("CODEX_REGRESSION_ATTEMPTS", script_text)
            self.assertIn("429 Too Many Requests|exceeded retry limit", script_text)
            self.assertIn("retry ${attempt}/${attempts}", script_text)
            self.assertIn("--skip-git-repo-check", script_text)
            self.assertIn("cleanup_tmp_trusted_projects", script_text)
            self.assertIn("trap cleanup_tmp_trusted_projects EXIT", script_text)
            self.assertIn(r'^\[projects\."\/tmp(\/[^"]*)?"\]$', script_text)

        for script in [
            "run_autoadvance_regression.sh",
            "run_worktree_remap_regression.sh",
        ]:
            script_text = (SCRIPTS_DIR / script).read_text(encoding="utf-8")
            self.assertIn(r"PASS.*add\(2, 3\) == 5", script_text)


if __name__ == "__main__":
    unittest.main()
