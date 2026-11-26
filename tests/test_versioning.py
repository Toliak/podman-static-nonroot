from __future__ import annotations

from helpers import ARCH_MAP, REQUIRED_VAR_KEYS, VERSION_RE, load_vars, run_tool


def test_default_vars() -> None:
    v = load_vars()
    for key in REQUIRED_VAR_KEYS:
        assert key in v, f"version.sh missing KEY={key}"
    assert v["PKG_NAME"] == "podman-static"
    assert VERSION_RE.match(v["PKG_VERSION"]), v["PKG_VERSION"]
    assert v["PKG_VERSION"] == "6.2.0"
    assert v["PKG_RELEASE"].isdigit()
    assert v["PKG_RELEASE"] == "1"
    assert v["PLATFORM"] == "linux/amd64"
    assert v["ARCH"] == "amd64"


def test_default_arch_map_and_filenames() -> None:
    v = load_vars()
    assert v["ARCH_DEB"] == ARCH_MAP["amd64"]["deb"]
    assert v["ARCH_RPM"] == ARCH_MAP["amd64"]["rpm"] == "x86_64"
    assert v["ARCH_PKG"] == ARCH_MAP["amd64"]["pkg"] == "x86_64"
    assert v["DEB_FILE"] == "podman-static_6.2.0-1_amd64.deb"
    assert v["RPM_FILE"] == "podman-static-6.2.0-1.x86_64.rpm"
    assert v["PKG_FILE"] == "podman-static-6.2.0-1-x86_64.pkg.tar.zst"


def test_describe_override_distance() -> None:
    v = load_vars({"PODMAN_STATIC_DESCRIBE": "v6.3.2-4-gabc1234"})
    assert v["PKG_VERSION"] == "6.3.2"
    assert v["PKG_RELEASE"] == "4"
    assert VERSION_RE.match(v["PKG_VERSION"])


def test_describe_bare_tag_release_one() -> None:
    v = load_vars({"PODMAN_STATIC_DESCRIBE": "v6.2.0"})
    assert v["PKG_VERSION"] == "6.2.0"
    assert v["PKG_RELEASE"] == "1"


def test_env_fallback_to_podman_version() -> None:
    v = load_vars(
        {
            "PODMAN_STATIC_GIT": "false",
            "PODMAN_STATIC_PODMAN_VERSION": "v6.5.1",
        }
    )
    assert v["PKG_VERSION"] == "6.5.1"
    assert v["PKG_RELEASE"] == "1"
    assert "6.5.1" in v["DEB_FILE"]


def test_platform_arm64_arch_map() -> None:
    v = load_vars({"PLATFORM": "linux/arm64"})
    assert v["ARCH"] == "arm64"
    assert v["ARCH_DEB"] == "arm64"
    assert v["ARCH_RPM"] == "aarch64"
    assert v["ARCH_PKG"] == "aarch64"
    assert ARCH_MAP["arm64"] == {"deb": "arm64", "rpm": "aarch64", "pkg": "aarch64"}


def test_single_key_mode() -> None:
    version = run_tool("bash", "scripts/version.sh", "PKG_VERSION")
    assert version.stdout.strip() == "6.2.0"
    arch = run_tool("bash", "scripts/version.sh", "ARCH")
    assert arch.stdout.strip() == "amd64"
