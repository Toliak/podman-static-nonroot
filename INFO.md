# INFO.md

Background for the `podman-static-nonroot` wrapper. It packages the static binaries
built by the vendored, read-only upstream project `mgoltzsche/podman-static`
(`v6.2.0-1-gc55c0fb`, Apache-2.0, 24 tracked files) into `.deb`, `.rpm` and Arch
`.pkg.tar.zst`. See `TODO.md` for the plan and `AGENTS.md` for the build contract.

Task 1 (this phase) repackages the upstream staging tree at the SAME absolute
paths upstream uses (`/usr/local`, `/etc/containers`). The hardcoded-path inventory
below therefore mostly matters for the FUTURE Task 2 (relocatable, `$HOME`-scoped
non-root tarball + `install.sh`); it is recorded now so the path audit is not
rediscovered later.

## Upstream build pipeline (`dist/podman-static/Makefile`)

- `ASSET_NAME := podman-linux-$(ARCH)` (`:35`), `ASSET_DIR` = `build/asset/<name>`
  (`:36`); `ARCH` comes from `PLATFORM` via sed (`:28`, `linux/amd64` -> `amd64`),
  `PLATFORM=linux/amd64` default (`:27`).
- Wrapper `make build` calls `make -C dist/podman-static singlearch-tar
  PLATFORM=linux/<ARCH>` (`:50-54`), which runs the `tar` target (`:109-111`).
  `tar` depends on `.podman-from-container` (`:113-122`).
- `.podman-from-container` assembles `build/asset/podman-linux-<ARCH>/` from the
  buildx-exported image rootfs: `etc/containers` (`:117`),
  `usr/local/{bin,lib,libexec}` (`:118`), `usr/local/share` completions (`:119`),
  the two quadlet-generator symlinks (`:120-121`), and `README.md` (`:122`). The
  tree is `usr/local/{bin,lib,libexec,share,lib/systemd}`, `etc/containers`,
  `README.md`. `tar` then creates `build/asset/podman-linux-<ARCH>.tar.gz`
  (`:109-111`).
- No `VERSION` variable and no version in artifact names; the release version
  comes from git tags in upstream CI (`.github/workflows/workflow.yml:54-64`).
  Source version is `ARG PODMAN_VERSION=v6.2.0` (`Dockerfile:34`).
- GPG signing infra (reusable later): `signed-tar` (`:124-136`) builds a detached
  `.asc` inside a `gpg-signer` container; `verify-signature` (`:138-152`) fetches
  key `0CCF102C4F95D89E583FF1D4F8B5AF50344BB503` (short `0CCF…BB503`) from
  `hkps://keyserver.ubuntu.com` and verifies. Upstream publishes
  `podman-linux-<arch>.tar.gz` + `.asc` (workflow `:60-64`).
- `scripts/stage.sh` copies `build/asset/podman-linux-<ARCH>/` into the wrapper's
  `$(ASSET_DIR)` (`out/asset/podman-linux-<ARCH>/`). The wrapper NEVER runs
  upstream `make install` (`:106-107`, needs root).

## Hardcoded absolute-path inventory (mostly FUTURE Task 2)

- `quadlet` has `_binDir=/usr/local/bin` COMPILED IN via
  `LDFLAGS_QUADLET="-X ...quadlet._binDir=/usr/local/bin"` (`Dockerfile:50-55`,
  value at `:51`); it cannot be rewritten in the payload.
- `mount_program = "/usr/local/bin/fuse-overlayfs"` in the storage drop-in
  `conf/containers/storage.conf.d/00-podman-static.conf:8`. `graphroot`/`runroot`
  are intentionally omitted (`:2-4`); podman 6 resolves rootless paths from
  `$HOME`/`$XDG_DATA_HOME`.
- `/usr/bin/docker` is a symlink to `/usr/local/bin/podman` (`Dockerfile:188`).
- `seccomp.json` at `/etc/containers/seccomp.json` (`Dockerfile:40-42` writes it,
  `:214` copies it into the image).
