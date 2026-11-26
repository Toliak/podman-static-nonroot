from __future__ import annotations

import hashlib
import posixpath
import re
import tarfile
from pathlib import Path

from helpers import extract_tarball, load_vars, user_tarball_path

TOP = "podman-static-user"

TEXT_SUFFIXES: tuple[str, ...] = (".sh", ".in", ".conf", ".json")
TEXT_NAMES: frozenset[str] = frozenset({"README.md", "RELEASE", "LICENSE"})

# `@PREFIX@/etc/containers/...` and `$var/etc/containers/...` are the relocatable
# forms; only a bare absolute `/etc/containers/...` is a hardcoded system path.
SYSTEM_ETC_RE = re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?/etc/containers")

REQUIRED_MEMBERS: frozenset[str] = frozenset(
    {
        "bin/podman",
        "bin/crun",
        "bin/runc",
        "bin/fuse-overlayfs",
        "bin/fusermount3",
        "bin/passt",
        "bin/pasta",
        "lib/podman/conmon",
        "lib/podman/netavark",
        "lib/podman/aardvark-dns",
        "lib/podman/catatonit",
        "lib/podman/rootlessport",
        "etc/containers/containers.conf.in",
        "etc/containers/storage.conf.in",
        "etc/containers/registries.conf",
        "etc/containers/policy.json",
        "env.sh.in",
        "install.sh",
        "uninstall.sh",
        "README.md",
        "RELEASE",
        "share/seccomp.json",
        "share/bash-completion/completions/podman",
    }
)


def _tarball(artifacts: Path) -> Path:
    return user_tarball_path(artifacts, load_vars())


def _member_map(artifacts: Path) -> dict[str, tarfile.TarInfo]:
    with tarfile.open(_tarball(artifacts), "r:gz") as tf:
        return {member.name: member for member in tf.getmembers()}


def _payload(members: dict[str, tarfile.TarInfo]) -> dict[str, tarfile.TarInfo]:
    prefix = TOP + "/"
    return {name[len(prefix) :]: m for name, m in members.items() if name.startswith(prefix)}


def _read_text(artifacts: Path, name: str) -> str:
    with tarfile.open(_tarball(artifacts), "r:gz") as tf:
        handle = tf.extractfile(name)
        assert handle is not None, name
        return handle.read().decode("utf-8", errors="replace")


def _is_text(rel: str) -> bool:
    return rel.endswith(TEXT_SUFFIXES) or rel in TEXT_NAMES


def _text_members(artifacts: Path) -> list[tuple[str, str]]:
    members = _member_map(artifacts)
    return [
        (name[len(TOP) + 1 :], _read_text(artifacts, name))
        for name, member in members.items()
        if member.isfile() and _is_text(name[len(TOP) + 1 :])
    ]


def test_user_tarball_name(artifacts: Path, tmp_path: Path) -> None:
    v = load_vars()
    tarball = user_tarball_path(artifacts, v)
    assert tarball == artifacts / v["USER_FILE"]
    assert tarball.is_file(), tarball
    assert tarball.name.endswith("-user.tar.gz"), tarball.name
    root = extract_tarball(tarball, tmp_path)
    assert root == tmp_path / TOP and root.is_dir(), root


def test_member_paths_safe(artifacts: Path) -> None:
    for name in _member_map(artifacts):
        assert name == TOP or name.startswith(TOP + "/"), name
        assert not name.startswith("/"), name
        assert not name.startswith("./"), name
        assert ".." not in name.split("/"), name


def test_no_forbidden_payload(artifacts: Path) -> None:
    members = _member_map(artifacts)
    for name in members:
        lowered = name.lower()
        for token in ("systemd", "quadlet", "usr/", "/docker"):
            assert token not in lowered, f"{token} in {name}"
    assert not any(n == TOP + "/usr" or n.startswith(TOP + "/usr/") for n in members)
    assert TOP + "/etc/containers/containers.conf" not in members
    assert TOP + "/etc/containers/storage.conf" not in members


def test_required_members(artifacts: Path) -> None:
    payload = _payload(_member_map(artifacts))
    present = {name for name, m in payload.items() if m.isfile() or m.issym() or m.islnk()}
    missing = REQUIRED_MEMBERS - present
    assert not missing, f"missing required members: {sorted(missing)}"
    if "LICENSE" in payload:
        assert payload["LICENSE"].isfile(), "LICENSE must be a regular file"


