from __future__ import annotations

import hashlib
import re
from pathlib import Path

from helpers import load_vars, run_tool


def test_out_has_exactly_packages_and_sums(artifacts: Path) -> None:
    v = load_vars()
    expected = {v["DEB_FILE"], v["RPM_FILE"], v["PKG_FILE"], v["USER_FILE"], "SHA256SUMS"}
    present = {path.name for path in artifacts.iterdir() if path.is_file()}
    assert expected <= present, expected - present
    package_files = {name for name in present if name.endswith((".deb", ".rpm", ".pkg.tar.zst"))}
    assert package_files == {v["DEB_FILE"], v["RPM_FILE"], v["PKG_FILE"]}, package_files


def test_sha256sums(artifacts: Path) -> None:
    v = load_vars()
    expected_names = {v["DEB_FILE"], v["RPM_FILE"], v["PKG_FILE"], v["USER_FILE"]}
    lines = [line for line in (artifacts / "SHA256SUMS").read_text().splitlines() if line.strip()]
    assert len(lines) == 4, lines
    seen: set[str] = set()
    for line in lines:
        parts = line.split()
        assert len(parts) == 2, f"malformed line: {line}"
        digest, name = parts
        assert re.fullmatch(r"[0-9a-fA-F]{64}", digest), digest
        assert name in expected_names, name
        assert name not in seen, f"duplicate entry: {name}"
        seen.add(name)
        data = (artifacts / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest.lower(), name
    assert seen == expected_names, expected_names - seen


def test_basenames_in_release_assets(artifacts: Path) -> None:
    v = load_vars()
    out = run_tool("make", "print-release-assets").stdout
    for name in (v["DEB_FILE"], v["RPM_FILE"], v["PKG_FILE"], v["USER_FILE"], "SHA256SUMS"):
        assert name in out, f"{name} missing from print-release-assets"


def test_release_assets_lists_both_arches() -> None:
    raw = run_tool("make", "print-release-assets").stdout.splitlines()
    out = [line for line in raw if line.strip() and not line.startswith("make[")]
    amd64 = load_vars({"PLATFORM": "linux/amd64", "ARCH": "amd64"})
    arm64 = load_vars({"PLATFORM": "linux/arm64", "ARCH": "arm64"})
    expected = {
        amd64["DEB_FILE"],
        amd64["RPM_FILE"],
        amd64["PKG_FILE"],
        amd64["USER_FILE"],
        arm64["DEB_FILE"],
        arm64["RPM_FILE"],
        arm64["PKG_FILE"],
        arm64["USER_FILE"],
        "SHA256SUMS",
    }
    assert len(out) == 9, out
    assert set(out) == expected, expected.symmetric_difference(out)
