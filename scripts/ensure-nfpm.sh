#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

NFPM_VERSION=${NFPM_VERSION:-v2.49.0}
NFPM_CACHE_DIR=${NFPM_CACHE_DIR:-.tools}
version_no_v=${NFPM_VERSION#v}

case "$(uname -m)" in
  x86_64) goarch=x86_64 ;;
  aarch64|arm64) goarch=arm64 ;;
  *) goarch=$(uname -m) ;;
esac

if [[ $NFPM_CACHE_DIR = /* ]]; then
  bin="$NFPM_CACHE_DIR/nfpm-$NFPM_VERSION"
else
  bin="$ROOT/$NFPM_CACHE_DIR/nfpm-$NFPM_VERSION"
fi

if [[ ! -x $bin ]]; then
  mkdir -p "$(dirname "$bin")"
  url="https://github.com/goreleaser/nfpm/releases/download/${NFPM_VERSION}/nfpm_${version_no_v}_Linux_${goarch}.tar.gz"
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT
  printf 'Downloading nfpm %s from %s\n' "$NFPM_VERSION" "$url" >&2
  if ! curl -fsSL -o "$tmp/nfpm.tar.gz" "$url"; then
    printf 'Failed to download nfpm; set NFPM_BIN to an existing nfpm binary\n' >&2
    exit 1
  fi
  tar -xzf "$tmp/nfpm.tar.gz" -C "$tmp" nfpm
  cp "$tmp/nfpm" "$bin"
  chmod 755 "$bin"
fi

printf '%s\n' "$bin"