def test_pasta_symlink_when_present(artifacts: Path) -> None:
    payload = _payload(_member_map(artifacts))
    assert "bin/passt" in payload, "bin/passt missing"
    assert "bin/pasta" in payload, "bin/pasta missing"
    pasta = payload["bin/pasta"]
    if pasta.issym():
        assert pasta.linkname == "passt", f"bin/pasta -> {pasta.linkname}"


def test_no_avx2_half_pair(artifacts: Path) -> None:
    payload = _payload(_member_map(artifacts))
    passt = "bin/passt.avx2" in payload
    pasta = "bin/pasta.avx2" in payload
    assert passt == pasta, "passt.avx2 and pasta.avx2 must both be present or both absent"
    if pasta:
        avx2 = payload["bin/pasta.avx2"]
        assert avx2.issym(), "bin/pasta.avx2 must be a symlink"
        assert avx2.linkname == "passt.avx2", f"bin/pasta.avx2 -> {avx2.linkname}"


def test_templates_have_placeholder(artifacts: Path) -> None:
    for rel in (
        "env.sh.in",
        "etc/containers/containers.conf.in",
        "etc/containers/storage.conf.in",
    ):
        text = _read_text(artifacts, f"{TOP}/{rel}")
        assert "@PREFIX@" in text, f"{rel} lacks @PREFIX@"


def test_text_members_have_no_system_paths(artifacts: Path) -> None:
    for rel, text in _text_members(artifacts):
        assert "/usr/local" not in text, f"{rel} hardcodes /usr/local"
        scrubbed = SYSTEM_ETC_RE.sub("", text)
        scrubbed = scrubbed.replace("@PREFIX@/etc/containers", "")
        scrubbed = scrubbed.replace("/etc/containers/policy.json", "")
        assert "/etc/containers" not in scrubbed, f"{rel} hardcodes /etc/containers"


def test_release_file(artifacts: Path) -> None:
    v = load_vars()
    fields: dict[str, str] = {}
    for line in _read_text(artifacts, f"{TOP}/RELEASE").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key.strip()] = value.strip()
    assert fields["format"] == "1", fields
    assert fields["name"] == "podman-static", fields
    assert fields["version"] == v["PKG_VERSION"], fields
    assert fields["release"] == v["PKG_RELEASE"], fields
    assert fields["arch"] == v["ARCH"], fields


def test_modes_and_no_special(artifacts: Path) -> None:
    members = _member_map(artifacts)
    payload = _payload(members)
    for name, member in members.items():
        assert not (member.isdev() or member.isfifo()), f"special file: {name}"
        assert member.mode & 0o6000 == 0, f"setuid/setgid bit: {name}"
    for rel in ("bin/podman", "lib/podman/conmon", "install.sh", "uninstall.sh"):
        assert payload[rel].mode & 0o111, f"{rel} not executable"
    for rel in (
        "env.sh.in",
        "etc/containers/containers.conf.in",
        "etc/containers/storage.conf.in",
        "README.md",
    ):
        assert not payload[rel].mode & 0o111, f"{rel} must not be executable"


def test_no_absolute_symlinks(artifacts: Path) -> None:
    for name, member in _member_map(artifacts).items():
        if not member.issym():
            continue
        target = member.linkname
        assert not posixpath.isabs(target), f"{name} -> {target} is absolute"
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
        assert not resolved.startswith(".."), f"{name} -> {target} escapes the payload"
        assert resolved == TOP or resolved.startswith(TOP + "/"), f"{name} -> {target} escapes"


def test_user_tarball_in_sha256sums(artifacts: Path) -> None:
    v = load_vars()
    entries: dict[str, str] = {}
    for line in (artifacts / "SHA256SUMS").read_text().splitlines():
        if line.strip():
            digest, name = line.split()
            entries[name] = digest
    user_file = v["USER_FILE"]
    assert user_file in entries, entries
    actual = hashlib.sha256((artifacts / user_file).read_bytes()).hexdigest()
    assert entries[user_file] == actual, user_file
