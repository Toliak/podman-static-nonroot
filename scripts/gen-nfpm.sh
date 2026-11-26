#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

ARCH=$(bash scripts/version.sh ARCH)
ASSET_DIR=${ASSET_DIR:-out/asset/podman-linux-$ARCH}
PKG_NAME=$(bash scripts/version.sh PKG_NAME)
PKG_VERSION=$(bash scripts/version.sh PKG_VERSION)
PKG_RELEASE=$(bash scripts/version.sh PKG_RELEASE)

template=$(< nfpm.yaml)
template=${template//@PKG_NAME@/$PKG_NAME}
template=${template//@PKG_VERSION@/$PKG_VERSION}
template=${template//@PKG_RELEASE@/$PKG_RELEASE}
template=${template//@ARCH@/$ARCH}
template=${template//@ASSET_DIR@/$ASSET_DIR}
printf '%s\n' "$template"
