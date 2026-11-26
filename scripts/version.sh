#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

PLATFORM=${PLATFORM:-linux/amd64}
DIST_DIR=${DIST_DIR:-dist/podman-static}
PKG_NAME=${PKG_NAME:-podman-static}
DOCKERFILE=${PODMAN_STATIC_DOCKERFILE:-$DIST_DIR/Dockerfile}

if [[ -n ${ARCH:-} ]]; then
  _arch=$ARCH
else
  _arch=$(printf '%s' "$PLATFORM" | sed -E 's!linux/([^/]+).*!\1!')
fi

case "$_arch" in
  amd64) ARCH_DEB=amd64; ARCH_RPM=x86_64; ARCH_PKG=x86_64 ;;
  arm64) ARCH_DEB=arm64; ARCH_RPM=aarch64; ARCH_PKG=aarch64 ;;
  *)     ARCH_DEB=$_arch; ARCH_RPM=$_arch; ARCH_PKG=$_arch ;;
esac
ARCH=$_arch

sanitize_version() {
  local value=$1
  value=${value#v}
  value=${value%%-*}
  value=$(printf '%s' "$value" | tr -cd '0-9.')
  value=${value%.}
  if [[ ! $value =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    value=""
  fi
  printf '%s' "$value"
}

git_disabled() {
  case ${PODMAN_STATIC_GIT:-} in
    false|False|FALSE|none|no|0) return 0 ;;
    *) return 1 ;;
  esac
}

describe=${PODMAN_STATIC_DESCRIBE:-}
if [[ -z $describe ]] && ! git_disabled; then
  if command -v git >/dev/null 2>&1 && git -C "$DIST_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    describe=$(git -C "$DIST_DIR" describe --tags --always 2>/dev/null || true)
  fi
fi

derived_version=""
derived_release=""
VERSION_SCHEME=git-describe

if [[ $describe =~ ^v?([0-9]+\.[0-9]+\.[0-9]+)-([0-9]+)-g[0-9a-fA-F]+(-dirty)?$ ]]; then
  derived_version=${BASH_REMATCH[1]}
  derived_release=${BASH_REMATCH[2]}
elif [[ $describe =~ ^v?([0-9]+\.[0-9]+\.[0-9]+)(-dirty)?$ ]]; then
  derived_version=${BASH_REMATCH[1]}
  derived_release=1
else
  VERSION_SCHEME=dockerfile-fallback
  fallback=${PODMAN_STATIC_PODMAN_VERSION:-}
  if [[ -z $fallback && -f $DOCKERFILE ]]; then
    fallback=$(awk -F= '/^[[:space:]]*ARG[[:space:]]+PODMAN_VERSION=/ {print $2; exit}' "$DOCKERFILE")
  fi
  derived_version=$(sanitize_version "$fallback")
  derived_release=1
fi

if [[ -z $derived_version ]]; then
  derived_version=0.0.0
  VERSION_SCHEME=default
fi
[[ $derived_release =~ ^[0-9]+$ ]] || derived_release=1

PKG_VERSION=${PKG_VERSION:-$derived_version}
PKG_RELEASE=${PKG_RELEASE:-$derived_release}

DEB_FILE="${PKG_NAME}_${PKG_VERSION}-${PKG_RELEASE}_${ARCH_DEB}.deb"
RPM_FILE="${PKG_NAME}-${PKG_VERSION}-${PKG_RELEASE}.${ARCH_RPM}.rpm"
PKG_FILE="${PKG_NAME}-${PKG_VERSION}-${PKG_RELEASE}-${ARCH_PKG}.pkg.tar.zst"
: "$VERSION_SCHEME" "$DEB_FILE" "$RPM_FILE" "$PKG_FILE"

VALID_KEYS=(PKG_NAME PKG_VERSION PKG_RELEASE ARCH ARCH_DEB ARCH_RPM ARCH_PKG PLATFORM VERSION_SCHEME DEB_FILE RPM_FILE PKG_FILE)

if [[ $# -gt 0 ]]; then
  key=$1
  case " ${VALID_KEYS[*]} " in
    *" $key "*) printf '%s\n' "${!key}" ;;
    *) printf 'unknown key: %s\n' "$key" >&2; exit 2 ;;
  esac
else
  for k in "${VALID_KEYS[@]}"; do
    printf '%s=%s\n' "$k" "${!k}"
  done
fi
