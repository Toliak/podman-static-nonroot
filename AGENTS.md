# AGENTS.md

`podman-static-nonroot` — wrapper tooling that builds `.deb`, `.rpm` and Arch
`.pkg.tar.zst` packages of the static `mgoltzsche/podman-static` binaries.
Task 1 (packaging) only; the relocatable non-root tarball + `install.sh` (Task 2),
the QEMU VM harness, CI/release wiring, GPG signatures and maintainer scripts are
planned, NOT implemented. Upstream source is fetched at build time (never vendored).

## Layout

- Root = `Makefile` + `nfpm.yaml` (committed `@...@` template) + `scripts/` + docs
  (`AGENTS.md`, `INFO.md`, `README.md`, `TODO.md`, `.gitignore`) + `Containerfile`
  (upstream fetch) + `Containerfile.tools` (tooling image) + `.containerignore`
  + generated `out/`, `.cache/`.
- `dist/` is GONE. Upstream is fetched by `Containerfile` into `.cache/upstream/`
  and verified by `scripts/verify-upstream.sh`; the compiled rootfs is exported to
  `.cache/rootfs/` by `podman build -o type=local`.
- `scripts/` — `version.sh` (VERSION/RELEASE + ARCH_DEB/RPM/PKG), `gen-nfpm.sh`
  (renders the template to stdout), `verify-upstream.sh` (pin + PODMAN_VERSION
  check), `pack.sh` (per-format nfpm runs + filename verify + SHA256SUMS),
  `stage.sh` (assembles `$(ASSET_DIR)` from the exported rootfs),
  `release-assets.sh`.
- `nfpm.yaml` — committed template, substituted by `gen-nfpm.sh` into
  `out/nfpm-<ARCH>.yaml`; `pack.sh` drives nfpm with that.
- `tests/` — self-contained Python project (`pyproject.toml`, `uv.lock`,
  `conftest.py`, `helpers.py`, `test_*.py`), pytest + ruff only;
  `tests/fixtures/asset/` is the committed synthetic staging tree mirroring
  upstream, so the fixture path needs no upstream build.
- `out/` — generated: staged asset tree `out/asset/podman-linux-<ARCH>/`, the
  three packages, `out/nfpm-<ARCH>.yaml`, `out/SHA256SUMS`; gitignored.
- `.cache/` — generated fetch/rootfs cache; gitignored.
- `INFO.md` = background (upstream build pipeline, path inventory, prereqs);
  `TODO.md` = tracked plan (do not remove).

## Commands

- Host prerequisites: `make`, `podman` (rootless), network. NO docker, NO buildx,
  NO host `nfpm`/`uv`/`shellcheck`/`rpm`/`ar`/`zstd`.
- Three podman operations: `Containerfile` fetch (`make fetch`), `podman build`
  of the fetched upstream `Dockerfile --target tar-archive -o type=local`
  (`make build`), `podman run` of the tooling image for pack/test/lint
  (`make all`, `make pack`, `make test`, `make lint`).
- `make tools-image` — builds `Containerfile.tools` (nfpm v2.49.0 + locked
  pytest/ruff venv + shellcheck + archive tools). Prerequisite of all
  containerized targets; cached after first build.
- `make all` = `tools-image` + `_pack-fixture _test _lint` inside the tooling
  image. 51 pytest tests + ruff + shellcheck; no upstream build, no docker.
- `make fetch` — fetches upstream at `UPSTREAM_REF` inside `Containerfile`,
  exports `.cache/upstream/`, verifies pin + `ARG PODMAN_VERSION`.
- `make build` — opt-in REAL upstream build: `fetch` + `podman build ... -o
  type=local,dest=.cache/rootfs` + `scripts/stage.sh` in the tooling image.
  Never `make install` (needs root). After it, `make pack` emits real packages.
- `make pack` — all three formats from `$(ASSET_DIR)` into `$(OUT_DIR)`.
  `make pack-deb | pack-rpm | pack-pkg` — one format.
- `make pack-fixture` — packs the synthetic fixture into `out/`.
  `make checksums` — (re)writes `out/SHA256SUMS`.
- Targets: `all fetch tools-image build stage pack pack-deb pack-rpm pack-pkg
  pack-fixture checksums test lint vet clean distclean vm-test print-vars
  print-release-assets register-qemu` plus `_`-prefixed internal targets that
  run scripts directly with no `podman run` (used inside the container so the
  tooling image never recurses).
- `make clean` = `rm -rf out .cache/rootfs`; `make distclean` also removes
  `.cache`.
