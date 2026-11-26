from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

from helpers import run_tool


def _home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return home


def _env(home: Path, **extra: str) -> dict[str, str]:
    env = {
        "HOME": str(home),
        "PODMAN_STATIC_PREFLIGHT": "0",
        "PODMAN_STATIC_EUID": "",
    }
    env.update(extra)
    return env


def _install(
    user_root: Path,
    prefix: Path | str,
    home: Path,
    **extra: str,
) -> subprocess.CompletedProcess[str]:
    return run_tool(
        "bash",
        str(user_root / "install.sh"),
        "--prefix",
        str(prefix),
        env=_env(home, **extra),
        check=False,
    )


def _uninstall(
    uninstaller: Path,
    home: Path,
    **extra: str,
) -> subprocess.CompletedProcess[str]:
    return run_tool("bash", str(uninstaller), env=_env(home, **extra), check=False)


def _snapshot(root: Path, skip: Path) -> dict[str, tuple[str, bytes]]:
    snap: dict[str, tuple[str, bytes]] = {}
    for path in sorted(root.rglob("*")):
        if path == skip or skip in path.parents:
            continue
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            snap[rel] = ("link", os.fsencode(os.readlink(path)))
        elif path.is_file():
            snap[rel] = ("file", path.read_bytes())
        elif path.is_dir():
            snap[rel] = ("dir", b"")
        else:
            snap[rel] = ("other", b"")
    return snap


def test_fresh_install(user_root: Path, tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    result = _install(user_root, prefix, _home(tmp_path))
    assert result.returncode == 0, result.stderr
    for rel in (
        "bin/podman",
        "bin/podman-env.sh",
        "bin/podman-static-uninstall.sh",
        "lib/podman/conmon",
        "etc/containers/containers.conf",
        "etc/containers/storage.conf",
        "etc/containers/registries.conf",
        "etc/containers/policy.json",
        ".podman-static/manifest",
    ):
        assert (prefix / rel).exists(), rel
    assert "Installed podman-static" in result.stdout


def test_no_writes_outside_prefix(user_root: Path, tmp_path: Path) -> None:
    home = _home(tmp_path)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "keep.txt").write_text("keep")
    prefix = tmp_path / "prefix"

    before = _snapshot(tmp_path, prefix)
    result = _install(user_root, prefix, home)
    assert result.returncode == 0, result.stderr
    after = _snapshot(tmp_path, prefix)
    assert before == after


def test_prefix_with_space(user_root: Path, tmp_path: Path) -> None:
    prefix = tmp_path / "with space" / "podman static"
    result = _install(user_root, prefix, _home(tmp_path))
    assert result.returncode == 0, result.stderr
    for rel in (
        "bin/podman-env.sh",
        "etc/containers/containers.conf",
        "etc/containers/storage.conf",
    ):
        text = (prefix / rel).read_text()
        assert str(prefix) in text, rel
        assert "@PREFIX@" not in text, rel


