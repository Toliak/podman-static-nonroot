#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

for arch in amd64 arm64; do
  for key in DEB_FILE RPM_FILE PKG_FILE USER_FILE; do
    ARCH="$arch" PLATFORM="linux/$arch" bash scripts/version.sh "$key"
  done
done
printf 'SHA256SUMS\n'