- `make print-vars` — show derived vars. `make print-release-assets` — prints
  the 6 package files (3 formats x 2 arches) + `SHA256SUMS` for a FUTURE CI step
  to consume. `make vm-test` — future/opt-in QEMU harness, not part of `make all`.
- `make register-qemu` — opt-in host binfmt registration for arm64 cross-build
  (`podman run --privileged multiarch/qemu-user-static`).
- `make build PROXY=socks5://127.0.0.1:23133` — opt-in proxy for network-
  restricted upstream clones. `PROXY` defaults to the standard `ALL_PROXY` /
  `HTTPS_PROXY` / `HTTP_PROXY` env vars; when set, podman builds get
  `--network=host` (so a `127.0.0.1` proxy is reachable inside RUN steps) and
  the proxy vars are passed through by `podman build --http-proxy`. Default
  (no proxy) path is unchanged and keeps its layer cache.

## Testing

- `tests/` is a Python project, pytest + ruff only; every non-unit test must be
  written in or executable via pytest. Tests run INSIDE the tooling image via
  `make test` (or `make _test` when already inside).
- The locked venv is built into `Containerfile.tools` with
  `uv sync --project /opt/tests-deps --frozen` from the committed `tests/uv.lock`;
  `PATH` is set to that venv. No host `uv`, no `--no-sync` at runtime.
- The session `artifacts` fixture packs the synthetic fixture tree via
  `make _pack` (internal target, nfpm on PATH inside the image).
- `tests/helpers.py:load_vars` neutralizes the wrapper's injected env so
  `version.sh` override hooks are testable hermetically.
- Markers `vm` and `e2e`, both opt-in, gated by `PODMAN_STATIC_VM_TEST=1` /
  `PODMAN_STATIC_E2E=1`. `e2e` runs the real `make build pack`; `vm` boots the
  (future) QEMU guest. Neither is in `make all`.
- Archive inspection: deb via stdlib `ar` parser + `tarfile`; rpm via `rpm -qip`
  / `rpm -qlp` / `rpm2cpio | bsdtar`; `.pkg.tar.zst` via `zstd -dc | tarfile`.
  All these tools live in the tooling image. Real `dpkg -i`/`rpm -i`/`pacman -U`
  installs belong to the future VM harness.
- `tests/uv.lock` is committed; the venv lives inside the image at
  `/opt/tests-deps/.venv`, NOT in the workspace.

## Conventions

- Makefile vars: `PODMAN ?= podman`, `PROXY ?=` (defaults to `ALL_PROXY` /
  `HTTPS_PROXY` / `HTTP_PROXY` env), `NFPM_VERSION ?= v2.49.0`,
  `NFPM_BIN ?=`, `UPSTREAM_REPO`, `UPSTREAM_REF ?= c55c0fb...` (full SHA),
  `UPSTREAM_VERSION ?= v6.2.0`, `CACHE_DIR ?= .cache`,
  `TOOLS_IMAGE ?= localhost/podman-static-nonroot-tools:$(NFPM_VERSION)`,
  `PLATFORM ?= linux/amd64`, `ARCH` (derived from `PLATFORM` via sed
  `s!linux/([^/]+).*!\1!`), `OUT_DIR ?= out`,
  `ASSET_DIR ?= $(OUT_DIR)/asset/podman-linux-$(ARCH)`,
  `PKG_NAME ?= podman-static`,
  `PKG_VERSION`, `PKG_RELEASE`, `ARCH_DEB`, `ARCH_RPM`, `ARCH_PKG` (last five from
  `scripts/version.sh`).
- `PACK_ENV` (inline env for scripts) and `PODMAN_ENV`/`PODMAN_RUN` (`-e` flags +
  `podman run --userns=keep-id -v "$(CURDIR):/work" -w /work`). `PODMAN_BUILD`
  wraps `podman build` with `PROXY_ENV` + `--network=host` when `PROXY` is set.
- `PROXY` is opt-in and never defaults to a hardcoded address; with no proxy the
  build command is plain `podman build` so the layer cache is preserved.
- `UPSTREAM_REF` is the exact fetch pin (full 40-char SHA — GitHub requires the
  full SHA for `git fetch origin <sha>`); `UPSTREAM_VERSION` is the semantic
  version stamped on packages. `make fetch` asserts the fetched `Dockerfile`'s
  `ARG PODMAN_VERSION` matches `UPSTREAM_VERSION`; keep them in sync when
  bumping upstream.
- Metadata (locked v1): name `podman-static`, license Apache-2.0, vendor/homepage
  `https://github.com/mgoltzsche/podman-static`; NO runtime deps (binaries are
  static/musl); NO maintainer scripts (systemd/subuid setup is a documented admin
  step); checksums only (`out/SHA256SUMS`).
