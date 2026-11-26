from __future__ import annotations

import io
import os
import re
import subprocess
import tarfile
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")

ARCH_MAP: dict[str, dict[str, str]] = {
    "amd64": {"deb": "amd64", "rpm": "x86_64", "pkg": "x86_64"},
    "arm64": {"deb": "arm64", "rpm": "aarch64", "pkg": "aarch64"},
}

FIXTURE_FILES: frozenset[str] = frozenset(
    {
        "README.md",
        "etc/containers/containers.conf",
        "etc/containers/policy.json",
        "etc/containers/registries.conf",
        "etc/containers/seccomp.json",
        "etc/containers/storage.conf.d/00-podman-static.conf",
        "usr/local/bin/aardvark-dns",
        "usr/local/bin/catatonit",
        "usr/local/bin/conmon",
        "usr/local/bin/crun",
        "usr/local/bin/fuse-overlayfs",
        "usr/local/bin/fusermount3",
        "usr/local/bin/netavark",
        "usr/local/bin/passt",
        "usr/local/bin/pasta",
        "usr/local/bin/podman",
        "usr/local/bin/rootlessport",
        "usr/local/bin/runc",
        "usr/local/lib/podman/helper",
        "usr/local/libexec/podman/quadlet",
        "usr/local/lib/systemd/system-generators/podman-system-generator",
        "usr/local/lib/systemd/user-generators/podman-user-generator",
        "usr/local/share/bash-completion/completions/podman",
        "usr/local/share/fish/vendor_completions.d/podman.fish",
        "usr/local/share/zsh/site-functions/_podman",
    }
)

PKG_EXTRA_FILES: frozenset[str] = frozenset(
    {
        "usr/bin/docker",
        "usr/share/doc/podman-static/README.md",
    }
)

EXPECTED_FILES: frozenset[str] = frozenset((FIXTURE_FILES - {"README.md"}) | PKG_EXTRA_FILES)

QUADLET_GENERATORS: frozenset[str] = frozenset(
    {
        "usr/local/lib/systemd/system-generators/podman-system-generator",
        "usr/local/lib/systemd/user-generators/podman-user-generator",
    }
)

PLAN_BINARIES: frozenset[str] = frozenset(
    {
        "usr/local/bin/podman",
        "usr/local/bin/crun",
        "usr/local/bin/runc",
        "usr/local/bin/conmon",
        "usr/local/bin/netavark",
        "usr/local/bin/aardvark-dns",
        "usr/local/bin/passt",
        "usr/local/bin/pasta",
        "usr/local/bin/fuse-overlayfs",
        "usr/local/bin/catatonit",
        "usr/local/bin/rootlessport",
        "usr/local/libexec/podman/quadlet",
    }
)

PKG_METADATA_FILES: frozenset[str] = frozenset(
    {
        ".PKGINFO",
        ".MTREE",
        ".BUILDINFO",
        ".INSTALL",
        ".CHANGELOG",
    }
)

TOLERATED_ROOT_ENTRIES: frozenset[str] = frozenset({"README.md"})

REQUIRED_VAR_KEYS: tuple[str, ...] = (
    "PKG_NAME",
    "PKG_VERSION",
    "PKG_RELEASE",
    "ARCH",
    "ARCH_DEB",
    "ARCH_RPM",
    "ARCH_PKG",
    "PLATFORM",
    "VERSION_SCHEME",
    "DEB_FILE",
    "RPM_FILE",
    "PKG_FILE",
)


def normalize(name: str) -> str:
    """Strip leading './' and '/' components and any trailing slashes from a path."""
    name = name.strip()
    while name.startswith("./") or name.startswith("/"):
        name = name[2:] if name.startswith("./") else name[1:]
    return name.rstrip("/")


