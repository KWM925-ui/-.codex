#!/usr/bin/env python3
"""Run the bounded acceptance checks for the productized Codex home."""

import argparse
import json
import os
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


DEFAULT_ROOT = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
SCRIPT_DIR = Path(__file__).resolve().parent
SAFE_REAL_AUTH_ENV_VARS = ["OPENAI_API_KEY"]


@dataclass
class StepResult:
    name: str
    ok: bool
    command: List[str] = field(default_factory=list)
    returncode: int = 0
    summary: str = ""
    details: Dict[str, object] = field(default_factory=dict)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a bounded Codex-home acceptance suite without writing reports "
            "or mutating runtime/history data."
        ),
    )
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT),
        help="Codex home root. Defaults to CODEX_HOME or ~/.codex.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON.",
    )
    parser.add_argument(
        "--include-real-smoke",
        action="store_true",
        help=(
            "Also run isolated real codex exec patch/no-op smoke presets. "
            "Defaults to off because this spends model calls."
        ),
    )
    parser.add_argument(
        "--codex-bin",
        default=os.environ.get("CODEX_BIN") or "codex",
        help="Codex executable for --include-real-smoke.",
    )
    parser.add_argument(
        "--real-timeout-seconds",
        type=int,
        default=240,
        help="Timeout per real-runner trial. Defaults to 240 seconds.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned checks without executing them.",
    )
    return parser


def _python_command(script_name: str, root: Path, *extra: str) -> List[str]:
    return [
        sys.executable,
        "-B",
        str(SCRIPT_DIR / script_name),
        "--root",
        str(root),
        *extra,
    ]


def _run_command(
    name: str,
    command: List[str],
    extra_env: Optional[Dict[str, str]] = None,
) -> StepResult:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra_env:
        env.update(extra_env)
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    output = completed.stdout.strip()
    error = completed.stderr.strip()
    summary = _summarize_command_output(name, completed.returncode, output, error)
    return StepResult(
        name=name,
        ok=completed.returncode == 0,
        command=command,
        returncode=completed.returncode,
        summary=summary,
        details={
            "stdout_tail": output[-1200:],
            "stderr_tail": error[-1200:],
        },
    )


def _check_real_auth_preflight(env: Dict[str, str]) -> StepResult:
    present = [
        name
        for name in SAFE_REAL_AUTH_ENV_VARS
        if env.get(name, "").strip()
    ]
    ok = bool(present)
    if ok:
        summary = "通过，发现安全外部认证变量：%s" % ", ".join(present)
    else:
        summary = (
            "阻塞，未发现安全外部认证变量；不会复制 live config/auth/token/key"
        )
    return StepResult(
        name="real_auth_preflight",
        ok=ok,
        summary=summary,
        details={
            "safe_auth_env_candidates": SAFE_REAL_AUTH_ENV_VARS,
            "present_auth_env_vars": present,
            "copied_live_config": False,
            "copied_live_auth": False,
            "blocked_without_model_call": not ok,
        },
    )


def _summarize_command_output(
    name: str,
    returncode: int,
    stdout: str,
    stderr: str,
) -> str:
    if returncode != 0:
        source = stderr or stdout
        return source.splitlines()[-1] if source else "command failed"

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return "通过"

    if name == "layout_audit":
        return "通过，结构审计 ok=%s" % payload.get("ok")
    if name == "context_firewall_audit":
        checks = payload.get("checks", [])
        return "通过，上下文合同 %d/%d" % (
            sum(1 for check in checks if check.get("ok")),
            len(checks),
        )
    if name == "agent_e2e_offline":
        controlled_ab = next(
            (
                item
                for item in payload.get("evals", [])
                if item.get("id") == "controlled_ab"
            ),
            {},
        )
        current = controlled_ab.get("strategies", {}).get("current_full_codex", {})
        return "通过，离线端到端 current_full_codex=%s/%s" % (
            current.get("passed"),
            current.get("tasks"),
        )
    if name == "project_task_workflow_smoke":
        return "通过，项目本地任务工作流 smoke 通过"
    if name.startswith("real_"):
        evals = payload.get("evals", [])
        wanted_id = {
            "real_patch_smoke": "real_model_ab",
            "real_noop_smoke": "real_noop_boundary",
            "real_ambiguous_smoke": "real_ambiguous_boundary",
        }.get(name, "real_model_ab")
        real_eval = next(
            (
                item
                for item in evals
                if item.get("id") == wanted_id
            ),
            {},
        )
        return "通过，真实 smoke trials=%s failures=%s safety_blocks=%s" % (
            real_eval.get("trial_count", 0),
            len(real_eval.get("failures", [])),
            real_eval.get("provider_safety_blocks", 0),
        )
    return "通过"


