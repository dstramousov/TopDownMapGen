#!/usr/bin/env bash
set -euo pipefail

# Remove only project-generated data and known disposable caches.
# Never scan the whole repository by extension: source assets or tools may
# legitimately use formats such as HTML or JavaScript in the future.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

remove_dir() {
    local path="$1"
    if [[ -e "$path" ]]; then
        rm -rf -- "$path"
        echo "Removed: $path"
    fi
}

remove_dir output
remove_dir out
remove_dir .pytest_cache
remove_dir .mypy_cache
remove_dir .ruff_cache
remove_dir build
remove_dir dist

while IFS= read -r -d '' cache_dir; do
    rm -rf -- "$cache_dir"
done < <(find . -type d -name '__pycache__' -print0)

while IFS= read -r -d '' junk_file; do
    rm -f -- "$junk_file"
done < <(
    find . -type f \
        \( -name '*.pyc' -o -name '*.pyo' -o -name '*.tmp' \
           -o -name '*.bak' -o -name '*.orig' -o -name '*.rej' \) \
        -print0
)

echo "Cleanup complete."
