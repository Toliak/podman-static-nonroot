from __future__ import annotations

import os
from pathlib import Path

import pytest

from helpers import ROOT, load_vars, pack_fixture, package_paths

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
    paths = package_paths(out_dir, load_vars())
    for fmt, path in paths.items():
        assert path.is_file(), f"missing {fmt} package: {path}"
    assert (out_dir / "SHA256SUMS").is_file(), "missing SHA256SUMS"
    return out_dir


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