def _current_temporary_eval_dirs() -> List[str]:
    tmp_dirs = []
    tmp_root = Path("/tmp")
    for pattern in ("codex-agent-e2e-*", "codex-runner-probe-*"):
        tmp_dirs.extend(sorted(path.as_posix() for path in tmp_root.glob(pattern)))
    return sorted(tmp_dirs)


def _owned_temporary_eval_dirs(
    tmp_dirs: List[str],
    temp_owner_id: Optional[str],
) -> List[str]:
    if not temp_owner_id:
        return tmp_dirs
    owner_markers = [
        "/codex-agent-e2e-%s-" % temp_owner_id,
        "/codex-runner-probe-%s-" % temp_owner_id,
    ]
    return sorted(
        path for path in tmp_dirs if any(marker in path for marker in owner_markers)
    )


def _check_hygiene(root: Path, temp_owner_id: Optional[str] = None) -> StepResult:
    bytecode_paths = sorted(
        path.relative_to(root).as_posix()
        for path in (root / "core/control_plane").rglob("*")
        if path.name == "__pycache__" or path.suffix == ".pyc"
    )
    observed_tmp_dirs = _current_temporary_eval_dirs()
    blocking_tmp_dirs = _owned_temporary_eval_dirs(observed_tmp_dirs, temp_owner_id)
    nonblocking_tmp_dirs = sorted(set(observed_tmp_dirs) - set(blocking_tmp_dirs))

    temp_trusted = _temporary_trusted_project_keys(root)
    ok = not bytecode_paths and not blocking_tmp_dirs and not temp_trusted
    details = {
        "bytecode_paths": bytecode_paths,
        "temporary_eval_dirs": blocking_tmp_dirs,
        "other_temporary_eval_dirs": nonblocking_tmp_dirs,
        "temporary_eval_dirs_observed": observed_tmp_dirs,
        "temp_owner_id": temp_owner_id or "",
        "temporary_trusted_projects": temp_trusted,
    }
    if ok:
        if nonblocking_tmp_dirs:
            summary = (
                "通过，没有本次验收残留；检测到其他并发评测临时目录 %d 个，已单独列出"
                % len(nonblocking_tmp_dirs)
            )
        else:
            summary = "通过，没有 bytecode、本次评测临时目录、临时 trusted project 残留"
    else:
        summary = "发现本次残留：bytecode=%d tmp_dirs=%d trusted_projects=%d" % (
            len(bytecode_paths),
            len(blocking_tmp_dirs),
            len(temp_trusted),
        )
    return StepResult(
        name="hygiene",
        ok=ok,
        summary=summary,
        details=details,
    )


def _temporary_trusted_project_keys(root: Path) -> List[str]:
    config_path = root / "config.toml"
    if not config_path.exists():
        return []
    keys = []
    prefix = '[projects."'
    suffix = '"]'
    for line in config_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix) and stripped.endswith(suffix):
            key = stripped[len(prefix):-len(suffix)]
            if key.startswith(("/tmp/codex-agent-e2e-", "/tmp/codex-runner-probe-")):
                keys.append(key)
    return sorted(keys)


