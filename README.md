# podman-static-nonroot

Builds `.deb`, `.rpm` and Arch `.pkg.tar.zst` packages of the statically linked
(musl) rootless podman binaries from `mgoltzsche/podman-static`. This is **Task 1**
(packaging). The relocatable **non-root tarball + `install.sh` (Task 2)**, the QEMU
VM harness, CI/release wiring, GPG signatures and maintainer scripts are **planned,
not implemented**.

Upstream source is **fetched at build time** inside `Containerfile` — it is not
vendored in this repository. Everything that does build work runs in **podman**
containers; docker is never used.

Packages install to the same absolute paths upstream uses (`/usr/local`,
`/etc/containers`); they contain NO runtime deps and NO maintainer scripts.

## Prerequisites

- `make`, `bash`, `podman` (rootless), network.
- Nothing else on the host: nfpm, pytest/ruff, shellcheck, `ar`, `rpm`, `zstd`,
  and `bsdtar` all live in the tooling image.
- NO `docker`, NO `buildx`, NO `~/.local/bin/docker` shim.

## Quickstart

```sh
make tools-image       # build the tooling image (cached after first run)
make all               # pack the synthetic fixture + test + lint, all in podman
make pack-fixture      # fixture packages into out/ only
make print-vars        # show derived VERSION/RELEASE/ARCH and paths
make clean             # rm -rf out/ .cache/rootfs
```

Real packages (opt-in, heavier — compiles the upstream static binaries):

```sh
make fetch             # fetch pinned upstream into .cache/upstream/
make build             # podman build of upstream Dockerfile -> out/asset/...
make pack              # all 3 formats -> out/ (+ SHA256SUMS)
```

If an upstream clone is blocked by your network, pass an opt-in proxy (also
honors standard `ALL_PROXY` / `HTTPS_PROXY` / `HTTP_PROXY` env vars):

```sh
make build PROXY=socks5://127.0.0.1:23133
```

When `PROXY` is set, podman builds use `--network=host` so a `127.0.0.1` proxy is
reachable inside RUN steps. With no proxy the build command is plain
`podman build` and its layer cache is preserved.

`make pack-deb` / `make pack-rpm` / `make pack-pkg` build one format;
`make checksums` rewrites `out/SHA256SUMS`; `make distclean` also removes `.cache/`.
`make print-release-assets` prints the 6 package files (3 formats x 2 arches) +
`SHA256SUMS` for a future CI step (CI wiring is deferred).

`make register-qemu` is opt-in host binfmt registration for arm64 cross-builds;
rootless `--privileged` may not be able to register `binfmt_misc` (may need host
root). amd64 is native and the default.

## How it works

| Step | Command | podman operation |
| --- | --- | --- |
| Fetch upstream | `make fetch` | `podman build -f Containerfile ... -o type=local` |
| Compile binaries | `make build` | `podman build -f .cache/upstream/Dockerfile --target tar-archive -o type=local` |
| Stage + pack + test | `make pack`, `make all` | `podman run` of the tooling image |

`UPSTREAM_REF` pins the exact commit (full 40-char SHA — GitHub requires it for
`git fetch origin <sha>`), `UPSTREAM_VERSION` sets the stamped package version;
`make fetch` verifies the fetched `Dockerfile`'s `ARG PODMAN_VERSION` agrees.

`podman build -o type=local` replaces `docker buildx build --output type=local`:
no builder, no `create-builder`. Rootless bind mounts use `--userns=keep-id`.

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

`.cache/` holds the fetched upstream tree (`upstream/`) and the exported rootfs
(`rootfs/`); both are gitignored.

## Naming / version scheme

VERSION/RELEASE come from `UPSTREAM_VERSION` (`v6.2.0` -> `6.2.0` / `1`), kept in
sync with the fetched upstream `Dockerfile` by `make fetch`. `ARCH` is `amd64` or
`arm64`; per-format arch:

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
on Ubuntu >= 23.10, and an optional `docker` compatibility symlink. See `INFO.md`.

The `/usr/bin/docker` symlink shipped inside the package is a payload name for
docker-compatible CLIs — it is NOT a build dependency and has nothing to do with
the docker CLI.

## Planned, not implemented (future)

- Task 2: relocatable, `$HOME`-scoped, non-root tarball + `install.sh` /
  `uninstall.sh` (no root, no writes outside the prefix). Rootless install into a
  home directory is NOT available yet.
- QEMU VM harness (`make vm-test`) that installs all three formats in one guest.
- CI/release wiring that consumes `make print-release-assets`.
- GPG package signatures and maintainer scripts.
