from __future__ import annotations

import re
from pathlib import Path

from helpers import (
    deb_control,
    load_vars,
    nfpm_config,
    package_paths,
    read_pkginfo,
    rpm_query,
    run_tool,
)


def test_deb_control_metadata(artifacts: Path) -> None:
    control, _ = deb_control(package_paths(artifacts, load_vars())["deb"])
    assert re.search(r"(?mi)^Package:\s*podman-static\s*$", control)
    assert re.search(r"(?mi)^Version:\s*6\.2\.0-1\s*$", control)
    assert re.search(r"(?mi)^Section:\s*utils\s*$", control)
    assert re.search(r"(?mi)^Priority:\s*optional\s*$", control)
    assert re.search(r"(?mi)^Architecture:\s*amd64\s*$", control)
    assert re.search(r"(?mi)^Maintainer:", control)
    assert re.search(r"(?mi)^Homepage:", control)
    assert re.search(r"(?mi)^Description:", control)


def test_rpm_metadata(artifacts: Path) -> None:
    query = rpm_query(package_paths(artifacts, load_vars())["rpm"])
    assert re.search(r"Name\s*:\s*podman-static", query)
    assert re.search(r"Version\s*:\s*6\.2\.0", query)
    assert re.search(r"Release\s*:\s*1\b", query)
    assert re.search(r"Architecture\s*:\s*x86_64", query)
    assert re.search(r"License\s*:\s*Apache-2\.0", query)
    assert re.search(r"URL\s*:", query)
    assert re.search(r"Summary\s*:", query)


def test_pkginfo_metadata(artifacts: Path) -> None:
    info = read_pkginfo(package_paths(artifacts, load_vars())["pkg"])
    assert info.get("pkgname") == ["podman-static"]
    assert info.get("pkgver") == ["6.2.0-1"]
    assert info.get("arch") == ["x86_64"]
    assert info.get("license") == ["Apache-2.0"]
    assert info.get("packager"), "packager field missing"
    assert info.get("url"), "url field missing"


def test_no_phantom_dependencies(artifacts: Path) -> None:
    paths = package_paths(artifacts, load_vars())
    control, _ = deb_control(paths["deb"])
    assert not re.search(r"(?mi)^Depends:", control), control
    assert "depends:" not in nfpm_config().lower()
    info = read_pkginfo(paths["pkg"])
    assert "depend" not in info, info


def test_release_assets_contain_produced_files(artifacts: Path) -> None:
    v = load_vars()
    out = run_tool("make", "print-release-assets").stdout
    for name in (v["DEB_FILE"], v["RPM_FILE"], v["PKG_FILE"]):
        assert name in out, f"{name} missing from print-release-assets"
