#!/usr/bin/env bash

set -euo pipefail

OUTPUT_DIR="${OUTPUT_DIR:-output}"
OUT_DIR="${OUT_DIR:-out}"

cleanup_dir() {
  local path="$1"

  if [[ -z "${path}" || "${path}" == "/" || "${path}" == "." ]]; then
    echo "ERROR: refusing to clean unsafe path: ${path}" >&2
    exit 2
  fi

  mkdir -p "${path}"
  find "${path}" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
}

cleanup_dir "${OUTPUT_DIR}"
cleanup_dir "${OUT_DIR}"
