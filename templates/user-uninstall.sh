#!/usr/bin/env bash
# podman-static non-root user uninstaller.
#
# Removes only the files recorded in .podman-static/manifest that are still
# unchanged. Everything under <prefix>/var is always left untouched.
set -euo pipefail

die() {
  printf 'uninstall.sh: error: %s\n' "$*" >&2
  exit 1
}

warn() {
  printf 'uninstall.sh: warning: %s\n' "$*" >&2
}

usage() {
  cat <<'EOF'
Usage: uninstall.sh [--prefix PATH]

Remove a podman-static user install from PATH. When run from an installed
prefix (bin/podman-static-uninstall.sh) the prefix can be derived automatically.

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

validate_rel() {
  local p=$1
  if [ -z "$p" ]; then
    die "malformed manifest: empty path"
  fi
  case $p in
    /*) die "malformed manifest: absolute path: $p" ;;
  esac
  case $p in
    *[[:space:]]*) die "malformed manifest: whitespace in path: $p" ;;
  esac
  case "/$p/" in
    */../*) die "malformed manifest: '..' path segment: $p" ;;
  esac
}

tmp=
cleanup_tmp() {
  if [ -n "$tmp" ]; then
    rm -f "$tmp"
  fi
}
trap cleanup_tmp EXIT

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
elif [ "$(basename "$0")" = "podman-static-uninstall.sh" ]; then
  script_dir=$(cd "$(dirname "$0")" && pwd -P)
  candidate=$(cd "$script_dir/.." && pwd -P)
  if [ -f "$candidate/.podman-static/manifest" ]; then
    prefix=$candidate
  fi
fi

if [ -z "${prefix:-}" ]; then
  die "cannot determine install prefix; pass --prefix PATH"
fi
case $prefix in
  */) prefix=${prefix%/} ;;
esac
[ -n "$prefix" ] || die "prefix must not be empty"

if [ "$(euid)" = "0" ]; then
  die "refusing to uninstall as root; run as a regular user"
fi

manifest=$prefix/.podman-static/manifest
if [ ! -f "$manifest" ] || [ ! -r "$manifest" ]; then
  die "$prefix does not look like a podman-static install (no manifest)"
fi

dirs=()
files=()
links=()
first=1
lineno=0
while IFS= read -r line; do
  lineno=$((lineno + 1))
  if [ "$first" -eq 1 ]; then
    if [ "$line" != "format=1" ]; then
      die "malformed manifest: first line must be format=1"
    fi
    first=0
    continue
  fi
  if [ -z "$line" ]; then
    continue
  fi
  case $line in
    name=* | version=* | release=* | arch=*) ;;
    dir=*)
      rel=${line#dir=}
      validate_rel "$rel"
      dirs+=("$rel")
      ;;
    file=*)
      rest=${line#file=}
      case $rest in
        *' '*) ;;
        *) die "malformed manifest line $lineno: $line" ;;
      esac
      hash=${rest%% *}
      rel=${rest#* }
      case $hash in
        '' | *[!0-9a-f]*) die "malformed manifest line $lineno: bad hash" ;;
      esac
      if [ "${#hash}" -ne 64 ] || [ -z "$rel" ]; then
        die "malformed manifest line $lineno: bad file entry"
      fi
      validate_rel "$rel"
      files+=("$hash $rel")
      ;;
    link=*)
      rest=${line#link=}
      case $rest in
        *' '*) ;;
        *) die "malformed manifest line $lineno: $line" ;;
      esac
      target=${rest%% *}
      rel=${rest#* }
      if [ -z "$target" ] || [ -z "$rel" ]; then
        die "malformed manifest line $lineno: bad link entry"
      fi
      case $target in
        /*) die "malformed manifest line $lineno: absolute link target" ;;
        *[[:space:]]*) die "malformed manifest line $lineno: whitespace in link target" ;;
      esac
      validate_rel "$rel"
      links+=("$target $rel")
      ;;
    *)
      die "malformed manifest line $lineno: $line"
      ;;
  esac
done <"$manifest"

if [ "$first" -ne 0 ]; then
  die "malformed manifest: empty manifest"
fi

blocked=0
blocked_list=()
if [ "${#files[@]}" -gt 0 ]; then
  for entry in "${files[@]}"; do
    hash=${entry%% *}
    rel=${entry#* }
    full=$prefix/$rel
    if [ ! -e "$full" ] && [ ! -L "$full" ]; then
      continue
    fi
    if [ -L "$full" ] || [ ! -f "$full" ]; then
      warn "$rel has been modified; keeping it"
      blocked=$((blocked + 1))
      blocked_list+=("$rel")
      continue
    fi
    actual=$(sha256sum "$full")
    actual=${actual%% *}
    if [ "$actual" != "$hash" ]; then
      warn "$rel has been modified; keeping it"
      blocked=$((blocked + 1))
      blocked_list+=("$rel")
      continue
    fi
    rm -f "$full"
  done
fi

if [ "${#links[@]}" -gt 0 ]; then
  for entry in "${links[@]}"; do
    target=${entry%% *}
    rel=${entry#* }
    full=$prefix/$rel
    if [ ! -e "$full" ] && [ ! -L "$full" ]; then
      continue
    fi
    if [ ! -L "$full" ] || [ "$(readlink "$full")" != "$target" ]; then
      warn "$rel has been modified; keeping it"
      blocked=$((blocked + 1))
      blocked_list+=("$rel")
      continue
    fi
    rm -f "$full"
  done
fi

if [ "${#dirs[@]}" -gt 0 ]; then
  tmp=$(mktemp)
  for rel in "${dirs[@]}"; do
    slashes=${rel//[!\/]/}
    printf '%d\t%s\n' "${#slashes}" "$rel" >>"$tmp"
  done
  while IFS=$'\t' read -r _ rel; do
    rmdir "$prefix/$rel" 2>/dev/null || true
  done < <(LC_ALL=C sort -rn -k1,1 "$tmp")
  rm -f "$tmp"
  tmp=
fi

if [ "$blocked" -eq 0 ]; then
  rm -f "$manifest"
  rmdir "$prefix/.podman-static" 2>/dev/null || true
  printf 'Removed podman-static from %s\n' "$prefix"
else
  printf 'uninstall.sh: %d path(s) preserved because they were modified:\n' "$blocked" >&2
  for rel in "${blocked_list[@]}"; do
    printf '  %s\n' "$rel" >&2
  done
fi

printf 'Note: container images and volumes under %s/var were left untouched.\n' "$prefix"

if [ "$blocked" -ne 0 ]; then
  exit 1
fi
