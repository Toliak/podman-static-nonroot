from __future__ import annotations

from pathlib import Path

from helpers import (
    EXPECTED_FILES,
    PKG_METADATA_FILES,
    QUADLET_GENERATORS,
    list_pkg,
    load_vars,
    member_names,
    normalize,
    package_paths,
    payload_inventory,
    read_pkginfo,
    symlink_map,
)


def _pkg(artifacts: Path) -> Path:
    return package_paths(artifacts, load_vars())["pkg"]


def test_filename(artifacts: Path) -> None:
    assert _pkg(artifacts).name == "podman-static-6.2.0-1-x86_64.pkg.tar.zst"


def test_dotfiles(artifacts: Path) -> None:
    names = {normalize(name) for name in member_names(list_pkg(_pkg(artifacts)))}
    assert ".PKGINFO" in names
    assert ".MTREE" in names


def test_pkginfo_fields_and_backup(artifacts: Path) -> None:
    info = read_pkginfo(_pkg(artifacts))
    assert info.get("pkgname") == ["podman-static"]
    assert info.get("pkgver") == ["6.2.0-1"]
    assert info.get("arch") == ["x86_64"]
    assert info.get("license") == ["Apache-2.0"]
    backups = info.get("backup", [])
    assert backups, "no backup entries"
    assert all(normalize(backup).startswith("etc/containers") for backup in backups), backups


def test_payload_inventory(artifacts: Path) -> None:
    inventory = payload_inventory(member_names(list_pkg(_pkg(artifacts))))
    assert EXPECTED_FILES <= inventory, EXPECTED_FILES - inventory
    assert not (inventory & PKG_METADATA_FILES), inventory & PKG_METADATA_FILES


def test_symlinks_preserved(artifacts: Path) -> None:
    symlinks = symlink_map(list_pkg(_pkg(artifacts)))
    assert "usr/bin/docker" in symlinks
    assert normalize(symlinks["usr/bin/docker"]) == "usr/local/bin/podman"
    for rel in QUADLET_GENERATORS:
        assert rel in symlinks, f"missing symlink {rel}"
