from __future__ import annotations

import os
from pathlib import Path

import pytest

from helpers import (
    ROOT,
    extract_tarball,
    load_vars,
    pack_fixture,
    package_paths,
    user_tarball_path,
)

E2E_ENABLED = os.environ.get("PODMAN_STATIC_E2E") == "1"

E2E_MARKS = (
    pytest.mark.e2e,
    pytest.mark.skipif(
        not E2E_ENABLED,
        reason="e2e opt-in: set PODMAN_STATIC_E2E=1 to run real upstream builds",
    ),
)


@pytest.fixture(scope="session")
def assets() -> Path:
    """Path to the read-only synthetic fixture asset tree."""
    return ROOT / "tests" / "fixtures" / "asset"


@pytest.fixture(scope="session")
def artifacts(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Pack the fixture tree once per session and return the output directory."""
    out_dir = tmp_path_factory.mktemp("pack")
    pack_fixture(out_dir)
    v = load_vars()
    for fmt, path in package_paths(out_dir, v).items():
        assert path.is_file(), f"missing {fmt} package: {path}"
    assert (out_dir / "SHA256SUMS").is_file(), "missing SHA256SUMS"
    user_tarball = user_tarball_path(out_dir, v)
    assert user_tarball.is_file(), f"missing user tarball: {user_tarball}"
    return out_dir


@pytest.fixture(scope="session")
def user_root(artifacts: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Extract the fixture user tarball once per session and return its root dir."""
    dest = tmp_path_factory.mktemp("user-tarball")
    return extract_tarball(user_tarball_path(artifacts, load_vars()), dest)


@pytest.fixture
def tmp_home(tmp_path: Path) -> Path:
    """A fresh fake $HOME for future install.sh (Task 2) tests."""
    home = tmp_path / "home"
    home.mkdir()
    return home


@pytest.fixture
def e2e() -> None:
    """Opt-in gate for real upstream e2e tests."""
    if not E2E_ENABLED:
        pytest.skip("set PODMAN_STATIC_E2E=1 to run e2e tests")
