from __future__ import annotations

from pathlib import Path

from helpers import (
    EXPECTED_FILES,
    PKG_METADATA_FILES,
    PLAN_BINARIES,
    TOLERATED_ROOT_ENTRIES,
    deb_data_members,
    list_pkg,
    load_vars,
    member_names,
    normalize,
    package_paths,
    payload_inventory,
    rpm_files,
)


def _paths(artifacts: Path) -> dict[str, Path]:
    return package_paths(artifacts, load_vars())


def _inventories(artifacts: Path) -> dict[str, frozenset[str]]:
    paths = _paths(artifacts)
    return {
        "deb": payload_inventory(member_names(deb_data_members(paths["deb"]))),
        "rpm": payload_inventory(rpm_files(paths["rpm"])),
        "pkg": payload_inventory(member_names(list_pkg(paths["pkg"]))),
    }


def test_inventory_identical_across_formats(artifacts: Path) -> None:
    inventories = _inventories(artifacts)
    assert inventories["deb"] == inventories["rpm"] == inventories["pkg"], inventories


def test_inventory_equals_expected(artifacts: Path) -> None:
    for fmt, names in _inventories(artifacts).items():
        reduced = names - TOLERATED_ROOT_ENTRIES
        assert reduced == EXPECTED_FILES, f"{fmt}: {reduced ^ EXPECTED_FILES}"


def test_all_plan_binaries_present(artifacts: Path) -> None:
    for fmt, names in _inventories(artifacts).items():
        assert PLAN_BINARIES <= names, f"{fmt}: missing {PLAN_BINARIES - names}"


def test_no_stray_paths_in_any_package(artifacts: Path) -> None:
    paths = _paths(artifacts)
    name_lists = {
        "deb": member_names(deb_data_members(paths["deb"])),
        "rpm": rpm_files(paths["rpm"]),
        "pkg": member_names(list_pkg(paths["pkg"])),
    }
    exempt = PKG_METADATA_FILES | TOLERATED_ROOT_ENTRIES
    for fmt, names in name_lists.items():
        for raw in names:
            normalized = normalize(raw)
            if normalized and normalized not in exempt:
                assert normalized.split("/")[0] in {"usr", "etc"}, f"{fmt}: stray path {raw}"
