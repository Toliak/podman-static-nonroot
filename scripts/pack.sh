#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

OUT_DIR=${OUT_DIR:-out}
NFPM_BIN=${NFPM_BIN:-nfpm}

v() { bash scripts/version.sh "$1"; }

ARCH=$(v ARCH)
ASSET_DIR=${ASSET_DIR:-$OUT_DIR/asset/podman-linux-$ARCH}
DEB_FILE=$(v DEB_FILE)
RPM_FILE=$(v RPM_FILE)
PKG_FILE=$(v PKG_FILE)
USER_FILE=$(v USER_FILE)

write_checksums() {
  local -a files=()
  local f
  for f in "$DEB_FILE" "$RPM_FILE" "$PKG_FILE" "$USER_FILE"; do
    if [[ -f "$OUT_DIR/$f" ]]; then
      files+=("$f")
    fi
  done
  if (( ${#files[@]} == 0 )); then
    printf 'no packages found in %s\n' "$OUT_DIR" >&2
    return 1
  fi
  ( cd "$OUT_DIR" && sha256sum "${files[@]}" > SHA256SUMS )
}

mode=${1:-}
if [[ $mode == "--checksums-only" ]]; then
  write_checksums
  exit 0
fi

formats=()
case "$mode" in
  "") formats=(deb rpm archlinux) ;;
  deb|rpm|archlinux) formats=("$mode") ;;
  *) printf 'unknown pack format: %s\n' "$mode" >&2; exit 2 ;;
esac

if [[ ! -d "$ASSET_DIR/usr/local" || ! -d "$ASSET_DIR/etc/containers" ]]; then
  printf 'asset tree %s is incomplete; run "make build" (podman) or "make pack-fixture"\n' "$ASSET_DIR" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
CONFIG="$OUT_DIR/nfpm-$ARCH.yaml"
ASSET_DIR="$ASSET_DIR" bash scripts/gen-nfpm.sh > "$CONFIG"

declare -A out_name=(
  [deb]="$DEB_FILE"
  [rpm]="$RPM_FILE"
  [archlinux]="$PKG_FILE"
)

for fmt in "${formats[@]}"; do
  "$NFPM_BIN" package --config "$CONFIG" --packager "$fmt" --target "$OUT_DIR/"
  want=${out_name[$fmt]}
  if [[ ! -f "$OUT_DIR/$want" ]]; then
    printf 'expected package not produced: %s\n' "$want" >&2
    exit 1
  fi
done

write_checksums
