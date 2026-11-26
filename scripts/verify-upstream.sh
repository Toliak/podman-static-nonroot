#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

UPSTREAM_REF=${UPSTREAM_REF:-c55c0fbb9ede2937f71536a394d5cccc5efafcfe}
UPSTREAM_VERSION=${UPSTREAM_VERSION:-v6.2.0}
CACHE_DIR=${CACHE_DIR:-.cache}

tree="$CACHE_DIR/upstream"
rev_file="$tree/.pinned-rev"

if [[ ! -f $rev_file ]]; then
  printf 'missing pinned revision marker: %s\n' "$rev_file" >&2
  exit 1
fi

rev=$(< "$rev_file")
if [[ $rev != "$UPSTREAM_REF"* ]]; then
  printf 'upstream revision mismatch: %s (want %s)\n' "$rev" "$UPSTREAM_REF" >&2
  exit 1
fi

if [[ ! -f $tree/Dockerfile ]]; then
  printf 'missing fetched upstream Dockerfile: %s\n' "$tree/Dockerfile" >&2
  exit 1
fi

dockerfile_version=$(awk -F= '/^[[:space:]]*ARG[[:space:]]+PODMAN_VERSION=/ {gsub(/[[:space:]]/, "", $2); print $2; exit}' "$tree/Dockerfile")
if [[ $dockerfile_version != "$UPSTREAM_VERSION" ]]; then
  printf 'upstream PODMAN_VERSION mismatch: %s (want %s)\n' "$dockerfile_version" "$UPSTREAM_VERSION" >&2
  exit 1
fi

printf 'verified upstream %s at %s (%s)\n' "$UPSTREAM_VERSION" "$UPSTREAM_REF" "$rev"
