import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

THIS_DIR = Path(__file__).resolve().parent
SCRIPT = THIS_DIR.parent / "scripts/project_task_workflow.py"


class ProjectTaskWorkflowTests(unittest.TestCase):
    def run_workflow(self, project_root: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                *args,
                "--project-root",
                str(project_root),
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def create_repo(self, root: Path) -> Path:
        project_root = root / "repo"
        project_root.mkdir()
        (project_root / "AGENTS.md").write_text("repo rules\n", encoding="utf-8")
        return project_root

    def test_task_lifecycle_has_separate_plan_and_implementation_gate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = self.create_repo(Path(tmpdir))
            (project_root / "docs").mkdir()
            (project_root / "src").mkdir()
            (project_root / "docs/auth.md").write_text("auth spec\n", encoding="utf-8")
            (project_root / "src/app.py").write_text("print('x')\n", encoding="utf-8")

            created = self.run_workflow(
                project_root,
                "create",
                "Add Login Flow",
                "--description",
                "Implement login safely",
                "--session-key",
                "session-a",
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            created_payload = json.loads(created.stdout)
            self.assertTrue(created_payload["ok"])
            self.assertEqual(created_payload["status"], "planning")
            self.assertFalse(created_payload["implementation_allowed"])

            task_id = created_payload["task_id"]
            task_dir = project_root / ".codex/tasks" / task_id
            self.assertTrue((task_dir / "task.json").is_file())
            self.assertTrue((task_dir / "prd.md").is_file())
            self.assertTrue((task_dir / "research").is_dir())
            session_pointer = (
                project_root / ".codex/task_runtime/sessions/session-a.json"
            )
            self.assertTrue(session_pointer.is_file())
            self.assertEqual(
                json.loads(session_pointer.read_text(encoding="utf-8"))["active_task"],
                ".codex/tasks/%s" % task_id,
            )

            blocked_start = self.run_workflow(project_root, "start", task_id)
            self.assertNotEqual(blocked_start.returncode, 0)
            blocked_payload = json.loads(blocked_start.stdout)
            self.assertIn("--confirm-plan-reviewed", blocked_payload["error"])
            still_planning = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(still_planning["status"], "planning")

            context_ok = self.run_workflow(
                project_root,
                "add-context",
                task_id,
                "implement",
                "docs/auth.md",
                "Authentication constraints",
            )
            self.assertEqual(context_ok.returncode, 0, context_ok.stderr)
            manifest_rows = (task_dir / "implement.jsonl").read_text(encoding="utf-8")
            self.assertIn("docs/auth.md", manifest_rows)

            context_blocked = self.run_workflow(
                project_root,
                "add-context",
                task_id,
                "implement",
                "src/app.py",
                "Source file that should be read just in time",
            )
            self.assertNotEqual(context_blocked.returncode, 0)
            blocked_context_payload = json.loads(context_blocked.stdout)
            self.assertIn("source-like file", blocked_context_payload["error"])

            started = self.run_workflow(
                project_root,
                "start",
                task_id,
                "--confirm-plan-reviewed",
                "--reviewed-by",
                "user",
                "--session-key",
                "session-a",
            )
            self.assertEqual(started.returncode, 0, started.stderr)
            started_task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(started_task["status"], "in_progress")
            self.assertTrue(started_task["implementation_confirmed"])
            self.assertEqual(started_task["plan_reviewed_by"], "user")

            validation = self.run_workflow(project_root, "validate")
            self.assertEqual(validation.returncode, 0, validation.stderr)
            self.assertTrue(json.loads(validation.stdout)["ok"])

            completed = self.run_workflow(
                project_root,
                "complete",
                task_id,
                "--evidence",
                "unit tests passed",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertFalse(session_pointer.exists())

            archived = self.run_workflow(project_root, "archive", task_id)
            self.assertEqual(archived.returncode, 0, archived.stderr)
            archived_payload = json.loads(archived.stdout)
            self.assertTrue(Path(archived_payload["archive_dir"]).is_dir())
            self.assertFalse(task_dir.exists())

            final_validation = self.run_workflow(
                project_root,
                "validate",
                "--include-archive",
            )
            self.assertEqual(final_validation.returncode, 0, final_validation.stderr)
            self.assertTrue(json.loads(final_validation.stdout)["ok"])

    def test_project_root_must_already_exist_and_title_must_be_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_root = Path(tmpdir) / "missing-repo"
            missing = self.run_workflow(missing_root, "create", "Will Not Create Root")
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("project root does not exist", json.loads(missing.stdout)["error"])
            self.assertFalse(missing_root.exists())

            project_root = self.create_repo(Path(tmpdir))
            empty_title = self.run_workflow(project_root, "create", "")
            self.assertNotEqual(empty_title.returncode, 0)
            self.assertIn("task title is required", json.loads(empty_title.stdout)["error"])

    def test_context_manifest_rejects_escapes_and_empty_reasons(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_root = self.create_repo(root)
            (project_root / "docs").mkdir()
            (project_root / "docs/spec.md").write_text("stable spec\n", encoding="utf-8")
            (root / "outside.md").write_text("outside\n", encoding="utf-8")

            created = self.run_workflow(project_root, "create", "Bounded Context")
            self.assertEqual(created.returncode, 0, created.stderr)
            task_id = json.loads(created.stdout)["task_id"]

            escaped = self.run_workflow(
                project_root,
                "add-context",
                task_id,
                "implement",
                "../outside.md",
                "outside file",
            )
            self.assertNotEqual(escaped.returncode, 0)
            self.assertIn("path escapes project root", json.loads(escaped.stdout)["error"])

            empty_reason = self.run_workflow(
                project_root,
                "add-context",
                task_id,
                "implement",
                "docs/spec.md",
                "   ",
            )
            self.assertNotEqual(empty_reason.returncode, 0)
            self.assertIn("context reason is required", json.loads(empty_reason.stdout)["error"])

            valid = self.run_workflow(
                project_root,
                "add-context",
                task_id,
                "check",
                "docs/spec.md",
                "Check expected behavior",
            )
            self.assertEqual(valid.returncode, 0, valid.stderr)

    def test_force_archive_clears_active_session_pointer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = self.create_repo(Path(tmpdir))
            created = self.run_workflow(
                project_root,
                "create",
                "Archive Active Planning Task",
                "--session-key",
                "session-a",
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            task_id = json.loads(created.stdout)["task_id"]
            session_pointer = (
                project_root / ".codex/task_runtime/sessions/session-a.json"
            )
            self.assertTrue(session_pointer.exists())

            archived = self.run_workflow(project_root, "archive", task_id, "--force")
            self.assertEqual(archived.returncode, 0, archived.stderr)
            self.assertFalse(session_pointer.exists())

            validation = self.run_workflow(project_root, "validate", "--include-archive")
            self.assertEqual(validation.returncode, 0, validation.stderr)
            self.assertTrue(json.loads(validation.stdout)["ok"])

    def test_validate_reports_bad_session_pointers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = self.create_repo(Path(tmpdir))
            created = self.run_workflow(project_root, "create", "Validate Sessions")
            self.assertEqual(created.returncode, 0, created.stderr)
            task_id = json.loads(created.stdout)["task_id"]
            completed = self.run_workflow(
                project_root,
                "complete",
                task_id,
                "--force",
                "--evidence",
                "forced for fixture",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            session_root = project_root / ".codex/task_runtime/sessions"
            session_root.mkdir(parents=True, exist_ok=True)
            (session_root / "escaped.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "workflow_kind": "codex_project_task",
                        "session_key": "escaped",
                        "active_task": "../outside",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (session_root / "completed.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "workflow_kind": "codex_project_task",
                        "session_key": "completed",
                        "active_task": ".codex/tasks/%s" % task_id,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            validation = self.run_workflow(project_root, "validate")
            self.assertNotEqual(validation.returncode, 0)
            payload = json.loads(validation.stdout)
            problems = [issue["problem"] for issue in payload["issues"]]
            self.assertIn(
                "path escapes project root: %s" % (project_root / "../outside").resolve(),
                problems,
            )
            self.assertIn("active task must be planning or in_progress", problems)


if __name__ == "__main__":
    unittest.main()
