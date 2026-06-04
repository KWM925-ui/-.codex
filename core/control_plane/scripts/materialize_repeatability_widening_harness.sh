#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 DEST_DIR" >&2
  exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
template_root="$(cd "${script_dir}/.." && pwd)/repeatability_widening_harness_template"
dest="$1"

mkdir -p "$dest"
if find "$dest" -mindepth 1 -maxdepth 1 | read -r _; then
  echo "destination must be empty or not exist: $dest" >&2
  exit 1
fi

cp -a "${template_root}/." "$dest/"

while IFS= read -r file; do
  sed -i "s|__HARNESS_ROOT__|$dest|g" "$file"
done < <(rg -l "__HARNESS_ROOT__" "$dest")

git -C "$dest" init -q
git -C "$dest" config user.email "harness@example.invalid"
git -C "$dest" config user.name "Harness"
git -C "$dest" add .
git -C "$dest" commit -q -m "baseline"

printf '\n- Local scratch: keep this dirty line untouched.\n' >> "${dest}/docs/operator_notes.md"
mkdir -p "${dest}/logs" "${dest}/.tmp"
printf 'manual probe: unchanged noise file\n' > "${dest}/logs/manual_probe.log"
printf 'cache: unchanged noise file\n' > "${dest}/.tmp/local_cache.txt"

rm -rf "$dest/__pycache__" "$dest/.git/index.lock"
