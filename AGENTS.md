# AGENTS.md

`podman-static-nonroot` — wrapper tooling that builds `.deb`, `.rpm` and Arch
`.pkg.tar.zst` packages of the static `mgoltzsche/podman-static` binaries.
Task 1 (packaging) only; the relocatable non-root tarball + `install.sh` (Task 2),
the QEMU VM harness, CI/release wiring, GPG signatures and maintainer scripts are
planned, NOT implemented. Consumes `dist/podman-static/` as a read-only input.

## Layout

- Root = `Makefile` + `nfpm.yaml` (committed `@...@` template) + `scripts/` + docs
  (`AGENTS.md`, `INFO.md`, `README.md`, `TODO.md`, `.gitignore`) + generated
  `out/`, `.tools/`, caches.
- `scripts/` — `version.sh` (VERSION/RELEASE + ARCH_DEB/RPM/PKG), `gen-nfpm.sh`
  (renders the template to stdout), `ensure-nfpm.sh` (download+pin+cache nfpm),
  `pack.sh` (per-format nfpm runs + filename verify + SHA256SUMS), `stage.sh`
  (`make build` body).
- `nfpm.yaml` — committed template, substituted by `gen-nfpm.sh` into
  `out/nfpm-<ARCH>.yaml`; `pack.sh` drives nfpm with that.
- `tests/` — self-contained `uv` Python project (`pyproject.toml`, `uv.lock`,
  `conftest.py`, `helpers.py`, `test_*.py`), pytest + ruff only;
  `tests/fixtures/asset/` is the committed synthetic staging tree mirroring
  upstream, so the default suite needs no docker and no host packaging tools.
- `dist/podman-static/` — vendored, read-only upstream checkout (24 tracked files,
  `v6.2.0-1-gc55c0fb`, Apache-2.0). LOCKED: leave untouched; add no files inside
  it and do not edit its `.github/workflows/workflow.yml`.
- `out/` — generated: staged asset tree `out/asset/podman-linux-<ARCH>/`, the
  three packages, `out/nfpm-<ARCH>.yaml`, `out/SHA256SUMS`; gitignored.
- `.tools/` — nfpm binary cache (`nfpm-<version>`); gitignored.
- `INFO.md` = background (upstream pipeline, path inventory, prereqs);
  `TODO.md` = tracked plan (do not remove).

## Commands

- Two build paths: the **fixture path** (default, no docker, no host packaging
  tools) packs `tests/fixtures/asset/`; the **real path** (opt-in, docker/buildx)
  runs upstream then packs the produced binaries.
- `make all` = `pack-fixture test lint` — green with NO docker; packs the synthetic
  fixture into `out/`, runs the suite, runs lint.
- `make build` — opt-in REAL upstream build (needs docker/buildx); `scripts/stage.sh`
  runs `make -C $(DIST_DIR) singlearch-tar PLATFORM=$(PLATFORM)` then copies
  `build/asset/podman-linux-<ARCH>/` into `$(ASSET_DIR)/`. After it, `make pack`
  emits real packages. Never `make install` in the vendored tree (needs root).
- `make pack` — all three formats from `$(ASSET_DIR)` into `$(OUT_DIR)`; `pack.sh`
  bootstraps the pinned nfpm. `make pack-deb | pack-rpm | pack-pkg` — one format.
- `make pack-fixture` — packs the synthetic fixture into `out/` with NO docker and
  NO host packaging tools. `make checksums` — (re)writes `out/SHA256SUMS`.
- Targets: `all build pack pack-deb pack-rpm pack-pkg pack-fixture checksums sync
  test lint vet clean vm-test print-vars print-release-assets ensure-nfpm`.
- `make ensure-nfpm` — nfpm pinned `v2.49.0`, rootless pure-Go static binary,
  downloaded on first use and cached at `.tools/nfpm-<version>`; override
  `NFPM_BIN`, `NFPM_CACHE_DIR`, `NFPM_VERSION`. No host `dpkg-deb`/`rpmbuild`/
  `makepkg` needed.
- `make sync` = `uv sync --project tests --frozen`; `make test` =
  `$(UV_RUN) pytest -q -c $(PYTEST_CONFIG) tests`; `make lint` = `ruff check` +
  `ruff format --check` + `shellcheck -x -S warning scripts/*.sh`;
  `make clean` = `rm -rf out/`.
- `make print-vars` — show derived vars. `make print-release-assets` — prints the
  6 package files (3 formats x 2 arches) + `SHA256SUMS` for a FUTURE CI step to
  consume. How it WOULD be wired (deferred; do not edit the vendored workflow):
  a CI job loops the two `PLATFORM`s running `make build pack`, collects
  `$(make print-release-assets)` and feeds that list to the release assets
  (mirroring upstream `workflow.yml:60-64` `github-release-files` and `:66-75`
  build steps). `make vm-test` — future/opt-in QEMU harness, not part of `make all`.

## Testing

- `tests/` is a self-contained `uv` Python project, pytest + ruff only; every
  non-unit test must be written in or executable via pytest. No live docker by
  default: the session `artifacts` fixture packs the synthetic fixture tree.