def test_generated_configs_point_into_prefix(user_root: Path, tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    result = _install(user_root, prefix, _home(tmp_path))
    assert result.returncode == 0, result.stderr

    storage = (prefix / "etc/containers/storage.conf").read_text()
    assert f'graphroot = "{prefix}/var/lib/containers/storage"' in storage
    assert f'mount_program = "{prefix}/bin/fuse-overlayfs"' in storage

    containers = (prefix / "etc/containers/containers.conf").read_text()
    assert f'helper_binaries_dir = ["{prefix}/lib/podman", "{prefix}/bin"]' in containers
    assert f'init_path = "{prefix}/lib/podman/catatonit"' in containers
    assert f'seccomp_profile = "{prefix}/share/seccomp.json"' in containers

    env = (prefix / "bin/podman-env.sh").read_text()
    assert f"CONTAINERS_CONF='{prefix}/etc/containers/containers.conf'" in env
    assert f"CONTAINERS_STORAGE_CONF='{prefix}/etc/containers/storage.conf'" in env
    assert f"CONTAINERS_REGISTRIES_CONF='{prefix}/etc/containers/registries.conf'" in env


def test_activation_script_is_idempotent(user_root: Path, tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    result = _install(user_root, prefix, _home(tmp_path))
    assert result.returncode == 0, result.stderr

    script = (
        "set -e\n"
        '. "$1/bin/podman-env.sh"\n'
        '. "$1/bin/podman-env.sh"\n'
        'printf "%s\\n" "$PATH"\n'
        'printf "%s\\n" "$CONTAINERS_CONF"\n'
    )
    env = _env(
        _home(tmp_path),
        PATH="/usr/local/bin:/usr/bin:/bin",
        CONTAINERS_CONF="",
        CONTAINERS_STORAGE_CONF="",
        CONTAINERS_REGISTRIES_CONF="",
        CONTAINERS_POLICY_JSON="",
    )
    activated = run_tool("bash", "-c", script, "_", str(prefix), env=env, check=False)
    assert activated.returncode == 0, activated.stderr
    lines = activated.stdout.splitlines()
    assert lines[0].split(":").count(str(prefix / "bin")) == 1
    assert lines[1] == str(prefix / "etc/containers/containers.conf")


def test_install_ownership_and_modes(user_root: Path, tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    result = _install(user_root, prefix, _home(tmp_path))
    assert result.returncode == 0, result.stderr

    uid = os.getuid()
    for path in (prefix, *prefix.rglob("*")):
        info = path.lstat()
        assert info.st_uid == uid, path
        if not path.is_symlink():
            assert not (info.st_mode & (stat.S_ISUID | stat.S_ISGID)), path

    assert (prefix / "bin/podman").stat().st_mode & 0o111
    assert (prefix / "bin/podman-env.sh").stat().st_mode & 0o777 == 0o644
    assert (prefix / ".podman-static/manifest").stat().st_mode & 0o777 == 0o600


def test_reinstall_is_noop(user_root: Path, tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    home = _home(tmp_path)
    first = _install(user_root, prefix, home)
    assert first.returncode == 0, first.stderr
    second = _install(user_root, prefix, home)
    assert second.returncode == 0, second.stderr
    assert "already" in second.stdout.lower()


def test_reinstall_after_modification_refused(user_root: Path, tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    home = _home(tmp_path)
    first = _install(user_root, prefix, home)
    assert first.returncode == 0, first.stderr
    with (prefix / "bin/podman").open("a") as handle:
        handle.write("tampered\n")
    second = _install(user_root, prefix, home)
    assert second.returncode != 0


def test_root_install_refused(user_root: Path, tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    result = _install(user_root, prefix, _home(tmp_path), PODMAN_STATIC_EUID="0")
    assert result.returncode != 0
    assert "root" in result.stderr.lower()
    assert not prefix.exists()


def test_invalid_prefixes_rejected(user_root: Path, tmp_path: Path) -> None:
    home = _home(tmp_path)
    for bad in ("relative-prefix", str(tmp_path / "a" / ".." / "b"), "/"):
        result = _install(user_root, bad, home)
        assert result.returncode != 0, bad

    regular = tmp_path / "regular"
    regular.write_text("not a directory")
    assert _install(user_root, regular, home).returncode != 0

    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target)
    assert _install(user_root, link, home).returncode != 0


def test_nonempty_unmanaged_prefix_rejected(user_root: Path, tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    (prefix / "foreign").write_text("keep")
    result = _install(user_root, prefix, _home(tmp_path))
    assert result.returncode != 0
    assert (prefix / "foreign").read_text() == "keep"


def test_unsafe_prefix_chars_rejected(user_root: Path, tmp_path: Path) -> None:
    home = _home(tmp_path)
    for bad in (f"{tmp_path}/bad$prefix", f"{tmp_path}/bad&prefix", f"{tmp_path}/bad`x`"):
        result = _install(user_root, bad, home)
        assert result.returncode != 0, bad


def test_preflight_warnings_toggle(user_root: Path, tmp_path: Path) -> None:
    home = _home(tmp_path)
    empty = tmp_path / "empty"
    empty.write_text("")
    missing = "/nonexistent/podman-static-tool"
    overrides = {
        "PODMAN_STATIC_NEWUIDMAP": missing,
        "PODMAN_STATIC_NEWGIDMAP": missing,
        "PODMAN_STATIC_NFT": missing,
        "PODMAN_STATIC_NSENTER": missing,
        "PODMAN_STATIC_FUSE_DEV": missing,
        "PODMAN_STATIC_SUBUID_FILE": str(empty),
        "PODMAN_STATIC_SUBGID_FILE": str(empty),
    }
    enabled = _install(
        user_root,
        tmp_path / "pf-enabled",
        home,
        PODMAN_STATIC_PREFLIGHT="1",
        **overrides,
    )
    assert enabled.returncode == 0, enabled.stderr
    assert "warning" in enabled.stderr.lower()

    disabled = _install(
        user_root,
        tmp_path / "pf-disabled",
        home,
        PODMAN_STATIC_PREFLIGHT="0",
        **overrides,
    )
    assert disabled.returncode == 0, disabled.stderr
    assert "warning" not in disabled.stderr.lower()


def test_uninstall_clean(user_root: Path, tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    home = _home(tmp_path)
    result = _install(user_root, prefix, home)
    assert result.returncode == 0, result.stderr

    uninstaller = prefix / "bin/podman-static-uninstall.sh"
    removed = _uninstall(uninstaller, home, PODMAN_STATIC_PREFIX="")
    assert removed.returncode == 0, removed.stderr
    assert not (prefix / "bin/podman").exists()
    assert not (prefix / ".podman-static/manifest").exists()


def test_uninstall_preserves_modified_foreign_and_var(user_root: Path, tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    home = _home(tmp_path)
    result = _install(user_root, prefix, home)
    assert result.returncode == 0, result.stderr

    modified = prefix / "etc/containers/registries.conf"
    modified.write_text(modified.read_text() + "\n# changed\n")
    marker = prefix / "var/lib/containers/storage/marker"
    marker.parent.mkdir(parents=True)
    marker.write_text("data")
    foreign = prefix / "foreign.txt"
    foreign.write_text("keep")

    uninstaller = prefix / "bin/podman-static-uninstall.sh"
    removed = _uninstall(uninstaller, home, PODMAN_STATIC_PREFIX="")
    assert removed.returncode == 1
    assert modified.exists()
    assert modified.read_text().endswith("# changed\n")
    assert marker.exists()
    assert foreign.exists()
    assert not (prefix / "bin/podman").exists()
    assert (prefix / ".podman-static/manifest").exists()
