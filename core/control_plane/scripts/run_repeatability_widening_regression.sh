#!/usr/bin/env bash
set -euo pipefail

count="${1:-3}"
prompt="${2:-继续，不要停}"
timestamp="$(date +%Y%m%d_%H%M%S)"
run_root="${3:-/tmp/repeatability_widening_regression_${timestamp}}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
materialize="${script_dir}/materialize_repeatability_widening_harness.sh"

echo "warning: this regression writes temporary harness artifacts under ${run_root} and runs real codex exec with bypassed approvals/sandbox inside that temp harness." >&2

mkdir -p "$run_root"

pass_count=0
config_path="${CODEX_HOME:-${HOME}/.codex}/config.toml"

cleanup_tmp_trusted_projects() {
  if [[ ! -f "$config_path" ]] || ! grep -Eq '^\[projects\."\/tmp(\/[^"]*)?"\]$' "$config_path"; then
    return
  fi
  local tmp_config
  tmp_config="$(mktemp "${config_path}.tmp.XXXXXX")"
  awk '
    /^\[projects\."\/tmp(\/[^"]*)?"\]$/ { skip=1; next }
    skip && /^\[/ { skip=0 }
    !skip { print }
  ' "$config_path" >"$tmp_config"
  chmod --reference="$config_path" "$tmp_config"
  mv "$tmp_config" "$config_path"
}

trap cleanup_tmp_trusted_projects EXIT

run_codex_exec() {
  local case_dir="$1"
  local exec_log="$2"
  local case_label="$3"
  local attempts="${CODEX_REGRESSION_ATTEMPTS:-3}"
  local retry_sleep="${CODEX_REGRESSION_RETRY_SLEEP_SECONDS:-20}"

  for attempt in $(seq 1 "$attempts"); do
    if codex exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox --ephemeral --color never -C "$case_dir" "$prompt" >"$exec_log" 2>&1; then
      return 0
    fi
    if [[ "$attempt" -lt "$attempts" ]] && rg -qi '429 Too Many Requests|exceeded retry limit' "$exec_log"; then
      echo "${case_label}: retry ${attempt}/${attempts} after transient rate limit" >&2
      sleep "$retry_sleep"
      continue
    fi
    return 1
  done
}

for i in $(seq 1 "$count"); do
  case_dir="${run_root}/case_$(printf '%02d' "$i")"
  "$materialize" "$case_dir"

  notes_hash_before="$(sha256sum "${case_dir}/docs/operator_notes.md" | awk '{print $1}')"
  probe_hash_before="$(sha256sum "${case_dir}/logs/manual_probe.log" | awk '{print $1}')"
  cache_hash_before="$(sha256sum "${case_dir}/.tmp/local_cache.txt" | awk '{print $1}')"

  if [[ -e "${case_dir}/artifacts/repeatability_result.txt" || -e "${case_dir}/artifacts/widening_result.txt" ]]; then
    echo "case_${i}: FAIL baseline artifacts unexpectedly exist"
    continue
  fi

  exec_log="${case_dir}/codex_exec.log"
  if ! run_codex_exec "$case_dir" "$exec_log" "case_${i}"; then
    echo "case_${i}: FAIL codex exec returned non-zero"
    continue
  fi

  if ! rg -q 'PASS: .*run_repeatability_validation\.sh' "${case_dir}/artifacts/repeatability_result.txt"; then
    echo "case_${i}: FAIL repeatability artifact missing"
    continue
  fi

  if ! rg -q 'PASS: .*run_widening_validation\.sh' "${case_dir}/artifacts/widening_result.txt"; then
    echo "case_${i}: FAIL widening artifact missing"
    continue
  fi

  notes_hash_after="$(sha256sum "${case_dir}/docs/operator_notes.md" | awk '{print $1}')"
  probe_hash_after="$(sha256sum "${case_dir}/logs/manual_probe.log" | awk '{print $1}')"
  cache_hash_after="$(sha256sum "${case_dir}/.tmp/local_cache.txt" | awk '{print $1}')"
  if [[ "${notes_hash_before}" != "${notes_hash_after}" ]]; then
    echo "case_${i}: FAIL dirty tracked note changed"
    continue
  fi
  if [[ "${probe_hash_before}" != "${probe_hash_after}" ]]; then
    echo "case_${i}: FAIL untracked probe log changed"
    continue
  fi
  if [[ "${cache_hash_before}" != "${cache_hash_after}" ]]; then
    echo "case_${i}: FAIL untracked cache file changed"
    continue
  fi

  mapfile -t tracked_changes < <(git -C "$case_dir" diff --name-only --relative HEAD | sort)
  expected_changes=(
    "docs/operator_notes.md"
    "supervisor/state_machine.md"
    "supervisor/supervisor_ledger.md"
  )
  if [[ "${tracked_changes[*]}" != "${expected_changes[*]}" ]]; then
    printf 'case_%s: FAIL tracked change surface expanded\n' "$i"
    printf 'expected: %s\n' "${expected_changes[*]}"
    printf 'actual: %s\n' "${tracked_changes[*]}"
    continue
  fi

  if ! rg -q 'Current phase is `S7: Widening Validation`' "${case_dir}/supervisor/state_machine.md"; then
    echo "case_${i}: FAIL state machine not advanced"
    continue
  fi

  if ! rg -q 'PASS: .*run_repeatability_validation\.sh' "${case_dir}/supervisor/supervisor_ledger.md"; then
    echo "case_${i}: FAIL ledger missing repeatability evidence"
    continue
  fi

  if ! rg -q 'PASS: .*run_widening_validation\.sh' "${case_dir}/supervisor/supervisor_ledger.md"; then
    echo "case_${i}: FAIL ledger missing widening evidence"
    continue
  fi

  if ! rg -q 'E\. Did Late-Phase Auto-Advance Work' "${exec_log}"; then
    echo "case_${i}: FAIL final output shape incomplete"
    continue
  fi

  echo "case_${i}: PASS"
  pass_count=$((pass_count + 1))
done

echo "summary: ${pass_count}/${count} passed"
echo "artifacts: ${run_root}"

if [[ "$pass_count" -ne "$count" ]]; then
  exit 1
fi