- Markers `vm` and `e2e`, both opt-in, gated by `PODMAN_STATIC_VM_TEST=1` /
  `PODMAN_STATIC_E2E=1`. `e2e` runs the real `make pack`; `vm` boots the (future)
  QEMU guest. Neither is in `make all`.
- Default suite needs no docker/buildx and no host `dpkg-deb`/`rpmbuild`/`makepkg`;
  formats are inspected as archives (ar / tar / rpm / zstd). Real
  `dpkg -i`/`rpm -i`/`pacman -U` installs belong to the future VM harness.
- `tests/uv.lock` is committed; the venv lives under `tests/.venv`.

## Conventions

- Makefile vars: `UV ?= uv`, `UV_RUN ?= $(UV) run --project tests --no-sync`,
  `PYTEST_CONFIG ?= tests/pyproject.toml`, `NFPM_VERSION ?= v2.49.0`,
  `PLATFORM ?= linux/amd64`, `ARCH` (derived from `PLATFORM` via sed
  `s!linux/([^/]+).*!\1!`), `OUT_DIR ?= out`,
  `ASSET_DIR ?= $(OUT_DIR)/asset/podman-linux-$(ARCH)`,
  `DIST_DIR ?= dist/podman-static`, `PKG_NAME ?= podman-static`,
  `PKG_VERSION`, `PKG_RELEASE`, `ARCH_DEB`, `ARCH_RPM`, `ARCH_PKG` (last five from
  `scripts/version.sh`).
- Metadata (locked v1): name `podman-static`, license Apache-2.0, vendor/homepage
  `https://github.com/mgoltzsche/podman-static`; NO runtime deps (binaries are
  static/musl); NO maintainer scripts (systemd/subuid setup is a documented admin
  step); checksums only (`out/SHA256SUMS`).
- Version scheme: `scripts/version.sh` derives VERSION/RELEASE from
  `git -C dist/podman-static describe --tags --always` (`v6.2.0-1-gc55c0fb` ->
  `6.2.0` / `1`), falling back to Dockerfile `ARG PODMAN_VERSION=v6.2.0`. No args
  -> `KEY=value` lines; `KEY` arg -> one value. No `-` in the version field.
- `nfpm.yaml` is a `@PKG_NAME@`/`@PKG_VERSION@`/`@PKG_RELEASE@`/`@ARCH@`/
  `@ASSET_DIR@` template; `gen-nfpm.sh` renders concrete YAML to stdout. `contents`:
  `type: tree` `@ASSET_DIR@/usr/local` -> `/usr/local`; `config|noreplace|tree`
  `@ASSET_DIR@/etc/containers` -> `/etc/containers`; a plain README.md content
  entry -> `/usr/share/doc/@PKG_NAME@/README.md` (nfpm drops `type: doc` entries);
  `type: symlink` `/usr/local/bin/podman` -> `/usr/bin/docker`. Top-level `rpm:`
  (group/summary) and `archlinux:` (packager) sections.
- Env overrides: `ASSET_DIR`, `OUT_DIR`, `PLATFORM`, `ARCH`, `DIST_DIR`,
  `PKG_NAME`, `PKG_VERSION`, `PKG_RELEASE`, `NFPM_VERSION`, `NFPM_BIN`,
  `NFPM_CACHE_DIR`, `PODMAN_STATIC_E2E`, `PODMAN_STATIC_VM_TEST`,
  `PODMAN_STATIC_VM_CACHE`.
- `.gitignore`: `out/`, `.venv*/`, `.pytest_cache/`, `.ruff_cache/`,
  `__pycache__/`, `*.py[cod]`, `.vm-cache/`, `tests/vm/results/`, `.tools/`,
  `dist/podman-static/build/`, `*.asc`, `*.sha256`.

## Gotchas

- nfpm does NOT substitute env vars in its config — the committed `nfpm.yaml` is a
  `@...@` template and `gen-nfpm.sh` is the renderer; do not try to drive it with
  `${...}`/env vars alone.
- nfpm AUTO-TRANSLATES arch: write `arch: amd64`/`arm64` once and it emits
  `x86_64`/`aarch64` for rpm and archlinux. `ARCH_DEB`/`ARCH_RPM`/`ARCH_PKG` from
  `version.sh` are for filename verification, not for the config.
- `config|noreplace|tree` marks `/etc/containers` files as conffiles/backup, so
  upgrades never clobber user config. Keep it.
- Leave the vendored upstream checkout untouched: add no files under
  `dist/podman-static/` and do not edit its `workflow.yml`. CI wiring is deferred to
  `print-release-assets` consumption by a future job.
- Symlinks are load-bearing and path-bound: relative quadlet-generator links
  (`Makefile:120-121`) and the `/usr/bin/docker` link (`Dockerfile:188`, declared
  as a `type: symlink` entry). They install to absolute `/usr` paths in Task 1;
  relocating them is Task 2's problem (quadlet `_binDir` is compiled in).
- FUTURE / not implemented: Task 2 relocatable non-root tarball + `install.sh`,
  the QEMU VM harness (`vm-test`), CI/release wiring, GPG package signatures, and
  maintainer scripts. Do not claim they exist; `make all` is fixture-only.