- systemd units / quadlet generators under `/usr/local/lib/systemd/` and
  `/usr/local/lib/systemd/{system,user}-generators/` (`Makefile:116-121`,
  `Dockerfile:61-63,217-219`) with relative symlinks (`Makefile:120-121`).
- `helper_binaries_dir` default `/usr/local/lib/podman`.
- Upstream is explicitly "without systemd support" (`README.md:3`); Task 2 excludes
  systemd units + quadlet generators from the user payload.

## Upstream host prerequisites (README.md:84-113)

These are HOST requirements, unchanged by packaging. v1 ships NO runtime deps and
NO maintainer scripts, so an admin must still do them:

- `nftables` (with `iptables-nft` if iptables compat is needed), `nsenter`
  (`:84-89`).
- `shadow` / `shadow-utils` `newuidmap` + `newgidmap`, setuid-root OR with
  `cap_setuid=ep` / `cap_setgid=ep` file caps (`:89`; Debian/Ubuntu package
  `uidmap`).
- `/etc/subuid` + `/etc/subgid` delegation for the user (`:91-98`), e.g.
  `<user>:100000:200000`. Normally needs root; a genuinely root-free install
  assumes the admin already delegated ranges.
- apparmor profile fix on Ubuntu >= 23.10 so it also matches
  `/usr/local/bin/podman` (`:100-106`).
- optional `docker` compatibility symlink (`:108-113`).
- Note `:77`: a newer `/usr/local/bin/runc` can break older host docker.

## Version derivation & arch mapping

`scripts/version.sh` (no args -> `KEY=value` lines; `KEY` arg -> one value):

- `git -C dist/podman-static describe --tags --always` -> `v6.2.0-1-gc55c0fb`:
  strip leading `v` -> VERSION `6.2.0`; the git distance past the tag -> RELEASE
  `1`; `gc55c0fb` is the short hash (not used). Sanitize: no `-` in the version
  field (rpm), deb `-` is the debian_revision, archlinux uses pkgver/pkgrel.
- Fallback when no git: `Dockerfile:34` `ARG PODMAN_VERSION=v6.2.0` -> `6.2.0`.
- `ARCH_MAP` (per-format values, used for filename verification):

  | PLATFORM | ARCH | ARCH_DEB (deb) | ARCH_RPM (rpm) | ARCH_PKG (archlinux) |
  | --- | --- | --- | --- | --- |
  | `linux/amd64` | `amd64` | `amd64` | `x86_64` | `x86_64` |
  | `linux/arm64/v8` | `arm64` | `arm64` | `aarch64` | `aarch64` |

  nfpm AUTO-TRANSLATES arch, so the config carries one `arch: amd64`/`arm64` and
  nfpm emits `x86_64`/`aarch64` for rpm/archlinux.

- Package filenames in `out/`:
  `podman-static_<VERSION>-<RELEASE>_<ARCH_DEB>.deb`,
  `podman-static-<VERSION>-<RELEASE>.<ARCH_RPM>.rpm`,
  `podman-static-<VERSION>-<RELEASE>-<ARCH_PKG>.pkg.tar.zst`, plus `SHA256SUMS`.

## Why nfpm

nfpm is a single, rootless, pure-Go static binary driven by one YAML config that
emits all three formats. That means the wrapper needs NO host `dpkg-deb`,
`rpmbuild`, or `makepkg`, NO root, and NO docker for the default (fixture) path —
`make all` / `make pack-fixture` work on a bare machine. The binary is pinned
`v2.49.0`, downloaded on first use and cached at `.tools/nfpm-<version>` (override
`NFPM_BIN`, `NFPM_CACHE_DIR`, `NFPM_VERSION`). v1 emits checksums only; GPG
package signatures are a future follow-up (the upstream `signed-tar` /
`verify-signature` GPG infra above could be reused). CI/release wiring is likewise
deferred: `make print-release-assets` exposes the 6 package files (3 formats x 2
arches) + `SHA256SUMS` for a future job to consume, and the vendored
`workflow.yml` is deliberately left untouched.
