# podman-static-nonroot

Builds `.deb`, `.rpm` and Arch `.pkg.tar.zst` packages plus a relocatable
non-root tarball of the statically linked (musl) rootless podman binaries from
`mgoltzsche/podman-static`. Task 1 is packaging; Task 2 is the `$HOME`-scoped
user tarball with `install.sh`/`uninstall.sh`. The QEMU VM harness, CI/release
wiring, GPG signatures and maintainer scripts are **planned, not implemented**.

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
make pack-fixture      # fixture packages + user tarball into out/ only
make pack-user         # relocatable non-root tarball only
make print-vars        # show derived VERSION/RELEASE/ARCH and paths
make clean             # rm -rf out/ .cache/rootfs
```

Real packages (opt-in, heavier — compiles the upstream static binaries):

```sh
make fetch             # fetch pinned upstream into .cache/upstream/
make build             # podman build of upstream Dockerfile -> out/asset/...
make pack              # 3 packages + user tarball -> out/ (+ SHA256SUMS)
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
`make print-release-assets` prints the 8 artifacts (4 formats x 2 arches) +
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
├── podman-static-<VERSION>-<RELEASE>-<ARCH>-user.tar.gz
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
| user tarball | `podman-static-<V>-<R>-<ARCH>-user.tar.gz` | `amd64` / `arm64` |

Example (amd64): `podman-static_6.2.0-1_amd64.deb`,
`podman-static-6.2.0-1.x86_64.rpm`,
`podman-static-6.2.0-1-x86_64.pkg.tar.zst`,
`podman-static-6.2.0-1-amd64-user.tar.gz`.

## Install

```sh
apt install ./out/podman-static_6.2.0-1_amd64.deb          # Debian / Ubuntu
dnf install ./out/podman-static-6.2.0-1.x86_64.rpm         # Fedora / RHEL
pacman -U ./out/podman-static-6.2.0-1-x86_64.pkg.tar.zst   # Arch Linux
```

Use the matching per-arch filename for your machine. The packages contain no
maintainer scripts, so the host setup below is **not** performed automatically;
it is required for rootless operation and must be done by an administrator (or
by you on a machine you control).

### Rootless prerequisites (all install methods)

The statically linked binaries are self-contained, but rootless podman still
relies on a few host facilities. Install them with your distro's package
manager:

| Distro | Command |
| --- | --- |
| Debian / Ubuntu | `sudo apt install uidmap nftables util-linux` |
| Fedora / RHEL | `sudo dnf install shadow-utils nftables util-linux` |
| Arch Linux | `sudo pacman -S shadow nftables util-linux` |

- **`newuidmap` / `newgidmap`** must be privileged to map subordinate UID/GID
  ranges. Verify the distro binaries carry the setuid bit or file capabilities:

  ```sh
  ls -l "$(command -v newuidmap)" "$(command -v newgidmap)"
  getcap "$(command -v newuidmap)" "$(command -v newgidmap)"
  ```

  A setuid-root binary (`-rwsr-xr-x root root`) or `cap_setuid=ep` /
  `cap_setgid=ep` capabilities are both sufficient. Do **not** copy or
  `chmod u+s` your own copies: setuid only takes effect when the file is owned
  by root, which a user-scoped install cannot arrange.

- **Subordinate UID/GID delegation** gives your user a range to map container
  IDs onto:

  ```sh
  sudo sh -c "echo $(id -un):100000:200000 >> /etc/subuid"
  sudo sh -c "echo $(id -gn):100000:200000 >> /etc/subgid"
  grep "^$(id -un):" /etc/subuid /etc/subgid   # verify; do not add twice
  ```

- **Unprivileged user namespaces** must be enabled. The
  `kernel.unprivileged_userns_clone` knob exists on Debian/Ubuntu (absent
  elsewhere means the feature is enabled); if it reports `0`, enable it
  persistently:

  ```sh
  echo 'kernel.unprivileged_userns_clone=1' | sudo tee /etc/sysctl.d/99-podman.conf
  sudo sysctl --system
  ```

- **AppArmor** (Ubuntu >= 23.10): the distro profile only matches
  `/usr/bin/podman`, so the first run can fail with `reexec: Permission denied`.
  Extend it to the packaged path:

  ```sh
  sudo sed -Ei 's!^profile podman /usr/bin/podman !profile podman /usr/{bin,local/bin}/podman !' /etc/apparmor.d/podman
  ```

- **`/dev/fuse`** must exist for the bundled `fuse-overlayfs` storage driver;
  load it with `sudo modprobe fuse` if it is missing.
- **`nftables`** and **`nsenter`** are used by the default netavark network
  stack; both are installed by the commands above.

Then verify the installation:

```sh
podman info
podman run --rm docker.io/library/alpine echo hello
```

The `/usr/bin/docker` symlink shipped inside the package is a payload name for
docker-compatible CLIs — it is NOT a build dependency and has nothing to do with
the docker CLI.

## Non-root install (user tarball)

`make pack-user` emits a relocatable tarball that installs without root into an
absolute, writable prefix (default `$HOME/.local/opt/podman-static`, spaces
allowed). Only files inside the prefix are written; installing as root is
refused.

```sh
tar -xzf out/podman-static-6.2.0-1-amd64-user.tar.gz
./podman-static-user/install.sh --prefix "$HOME/.local/opt/podman-static"
. "$HOME/.local/opt/podman-static/bin/podman-env.sh"
podman --version
podman run --rm docker.io/library/alpine echo hello
"$HOME/.local/opt/podman-static/bin/podman-static-uninstall.sh"
```

The installer generates `etc/containers/{containers.conf,storage.conf}` from
`@PREFIX@` templates, wires the bundled helpers/runtimes/seccomp explicitly, and
records every installed file in `.podman-static/manifest`. Container images and
volumes live under `<prefix>/var` (a dedicated store, never the distro podman
store) and are preserved by uninstall. Uninstall removes only files that are
still unchanged; modified and unrelated files are reported and kept. An
identical reinstall is a no-op; a different release requires uninstall first.

The same [rootless prerequisites](#rootless-prerequisites-all-install-methods)
apply. `install.sh` only detects and **warns** about them — it never changes host
policy. Without subuid/subgid delegation and privileged `newuidmap`/`newgidmap`,
podman falls back to a degraded single-UID mapping (containers still run, but
files appear owned by your user and multi-UID images misbehave). systemd units,
quadlet generators and the `docker` alias are **not** part of the user payload.

## Planned, not implemented (future)

- QEMU VM harness (`make vm-test`) that installs all three formats + the user
  tarball in one guest.
- CI/release wiring that consumes `make print-release-assets`.
- GPG package signatures and maintainer scripts.
- In-place upgrades of the user tarball.
