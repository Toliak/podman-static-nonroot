#!/usr/bin/env bash
# podman-static non-root user installer.
#
# Installs the bundled, relocatable payload into an absolute prefix under the
# caller's control. Only warns about host prerequisites; never runs podman.
set -euo pipefail

die() {
  printf 'install.sh: error: %s\n' "$*" >&2
  exit 1
}

warn() {
  printf 'install.sh: warning: %s\n' "$*" >&2
}

usage() {
  cat <<'EOF'
Usage: install.sh [--prefix PATH]

Install the bundled podman-static payload into PATH (default:
$HOME/.local/opt/podman-static). The prefix must be absolute and writable.
Spaces are supported. Installing as root is refused.

Options:
  --prefix PATH   install prefix
  -h, --help      show this help
EOF
}

euid() {
  if [ -n "${PODMAN_STATIC_EUID:-}" ]; then
    printf '%s\n' "$PODMAN_STATIC_EUID"
  else
    id -u
  fi
}

resolve_tool() {
  local override=$1 name=$2 path
  if [ -n "$override" ]; then
    path=$override
  else
    path=$(command -v "$name" 2>/dev/null || true)
  fi
  printf '%s\n' "$path"
}

check_tool() {
  local override=$1 name=$2 path
  path=$(resolve_tool "$override" "$name")
  if [ -z "$path" ] || [ ! -x "$path" ]; then
    warn "$name not found; rootless podman may not work until it is installed"
  fi
}

check_subid() {
  local kind=$1 file=$2 user uid n found
  found=0
  user=$(id -un 2>/dev/null || true)
  uid=$(euid)
  if [ ! -r "$file" ]; then
    warn "could not verify $kind delegation (cannot read $file)"
    return 0
  fi
  while IFS=: read -r n _; do
    if [ "$n" = "$user" ] || [ "$n" = "$uid" ]; then
      found=1
      break
    fi
  done < "$file"
  if [ "$found" -eq 1 ]; then
    return 0
  fi
  warn "no $kind range for $user in $file; rootless podman needs subuid/subgid delegation"
}

run_preflight() {
  local fuse user_clone
  if [ "${PODMAN_STATIC_PREFLIGHT:-1}" = "0" ]; then
    return 0
  fi
  check_tool "${PODMAN_STATIC_NEWUIDMAP:-}" newuidmap
  check_tool "${PODMAN_STATIC_NEWGIDMAP:-}" newgidmap
  check_subid subuid "${PODMAN_STATIC_SUBUID_FILE:-/etc/subuid}"
  check_subid subgid "${PODMAN_STATIC_SUBGID_FILE:-/etc/subgid}"
  check_tool "${PODMAN_STATIC_NFT:-}" nft
  check_tool "${PODMAN_STATIC_NSENTER:-}" nsenter
  fuse=${PODMAN_STATIC_FUSE_DEV:-/dev/fuse}
  if [ ! -e "$fuse" ]; then
    warn "$fuse not found; rootless overlay storage needs /dev/fuse"
  fi
  user_clone=/proc/sys/kernel/unprivileged_userns_clone
  if [ -e "$user_clone" ] && [ "$(cat "$user_clone" 2>/dev/null || true)" = "0" ]; then
    warn "unprivileged user namespaces are disabled ($user_clone is 0)"
  fi
  printf '%s\n' 'install.sh: note: subuid/subgid delegation, newuidmap/newgidmap, nftables, nsenter and /dev/fuse are host administrator prerequisites' >&2
}

