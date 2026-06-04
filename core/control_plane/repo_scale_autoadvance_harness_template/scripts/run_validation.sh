#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "${repo_root}"
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="${repo_root}/src" \
python3 -m unittest tests.test_progress_budget -q