def run_tool(
    *args: str,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a command under a merged environment, defaulting to ROOT, optionally asserting rc."""
    merged = dict(os.environ)
    if env:
        merged.update(env)
    result = subprocess.run(
        list(args),
        cwd=cwd or ROOT,
        env=merged,
        capture_output=True,
        text=True,
        check=False,
    )
    if check:
        assert result.returncode == 0, (
            f"command failed: {args!r}\nrc={result.returncode}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


def load_vars(env: dict[str, str] | None = None) -> dict[str, str]:
    """Run scripts/version.sh and parse its KEY=value lines into a dict.

    The wrapper injects derived vars into the container environment; neutralize
    them here so each test controls version.sh's inputs explicitly.
    """
    clean = {
        "PLATFORM": "",
        "ARCH": "",
        "PKG_NAME": "",
        "PKG_VERSION": "",
        "PKG_RELEASE": "",
        "UPSTREAM_VERSION": "",
        "UPSTREAM_REF": "",
        "UPSTREAM_REPO": "",
        "NFPM_VERSION": "",
        "NFPM_BIN": "",
        "ASSET_DIR": "",
        "OUT_DIR": "",
        "CACHE_DIR": "",
    }
    if env:
        clean.update(env)
    result = run_tool("bash", "scripts/version.sh", env=clean)
    out: dict[str, str] = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip()
    return out


def nfpm_config(
    asset_dir: str | Path = "tests/fixtures/asset",
    env: dict[str, str] | None = None,
) -> str:
    """Render the nfpm.yaml template through scripts/gen-nfpm.sh and return the YAML text."""
    merged = dict(env or {})
    merged["ASSET_DIR"] = str(asset_dir)
    result = run_tool("bash", "scripts/gen-nfpm.sh", env=merged)
    return result.stdout


def pack_fixture(out_dir: Path) -> Path:
    """Pack the synthetic fixture tree into out_dir via the internal make target."""
    run_tool(
        "make",
        "_pack",
        "ASSET_DIR=tests/fixtures/asset",
        f"OUT_DIR={out_dir}",
    )
    return out_dir


def package_paths(out_dir: Path, vars: dict[str, str]) -> dict[str, Path]:
    """Map format keys to the expected package file paths inside out_dir."""
    return {
        "deb": out_dir / vars["DEB_FILE"],
        "rpm": out_dir / vars["RPM_FILE"],
        "pkg": out_dir / vars["PKG_FILE"],
    }


def read_ar(deb: Path) -> dict[str, bytes]:
    """Parse a .deb ar archive into member name -> bytes using only the stdlib."""
    data = deb.read_bytes()
    assert data.startswith(b"!<arch>\n"), "not an ar archive"
    offset = 8
    members: dict[str, bytes] = {}
    while offset + 60 <= len(data):
        header = data[offset : offset + 60]
        offset += 60
        raw_name = header[0:16].decode("ascii", errors="replace").strip()
        size_field = header[48:58].decode("ascii", errors="replace").strip()
        if not size_field.isdigit():
            break
        size = int(size_field)
        content = data[offset : offset + size]
        offset += size
        if raw_name.startswith("#1/"):
            long_name_len = int(raw_name[3:])
            raw_name = (
                content[:long_name_len].decode("ascii", errors="replace").rstrip("\x00 ").strip()
            )
            content = content[long_name_len:]
        if size % 2 == 1 and data[offset : offset + 1] == b"\n":
            offset += 1
        name = raw_name.rstrip("/").strip()
        if name in {"", "/", "//", "__.SYMDEF", "__.SYMDEF SORTED"}:
            continue
        members[name] = content
    return members


def _ar_member(members: dict[str, bytes], prefix: str) -> bytes:
    """Return the first ar member whose name starts with prefix."""
    for name, content in members.items():
        if name.startswith(prefix):
            return content
    raise AssertionError(f"ar member starting with {prefix!r} not found: {sorted(members)}")


def deb_control(deb: Path) -> tuple[str, str]:
    """Return (control_text, conffiles_text) extracted from the .deb control.tar.*."""
    control_bytes = _ar_member(read_ar(deb), "control.tar")
    control = ""
    conffiles = ""
    with tarfile.open(fileobj=io.BytesIO(control_bytes), mode="r:*") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            name = normalize(member.name)
            if name in {"control", "conffiles"}:
                text = tf.extractfile(member).read().decode("utf-8", errors="replace")
                if name == "control":
                    control = text
                else:
                    conffiles = text
    return control, conffiles


def deb_data_members(deb: Path) -> list[tarfile.TarInfo]:
    """Return the TarInfo members of a .deb data.tar.* payload."""
    data_bytes = _ar_member(read_ar(deb), "data.tar")
    with tarfile.open(fileobj=io.BytesIO(data_bytes), mode="r:*") as tf:
        return tf.getmembers()


def _pkg_tar_bytes(pkg: Path) -> bytes:
    """Decompress a .pkg.tar.zst to an uncompressed tar byte stream via zstd -dc."""
    result = subprocess.run(
        ["zstd", "-dc", str(pkg)],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"zstd -dc failed: {result.stderr.decode('utf-8', errors='replace')}"
    )
    return result.stdout


def list_pkg(pkg: Path) -> list[tarfile.TarInfo]:
    """List .pkg.tar.zst members using zstd -dc plus stdlib tarfile."""
    with tarfile.open(fileobj=io.BytesIO(_pkg_tar_bytes(pkg)), mode="r:") as tf:
        return tf.getmembers()


def read_pkginfo(pkg: Path) -> dict[str, list[str]]:
    """Parse .PKGINFO from a .pkg.tar.zst into key -> list of values."""
    info: dict[str, list[str]] = {}
    with tarfile.open(fileobj=io.BytesIO(_pkg_tar_bytes(pkg)), mode="r:") as tf:
        for member in tf.getmembers():
            if member.isfile() and normalize(member.name) == ".PKGINFO":
                text = tf.extractfile(member).read().decode("utf-8", errors="replace")
                for line in text.splitlines():
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#") or "=" not in stripped:
                        continue
                    key, value = stripped.split("=", 1)
                    info.setdefault(key.strip(), []).append(value.strip())
    return info


def rpm_query(rpm_path: Path) -> str:
    """Return `rpm -qip` stdout (stderr ignored: harmless transaction-lock warning)."""
    result = subprocess.run(
        ["rpm", "-qip", str(rpm_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


def rpm_files(rpm_path: Path) -> list[str]:
    """Return `rpm -qlp` payload path names."""
    result = subprocess.run(
        ["rpm", "-qlp", str(rpm_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.splitlines()


def rpm_symlink_map(rpm_path: Path) -> dict[str, str]:
    """Return symlink name -> target parsed from `rpm2cpio | bsdtar -tvf -` (best effort)."""
    cpio = subprocess.run(
        ["rpm2cpio", str(rpm_path)],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if cpio.returncode != 0 or not cpio.stdout:
        return {}
    verbose = subprocess.run(
        ["bsdtar", "-tvf", "-"],
        input=cpio.stdout,
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if verbose.returncode != 0:
        return {}
    symlinks: dict[str, str] = {}
    for line in verbose.stdout.decode("utf-8", errors="replace").splitlines():
        if not line.startswith("l"):
            continue
        left, _, target = line.partition(" -> ")
        parts = left.split()
        if parts:
            symlinks[normalize(parts[-1])] = target.strip()
    return symlinks


def member_names(members: Iterable[tarfile.TarInfo]) -> list[str]:
    """Return the raw names of TarInfo members."""
    return [member.name for member in members]


def symlink_map(members: Iterable[tarfile.TarInfo]) -> dict[str, str]:
    """Map normalized symlink names to their raw link targets from TarInfo members."""
    return {normalize(member.name): member.linkname for member in members if member.issym()}


def payload_inventory(names: Iterable[str]) -> frozenset[str]:
    """Reduce mixed file/dir/symlink names to the regular-file+symlink payload inventory."""
    normalized = {normalize(name) for name in names}
    normalized = {name for name in normalized if name and name not in PKG_METADATA_FILES}
    directories = {
        name for name in normalized if any(other.startswith(name + "/") for other in normalized)
    }
    return frozenset(normalized - directories)
