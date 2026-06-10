#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SERVICE_DIR="${ROOT_DIR}/aws/original-issuer"
BUILD_DIR="${SERVICE_DIR}/.build"
PACKAGE_DIR="${BUILD_DIR}/package"
ZIP_PATH="${BUILD_DIR}/original-issuer.zip"

PYTHON_BIN="${PYTHON_BIN:-python3}"

rm -rf "${PACKAGE_DIR}" "${ZIP_PATH}"
mkdir -p "${PACKAGE_DIR}"

"${PYTHON_BIN}" -m pip install \
  --upgrade \
  --target "${PACKAGE_DIR}" \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.11 \
  --only-binary=:all: \
  --no-compile \
  -r "${SERVICE_DIR}/requirements.txt"

rsync -a \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  "${ROOT_DIR}/src/mtm_hbl" \
  "${PACKAGE_DIR}/"

rsync -a \
  --exclude '.DS_Store' \
  "${ROOT_DIR}/config" \
  "${PACKAGE_DIR}/"

rsync -a \
  --exclude '.DS_Store' \
  "${ROOT_DIR}/assets" \
  "${PACKAGE_DIR}/"

(cd "${PACKAGE_DIR}" && zip -q -r "${ZIP_PATH}" .)

echo "${ZIP_PATH}"