verify_manifest() {
  local mf=$1 line hash target rel rest lrest actual
  local m_name='' m_version='' m_release='' m_arch=''
  local ok=1 first=1
  while IFS= read -r line; do
    if [ -z "$line" ]; then
      continue
    fi
    if [ "$first" -eq 1 ]; then
      if [ "$line" != "format=1" ]; then
        return 1
      fi
      first=0
      continue
    fi
    case $line in
      name=*) m_name=${line#name=} ;;
      version=*) m_version=${line#version=} ;;
      release=*) m_release=${line#release=} ;;
      arch=*) m_arch=${line#arch=} ;;
      dir=*) ;;
      file=*)
        rest=${line#file=}
        case $rest in
          *' '*) ;;
          *) return 1 ;;
        esac
        hash=${rest%% *}
        rel=${rest#* }
        case $hash in
          '' | *[!0-9a-f]*) return 1 ;;
        esac
        if [ "${#hash}" -ne 64 ] || [ -z "$rel" ]; then
          return 1
        fi
        if [ -f "$prefix/$rel" ] && [ ! -L "$prefix/$rel" ]; then
          actual=$(sha256sum "$prefix/$rel")
          actual=${actual%% *}
          if [ "$actual" != "$hash" ]; then
            ok=0
          fi
        else
          ok=0
        fi
        ;;
      link=*)
        lrest=${line#link=}
        case $lrest in
          *' '*) ;;
          *) return 1 ;;
        esac
        target=${lrest%% *}
        rel=${lrest#* }
        if [ -z "$target" ] || [ -z "$rel" ]; then
          return 1
        fi
        case $target in
          /*) return 1 ;;
        esac
        if [ -L "$prefix/$rel" ] && [ "$(readlink "$prefix/$rel")" = "$target" ]; then
          :
        else
          ok=0
        fi
        ;;
      *) return 1 ;;
    esac
  done < "$mf"
  if [ "$first" -ne 0 ] || [ "$ok" -ne 1 ]; then
    return 1
  fi
  if [ "$m_name" != "$rel_name" ] ||
    [ "$m_version" != "$rel_version" ] ||
    [ "$m_release" != "$rel_release" ] ||
    [ "$m_arch" != "$rel_arch" ]; then
    return 1
  fi
  return 0
}

render_template() {
  local input=$1 output=$2 content
  content=$(<"$input")
  content=${content//@PREFIX@/$prefix}
  case $content in
    *'@PREFIX@'*) die "failed to render $input (placeholder left behind)" ;;
  esac
  printf '%s\n' "$content" >"$output"
  chmod 0644 "$output"
}

write_manifest() {
  local manifest_dir=$prefix/.podman-static
  local tmp rel full hash target kind dirs files links
  list_rels() {
    local full
    find "$prefix" -mindepth 1 -type "$1" \
      ! -path "$prefix/.podman-static" \
      ! -path "$prefix/.podman-static/*" -print |
      LC_ALL=C sort |
      while IFS= read -r full; do
        printf '%s\n' "${full#"$prefix"/}"
      done
  }
  dirs=$(list_rels d)
  files=$(list_rels f)
  links=$(list_rels l)

  mkdir -p "$manifest_dir"
  tmp=$manifest_dir/.entries.$$
  : >"$tmp"
  while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    case $rel in
      *[[:space:]]*) die "installed path contains whitespace: $rel" ;;
    esac
    printf 'F %s\n' "$rel" >>"$tmp"
  done <<<"$files"
  while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    case $rel in
      *[[:space:]]*) die "installed path contains whitespace: $rel" ;;
    esac
    printf 'L %s\n' "$rel" >>"$tmp"
  done <<<"$links"

  {
    printf 'format=1\n'
    printf 'name=%s\n' "$rel_name"
    printf 'version=%s\n' "$rel_version"
    printf 'release=%s\n' "$rel_release"
    printf 'arch=%s\n' "$rel_arch"
    while IFS= read -r rel; do
      [ -n "$rel" ] || continue
      printf 'dir=%s\n' "$rel"
    done <<<"$dirs"
    while IFS=' ' read -r kind rel; do
      [ -n "$rel" ] || continue
      full=$prefix/$rel
      if [ "$kind" = "F" ]; then
        hash=$(sha256sum "$full")
        hash=${hash%% *}
        printf 'file=%s %s\n' "$hash" "$rel"
      else
        target=$(readlink "$full")
        printf 'link=%s %s\n' "$target" "$rel"
      fi
    done < <(LC_ALL=C sort -k2,2 "$tmp")
  } >"$manifest_dir/manifest"
  rm -f "$tmp"
  chmod 0600 "$manifest_dir/manifest"
}

prefix_arg=
while [ "$#" -gt 0 ]; do
  case $1 in
    --prefix)
      [ "$#" -ge 2 ] || die "--prefix requires a path"
      prefix_arg=$2
      shift 2
      ;;
    --prefix=*)
      prefix_arg=${1#--prefix=}
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

if [ -n "$prefix_arg" ]; then
  prefix=$prefix_arg
elif [ -n "${PODMAN_STATIC_PREFIX:-}" ]; then
  prefix=$PODMAN_STATIC_PREFIX
else
  prefix=${HOME:-}/.local/opt/podman-static
fi

case $prefix in
  */) prefix=${prefix%/} ;;
esac

if [ "$(euid)" = "0" ]; then
  die "refusing to install as root; run as a regular user"
fi

[ -n "$prefix" ] || die "prefix must not be empty"
if [ "$prefix" = "/" ]; then
  die "prefix must not be /"
fi
case $prefix in
  /*) ;;
  *) die "prefix must be an absolute path: $prefix" ;;
esac
case "/$prefix/" in
  */../*) die "prefix must not contain '..' path segments: $prefix" ;;
esac
case $prefix in
  *[![:print:]]*) die "prefix must not contain control characters" ;;
esac
case $prefix in
  *"'"* | *'"'* | *'\'* | *'`'* | *'$'* | *'&'*)
    die "prefix must not contain quotes, backslashes, backticks, '\$' or '&': $prefix"
    ;;
esac
home_norm=${HOME:-}
case $home_norm in
  */) home_norm=${home_norm%/} ;;
