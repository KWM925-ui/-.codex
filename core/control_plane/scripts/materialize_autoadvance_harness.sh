#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 DEST_DIR" >&2
  exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
template_root="$(cd "${script_dir}/.." && pwd)/autoadvance_harness_template"
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

rm -rf "$dest/__pycache__"