- Version scheme: `scripts/version.sh` derives VERSION/RELEASE from
  `UPSTREAM_VERSION` (`v6.2.0` -> `6.2.0` / `1`). No args -> `KEY=value` lines;
  `KEY` arg -> one value. No `-` in the version field. Override hooks:
  `PODMAN_STATIC_DESCRIBE`, `PODMAN_STATIC_GIT`, `PODMAN_STATIC_PODMAN_VERSION`.
- `nfpm.yaml` is a `@PKG_NAME@`/`@PKG_VERSION@`/`@PKG_RELEASE@`/`@ARCH@`/
  `@ASSET_DIR@` template; `gen-nfpm.sh` renders concrete YAML to stdout. `contents`:
  `type: tree` `@ASSET_DIR@/usr/local` -> `/usr/local`; `config|noreplace|tree`
  `@ASSET_DIR@/etc/containers` -> `/etc/containers`; a plain README.md content
  entry -> `/usr/share/doc/@PKG_NAME@/README.md` (nfpm drops `type: doc` entries);
  `type: symlink` `/usr/local/bin/podman` -> `/usr/bin/docker`. Top-level `rpm:`
  (group/summary) and `archlinux:` (packager) sections.
- Env overrides: `ASSET_DIR`, `OUT_DIR`, `PLATFORM`, `ARCH`, `CACHE_DIR`,
  `UPSTREAM_REPO`, `UPSTREAM_REF`, `UPSTREAM_VERSION`, `PKG_NAME`, `PKG_VERSION`,
  `PKG_RELEASE`, `NFPM_VERSION`, `NFPM_BIN`, `PODMAN_STATIC_E2E`,
  `PODMAN_STATIC_VM_TEST`, `PODMAN_STATIC_VM_CACHE`.
- `.gitignore`: `out/`, `.cache/`, `.venv*/`, `.pytest_cache/`, `.ruff_cache/`,
  `__pycache__/`, `*.py[cod]`, `.vm-cache/`, `tests/vm/results/`, `*.asc`,
  `*.sha256`.

## Gotchas

- NO docker anywhere: no `docker` CLI, no daemon, no `buildx`, no
  `~/.local/bin/docker` shim. Upstream's `Makefile` is NOT used; the fetched
  `Dockerfile` is built directly with `podman build`. Registry refs
  (`docker.io/library/...`) are images, not the docker CLI — podman pulls them.
- `podman build -o type=local,dest=...` replaces `docker buildx build --output
  type=local`; no builder, no `create-builder`. `--platform linux/$(ARCH)` is
  native for amd64; arm64 needs host binfmt (`make register-qemu`) and rootless
  `--privileged` may not be able to register `binfmt_misc` (may need host root).
- Rootless bind mounts need `--userns=keep-id`; do NOT add `:z`/`:Z` SELinux
  relabeling. The container runs as the host UID and writes `out/` as that user.
- `FROM scratch AS export` + `COPY --from=fetch /src/ /` is what makes
  `-o type=local` emit ONLY the upstream tree (not the alpine base).
- GitHub rejects short SHAs: `git fetch origin c55c0fb` fails with "couldn't find
  remote ref"; use the full 40-char SHA.
- nfpm does NOT substitute env vars in its config — the committed `nfpm.yaml` is
  a `@...@` template and `gen-nfpm.sh` is the renderer.
- nfpm AUTO-TRANSLATES arch: write `arch: amd64`/`arm64` once and it emits
  `x86_64`/`aarch64` for rpm and archlinux. `ARCH_DEB`/`ARCH_RPM`/`ARCH_PKG` are
  for filename verification, not for the config.
- `config|noreplace|tree` marks `/etc/containers` files as conffiles/backup, so
  upgrades never clobber user config. Keep it.
- Symlinks are load-bearing and path-bound: relative quadlet-generator links and
  the `/usr/bin/docker` link. They install to absolute `/usr` paths in Task 1;
  relocating them is Task 2's problem (quadlet `_binDir` is compiled in).
- Network is required at build time (fetch clone, nfpm release, uv wheels,
  upstream's Go/Rust/git clones); pins + podman layer cache are the mitigation.
  `passt.top` is a flaky upstream clone — `make build PROXY=...` routes it through
  an optional SOCKS/HTTP proxy with `--network=host`.
- The installed `/usr/local/bin/docker` symlink inside the package is a payload
  name for docker-compatible CLIs, NOT a build dependency.
- FUTURE / not implemented: Task 2 relocatable non-root tarball + `install.sh`,
  the QEMU VM harness (`vm-test`), CI/release wiring, GPG package signatures, and
  maintainer scripts. Do not claim they exist; `make all` is fixture-only.
