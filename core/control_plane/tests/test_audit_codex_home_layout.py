import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from codex_home_test_fixtures import (
    ARCHIVE_REVIEW_SCRIPT,
    DOCTOR_SCRIPT,
    EXPLAIN_SCRIPT,
    LIFECYCLE_REVIEW_SCRIPT,
    MIGRATION_REVIEW_SCRIPT,
    PROD_MANIFEST,
    REPORT_SCRIPT,
    RUNTIME_REVIEW_SCRIPT,
    SCRIPT,
    TOOL_OWNED_REVIEW_SCRIPT,
    _fresh_timestamp,
    _materialize_layout,
    _write_config,
    _write_file,
    _write_root_index,
)


class AuditCodexHomeLayoutTests(unittest.TestCase):
    def run_audit(self, root: Path, manifest_path: Path, config_path: Path):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--root",
                str(root),
                "--manifest",
                str(manifest_path),
                "--config",
                str(config_path),
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def run_explain(self, root: Path, target: str):
        return subprocess.run(
            [
                sys.executable,
                str(EXPLAIN_SCRIPT),
                target,
                "--root",
                str(root),
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def run_doctor(self, root: Path, target: str):
        return subprocess.run(
            [
                sys.executable,
                str(DOCTOR_SCRIPT),
                target,
                "--root",
                str(root),
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def run_report(self, root: Path):
        return subprocess.run(
            [
                sys.executable,
                str(REPORT_SCRIPT),
                "--root",
                str(root),
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def run_runtime_review(self, root: Path):
        return subprocess.run(
            [
                sys.executable,
                str(RUNTIME_REVIEW_SCRIPT),
                "--root",
                str(root),
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def run_tool_owned_review(self, root: Path):
        return subprocess.run(
            [
                sys.executable,
                str(TOOL_OWNED_REVIEW_SCRIPT),
                "--root",
                str(root),
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def run_archive_review(self, root: Path):
        return subprocess.run(
            [
                sys.executable,
                str(ARCHIVE_REVIEW_SCRIPT),
                "--root",
                str(root),
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def run_lifecycle_review(self, root: Path):
        return subprocess.run(
            [
                sys.executable,
                str(LIFECYCLE_REVIEW_SCRIPT),
                "--root",
                str(root),
                "--large-session-mb",
                "1",
                "--old-session-days",
                "1",
                "--large-runtime-mb",
                "1",
                "--max-items",
                "5",
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def run_migration_review(self, root: Path):
        return subprocess.run(
            [
                sys.executable,
                str(MIGRATION_REVIEW_SCRIPT),
                "--root",
                str(root),
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_valid_layout_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])

    def test_policy_explain_for_runtime_surface(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            result = self.run_explain(root, "tmp")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["surface"]["selector_type"], "runtime_category")
            self.assertEqual(payload["surface"]["selector"], "temp")
            self.assertEqual(
                payload["execution_modes"],
                ["reversible_only", "rotation_allowed", "manual_review_only"],
            )

    def test_policy_explain_uses_runtime_registry_for_new_state_surface(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            result = self.run_explain(root, "goals_1.sqlite")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["surface"]["selector_type"], "runtime_category")
            self.assertEqual(payload["surface"]["selector"], "state")
            self.assertEqual(
                payload["execution_modes"],
                ["preserve_only", "manual_review_only"],
            )

    def test_policy_explain_for_namespace_surface(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            result = self.run_explain(
                root,
                "project_assets/shared_imports/vendor_imports",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["surface"]["selector_type"], "namespace_type")
            self.assertEqual(payload["surface"]["selector"], "shared_asset_bundle")
            self.assertIn("tool_only", payload["execution_modes"])

    def test_policy_explain_for_compatibility_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            result = self.run_explain(root, "control_plane")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["surface"]["kind"], "compatibility_surface")
            self.assertEqual(payload["surface"]["selector_type"], "compatibility_category")
            self.assertEqual(payload["surface"]["selector"], "core")
            self.assertEqual(
                payload["execution_modes"],
                ["preserve_only", "manual_review_only"],
            )

    def test_policy_explain_for_compatibility_target(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            result = self.run_explain(root, "core/control_plane")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["surface"]["kind"], "compatibility_target")
            self.assertEqual(
                payload["surface"]["compatibility_entrypoint"],
                "control_plane",
            )
            self.assertEqual(payload["surface"]["selector"], "core")

    def test_policy_doctor_for_project_compatibility_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            result = self.run_doctor(root, "pandeng_supervisor")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["surface"]["kind"], "compatibility_surface")
            self.assertEqual(payload["surface"]["selector"], "project_assets")
            self.assertEqual(payload["health_class"], "stable_preserve")

    def test_policy_doctor_for_history_surface(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            result = self.run_doctor(root, "memories")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["health_class"], "archive_governed")
            self.assertEqual(payload["recommended_action"], "archive_with_continuity")

    def test_policy_doctor_for_runtime_surface(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            result = self.run_doctor(root, "tmp")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["health_class"], "reversible_governed")
            self.assertEqual(payload["recommended_action"], "quarantine_or_rotate")

    def test_policy_doctor_for_tool_governed_namespace_surface(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            result = self.run_doctor(
                root,
                "project_assets/shared_imports/vendor_imports",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["health_class"], "tool_governed_reversible")
            self.assertEqual(
                payload["recommended_action"],
                "use_owning_tool_or_quarantine",
            )

    def test_policy_report_batches_root_and_namespace_surfaces(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            result = self.run_report(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["layout_version"], manifest["layout_version"])
            self.assertEqual(
                payload["summary"]["total_surfaces"],
                len(manifest["core_surfaces"])
                + len(manifest["compatibility_surfaces"])
                + len(manifest["runtime_surfaces"])
                + len(manifest["history_surfaces"])
                + len(manifest["project_namespaces"]),
            )
            self.assertEqual(payload["targets"], payload["surfaces"])
            targets = [entry["target"] for entry in payload["surfaces"]]
            self.assertIn("control_plane", targets)
            self.assertIn("tmp", targets)
            self.assertIn("goals_1.sqlite", targets)
            self.assertIn("project_assets/shared_imports", targets)
            self.assertIn(
                "use_owning_tool_or_quarantine",
                payload["summary"]["by_recommended_action"],
            )
            group_ids = [group["group_id"] for group in payload["action_groups"]]
            self.assertIn("runtime_reversible", group_ids)
            self.assertIn("tool_owned_reversible", group_ids)
            runtime_group = next(
                group
                for group in payload["action_groups"]
                if group["group_id"] == "runtime_reversible"
            )
            runtime_targets = [item["target"] for item in runtime_group["targets"]]
            self.assertEqual(runtime_targets, [".tmp", "cache", "models_cache.json", "tmp"])
            tool_group = next(
                group
                for group in payload["action_groups"]
                if group["group_id"] == "tool_owned_reversible"
            )
            tool_targets = [item["target"] for item in tool_group["targets"]]
            self.assertEqual(tool_targets, ["project_assets/shared_imports"])

    def test_runtime_review_focuses_reversible_runtime_batch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            result = self.run_runtime_review(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["layout_version"], manifest["layout_version"])
            self.assertEqual(payload["group"]["group_id"], "runtime_reversible")
            self.assertEqual(payload["summary"]["total_targets"], 4)
            self.assertEqual(
                payload["summary"]["by_runtime_category"],
                {"cache": 2, "temp": 2},
            )
            self.assertEqual(
                payload["summary"]["by_retention_class"],
                {
                    "live_runtime_temp": 2,
                    "rebuildable_runtime_cache": 2,
                },
            )
            targets = {entry["target"]: entry for entry in payload["targets"]}
            self.assertEqual(
                targets["cache"]["retention_class"],
                "rebuildable_runtime_cache",
            )
            self.assertTrue(targets["cache"]["rotation_allowed"])
            self.assertEqual(targets["cache"]["operator_bias"], "rotation_first")
            self.assertEqual(
                targets["tmp"]["retention_class"],
                "live_runtime_temp",
            )
            self.assertEqual(targets["tmp"]["operator_bias"], "quarantine_first")
            out_of_scope = [
                entry["target"]
                for entry in payload["out_of_scope_runtime_surfaces"]
            ]
            self.assertIn("auth.json", out_of_scope)
            self.assertIn("goals_1.sqlite", out_of_scope)
            self.assertIn("state_5.sqlite", out_of_scope)
            self.assertNotIn("tmp", out_of_scope)

    def test_tool_owned_review_focuses_shared_imports_namespace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            result = self.run_tool_owned_review(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["layout_version"], manifest["layout_version"])
            self.assertEqual(payload["group"]["group_id"], "tool_owned_reversible")
            self.assertEqual(payload["summary"]["total_targets"], 1)
            self.assertEqual(
                payload["summary"]["by_namespace_type"],
                {"shared_asset_bundle": 1},
            )
            self.assertEqual(
                payload["summary"]["workflow_status_counts"],
                {"no_local_workflow_artifacts_detected": 1},
            )
            self.assertEqual(payload["summary"]["total_registered_subsurfaces"], 1)
            self.assertEqual(payload["summary"]["total_compatibility_entrypoints"], 1)
            target = payload["targets"][0]
            self.assertEqual(target["target"], "project_assets/shared_imports")
            self.assertEqual(target["namespace_id"], "shared_imports")
            self.assertEqual(target["workflow_artifacts"], [])
            self.assertEqual(
                target["workflow_status"],
                "no_local_workflow_artifacts_detected",
            )
            self.assertTrue(target["quarantine_fallback_allowed"])
            self.assertEqual(target["operator_bias"], "owning_tool_first")
            compat = target["compatibility_entrypoints"][0]
            self.assertEqual(compat["path"], "vendor_imports")
            self.assertTrue(compat["exists"])
            self.assertTrue(compat["is_symlink"])
            self.assertTrue(compat["resolves_to_expected"])
            subsurface = target["registered_subsurfaces"][0]
            self.assertEqual(
                subsurface["path"],
                "project_assets/shared_imports/vendor_imports",
            )
            self.assertEqual(subsurface["inventory_state"], "empty")
            self.assertEqual(subsurface["non_placeholder_count"], 0)
            other_groups = {
                group["group_id"]: group
                for group in payload["other_attention_groups"]
            }
            self.assertIn("runtime_reversible", other_groups)
            self.assertEqual(
                other_groups["runtime_reversible"]["targets"],
                [".tmp", "cache", "models_cache.json", "tmp"],
            )

    def test_archive_review_plans_history_and_namespace_targets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            result = self.run_archive_review(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["layout_version"], manifest["layout_version"])
            self.assertEqual(payload["group"]["group_id"], "archive_governed")
            self.assertEqual(payload["summary"]["total_targets"], 10)
            self.assertEqual(
                payload["summary"]["by_scope"],
                {"history_surface": 6, "namespace_surface": 4},
            )
            self.assertEqual(payload["summary"]["targets_with_mirror_continuity"], 3)
            self.assertEqual(
                payload["summary"]["targets_with_compatibility_entrypoints"],
                3,
            )
            bucket_ids = [
                bucket["bucket_id"]
                for bucket in payload["planning_buckets"]
            ]
            self.assertEqual(bucket_ids, ["history_archive", "namespace_archive"])
            targets = {entry["target"]: entry for entry in payload["targets"]}
            sessions = targets["sessions"]
            self.assertEqual(sessions["scope"], "history_surface")
            self.assertEqual(sessions["history_category"], "sessions")
            self.assertIn("session_index.jsonl", sessions["protected_paths"])
            self.assertEqual(
                sessions["preserve_only_dependencies"],
                ["session_index.jsonl"],
            )
            config_snapshot = targets[
                "config.toml.before-openai-login.20260428-134805"
            ]
            self.assertEqual(
                config_snapshot["rewrite_policy"],
                "do_not_modify_in_place",
            )
            self.assertEqual(
                targets["state_5.sqlite.bak_20260604_2110"]["archive_bias"],
                "frozen_evidence_first",
            )
            self.assertEqual(
                targets["state_5.sqlite.bak_ui_probe_20260605_054407"]["archive_bias"],
                "frozen_evidence_first",
            )
            pandeng = targets["project_assets/pandeng"]
            self.assertEqual(pandeng["scope"], "namespace_surface")
            compat_paths = [
                item["path"]
                for item in pandeng["compatibility_entrypoints"]
            ]
            self.assertEqual(
                compat_paths,
                ["pandeng_supervisor", "worktree_snapshots"],
            )
            self.assertEqual(pandeng["namespace_type"], "project_overlay")
            preserve_only = {
                item["target"]
                for item in payload["preserve_only_history_surfaces"]
            }
            self.assertEqual(
                preserve_only,
                {
                    "archived_sessions",
                    "attachments",
                    "session_index.jsonl.bak_20260604_2109",
                    "session_index.jsonl",
                    "sessions_archive",
                },
            )

    def test_lifecycle_review_reports_candidates_without_mutation_or_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            session_path = root / "sessions/2026/05/11/large-session.jsonl"
            session_secret = "SESSION_CONTENT_SHOULD_NOT_APPEAR"
            session_path.parent.mkdir(parents=True, exist_ok=True)
            session_path.write_text(
                json.dumps(
                    {
                        "timestamp": _fresh_timestamp(-172800),
                        "type": "event_msg",
                        "payload": {
                            "type": "user_message",
                            "message": session_secret + ("x" * (1024 * 1024 + 1)),
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            _write_file(root / ".tmp/lifecycle-candidate.tmp", "t" * (1024 * 1024 + 1))

            result = self.run_lifecycle_review(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(session_secret, result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["layout_version"], manifest["layout_version"])
            self.assertTrue(payload["privacy"]["report_only"])
            self.assertFalse(payload["privacy"]["raw_session_content_read"])
            self.assertFalse(payload["privacy"]["raw_session_content_emitted"])
            self.assertFalse(payload["privacy"]["mutated_files"])
            self.assertFalse(payload["privacy"]["hard_delete_performed"])
            self.assertFalse(payload["privacy"]["runtime_rotation_performed"])
            self.assertFalse(payload["privacy"]["archive_move_performed"])
            self.assertEqual(payload["thresholds"]["large_session_mb"], 1)
            self.assertEqual(payload["thresholds"]["large_runtime_mb"], 1)
            self.assertGreaterEqual(payload["summary"]["session_candidate_count"], 1)
            self.assertGreaterEqual(payload["summary"]["runtime_candidate_count"], 4)
            session_candidates = {
                item["path"]: item
                for item in payload["session_file_candidates"]
            }
            candidate = session_candidates["sessions/2026/05/11/large-session.jsonl"]
            self.assertIn("large_session_file", candidate["reasons"])
            self.assertTrue(candidate["requires_manual_review"])
            runtime_candidates = {
                item["target"]: item
                for item in payload["runtime_candidates"]
            }
            self.assertIn(".tmp", runtime_candidates)
            self.assertIn("temp_surface_has_files", runtime_candidates[".tmp"]["reasons"])
            self.assertFalse(runtime_candidates[".tmp"]["mutation_performed"])
            buckets = {
                item["target"]: item
                for item in payload["history_bucket_summaries"]
            }
            self.assertIn("sessions", buckets)
            self.assertFalse(buckets["sessions"]["mutation_performed"])

    def test_migration_review_exposes_reference_mirror_candidate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            candidate_contract = {
                "schema_version": 1,
                "generated_for_layout_version": manifest["layout_version"],
                "candidates": [
                    {
                        "id": "reference_mirrors_upstream_audit_phase14",
                        "selector_type": "namespace_type",
                        "selector": "reference_bundle",
                        "target": "project_assets/reference_mirrors",
                        "candidate_kind": "compatibility_preserving_namespace_archive_candidate",
                        "phase": "phase14",
                        "scope_root": "project_assets/reference_mirrors/upstream_audit",
                        "compatibility_entrypoints": ["upstream_audit"],
                        "protected_paths": [
                            "project_assets/reference_mirrors",
                            "project_assets/reference_mirrors/upstream_audit",
                            "upstream_audit",
                        ],
                        "preconditions": ["fixture"],
                        "planned_steps": ["fixture"],
                        "forbidden_actions": ["fixture"],
                        "validation_commands": ["fixture"],
                    }
                ],
            }
            _write_file(
                root / "core/control_plane/codex_home_migration_candidates.json",
                json.dumps(candidate_contract, indent=2),
            )

            result = self.run_migration_review(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["layout_version"], manifest["layout_version"])
            self.assertEqual(payload["summary"]["total_candidates"], 1)
            self.assertEqual(
                payload["summary"]["candidate_ids"],
                ["reference_mirrors_upstream_audit_phase14"],
            )
            self.assertTrue(payload["summary"]["all_compatibility_entrypoints_resolve"])
            candidate = payload["candidates"][0]
            self.assertEqual(
                candidate["target"],
                "project_assets/reference_mirrors",
            )
            self.assertTrue(candidate["all_compatibility_entrypoints_resolve"])
            self.assertEqual(
                candidate["compatibility_status"][0]["path"],
                "upstream_audit",
            )

    def test_migration_candidate_wrong_compatibility_target_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            contract_path = root / "core/control_plane/codex_home_migration_candidates.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["candidates"][0]["scope_root"] = "project_assets/reference_mirrors/not_upstream"
            contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn(
                "migration_candidates:scope_root:reference_mirrors_upstream_audit_phase14",
                failed,
            )
            self.assertIn(
                "migration_candidates:compat_target:reference_mirrors_upstream_audit_phase14:upstream_audit",
                failed,
            )

    def test_migration_candidate_missing_protected_entrypoint_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            contract_path = root / "core/control_plane/codex_home_migration_candidates.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["candidates"][0]["protected_paths"] = [
                "project_assets/reference_mirrors",
                "project_assets/reference_mirrors/upstream_audit",
            ]
            contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn(
                "migration_candidates:compat_protected:reference_mirrors_upstream_audit_phase14:upstream_audit",
                failed,
            )

    def test_broken_compatibility_symlink_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            bad_link = root / "pandeng_supervisor"
            bad_link.unlink()
            bad_link.symlink_to("project_assets/pandeng/not_supervisor")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn("compat:pandeng_supervisor", failed)

    def test_forbidden_trusted_project_prefix_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path, extra_project_key="/tmp/regression_case")
            _write_root_index(root)

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn("config:forbidden_project_key_prefixes", failed)

    def test_root_surface_index_missing_entry_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)
            index_path = root / "core/control_plane/codex_home_surface_index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["root_surfaces"] = [
                entry for entry in index["root_surfaces"] if entry["path"] != "README.md"
            ]
            index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn("root_index:coverage", failed)

    def test_root_surface_index_allows_stale_optional_runtime_surface(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)
            optional_sidecar = root / "goals_1.sqlite-wal"
            optional_sidecar.unlink()
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            checks = {check["name"]: check for check in payload["checks"]}
            self.assertTrue(checks["root_index:coverage"]["ok"])
            self.assertTrue(checks["root_index:goals_1.sqlite-wal"]["ok"])

    def test_indexed_authoritative_runtime_root_must_be_manifest_surface(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            config_path = root / "config.toml"
            _write_config(config_path)
            extra = root / "extra_runtime.sqlite"
            _write_file(extra, "data\n")
            _write_root_index(root)
            index_path = root / "core/control_plane/codex_home_surface_index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            for entry in index["root_surfaces"]:
                if entry["path"] == "extra_runtime.sqlite":
                    entry["layer"] = "runtime"
                    entry["status"] = "authoritative_root"
                    entry["category"] = "runtime_state"
                    break
            index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn("root_index:runtime_manifest_alignment", failed)

    def test_namespace_registry_missing_manifest_namespace_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            registry_path = root / "project_assets/namespace_registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["namespaces"] = [
                entry for entry in registry["namespaces"] if entry["id"] != "codex_home"
            ]
            registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn("namespace_registry:ids", failed)

    def test_runtime_registry_missing_surface_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            registry_path = root / "runtime/runtime_surface_registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["surfaces"] = [
                entry for entry in registry["surfaces"] if entry["root_path"] != "installation_id"
            ]
            registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn("runtime_registry:root_paths", failed)

    def test_history_registry_mirror_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            registry_path = root / "history/history_surface_registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            for entry in registry["surfaces"]:
                if entry["root_path"] == "session_index.jsonl":
                    entry["mirror_path"] = "history/wrong_session_index.jsonl"
                    break
            registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn("history_registry:mirror:session_index.jsonl", failed)

    def test_core_registry_missing_surface_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            registry_path = root / "core/core_surface_registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["surfaces"] = [
                entry for entry in registry["surfaces"] if entry["root_path"] != "AGENTS.md"
            ]
            registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn("core_registry:root_paths", failed)

    def test_namespace_standards_reject_overlay_without_supervisor(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            registry_path = root / "project_assets/namespace_registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            for namespace in registry["namespaces"]:
                if namespace["id"] == "system_cleanup":
                    namespace["subsurfaces"] = []
                    break
            registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn("namespace_registry:subsurfaces:system_cleanup", failed)

    def test_namespace_standards_unknown_type_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            registry_path = root / "project_assets/namespace_registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            for namespace in registry["namespaces"]:
                if namespace["id"] == "system_cleanup":
                    namespace["type"] = "unknown_type"
                    break
            registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn("namespace_standards:type:system_cleanup", failed)

    def test_history_snapshot_policy_kind_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            policy_path = root / "history/config_snapshot_policy.json"
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["surfaces"][0]["snapshot_kind"] = "wrong_kind"
            policy_path.write_text(json.dumps(policy, indent=2), encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn(
                "history_snapshot_policy:snapshot_kind:config.toml.before-openai-login.20260428-134805",
                failed,
            )

    def test_runtime_class_policy_mirror_requirement_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            policy_path = root / "runtime/runtime_class_policy.json"
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            for entry in policy["allowed_categories"]:
                if entry["category"] == "runtime_marker":
                    entry["mirror_required"] = True
                    break
            policy_path.write_text(json.dumps(policy, indent=2), encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn("runtime_class_policy:mirror_required:runtime_marker", failed)

    def test_runtime_class_policy_unknown_surface_category_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            registry_path = root / "runtime/runtime_surface_registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            for entry in registry["surfaces"]:
                if entry["root_path"] == "cache":
                    entry["category"] = "unknown_category"
                    break
            registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn("runtime_class_policy:surface:cache", failed)

    def test_operations_policy_missing_namespace_coverage_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            policy_path = root / "core/control_plane/codex_home_lifecycle_operations.json"
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["surface_policies"] = [
                entry
                for entry in policy["surface_policies"]
                if not (
                    entry["selector_type"] == "namespace_type"
                    and entry["selector"] == "shared_asset_bundle"
                )
            ]
            policy_path.write_text(json.dumps(policy, indent=2), encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn(
                "operations_policy:coverage:namespace:shared_asset_bundle",
                failed,
            )

    def test_operations_policy_hard_delete_must_stay_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            policy_path = root / "core/control_plane/codex_home_lifecycle_operations.json"
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["global_rules"]["allow_hard_delete"] = True
            policy_path.write_text(json.dumps(policy, indent=2), encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn("operations_policy:allow_hard_delete", failed)

    def test_generated_contract_layout_version_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            registry_path = root / "runtime/runtime_surface_registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["generated_for_layout_version"] = "wrong.phase"
            registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn(
                "generated_contract:runtime/runtime_surface_registry.json:layout_version",
                failed,
            )

    def test_config_must_require_clarification_before_unclear_work(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            text = config_path.read_text(encoding="utf-8")
            text = text.replace(
                "Ask concise clarifying questions before substantive work when the user's goal, constraints, success criteria, or risk tolerance are materially unclear; do not guess the user's intent from habit, prior projects, or agent experience.\n",
                "",
            )
            config_path.write_text(text, encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn("config:clarify_before_substantive_work", failed)

    def test_config_must_require_evidence_before_conclusion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            text = config_path.read_text(encoding="utf-8")
            text = text.replace(
                "Do not present memory, experience, or plausibility as fact. If a conclusion is not backed by fresh evidence or a clearly cited source, label it as an inference, assumption, or uncertainty.\n",
                "",
            )
            config_path.write_text(text, encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn("config:evidence_before_conclusion", failed)

    def test_execution_mode_policy_missing_runtime_coverage_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            policy_path = root / "core/control_plane/codex_home_execution_modes.json"
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            policy["selector_modes"] = [
                entry
                for entry in policy["selector_modes"]
                if not (
                    entry["selector_type"] == "runtime_category"
                    and entry["selector"] == "temp"
                )
            ]
            policy_path.write_text(json.dumps(policy, indent=2), encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn("execution_mode_policy:coverage:runtime:temp", failed)

    def test_execution_mode_policy_requires_single_base_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            policy_path = root / "core/control_plane/codex_home_execution_modes.json"
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            for entry in policy["selector_modes"]:
                if (
                    entry["selector_type"] == "namespace_type"
                    and entry["selector"] == "shared_asset_bundle"
                ):
                    entry["execution_modes"] = [
                        "reversible_only",
                        "archive_only",
                        "tool_only",
                        "manual_review_only",
                    ]
                    break
            policy_path.write_text(json.dumps(policy, indent=2), encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn(
                "execution_mode_policy:base_mode:namespace_type:shared_asset_bundle",
                failed,
            )

    def test_invalid_namespace_registry_json_reports_failure_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            registry_path = root / "project_assets/namespace_registry.json"
            registry_path.write_text("{bad json\n", encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn("namespace_registry:json", failed)

    def test_supervisor_workflow_protocol_gate_missing_phrase_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            protocol_path = (
                root
                / "project_assets/codex_home/supervisor/child_execution_protocol.md"
            )
            text = protocol_path.read_text(encoding="utf-8")
            text = text.replace(
                "No formal run and no new patch unless both:\n",
                "",
            )
            protocol_path.write_text(text, encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn("supervisor_workflow:pack:codex_home:protocol_gate", failed)

    def test_supervisor_workflow_only_question_empty_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            ledger_path = root / "project_assets/codex_home/supervisor/supervisor_ledger.md"
            text = ledger_path.read_text(encoding="utf-8")
            text = text.replace(
                "- Decide whether to pilot the workflow in a real target repo without copying Trellis.\n",
                "",
            )
            ledger_path.write_text(text, encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn(
                "supervisor_workflow:pack:codex_home:only_question_nonempty",
                failed,
            )

    def test_supervisor_workflow_forbidden_section_stale_marker_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            ledger_path = root / "project_assets/codex_home/supervisor/supervisor_ledger.md"
            text = ledger_path.read_text(encoding="utf-8")
            text = text.replace(
                "- No destructive changes.\n",
                "- No destructive changes.\n- Do not drift back to layout governance.\n",
            )
            ledger_path.write_text(text, encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn(
                "supervisor_workflow:pack:codex_home:forbidden_next_round_no_stale_markers",
                failed,
            )

    def test_supervisor_workflow_promotion_gate_stale_marker_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            ledger_path = root / "project_assets/codex_home/supervisor/supervisor_ledger.md"
            text = ledger_path.read_text(encoding="utf-8")
            text = text.replace(
                "- project_task_workflow_smoke, layout audit, context-firewall audit, and default acceptance stay green.\n",
                (
                    "- project_task_workflow_smoke, layout audit, context-firewall audit, and default acceptance stay green.\n"
                    "- a second bounded migration candidate is specified.\n"
                ),
            )
            ledger_path.write_text(text, encoding="utf-8")

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn(
                "supervisor_workflow:pack:codex_home:promotion_gate_no_stale_markers",
                failed,
            )

    def test_project_task_workflow_missing_creation_boundary_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / ".codex"
            root.mkdir()
            manifest = json.loads(PROD_MANIFEST.read_text(encoding="utf-8"))
            manifest["home_root"] = root.as_posix()
            _materialize_layout(root, manifest)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            config_path = root / "config.toml"
            _write_config(config_path)
            _write_root_index(root)

            workflow_doc = root / "core/control_plane/project_task_workflow.md"
            text = workflow_doc.read_text(encoding="utf-8")
            workflow_doc.write_text(
                text.replace("Creating a task records planning state only", ""),
                encoding="utf-8",
            )

            result = self.run_audit(root, manifest_path, config_path)
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            failed = [check["name"] for check in payload["checks"] if not check["ok"]]
            self.assertIn("project_task_workflow:doc_contract", failed)


if __name__ == "__main__":
    unittest.main()
