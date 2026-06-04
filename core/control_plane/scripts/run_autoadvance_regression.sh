#!/usr/bin/env bash
set -euo pipefail

count="${1:-3}"
prompt="${2:-继续，不要停}"
timestamp="$(date +%Y%m%d_%H%M%S)"
run_root="${3:-/tmp/codex_autoadvance_regression_${timestamp}}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
materialize="${script_dir}/materialize_autoadvance_harness.sh"

mkdir -p "$run_root"

pass_count=0

for i in $(seq 1 "$count"); do
  case_dir="${run_root}/case_$(printf '%02d' "$i")"
  "$materialize" "$case_dir"

  baseline_log="${case_dir}/baseline.log"
  if python3 "${case_dir}/test_math.py" >"${baseline_log}" 2>&1; then
    echo "case_${i}: FAIL baseline unexpectedly passed"
    continue
  fi

  exec_log="${case_dir}/codex_exec.log"
  if ! codex exec --dangerously-bypass-approvals-and-sandbox --ephemeral --color never -C "$case_dir" "$prompt" >"${exec_log}" 2>&1; then
    echo "case_${i}: FAIL codex exec returned non-zero"
    continue
  fi

  if ! python3 "${case_dir}/test_math.py" >"${case_dir}/post_validation.log" 2>&1; then
    echo "case_${i}: FAIL post-validation still failing"
    continue
  fi

  if ! rg -q 'return a \+ b' "${case_dir}/math_bug.py"; then
    echo "case_${i}: FAIL patch not applied"
    continue
  fi

  if ! rg -q 'Current phase is .*S5: Low-Pollution Validation' "${case_dir}/supervisor/state_machine.md"; then
    echo "case_${i}: FAIL state machine not advanced"
    continue
  fi

  if ! rg -q 'PASS: add\(2, 3\) == 5' "${case_dir}/supervisor/supervisor_ledger.md"; then
    echo "case_${i}: FAIL ledger missing validation evidence"
    continue
  fi

  if ! rg -q '^D\. Did Same-Turn Auto-Advance Work' "${case_dir}/codex_exec.log"; then
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
