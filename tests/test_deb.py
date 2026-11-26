from __future__ import annotations

from pathlib import Path

from helpers import (
    EXPECTED_FILES,
    PKG_METADATA_FILES,
    QUADLET_GENERATORS,
    TOLERATED_ROOT_ENTRIES,
    deb_control,
    deb_data_members,
    load_vars,
    member_names,
    normalize,
    package_paths,
    payload_inventory,
    read_ar,
    symlink_map,
)


def _deb(artifacts: Path) -> Path:
    return package_paths(artifacts, load_vars())["deb"]


def test_ar_members(artifacts: Path) -> None:
    members = read_ar(_deb(artifacts))
    assert "debian-binary" in members
    assert any(name.startswith("control.tar") for name in members)
    assert any(name.startswith("data.tar") for name in members)


def test_control_and_conffiles(artifacts: Path) -> None:
    control, conffiles = deb_control(_deb(artifacts))
    assert "Package: podman-static" in control
    assert "Version: 6.2.0-1" in control
    assert "Architecture: amd64" in control
    lines = [normalize(line) for line in conffiles.splitlines() if line.strip()]
    assert lines, "conffiles is empty"
    assert all(line.startswith("etc/containers/") for line in lines), lines


def test_data_inventory(artifacts: Path) -> None:
    inventory = payload_inventory(member_names(deb_data_members(_deb(artifacts))))
    assert EXPECTED_FILES <= inventory, EXPECTED_FILES - inventory


def test_docker_symlink(artifacts: Path) -> None:
    symlinks = symlink_map(deb_data_members(_deb(artifacts)))
    assert "usr/bin/docker" in symlinks
    assert normalize(symlinks["usr/bin/docker"]) == "usr/local/bin/podman"


def test_quadlet_symlinks_preserved(artifacts: Path) -> None:
    symlinks = symlink_map(deb_data_members(_deb(artifacts)))
    for rel in QUADLET_GENERATORS:
        assert rel in symlinks, f"missing symlink {rel}"
        assert symlinks[rel].startswith("../"), symlinks[rel]


def test_no_absolute_build_paths(artifacts: Path) -> None:
    exempt = PKG_METADATA_FILES | TOLERATED_ROOT_ENTRIES
    for name in member_names(deb_data_members(_deb(artifacts))):
        normalized = normalize(name)
        if normalized and normalized not in exempt:
            assert normalized.split("/")[0] in {"usr", "etc"}, name
