#!/usr/bin/env python3
"""Run the bounded acceptance checks for the productized Codex home."""

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from agent_e2e_common import _temporary_trusted_project_keys
from agent_e2e_real_runner import _live_provider_config_text


DEFAULT_ROOT = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
SCRIPT_DIR = Path(__file__).resolve().parent
SAFE_REAL_AUTH_ENV_VARS = ["OPENAI_API_KEY"]
GATE_PROFILES = {
    "quick": "fast deterministic gate for ordinary control-plane edits",
    "standard": "quick gate plus the full control-plane unit suite",
    "full": "standard gate plus offline profile sweeps",
    "release": "full gate plus public export hygiene checks",
    "real": "full gate plus real codex exec smoke checks",
    "saturation": (
        "full gate plus current-full real-runner and shell regression batches"
    ),
}


@dataclass
class StepResult:
    name: str
    ok: bool
    command: List[str] = field(default_factory=list)
    returncode: int = 0
    summary: str = ""
    details: Dict[str, object] = field(default_factory=dict)
    budget_seconds: float = 0.0
    duration_seconds: float = 0.0
    budget_ok: Optional[bool] = None
    cost_class: str = "cheap"


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
        "--gate-profile",
        choices=sorted(GATE_PROFILES),
        default="quick",
        help=(
            "Acceptance depth. quick is the default fast gate; standard adds "
            "all unit tests; full adds offline profile sweeps; real and "
            "saturation spend model calls only when explicitly selected."
        ),
    )
    parser.add_argument(
        "--include-real-smoke",
        action="store_true",
        help=(
            "Also run isolated real codex exec patch/no-op smoke presets. "
            "Defaults to off because this spends model calls. This is implied "
            "by --gate-profile real."
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
        "--real-use-live-provider-config",
        action="store_true",
        help=(
            "For --include-real-smoke, let isolated real-runner checks copy "
            "only the active live model-provider fragment into temporary "
            "CODEX_HOME. Secret values are not printed and temp dirs are "
            "deleted after the run."
        ),
    )
    parser.add_argument(
        "--export-root",
        default="",
        help=(
            "Candidate public export repository root. Required by "
            "--gate-profile release."
        ),
    )
    parser.add_argument(
        "--fail-on-budget-overrun",
        action="store_true",
        help=(
            "Fail the acceptance payload when a step exceeds its soft runtime "
            "budget. Defaults to off so transient machine load is reported "
            "without hiding functional pass/fail status."
        ),
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


def _script_command(script_name: str, *extra: str) -> List[str]:
    return [
        sys.executable,
        "-B",
        str(SCRIPT_DIR / script_name),
        *extra,
    ]


def _run_command(
    name: str,
    command: List[str],
    budget_seconds: float = 0.0,
    cost_class: str = "cheap",
    extra_env: Optional[Dict[str, str]] = None,
) -> StepResult:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra_env:
        env.update(extra_env)
    started = time.monotonic()
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    duration_seconds = time.monotonic() - started
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
        budget_seconds=budget_seconds,
        duration_seconds=round(duration_seconds, 3),
        budget_ok=(
            duration_seconds <= budget_seconds
            if budget_seconds > 0 and completed.returncode == 0
            else None
        ),
        cost_class=cost_class,
    )


def _check_real_auth_preflight(
    env: Dict[str, str],
    root: Optional[Path] = None,
    use_live_provider_config: bool = False,
) -> StepResult:
    if use_live_provider_config:
        try:
            _live_provider_config_text(root or DEFAULT_ROOT)
        except ValueError as exc:
            return StepResult(
                name="real_auth_preflight",
                ok=False,
                summary="阻塞，live provider 配置不可用于隔离真实 runner：%s" % exc,
                details={
                    "safe_auth_env_candidates": SAFE_REAL_AUTH_ENV_VARS,
                    "present_auth_env_vars": [],
                    "copied_live_config": False,
                    "copied_live_auth": False,
                    "copied_live_provider_fragment": False,
                    "blocked_without_model_call": True,
                },
            )
        return StepResult(
            name="real_auth_preflight",
            ok=True,
            summary=(
                "通过，将使用 live provider 片段生成临时隔离配置；不输出密钥"
            ),
            details={
                "safe_auth_env_candidates": SAFE_REAL_AUTH_ENV_VARS,
                "present_auth_env_vars": [],
                "copied_live_config": False,
                "copied_live_auth": False,
                "copied_live_provider_fragment": True,
                "blocked_without_model_call": False,
            },
        )

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
            "copied_live_provider_fragment": False,
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
    if name.startswith("agent_e2e_offline"):
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
            "real_current_full": "real_model_ab",
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
    if name == "public_export_hygiene":
        checks = payload.get("checks", [])
        return "通过，公开导出卫生检查 %d/%d" % (
            sum(1 for check in checks if check.get("ok")),
            len(checks),
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
    started = time.monotonic()
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
    duration_seconds = time.monotonic() - started
    return StepResult(
        name="hygiene",
        ok=ok,
        summary=summary,
        details=details,
        budget_seconds=1.0,
        duration_seconds=round(duration_seconds, 3),
        budget_ok=(duration_seconds <= 1.0 if ok else None),
        cost_class="cheap",
    )


def _planned_hygiene() -> StepResult:
    return _result(
        name="hygiene",
        summary="验收卫生检查",
        budget_seconds=1.0,
        cost_class="cheap",
    )


def _unit_test_command(test_path: Path) -> List[str]:
    return [
        sys.executable,
        "-B",
        "-m",
        "unittest",
        test_path.as_posix(),
    ]


def _unit_test_discovery_command(root: Path) -> List[str]:
    return [
        sys.executable,
        "-B",
        "-m",
        "unittest",
        "discover",
        "-s",
        (root / "core/control_plane/tests").as_posix(),
        "-p",
        "test*.py",
    ]


def _public_export_command(export_root: str) -> List[str]:
    return _script_command(
        "audit_codex_public_export.py",
        "--export-root",
        export_root or "__missing_export_root__",
        "--json",
    )


def _shell_regression_command(script_name: str, prefix: str, count: int) -> List[str]:
    script_path = (SCRIPT_DIR / script_name).as_posix()
    return [
        "bash",
        "-lc",
        (
            "set -euo pipefail; "
            "run_root=\"$(mktemp -d /tmp/%s-XXXXXX)\"; "
            "cleanup() { rm -rf \"$run_root\"; }; "
            "trap cleanup EXIT; "
            "CODEX_REGRESSION_ATTEMPTS=\"${CODEX_REGRESSION_ATTEMPTS:-3}\" "
            "CODEX_REGRESSION_RETRY_SLEEP_SECONDS="
            "\"${CODEX_REGRESSION_RETRY_SLEEP_SECONDS:-20}\" "
            "\"$1\" %d \"继续，不要停\" \"$run_root\""
        )
        % (prefix, count),
        "bash",
        script_path,
    ]


def _result(
    name: str,
    summary: str,
    command: Optional[List[str]] = None,
    budget_seconds: float = 0.0,
    cost_class: str = "cheap",
) -> StepResult:
    return StepResult(
        name=name,
        ok=True,
        command=command or [],
        summary=summary,
        budget_seconds=budget_seconds,
        cost_class=cost_class,
    )


def _planned_commands(
    root: Path,
    gate_profile: str,
    include_real_smoke: bool,
    codex_bin: str,
    real_timeout_seconds: int,
    real_use_live_provider_config: bool,
    export_root: str = "",
) -> List[StepResult]:
    steps = [
        _result(
            name="layout_audit",
            command=_python_command("audit_codex_home_layout.py", root, "--json"),
            summary="结构审计",
            budget_seconds=2.0,
        ),
        _result(
            name="context_firewall_audit",
            command=_python_command("audit_context_firewall.py", root, "--json"),
            summary="上下文合同审计",
            budget_seconds=2.0,
        ),
        _result(
            name="agent_e2e_offline",
            command=_python_command("run_agent_e2e_evals.py", root, "--json"),
            summary="离线端到端评测",
            budget_seconds=8.0,
        ),
        _result(
            name="project_task_workflow_smoke",
            command=_unit_test_command(
                root / "core/control_plane/tests/test_project_task_workflow.py"
            ),
            summary="项目本地任务工作流 smoke",
            budget_seconds=2.0,
        ),
    ]

    if gate_profile in {"standard", "full", "release", "real", "saturation"}:
        steps.append(
            _result(
                name="control_plane_unittests",
                command=_unit_test_discovery_command(root),
                summary="完整控制面单测",
                budget_seconds=90.0,
                cost_class="medium",
            )
        )

    if gate_profile in {"full", "release", "real", "saturation"}:
        for profile in ("strict", "exploratory"):
            steps.append(
                _result(
                    name="agent_e2e_offline_%s" % profile,
                    command=_python_command(
                        "run_agent_e2e_evals.py",
                        root,
                        "--profile",
                        profile,
                        "--json",
                    ),
                    summary="离线端到端 profile=%s" % profile,
                    budget_seconds=8.0,
                    cost_class="medium",
                )
            )

    if gate_profile == "release":
        steps.append(
            _result(
                name="public_export_hygiene",
                command=_public_export_command(export_root),
                summary="公开导出卫生检查",
                budget_seconds=5.0,
                cost_class="medium",
            )
        )

    real_smoke_enabled = include_real_smoke or gate_profile == "real"
    if real_smoke_enabled or gate_profile == "saturation":
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
        if real_use_live_provider_config:
            real_common.append("--real-use-live-provider-config")
        steps.extend(
            [
                _result(
                    name="real_auth_preflight",
                    summary="真实 runner 安全认证预检",
                    budget_seconds=3.0,
                    cost_class="real",
                ),
            ]
        )
        if gate_profile == "saturation":
            steps.append(
                _result(
                    name="real_current_full",
                    command=_python_command(
                        "run_agent_e2e_evals.py",
                        root,
                        "--real-preset",
                        "current-full",
                        *real_common,
                    ),
                    summary="真实 current-full 批量评测",
                    budget_seconds=1800.0,
                    cost_class="saturation",
                )
            )
            shell_regressions = [
                (
                    "shell_autoadvance_regression",
                    "run_autoadvance_regression.sh",
                    "codex-saturation-autoadvance",
                    1,
                    600.0,
                ),
                (
                    "shell_worktree_remap_regression",
                    "run_worktree_remap_regression.sh",
                    "codex-saturation-worktree-remap",
                    1,
                    600.0,
                ),
                (
                    "shell_repeatability_widening_regression",
                    "run_repeatability_widening_regression.sh",
                    "codex-saturation-repeatability",
                    1,
                    900.0,
                ),
                (
                    "shell_repo_scale_regression",
                    "run_repo_scale_autoadvance_regression.sh",
                    "codex-saturation-repo-scale",
                    1,
                    900.0,
                ),
            ]
            for name, script_name, prefix, count, budget_seconds in shell_regressions:
                steps.append(
                    _result(
                        name=name,
                        command=_shell_regression_command(script_name, prefix, count),
                        summary=name.replace("_", " "),
                        budget_seconds=budget_seconds,
                        cost_class="saturation",
                    )
                )
        else:
            steps.extend(
                [
                    _result(
                        name="real_patch_smoke",
                        command=_python_command(
                            "run_agent_e2e_evals.py",
                            root,
                            "--real-preset",
                            "patch-smoke",
                            *real_common,
                        ),
                        summary="真实 patch smoke",
                        budget_seconds=600.0,
                        cost_class="real",
                    ),
                    _result(
                        name="real_noop_smoke",
                        command=_python_command(
                            "run_agent_e2e_evals.py",
                            root,
                            "--real-preset",
                            "noop-smoke",
                            *real_common,
                        ),
                        summary="真实 no-op smoke",
                        budget_seconds=600.0,
                        cost_class="real",
                    ),
                    _result(
                        name="real_ambiguous_smoke",
                        command=_python_command(
                            "run_agent_e2e_evals.py",
                            root,
                            "--real-preset",
                            "ambiguous-smoke",
                            *real_common,
                        ),
                        summary="真实模糊需求 smoke",
                        budget_seconds=300.0,
                        cost_class="real",
                    ),
                ]
            )
    return steps


def _attach_preflight_timing(
    result: StepResult,
    started: float,
    planned_step: StepResult,
) -> StepResult:
    duration_seconds = time.monotonic() - started
    result.budget_seconds = planned_step.budget_seconds
    result.duration_seconds = round(duration_seconds, 3)
    result.budget_ok = (
        duration_seconds <= planned_step.budget_seconds
        if planned_step.budget_seconds > 0 and result.ok
        else None
    )
    result.cost_class = planned_step.cost_class
    return result


def _total_budget_seconds(steps: List[StepResult]) -> float:
    return round(sum(step.budget_seconds for step in steps), 3)


def _total_duration_seconds(steps: List[StepResult]) -> float:
    return round(sum(step.duration_seconds for step in steps), 3)


def _budget_ok(steps: List[StepResult]) -> bool:
    return all(step.budget_ok is not False for step in steps)


def _run_acceptance(args: argparse.Namespace) -> Dict[str, object]:
    root = Path(args.root).resolve()
    temp_owner_id = "acceptance-%s" % uuid.uuid4().hex[:12]
    gate_profile = getattr(args, "gate_profile", "quick")
    if gate_profile not in GATE_PROFILES:
        raise ValueError("unknown gate profile: %s" % gate_profile)
    real_use_live_provider_config = bool(
        getattr(args, "real_use_live_provider_config", False)
    )
    include_real_smoke = bool(getattr(args, "include_real_smoke", False))
    export_root = getattr(args, "export_root", "")
    planned = _planned_commands(
        root,
        gate_profile,
        include_real_smoke,
        args.codex_bin,
        args.real_timeout_seconds,
        real_use_live_provider_config,
        export_root,
    )
    if args.dry_run:
        dry_run_steps = planned + [_planned_hygiene()]
        return {
            "ok": True,
            "root": root.as_posix(),
            "dry_run": True,
            "gate_profile": gate_profile,
            "gate_profile_description": GATE_PROFILES[gate_profile],
            "include_real_smoke": include_real_smoke,
            "real_smoke_enabled": include_real_smoke or gate_profile == "real",
            "real_use_live_provider_config": real_use_live_provider_config,
            "export_root": export_root,
            "total_budget_seconds": _total_budget_seconds(dry_run_steps),
            "budget_ok": True,
            "steps": [asdict(step) for step in dry_run_steps],
        }

    results: List[StepResult] = []
    for step in planned:
        if step.name == "real_auth_preflight":
            started = time.monotonic()
            result = _check_real_auth_preflight(
                os.environ,
                root,
                real_use_live_provider_config,
            )
            result = _attach_preflight_timing(result, started, step)
        else:
            result = _run_command(
                step.name,
                step.command,
                step.budget_seconds,
                step.cost_class,
                {"CODEX_AGENT_E2E_OWNER_ID": temp_owner_id}
                if step.name.startswith("agent_e2e_offline")
                or step.name.startswith("real_")
                else None,
            )
        results.append(result)
        if not result.ok:
            break

    results.append(_check_hygiene(root, temp_owner_id))

    functional_ok = bool(results) and all(result.ok for result in results)
    budget_ok = _budget_ok(results)
    ok = functional_ok and (
        budget_ok or not bool(getattr(args, "fail_on_budget_overrun", False))
    )
    return {
        "ok": ok,
        "functional_ok": functional_ok,
        "budget_ok": budget_ok,
        "root": root.as_posix(),
        "dry_run": False,
        "gate_profile": gate_profile,
        "gate_profile_description": GATE_PROFILES[gate_profile],
        "include_real_smoke": include_real_smoke,
        "real_smoke_enabled": include_real_smoke or gate_profile == "real",
        "real_use_live_provider_config": real_use_live_provider_config,
        "export_root": export_root,
        "total_duration_seconds": _total_duration_seconds(results),
        "total_budget_seconds": _total_budget_seconds(results),
        "steps": [asdict(result) for result in results],
    }


def _print_human(payload: Dict[str, object]) -> None:
    status = "通过" if payload["ok"] else "失败"
    profile = payload.get("gate_profile", "quick")
    duration = payload.get("total_duration_seconds")
    budget = payload.get("total_budget_seconds")
    budget_ok = payload.get("budget_ok", True)
    if duration is not None and budget is not None:
        suffix = "，耗时 %.2fs / 预算 %.2fs" % (float(duration), float(budget))
        if not budget_ok:
            suffix += "，已超预算"
    else:
        suffix = ""
    print("总验收：%s（profile=%s%s）" % (status, profile, suffix))
    for raw_step in payload["steps"]:  # type: ignore[index]
        step = raw_step  # type: ignore[assignment]
        marker = "OK" if step["ok"] else "FAIL"
        time_part = ""
        if step.get("duration_seconds") is not None and step.get("duration_seconds"):
            time_part = "，耗时 %.2fs" % float(step["duration_seconds"])
            if step.get("budget_seconds"):
                time_part += " / 预算 %.2fs" % float(step["budget_seconds"])
            if step.get("budget_ok") is False:
                time_part += "，超预算"
        print("- %s %s：%s%s" % (marker, step["name"], step["summary"], time_part))
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
