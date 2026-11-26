from __future__ import annotations

import re

from helpers import ROOT, run_tool


def _make(*args: str) -> str:
    return run_tool("make", *args).stdout


def test_pack_targets_dry_run_reference_packager() -> None:
    for target in ("_pack-deb", "_pack-rpm", "_pack-pkg"):
        out = _make("-n", target).lower()
        assert "nfpm" in out or "pack.sh" in out or "package" in out, (
            f"{target} dry-run does not reference packaging: {out}"
        )


def test_public_targets_run_via_podman() -> None:
    for target in ("pack", "pack-user", "test", "lint", "all"):
        out = _make("-n", target).lower()
        assert "podman" in out, f"{target} dry-run does not use podman: {out}"
    assert "_all" in _make("-n", "all"), "all must delegate to _all"


def test_pack_dry_run_runs_both_packagers() -> None:
    out = _make("-n", "_pack")
    assert "scripts/pack.sh" in out, out
    assert "scripts/pack-user.sh" in out, out


def test_pack_user_target_references_pack_user_script() -> None:
    out = _make("-n", "_pack-user")
    assert "scripts/pack-user.sh" in out, out


def test_print_vars() -> None:
    out = _make("print-vars")
    assert re.search(r"PKG_VERSION[^\n]*6\.2\.0", out), out
    assert "podman-static" in out
    assert "UPSTREAM_REF=c55c0fb" in out, out
    assert "USER_FILE=podman-static-6.2.0-1-amd64-user.tar.gz" in out, out


def test_test_target_uses_pytest() -> None:
    out = _make("-n", "_test").lower()
    assert "pytest" in out, out


def test_lint_and_vet_shellcheck_templates() -> None:
    for target in ("_lint", "_vet"):
        out = _make("-n", target)
        assert "shellcheck" in out, out
        assert "templates/*.sh" in out, f"{target} does not shellcheck templates/*.sh: {out}"


def test_tools_image_uses_frozen_lock() -> None:
    containerfile = (ROOT / "Containerfile.tools").read_text()
    assert "uv sync" in containerfile, containerfile
    assert "--frozen" in containerfile, containerfile


def test_phony_lists_core_targets() -> None:
    makefile = (ROOT / "Makefile").read_text()
    phony = "\n".join(line for line in makefile.splitlines() if ".PHONY" in line)
    assert ".PHONY" in makefile
    for target in ("pack", "build", "test", "lint", "fetch", "tools-image", "_all"):
        assert re.search(rf"\b{target}\b", phony), f"{target} not in .PHONY"


def test_clean_dry_run_removes_out() -> None:
    out = _make("-n", "clean")
    assert "rm -rf out" in out, out


def test_no_docker_cli_or_buildx() -> None:
    paths = [
        ROOT / "Makefile",
        *sorted((ROOT / "scripts").glob("*.sh")),
        *sorted((ROOT / "templates").glob("*.sh")),
    ]
    for path in paths:
        text = path.read_text().lower()
        for forbidden in ("docker build", "docker run", "buildx", "dist/podman-static"):
            assert forbidden not in text, f"{path}: {forbidden}"
