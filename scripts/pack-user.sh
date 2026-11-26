#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

v() { bash scripts/version.sh "$1"; }

OUT_DIR=${OUT_DIR:-out}
ARCH=$(v ARCH)
ASSET_DIR=${ASSET_DIR:-$OUT_DIR/asset/podman-linux-$ARCH}
CACHE_DIR=${CACHE_DIR:-.cache}
USER_FILE=$(v USER_FILE)
VERSION=$(v PKG_VERSION)
RELEASE=$(v PKG_RELEASE)
PKG_NAME=$(v PKG_NAME)

TOP=podman-static-user
SRC=$ASSET_DIR/usr/local

die() {
  printf 'pack-user: %s\n' "$*" >&2
  exit 1
}

[[ -d $SRC/bin ]] || die "asset tree $ASSET_DIR is incomplete; run \"make build\" or \"make pack-fixture\""
[[ -x $SRC/bin/podman ]] || die "missing $SRC/bin/podman"
if [[ ! -d $CACHE_DIR/upstream ]] && [[ -z ${PODMAN_STATIC_PACK_USER_QUIET:-} ]]; then
  printf 'pack-user: no %s/upstream (LICENSE omitted)\n' "$CACHE_DIR" >&2
fi

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
root=$stage/$TOP
mkdir -p "$root/bin" "$root/lib/podman" "$root/share" "$root/etc/containers"

copy_exec() {
  local name=$1
  [[ -f $SRC/bin/$name ]] || die "missing binary: usr/local/bin/$name"
  cp -p "$SRC/bin/$name" "$root/bin/$name"
  chmod 0755 "$root/bin/$name"
}

link_or_copy() {
  local name=$1
  local path=$SRC/bin/$name
  [[ -e $path || -L $path ]] || return 0
  if [[ -L $path ]]; then
    local target
    target=$(readlink "$path")
    [[ $target != */* ]] || die "refusing non-local symlink: bin/$name -> $target"
    [[ -f $SRC/bin/$target ]] || die "broken symlink: bin/$name -> $target"
    ln -s "$target" "$root/bin/$name"
  else
    cp -p "$path" "$root/bin/$name"
    chmod 0755 "$root/bin/$name"
  fi
}

lib_helper() {
  local name=$1
  if [[ -f $SRC/lib/podman/$name ]]; then
    cp -p "$SRC/lib/podman/$name" "$root/lib/podman/$name"
  elif [[ -f $SRC/bin/$name ]]; then
    cp -p "$SRC/bin/$name" "$root/lib/podman/$name"
  else
    die "missing helper: $name (usr/local/lib/podman or usr/local/bin)"
  fi
  chmod 0755 "$root/lib/podman/$name"
}

for name in podman crun runc fuse-overlayfs fusermount3 passt; do
  copy_exec "$name"
done
link_or_copy pasta

if [[ -e $SRC/bin/passt.avx2 || -L $SRC/bin/passt.avx2 || -L $SRC/bin/pasta.avx2 ]]; then
  copy_exec passt.avx2
  link_or_copy pasta.avx2
  [[ -L $root/bin/pasta.avx2 ]] || die "passt.avx2 present but pasta.avx2 is not a symlink"
fi

for name in conmon netavark aardvark-dns catatonit rootlessport; do
  lib_helper "$name"
done

copy_optional() {
  local src=$1 dst=$2
  [[ -e $src ]] || return 0
  mkdir -p "$(dirname "$dst")"
  cp -p "$src" "$dst"
  chmod 0644 "$dst"
}

copy_optional "$SRC/share/bash-completion/completions/podman" \
  "$root/share/bash-completion/completions/podman"
copy_optional "$SRC/share/zsh/site-functions/_podman" "$root/share/zsh/site-functions/_podman"
copy_optional "$SRC/share/fish/vendor_completions.d/podman.fish" \
  "$root/share/fish/vendor_completions.d/podman.fish"

copy_optional "$ASSET_DIR/etc/containers/seccomp.json" "$root/share/seccomp.json"
[[ -f $root/share/seccomp.json ]] || die "missing etc/containers/seccomp.json"
copy_optional "$ASSET_DIR/etc/containers/registries.conf" "$root/etc/containers/registries.conf"
[[ -f $root/etc/containers/registries.conf ]] || die "missing etc/containers/registries.conf"
copy_optional "$ASSET_DIR/etc/containers/policy.json" "$root/etc/containers/policy.json"
[[ -f $root/etc/containers/policy.json ]] || die "missing etc/containers/policy.json"

for name in containers.conf.in storage.conf.in env.sh.in; do
  [[ -f templates/$name ]] || die "missing templates/$name"
done
cp templates/containers.conf.in "$root/etc/containers/containers.conf.in"
cp templates/storage.conf.in "$root/etc/containers/storage.conf.in"
cp templates/env.sh.in "$root/env.sh.in"
cp templates/user-install.sh "$root/install.sh"
cp templates/user-uninstall.sh "$root/uninstall.sh"
cp templates/user-README.md "$root/README.md"
chmod 0755 "$root/install.sh" "$root/uninstall.sh"

if [[ -f $CACHE_DIR/upstream/LICENSE ]]; then
  cp "$CACHE_DIR/upstream/LICENSE" "$root/LICENSE"
  chmod 0644 "$root/LICENSE"
fi

cat > "$root/RELEASE" <<EOF
format=1
name=$PKG_NAME
version=$VERSION
release=$RELEASE
arch=$ARCH
EOF
chmod 0644 "$root/RELEASE"

while IFS= read -r rel; do
  case $rel in
    *systemd* | *quadlet* | *docker*)
      die "forbidden member in user payload: $rel"
      ;;
  esac
done < <(cd "$root" && find . -mindepth 1 | sort)

mkdir -p "$OUT_DIR"
tar --sort=name --owner=0 --group=0 --numeric-owner \
  -C "$stage" -czf "$OUT_DIR/$USER_FILE" "$TOP"

listing=$(mktemp)
trap 'rm -rf "$stage" "$listing"' EXIT
tar -tzf "$OUT_DIR/$USER_FILE" > "$listing"
if grep -Eq '(^/|(^|/)\.\.(/|$))' "$listing"; then
  die "unsafe member path in $USER_FILE"
fi
if ! grep -qx "$TOP/install.sh" "$listing"; then
  die "install.sh missing from $USER_FILE"
fi

OUT_DIR="$OUT_DIR" bash scripts/pack.sh --checksums-only
printf 'packed %s\n' "$OUT_DIR/$USER_FILE"
