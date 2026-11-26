from __future__ import annotations

import os
from pathlib import Path

from helpers import FIXTURE_FILES, QUADLET_GENERATORS


def _inventory(root: Path) -> frozenset[str]:
    return frozenset(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    )


def test_fixture_inventory(assets: Path) -> None:
    assert assets.is_dir()
    assert _inventory(assets) == FIXTURE_FILES


def test_quadlet_generators_are_relative_symlinks(assets: Path) -> None:
    for rel in QUADLET_GENERATORS:
        link = assets / rel
        assert link.is_symlink(), f"not a symlink: {rel}"
        target = os.readlink(link)
        assert not os.path.isabs(target), f"absolute symlink target: {target}"
        assert target.startswith(".."), f"not a relative parent link: {target}"
        resolved = (link.parent / target).resolve()
        assert resolved.is_file(), f"broken symlink: {rel} -> {target}"


def test_binaries_are_executable(assets: Path) -> None:
    bindir = assets / "usr/local/bin"
    files = sorted(path for path in bindir.iterdir() if path.is_file())
    assert files, "no binaries in usr/local/bin"
    for binary in files:
        assert binary.stat().st_mode & 0o111, f"not executable: {binary.name}"


def test_etc_containers_config_files(assets: Path) -> None:
    etc = assets / "etc/containers"
    for name in (
        "containers.conf",
        "policy.json",
        "registries.conf",
        "seccomp.json",
        "storage.conf.d/00-podman-static.conf",
    ):
        assert (etc / name).is_file(), f"missing config: {name}"
