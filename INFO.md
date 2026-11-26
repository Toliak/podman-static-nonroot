# INFO.md

Background for the `podman-static-nonroot` wrapper. It packages the static binaries
built by the upstream project `mgoltzsche/podman-static` (Apache-2.0) into `.deb`,
`.rpm` and Arch `.pkg.tar.zst`. Upstream is **fetched at build time**, never vendored:
`Containerfile` clones the exact pin `UPSTREAM_REF` into `.cache/upstream/`. See
`TODO.md` for the plan and `AGENTS.md` for the build contract.

Task 1 (this phase) repackages the upstream staging tree at the SAME absolute
paths upstream uses (`/usr/local`, `/etc/containers`). The hardcoded-path inventory
below therefore mostly matters for the FUTURE Task 2 (relocatable, `$HOME`-scoped
non-root tarball + `install.sh`); it is recorded now so the path audit is not
rediscovered later.

Line references such as `Dockerfile:34` / `Makefile:120` refer to the fetched upstream
tree under `.cache/upstream/` (at pin `c55c0fbb9ede2937f71536a394d5cccc5efafcfe`,
`v6.2.0-1-gc55c0fb`), not to a file in this repository.

## Upstream build pipeline (podman-orchestrated)

- `make fetch`: `podman build -f Containerfile --target export -o
  type=local,dest=.cache/upstream`. `Containerfile` does `git fetch --depth=1
  origin "$UPSTREAM_REF"` inside an alpine stage, writes `.pinned-rev`, and a
  `FROM scratch` stage exports ONLY the upstream tree. `scripts/verify-upstream.sh`
  asserts the rev matches `UPSTREAM_REF` and that `ARG PODMAN_VERSION` in the
  fetched `Dockerfile` matches `UPSTREAM_VERSION`.
- `make build`: `podman build -f .cache/upstream/Dockerfile --target tar-archive
  --platform linux/$(ARCH) -o type=local,dest=.cache/rootfs .cache/upstream`.
  This replaces upstream's `docker buildx build --output type=local` — no builder,
  no `create-builder`, no upstream `Makefile`. `--target tar-archive` exports the
  alpine image rootfs containing all static binaries + `/etc/containers` config.
- `scripts/stage.sh` (run in the tooling image) assembles
  `out/asset/podman-linux-<ARCH>/` from that rootfs: `etc/containers`,
  `usr/local/{bin,lib,libexec,share}`, the two relative quadlet-generator
  symlinks, and `README.md` from the fetched tree. This mirrors upstream's
  `.podman-from-container` target (`.cache/upstream/Makefile:113-122`) without
  invoking it. The wrapper NEVER runs upstream `make install` (needs root).
- The upstream `Dockerfile` is a multi-stage alpine build: golang/rust builder
  stages statically compile `podman`, `quadlet` (with `_binDir=/usr/local/bin`
  injected), `rootlessport`, `runc`, `crun`, `conmon`, `netavark`,
  `aardvark-dns`, `passt`/`pasta`, `fuse-overlayfs` + libfuse, and `catatonit`;
  `podmanall`/`tar-archive` stages assemble the final tree plus the
  `/usr/bin/docker` symlink.
- `make pack`: `nfpm` (pinned `v2.49.0`, baked into `Containerfile.tools`) renders
  `nfpm.yaml` and emits the three packages + `out/SHA256SUMS`.
- Upstream's own release CI (`.github/workflows/workflow.yml` in the fetched tree)
  does `make images test`, `make clean multiarch-tar [TAR_TARGET=signed-tar]`,
  GPG-signs via `signed-tar` / `verify-signature` (key `0CCF…BB503`, short
  `0CCF102C4F95D89E583FF1D4F8B5AF50344BB503`, `hkps://keyserver.ubuntu.com`) and
  publishes `.tar.gz` + `.asc`. This wrapper does NOT use that CI; the GPG infra
  is reusable later for package signatures.

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

## Upstream host prerequisites (upstream README.md:84-113)

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

- `UPSTREAM_VERSION` (`v6.2.0` by default) -> VERSION `6.2.0`; RELEASE `1`.
  `make fetch` keeps it in sync with the fetched `Dockerfile`'s
  `ARG PODMAN_VERSION`. Sanitize: no `-` in the version field (rpm), deb `-` is
  the debian_revision, archlinux uses pkgver/pkgrel.
- Override hooks (used by the test suite): `PODMAN_STATIC_DESCRIBE`,
  `PODMAN_STATIC_GIT`, `PODMAN_STATIC_PODMAN_VERSION`.
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

## Why nfpm in a tooling image

nfpm is a single, rootless, pure-Go static binary driven by one YAML config that
emits all three formats. It is baked into `Containerfile.tools` (pinned `v2.49.0`)
along with the locked pytest/ruff venv (`uv sync --frozen` from `tests/uv.lock`),
shellcheck and the archive inspection tools (`ar`, `rpm`, `rpm2cpio`, `bsdtar`,
`zstd`). Every pack/test/lint target runs via `podman run --userns=keep-id`, so
the host needs NO `nfpm`, `uv`, `pytest`, `ruff`, `shellcheck`, `dpkg-deb`,
`rpmbuild`, `makepkg`, root, or docker. v1 emits checksums only; GPG package
signatures are a future follow-up (upstream's `signed-tar` / `verify-signature`
GPG infra could be reused). CI/release wiring is likewise deferred:
`make print-release-assets` exposes the 6 package files (3 formats x 2 arches) +
`SHA256SUMS` for a future job to consume.

## Container vs host boundary

| Step | Where | Tool |
| --- | --- | --- |
| Fetch upstream source | podman build | `Containerfile` (`git fetch`) |
| Compile static binaries | podman build | fetched upstream `Dockerfile`, `-o type=local` |
| Stage asset tree / pack / test / lint | podman run | tooling image |
| Orchestration | host | `make` only |

NO docker CLI, daemon, buildx, or `~/.local/bin/docker` shim. Registry refs
(`docker.io/library/...`, `docker.io/multiarch/qemu-user-static`) are images, not
the docker CLI — podman pulls them. "non-root" in the project name refers to the
installed binaries being rootless, NOT to the build environment; build containers
run rootless but as root inside their user namespace for `apk`/compilation.

## Proxy support (opt-in)

`PROXY` defaults to the standard `ALL_PROXY` / `HTTPS_PROXY` / `HTTP_PROXY` env
vars (explicit `make ... PROXY=...` overrides). When set, `PODMAN_BUILD` prefixes
the build with those env vars and adds `--network=host`, so a proxy listening on
`127.0.0.1` on the host is reachable from inside build RUN steps; `podman build
--http-proxy` (default true) passes them through. Without a proxy the command is
plain `podman build` and cached layers are reused. This exists because upstream
`Dockerfile`'s `git clone https://passt.top/passt` can be blocked/flaky on some
networks; `make build PROXY=socks5://127.0.0.1:23133` routes it through a SOCKS5
proxy.
