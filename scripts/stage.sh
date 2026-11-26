#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

CACHE_DIR=${CACHE_DIR:-.cache}
PLATFORM=${PLATFORM:-linux/amd64}
OUT_DIR=${OUT_DIR:-out}
ARCH=$(bash scripts/version.sh ARCH)
ASSET_DIR=${ASSET_DIR:-$OUT_DIR/asset/podman-linux-$ARCH}

rootfs="$CACHE_DIR/rootfs"
upstream="$CACHE_DIR/upstream"

if [[ ! -d $rootfs/usr/local || ! -d $rootfs/etc/containers ]]; then
  printf 'rootfs %s is incomplete; run "make build" (podman)\n' "$rootfs" >&2
  exit 1
fi
if [[ ! -f $upstream/README.md ]]; then
  printf 'upstream tree %s is incomplete; run "make fetch" (podman)\n' "$upstream" >&2
  exit 1
fi

rm -rf "$ASSET_DIR"
mkdir -p "$ASSET_DIR/etc/containers" \
         "$ASSET_DIR/usr/local/lib/systemd/system-generators" \
         "$ASSET_DIR/usr/local/lib/systemd/user-generators"

cp -a "$rootfs/etc/containers/." "$ASSET_DIR/etc/containers/"
cp -a "$rootfs/usr/local/." "$ASSET_DIR/usr/local/"

rm -f "$ASSET_DIR/usr/local/lib/systemd/system-generators/podman-system-generator" \
      "$ASSET_DIR/usr/local/lib/systemd/user-generators/podman-user-generator"
ln -s ../../../libexec/podman/quadlet "$ASSET_DIR/usr/local/lib/systemd/user-generators/podman-user-generator"
ln -s ../../../libexec/podman/quadlet "$ASSET_DIR/usr/local/lib/systemd/system-generators/podman-system-generator"
cp "$upstream/README.md" "$ASSET_DIR/README.md"
printf 'staged %s -> %s\n' "$rootfs" "$ASSET_DIR"
