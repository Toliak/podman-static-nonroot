from __future__ import annotations

import re
import shutil
from pathlib import Path

from helpers import (
    EXPECTED_FILES,
    load_vars,
    package_paths,
    payload_inventory,
    rpm_files,
    rpm_query,
    rpm_symlink_map,
)


def _rpm(artifacts: Path) -> Path:
    return package_paths(artifacts, load_vars())["rpm"]


def test_filename(artifacts: Path) -> None:
    path = _rpm(artifacts)
    assert path.name == "podman-static-6.2.0-1.x86_64.rpm"
    assert re.fullmatch(r"podman-static-6\.2\.0-1\.x86_64\.rpm", path.name)


def test_rpm_query_fields(artifacts: Path) -> None:
    query = rpm_query(_rpm(artifacts))
    assert re.search(r"Name\s*:\s*podman-static", query)
    assert re.search(r"Version\s*:\s*6\.2\.0", query)
    assert re.search(r"Release\s*:\s*1\b", query)
    assert re.search(r"Architecture\s*:\s*x86_64", query)
    assert re.search(r"License\s*:\s*Apache-2\.0", query)


def test_rpm_payload_inventory(artifacts: Path) -> None:
    names = rpm_files(_rpm(artifacts))
    assert names, "rpm -qlp returned no files"
    inventory = payload_inventory(names)
    assert EXPECTED_FILES <= inventory, EXPECTED_FILES - inventory


def test_rpm_symlink_preserved_optional(artifacts: Path) -> None:
    if not (shutil.which("rpm2cpio") and shutil.which("bsdtar")):
        return
    symlinks = rpm_symlink_map(_rpm(artifacts))
    if not symlinks:
        return
    assert "usr/bin/docker" in symlinks, sorted(symlinks)
