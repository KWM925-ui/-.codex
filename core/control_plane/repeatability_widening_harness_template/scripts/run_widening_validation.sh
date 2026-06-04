#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "${repo_root}/artifacts"

cd "${repo_root}"
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="${repo_root}/src" \
python3 -m unittest tests.test_widening -q

printf 'PASS: bash %s/scripts/run_widening_validation.sh\n' "${repo_root}" \
  > "${repo_root}/artifacts/widening_result.txt"
