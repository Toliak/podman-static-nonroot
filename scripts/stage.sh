#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

DIST_DIR=${DIST_DIR:-dist/podman-static}
PLATFORM=${PLATFORM:-linux/amd64}
OUT_DIR=${OUT_DIR:-out}
ARCH=$(bash scripts/version.sh ARCH)
ASSET_DIR=${ASSET_DIR:-$OUT_DIR/asset/podman-linux-$ARCH}

make -C "$DIST_DIR" singlearch-tar PLATFORM="$PLATFORM"

src="$DIST_DIR/build/asset/podman-linux-$ARCH"
if [[ ! -d $src ]]; then
  printf 'upstream staging tree missing: %s\n' "$src" >&2
  exit 1
fi
mkdir -p "$ASSET_DIR"
cp -a "$src/." "$ASSET_DIR/"
printf 'staged %s -> %s\n' "$src" "$ASSET_DIR"
