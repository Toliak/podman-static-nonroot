from __future__ import annotations

import re

from helpers import ROOT, run_tool


def _make(*args: str) -> str:
    return run_tool("make", *args).stdout


def test_pack_targets_dry_run_reference_packager() -> None:
    for target in ("pack-deb", "pack-rpm", "pack-pkg"):
        out = _make("-n", target).lower()
        assert "nfpm" in out or "pack.sh" in out or "package" in out, (
            f"{target} dry-run does not reference packaging: {out}"
        )


def test_print_vars() -> None:
    out = _make("print-vars")
    assert re.search(r"PKG_VERSION[^\n]*6\.2\.0", out), out
    assert "podman-static" in out


def test_test_target_uses_no_sync_and_pytest() -> None:
    out = _make("-n", "test").lower()
    assert "pytest" in out, out
    assert "--no-sync" in out, out


def test_sync_target_uses_frozen() -> None:
    out = _make("-n", "sync").lower()
    assert "--frozen" in out, out
    assert "sync" in out, out


def test_phony_lists_core_targets() -> None:
    makefile = (ROOT / "Makefile").read_text()
    phony = "\n".join(line for line in makefile.splitlines() if ".PHONY" in line)
    assert ".PHONY" in makefile
    for target in ("pack", "build", "test", "lint"):
        assert re.search(rf"\b{target}\b", phony), f"{target} not in .PHONY"


def test_clean_dry_run_removes_out() -> None:
    out = _make("-n", "clean")
    assert "rm -rf out" in out, out
