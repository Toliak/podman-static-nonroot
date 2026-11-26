# podman-static-nonroot

Builds `.deb`, `.rpm` and Arch `.pkg.tar.zst` packages of the statically linked
(musl) rootless podman binaries from the vendored `mgoltzsche/podman-static`
upstream. This is **Task 1** (packaging). The relocatable **non-root tarball +
`install.sh` (Task 2)**, the QEMU VM harness, CI/release wiring, GPG signatures
and maintainer scripts are **planned, not implemented**.

Packages install to the same absolute paths upstream uses (`/usr/local`,
`/etc/containers`); they contain NO runtime deps and NO maintainer scripts.

## Prerequisites

- `make`, `bash`, `curl`, `uv` (Python >= 3.10 for the `tests/` project).
- Test-side archive inspection: `ar`, `tar`, `rpm`, `zstd`/`bsdtar` where
  available. These are NOT needed to BUILD packages.
- `docker` + `buildx` — ONLY for `make build` (real upstream binaries).
- Packaging uses **nfpm** (pinned `v2.49.0`), a rootless pure-Go static binary
  downloaded on first use and cached at `.tools/nfpm-<version>`. No host
  `dpkg-deb` / `rpmbuild` / `makepkg`, and no root, are needed.

## Quickstart

```sh
make all                # packs the synthetic fixture + test + lint; green with NO docker
make pack-fixture       # fixture packages into out/ only (no docker, no host tools)
make print-vars         # show derived VERSION/RELEASE/ARCH and paths
make clean              # rm -rf out/
```

Real packages (opt-in, needs docker/buildx):

```sh
make build              # real upstream build -> out/asset/podman-linux-<ARCH>/
make pack               # all 3 formats -> out/ (+ SHA256SUMS)
```

`make pack-deb` / `make pack-rpm` / `make pack-pkg` build one format;
`make checksums` rewrites `out/SHA256SUMS`;
`make print-release-assets` prints the 6 package files (3 formats x 2 arches) +
`SHA256SUMS` for a future CI step (CI wiring is deferred, the vendored upstream
workflow is left untouched).

## out/ layout

```
out/
├── asset/podman-linux-<ARCH>/                          staged tree (usr/local/, etc/containers/, README.md)
├── nfpm-<ARCH>.yaml                                    rendered nfpm config
├── podman-static_<VERSION>-<RELEASE>_<ARCH_DEB>.deb
├── podman-static-<VERSION>-<RELEASE>.<ARCH_RPM>.rpm
├── podman-static-<VERSION>-<RELEASE>-<ARCH_PKG>.pkg.tar.zst
└── SHA256SUMS
```

## Naming / version scheme

VERSION/RELEASE come from `git -C dist/podman-static describe --tags --always`
(`v6.2.0-1-gc55c0fb` -> `6.2.0` / `1`), falling back to `PODMAN_VERSION=v6.2.0`.
`ARCH` is `amd64` or `arm64`; per-format arch:

| Format | Filename | ARCH (amd64 / arm64) |
| --- | --- | --- |
| deb | `podman-static_<V>-<R>_<ARCH_DEB>.deb` | `amd64` / `arm64` |
| rpm | `podman-static-<V>-<R>.<ARCH_RPM>.rpm` | `x86_64` / `aarch64` |
| archlinux | `podman-static-<V>-<R>-<ARCH_PKG>.pkg.tar.zst` | `x86_64` / `aarch64` |

Example (amd64): `podman-static_6.2.0-1_amd64.deb`,
`podman-static-6.2.0-1.x86_64.rpm`,
`podman-static-6.2.0-1-x86_64.pkg.tar.zst`.

## Install

```sh
apt install ./out/podman-static_6.2.0-1_amd64.deb          # Debian / Ubuntu
dnf install ./out/podman-static-6.2.0-1.x86_64.rpm         # Fedora / RHEL
pacman -U ./out/podman-static-6.2.0-1-x86_64.pkg.tar.zst   # Arch Linux
```

Use the matching per-arch filename for your machine. Upstream host prerequisites
still apply and are NOT handled by the packages (no maintainer scripts):
`nftables`, `nsenter`, setuid/cap-enabled `newuidmap`/`newgidmap`,
`/etc/subuid` + `/etc/subgid` delegation for your user, the apparmor profile fix
on Ubuntu >= 23.10, and the optional `docker` symlink. See `INFO.md`.

## Planned, not implemented (future)

- Task 2: relocatable, `$HOME`-scoped, non-root tarball + `install.sh` /
  `uninstall.sh` (no root, no writes outside the prefix). Rootless install into a
  home directory is NOT available yet.
- QEMU VM harness (`make vm-test`) that installs all three formats in one guest.
- CI/release wiring that consumes `make print-release-assets`.
- GPG package signatures and maintainer scripts.
