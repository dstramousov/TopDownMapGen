#!/usr/bin/env bash

set -euo pipefail

OUTPUT_DIR="${OUTPUT_DIR:-output}"
OUT_DIR="${OUT_DIR:-out}"

remove_dir_contents() {
  local dir="$1"
  if [[ -d "${dir}" ]]; then
    rm -rf -- "${dir:?}"/*
  else
    mkdir -p -- "${dir}"
  fi
}

remove_pycache() {
  find . -type d -name '__pycache__' -prune -exec rm -rf -- {} +
  rm -rf -- .pytest_cache
}

remove_dir_contents "${OUTPUT_DIR}"
remove_dir_contents "${OUT_DIR}"
remove_pycache

echo "Cleaned: ${OUTPUT_DIR}/, ${OUT_DIR}/, __pycache__, .pytest_cache"
