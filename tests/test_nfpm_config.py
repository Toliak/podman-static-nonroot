from __future__ import annotations

import re
from pathlib import Path

from helpers import ROOT, nfpm_config

REQUIRED_SCALARS = {
    "name": "podman-static",
    "arch": "amd64",
    "platform": "linux",
    "version": "6.2.0",
    "release": "1",
    "license": "Apache-2.0",
    "section": "utils",
    "priority": "optional",
}

LABEL_KEYS = ("maintainer", "description", "vendor", "homepage")

TYPE_TOKENS = ("tree", "symlink", "noreplace", "config")

ALLOWED_DST_PREFIXES = (
    "/usr/local",
    "/etc/containers",
    "/usr/share/doc",
    "/usr/bin",
)


def test_required_scalar_fields() -> None:
    config = nfpm_config()
    for key, value in REQUIRED_SCALARS.items():
        pattern = rf"(?m)^\s*{key}:\s*\"?{re.escape(value)}\"?\s*$"
        assert re.search(pattern, config), f"{key}: {value} missing"
    for key in LABEL_KEYS:
        assert re.search(rf"(?m)^\s*{key}:", config), f"{key}: missing"


def test_content_types_and_sections() -> None:
    config = nfpm_config()
    for token in TYPE_TOKENS:
        assert token in config, f"content token {token!r} missing"
    assert "/usr/share/doc/podman-static/README.md" in config
    lines = [line.strip() for line in config.splitlines()]
    assert any(line.startswith("rpm:") for line in lines)
    assert any(line.startswith("archlinux:") for line in lines)


def test_no_remaining_template_tokens() -> None:
    config = nfpm_config()
    for token in (
        "@PKG_NAME@",
        "@PKG_VERSION@",
        "@PKG_RELEASE@",
        "@ARCH@",
        "@ASSET_DIR@",
    ):
        assert token not in config, f"unrendered token {token}"
    assert not re.search(r"@[A-Z][A-Z0-9_]*@", config), "uppercase placeholder remains"


def test_every_dst_is_absolute_system_path() -> None:
    config = nfpm_config()
    dsts = [
        line.split("dst:", 1)[1].strip().strip("\"'")
        for line in config.splitlines()
        if "dst:" in line
    ]
    assert dsts, "no dst: entries found"
    for dst in dsts:
        assert dst.startswith("/"), f"dst not absolute: {dst}"
        assert dst.startswith(ALLOWED_DST_PREFIXES), f"dst not a system path: {dst}"
        assert not dst.startswith("/tmp"), f"temp path leaked: {dst}"
        assert "out/" not in dst and "build/" not in dst, f"build path leaked: {dst}"
        assert str(ROOT) not in dst, f"workspace path leaked: {dst}"


def test_asset_dir_is_substituted() -> None:
    config = nfpm_config()
    assert "tests/fixtures/asset" in config
    assert "@ASSET_DIR@" not in config
    assert str(ROOT) not in config, "absolute workspace path leaked into config"
    custom = nfpm_config(asset_dir=Path("custom-stage"))
    assert "custom-stage" in custom
    assert "tests/fixtures/asset" not in custom