def _planned_commands(
    root: Path,
    include_real_smoke: bool,
    codex_bin: str,
    real_timeout_seconds: int,
) -> List[StepResult]:
    steps = [
        StepResult(
            name="layout_audit",
            ok=True,
            command=_python_command("audit_codex_home_layout.py", root, "--json"),
            summary="结构审计",
        ),
        StepResult(
            name="context_firewall_audit",
            ok=True,
            command=_python_command("audit_context_firewall.py", root, "--json"),
            summary="上下文合同审计",
        ),
        StepResult(
            name="agent_e2e_offline",
            ok=True,
            command=_python_command("run_agent_e2e_evals.py", root, "--json"),
            summary="离线端到端评测",
        ),
        StepResult(
            name="project_task_workflow_smoke",
            ok=True,
            command=[
                sys.executable,
                "-B",
                "-m",
                "unittest",
                str(SCRIPT_DIR.parent / "tests/test_project_task_workflow.py"),
            ],
            summary="项目本地任务工作流 smoke",
        ),
    ]
    if include_real_smoke:
        real_common = [
            "--real-runner",
            "codex",
            "--codex-bin",
            codex_bin,
            "--real-timeout-seconds",
            str(real_timeout_seconds),
            "--fail-fast",
            "--progress",
            "--json",
        ]
        steps.extend(
            [
                StepResult(
                    name="real_auth_preflight",
                    ok=True,
                    summary="真实 smoke 安全认证预检",
                ),
                StepResult(
                    name="real_patch_smoke",
                    ok=True,
                    command=_python_command(
                        "run_agent_e2e_evals.py",
                        root,
                        "--real-preset",
                        "patch-smoke",
                        *real_common,
                    ),
                    summary="真实 patch smoke",
                ),
                StepResult(
                    name="real_noop_smoke",
                    ok=True,
                    command=_python_command(
                        "run_agent_e2e_evals.py",
                        root,
                        "--real-preset",
                        "noop-smoke",
                        *real_common,
                    ),
                    summary="真实 no-op smoke",
                ),
                StepResult(
                    name="real_ambiguous_smoke",
                    ok=True,
                    command=_python_command(
                        "run_agent_e2e_evals.py",
                        root,
                        "--real-preset",
                        "ambiguous-smoke",
                        *real_common,
                    ),
                    summary="真实模糊需求 smoke",
                ),
            ]
        )
    return steps


def _run_acceptance(args: argparse.Namespace) -> Dict[str, object]:
    root = Path(args.root).resolve()
    temp_owner_id = "acceptance-%s" % uuid.uuid4().hex[:12]
    planned = _planned_commands(
        root,
        args.include_real_smoke,
        args.codex_bin,
        args.real_timeout_seconds,
    )
    if args.dry_run:
        return {
            "ok": True,
            "root": root.as_posix(),
            "dry_run": True,
            "include_real_smoke": args.include_real_smoke,
            "steps": [asdict(step) for step in planned],
        }

    results: List[StepResult] = []
    for step in planned:
        if step.name == "real_auth_preflight":
            result = _check_real_auth_preflight(os.environ)
        else:
            result = _run_command(
                step.name,
                step.command,
                {"CODEX_AGENT_E2E_OWNER_ID": temp_owner_id}
                if step.name == "agent_e2e_offline" or step.name.startswith("real_")
                else None,
            )
        results.append(result)
        if not result.ok:
            break

    results.append(_check_hygiene(root, temp_owner_id))

    ok = bool(results) and all(result.ok for result in results)
    return {
        "ok": ok,
        "root": root.as_posix(),
        "dry_run": False,
        "include_real_smoke": args.include_real_smoke,
        "steps": [asdict(result) for result in results],
    }


def _print_human(payload: Dict[str, object]) -> None:
    status = "通过" if payload["ok"] else "失败"
    print("总验收：%s" % status)
    for raw_step in payload["steps"]:  # type: ignore[index]
        step = raw_step  # type: ignore[assignment]
        marker = "OK" if step["ok"] else "FAIL"
        print("- %s %s：%s" % (marker, step["name"], step["summary"]))
        if not step["ok"]:
            command = " ".join(step.get("command") or [])
            if command:
                print("  命令：%s" % command)
            details = step.get("details") or {}
            stderr_tail = details.get("stderr_tail") if isinstance(details, dict) else ""
            stdout_tail = details.get("stdout_tail") if isinstance(details, dict) else ""
            tail = stderr_tail or stdout_tail
            if tail:
                print("  末尾输出：%s" % tail)


def main() -> int:
    args = _build_parser().parse_args()
    payload = _run_acceptance(args)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        _print_human(payload)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