esac
if [ -n "$home_norm" ] && [ "$prefix" = "$home_norm" ]; then
  die "prefix must not be \$HOME itself"
fi

src=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
if [ ! -f "$src/RELEASE" ] || [ ! -f "$src/bin/podman" ]; then
  die "run install.sh from the extracted podman-static-user directory"
fi

rel_name='' rel_version='' rel_release='' rel_arch=''
while IFS= read -r line; do
  case $line in
    name=*) rel_name=${line#name=} ;;
    version=*) rel_version=${line#version=} ;;
    release=*) rel_release=${line#release=} ;;
    arch=*) rel_arch=${line#arch=} ;;
  esac
done <"$src/RELEASE"
if [ -z "$rel_name" ] || [ -z "$rel_version" ] ||
  [ -z "$rel_release" ] || [ -z "$rel_arch" ]; then
  die "invalid RELEASE file in $src"
fi

if [ -L "$prefix" ]; then
  die "prefix is a symlink: $prefix"
fi
if [ -e "$prefix" ] && [ ! -d "$prefix" ]; then
  die "prefix exists and is not a directory: $prefix"
fi

manifest=$prefix/.podman-static/manifest
if [ -f "$manifest" ]; then
  if verify_manifest "$manifest"; then
    printf '%s already has podman-static %s installed\n' "$prefix" "$rel_version"
    exit 0
  fi
  die "existing install in $prefix differs; run \"$prefix/bin/podman-static-uninstall.sh\" first"
fi

if [ -d "$prefix" ]; then
  has_entries=0
  shopt -s dotglob nullglob
  for entry in "$prefix"/*; do
    has_entries=1
    break
  done
  shopt -u dotglob nullglob
  if [ "$has_entries" -ne 0 ]; then
    die "prefix is not empty and has no podman-static manifest: $prefix"
  fi
fi

run_preflight

created_prefix=0
if [ ! -d "$prefix" ]; then
  mkdir -p "$prefix"
  created_prefix=1
fi
staging=$prefix/.install.$$
cleanup() {
  local rc=$? keep entry
  rm -rf "$staging"
  if [ "$rc" -ne 0 ] && [ "$created_prefix" -eq 1 ] && [ -d "$prefix" ]; then
    keep=0
    shopt -s dotglob nullglob
    for entry in "$prefix"/*; do
      keep=1
      break
    done
    shopt -u dotglob nullglob
    if [ "$keep" -eq 0 ]; then
      rmdir "$prefix" 2>/dev/null || true
    fi
  fi
  exit "$rc"
}
trap cleanup EXIT

[ ! -e "$staging" ] || die "staging path already exists: $staging"
mkdir "$staging"

mkdir -p "$staging/lib"
cp -a "$src/bin" "$staging/bin"
cp -a "$src/lib/podman" "$staging/lib/podman"
cp -a "$src/share" "$staging/share"
mkdir -p "$staging/etc/containers" "$staging/share/doc/podman-static"

chmod 0755 "$staging/bin/"*
chmod 0755 "$staging/lib/podman/"*

render_template "$src/env.sh.in" "$staging/bin/podman-env.sh"
render_template "$src/etc/containers/containers.conf.in" \
  "$staging/etc/containers/containers.conf"
render_template "$src/etc/containers/storage.conf.in" \
  "$staging/etc/containers/storage.conf"

cp -p "$src/etc/containers/registries.conf" "$staging/etc/containers/registries.conf"
cp -p "$src/etc/containers/policy.json" "$staging/etc/containers/policy.json"
chmod 0644 "$staging/etc/containers/registries.conf" \
  "$staging/etc/containers/policy.json"

cp -p "$src/README.md" "$staging/share/doc/podman-static/README.md"
chmod 0644 "$staging/share/doc/podman-static/README.md"
if [ -f "$src/LICENSE" ]; then
  cp -p "$src/LICENSE" "$staging/share/doc/podman-static/LICENSE"
  chmod 0644 "$staging/share/doc/podman-static/LICENSE"
fi

cp -p "$src/uninstall.sh" "$staging/bin/podman-static-uninstall.sh"
chmod 0755 "$staging/bin/podman-static-uninstall.sh"

chmod -R u-s,g-s "$staging"

shopt -s dotglob nullglob
for entry in "$staging"/*; do
  mv "$entry" "$prefix/"
done
shopt -u dotglob nullglob
rmdir "$staging"

write_manifest

cat <<EOF
Installed podman-static $rel_version to $prefix
Activate:  . "$prefix/bin/podman-env.sh"
Verify:    podman --version
Try:       podman run --rm docker.io/library/alpine echo hello
Uninstall: "$prefix/bin/podman-static-uninstall.sh"
EOF
