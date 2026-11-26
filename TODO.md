# TODO

Test/tooling conventions mirror `/home/agentic/Projects/pinp`: tooling is non-Python (`Makefile` + shell + `nfpm.yaml`); a self-contained `uv` Python black-box suite lives under `tests/`; heavy infra is an opt-in, marker-gated VM harness; docs are `AGENTS.md` / `INFO.md` / `TODO.md`. Every non-unit test must be written in or executable via pytest.

## Architecture change (2026-11-26)

All `[x]` items below describe the ORIGINAL Task 1 design (vendored
`dist/podman-static`, docker/buildx for the real build, host-side nfpm) and are
kept as a historical record. The following decisions supersede them; the current
truth is in `AGENTS.md` / `INFO.md` / `README.md`.

- Full cutover: `dist/podman-static/` is DELETED (was an untracked nested git
  checkout). Upstream source is fetched at build time inside `Containerfile` into
  `.cache/upstream/`; the compiled rootfs is exported to `.cache/rootfs/`.
- NO docker anywhere: no CLI, no daemon, no `buildx`, no `~/.local/bin/docker`
  shim, no upstream `Makefile`. Upstream `Dockerfile` is built directly with
  `podman build --target tar-archive -o type=local` (no builder).
- Everything in podman: host `make` orchestrates three podman operations —
  `Containerfile` fetch, `podman build` of the fetched Dockerfile, `podman run` of
  `Containerfile.tools` for stage/pack/test/lint. NO nested podman.
- podman is MANDATORY for `make all`; there is no container-free host fallback.
  `scripts/ensure-nfpm.sh` and `.tools/` are gone; nfpm v2.49.0, the locked
  pytest/ruff venv, shellcheck and archive tools are baked into the tooling image.
- Public targets (`all pack test lint ...`) wrap `_`-prefixed internal targets;
  the tooling image runs internal targets so it never recurses.
- Pinning: `UPSTREAM_REF=c55c0fbb9ede2937f71536a394d5cccc5efafcfe` (full 40-char
  SHA — GitHub rejects short SHAs for `git fetch`), `UPSTREAM_VERSION=v6.2.0`.
  `make fetch` + `scripts/verify-upstream.sh` assert the rev and that the fetched
  `Dockerfile`'s `ARG PODMAN_VERSION` matches `UPSTREAM_VERSION`.
- `scripts/version.sh` now derives VERSION/RELEASE from `UPSTREAM_VERSION`; the
  `PODMAN_STATIC_DESCRIBE` / `PODMAN_STATIC_GIT` /
  `PODMAN_STATIC_PODMAN_VERSION` override hooks remain for the test suite.
- `PROXY` is opt-in (defaults to standard `ALL_PROXY`/`HTTPS_PROXY`/`HTTP_PROXY`
  env vars): when set, podman builds get `--network=host` + proxy passthrough so a
  `127.0.0.1` SOCKS/HTTP proxy works inside RUN steps. Needed for the flaky
  `passt.top` upstream clone; the no-proxy path is unchanged and keeps its cache.
- Deferred items (CI wiring, GPG signatures, VM harness, Task 2) are UNCHANGED;
  the old "leave upstream untouched / CI deferred because workflow.yml is
  vendored" rationale no longer applies — CI wiring is simply still deferred.

## Task 1 decisions (2026-11-26)

Task 1 is implemented; `make all` is green (49 pytest tests + ruff + shellcheck).
Decisions on the "Confirm before coding" items (all reversible via Makefile vars /
`nfpm.yaml`):

- Package name `podman-static`; NO runtime/weak deps; NO maintainer scripts.
- v1 emits checksums only (`out/SHA256SUMS`); GPG signatures are a follow-up.
- Test suite is stdlib-only (pytest + ruff); `.pkg.tar.zst` is read via `zstd -dc`
  into stdlib `tarfile` — no `PyYAML`/`zstandard` dependency.
- CI wiring is OUT of scope here: editing the vendored
  `.github/workflows/workflow.yml` would violate "leave upstream untouched".
  `make print-release-assets` exposes the manifest a future job would consume.
- nfpm does NOT env-template its config and DROPS `type: doc` entries, so
  `nfpm.yaml` is a `@TOKEN@` template rendered by `scripts/gen-nfpm.sh`, and the
  README uses a plain content entry (not `type: doc`).
- Degraded-mode semantics / bundled helpers (Task 2) remain open.

- [x] Record project context and the locked decisions (fold into `INFO.md` / `AGENTS.md` when tooling lands). — Resolved (2026-11-26).
  - Input: `dist/podman-static` is a vendored, clean checkout of `mgoltzsche/podman-static` (`v6.2.0-1-gc55c0fb`, `origin https://github.com/mgoltzsche/podman-static`, `LICENSE` Apache-2.0, 24 tracked files). The user's `./out/podman-static` path does not exist; there is no `out/` dir anywhere today.
  - Decision (2026-11-25): the tooling is a NEW wrapper project at the workspace root `/home/agentic/Projects/podman-static-nonroot/` (not a git repo today), consuming `dist/podman-static` as a read-only input. Leave the upstream checkout untouched — do not add files inside it.
  - Decision (2026-11-25): `out/` becomes the wrapper's generated output dir (staged asset tree + `.deb` + `.rpm` + `.pkg.tar.zst` + relocatable user tarball), gitignored. This resolves the `./out` reference.
  - Decision (2026-11-25): tooling = `Makefile` + shell scripts + `nfpm.yaml`; Python is tests-only (same split as `pinp`: Go source / Python tests).
  - Decision (2026-11-25): packaging backend = **nfpm** (rootless, single config, pure-Go binary, no host `dpkg-deb` / `rpmbuild` / `makepkg`).
  - Decision (2026-11-25): VM harness = ONE generic **non-SELinux** QEMU guest validating all three formats; explicitly drop `pinp`'s `semodule -DB` / `ausearch` / `audit2allow` / `:z`/`:Z` / label-gating machinery.
  - Decision (2026-11-25): Task 2 emits a relocatable tarball + `install.sh` by transforming the asset tree at pack time (no upstream patches).
  - Pacman's package format is **`.pkg.tar.zst`** (Arch Linux). nfpm format keys: `deb`, `rpm`, `archlinux`.
  - Key upstream facts: `Makefile:35-36,109-122` assembles `build/asset/podman-linux-<ARCH>/{usr/local/{bin,lib,libexec,share,lib/systemd},etc/containers,README.md}` (`usr/local` + `etc/containers`, relative quadlet-generator symlinks at `Makefile:120-121`) and tars it to `build/asset/podman-linux-<ARCH>.tar.gz`. No `VERSION` variable, no version in artifact names; release version comes from git tags (`workflow.yml:54-64`), source version `PODMAN_VERSION=v6.2.0` (`Dockerfile:34`). Signing infra to reuse: `signed-tar` / `verify-signature` / GPG key `0CCF…BB503` (`Makefile:124-152`).

- [x] Scaffold the wrapper project (do this first; every later item's paths depend on it). — Resolved (2026-11-26).
  - Root: `Makefile`, `.gitignore`, `AGENTS.md`, `INFO.md`, `TODO.md`, `README.md`, `nfpm.yaml`, `scripts/`. Generated: `out/`, `.venv/`, caches.
  - `.gitignore`: `out/`, `.venv*/`, `.pytest_cache/`, `.ruff_cache/`, `__pycache__/`, `*.py[cod]`, `.vm-cache/`, `tests/vm/results/`, `*.asc`, `*.sha256`.
  - Root `Makefile` mirrors `pinp/Makefile`: `UV ?= uv`, `UV_RUN ?= $(UV) run --project tests --no-sync`, `PYTEST_CONFIG ?= tests/pyproject.toml`, targets `all: build test lint`, `build | pack | sync | test | lint | vm-test | clean | vet`. `sync` = `uv sync --project tests --frozen`; `test` = `$(UV_RUN) pytest -q -c $(PYTEST_CONFIG) tests`; `lint` = `ruff check` + `ruff format --check` + `shellcheck -x -S warning scripts/*.sh tests/vm/*.sh`.
  - Docs: `AGENTS.md` (Layout / Commands / Testing / Conventions / Gotchas, same sections as `pinp/AGENTS.md`), `INFO.md` (upstream build pipeline, hardcoded-path inventory, host prerequisites from `README.md:86-106`), `README.md` (how to build packages + non-root install).
  - Refresh `AGENTS.md` when each later item lands (pinp convention).

- [x] Set up the Python black-box test ecosystem under `tests/` (mirror `pinp/tests/`). — Resolved (2026-11-26).
  - `tests/pyproject.toml`: `[project] name = "podman-static-nonroot-tests"`, `version = "0.1.0"`, `requires-python = ">=3.10"`; `[dependency-groups] dev = ["pytest>=8.0", "ruff>=0.6"]`; `[tool.uv] package = false`; `[tool.pytest.ini_options] testpaths=["."]`, `pythonpath=["."]`, `norecursedirs=[".venv","build","out","vm/results"]`, markers `vm` (opt-in QEMU install matrix, `PODMAN_STATIC_VM_TEST=1`) and `e2e` (opt-in real upstream build); `[tool.ruff] line-length=100`, `target-version="py310"`, `extend-exclude=[".venv"]`, `lint.select=["E","F","I","UP","B"]`, `isort known-first-party=["helpers"]`.
  - Commit `tests/uv.lock` (`uv lock`), keep deps minimal like `pinp` (pytest + ruff only).
  - `tests/conftest.py`: session-scoped `artifacts` fixture that packs from a small **synthetic** fixture asset tree committed at `tests/fixtures/asset/` (mirror `pinp`'s `stub_podman` / `CANNED_INFO` canned input) so `make all` needs NEITHER docker/buildx NOR host packaging tools; plus a `tmp_home` fixture (a fake `$HOME` as an unprivileged user) for install.sh tests. A separate `@pytest.mark.e2e` fixture runs the real `make pack` when `PODMAN_STATIC_E2E=1`.
  - `tests/helpers.py`: `ROOT = Path(__file__).resolve().parents[1]`; constants (`EXPECTED_FILES`, `ARCH_MAP`, `VERSION_RE`); `run_tool()` subprocess wrapper; `read_ar()` (stdlib `ar` parser for `.deb`), `list_tar()` (`tarfile` + `gzip`/`zstd` via `tar --zstd`/`bsdtar` with a pinned `zstandard` dep only if needed), `read_pkginfo()`, `nfpm_config()` loader, `pack_fixture()` that invokes `make pack` against `tests/fixtures/asset`.
  - All `test_*.py` use `from __future__ import annotations`, type annotations, `from helpers import ...`. Confirm before coding: whether to add a tiny `PyYAML`/`zstandard` dep to `uv.lock` or stay stdlib-only via `tar --zstd` subprocess.

- [x] Orchestrate the upstream build (`make build`) without requiring root. — Resolved (2026-11-26).
  - `make build` delegates to `make -C dist/podman-static singlearch-tar PLATFORM=linux/$(ARCH)` (or `tar`), then copies `dist/podman-static/build/asset/podman-linux-<ARCH>/` into `out/asset/podman-linux-<ARCH>/`. Never `make install` (`Makefile:106-107` needs root).
  - Keep the wrapper hermetic: do not import `build/images/podman/...` internals; consume only the assembled staging tree. Document that a real docker/buildx build is opt-in behind `PODMAN_STATIC_E2E=1` (default suite uses the synthetic fixture).
  - Touch points: root `Makefile`, `AGENTS.md` Commands section.
  - Verification: `make build` on a machine with docker/buildx produces a complete `out/asset/...` tree; `make all` still passes with no docker available.

- [x] Derive package `VERSION` / `RELEASE` and per-format `ARCH` mapping (Task 1). — Resolved (2026-11-26).
  - `VERSION ?= $(shell git -C dist/podman-static describe --tags --always ...)`, strip leading `v` → e.g. `6.2.0`; `RELEASE ?=` from git distance/`gc55c0fb`. Sanitize for rpm (no `-` in version field), deb (`-` = debian_revision), archlinux (`pkgver`/`pkgrel`). Fall back to `PODMAN_VERSION` (`v6.2.0`) when no git.
  - `ARCH_MAP`: `amd64` → deb `amd64`, rpm `x86_64`, archlinux `x86_64`; `arm64` → deb `arm64`, rpm `aarch64`, archlinux `aarch64`. `PLATFORM` → `ARCH` via the upstream `sed` trick (`Makefile:28`).
  - Package metadata: name `podman-static`, `license: Apache-2.0`, `vendor/homepage = https://github.com/mgoltzsche/podman-static`, `maintainer`, `description` from `README.md:3`, `url`. No runtime dependencies (binaries are fully static, musl) — document host prerequisites separately instead.
  - Tests: `tests/test_versioning.py` (derivation, arch map, sanitization, no-git fallback), `tests/test_pack_metadata.py` (nfpm config fields, no absolute temp paths leaking into `contents`, no phantom deps).
  - Confirm before coding: package name (`podman-static` vs `podman-static-nonroot`) and whether to declare weak deps (`uidmap`, `nftables`) — recommend none, since nfpm is cross-distro and static binaries need none.

- [x] Author `nfpm.yaml` consuming the staged asset tree (Task 1). — Resolved (2026-11-26).
  - `name`, `arch`, `version`, `release`, `license`, `maintainer`, `description`, `homepage`, `platform: linux`; `formats: [deb, rpm, archlinux]` (or three `nfpm package --packager <fmt>` invocations with `overrides:`).
  - `contents:` glob `out/asset/podman-linux-<ARCH>/usr/local/*` → `/usr/local/*` and `etc/containers/*` → `/etc/containers/*`; mark `/etc/containers/**` as `type: config|noreplace` (conffile) so upgrades never clobber user config; preserve the two relative quadlet-generator symlinks (`Makefile:120-121`) and the `/usr/bin/docker` symlink (`Dockerfile:188`) as `type: symlink` entries.
  - `overrides:` per format for arch strings, rpm `group`/`summary`, deb `section: utils` / `priority: optional`, archlinux `packager`/`backup` (the `/etc/containers/*` files).
  - Decide maintainer scripts (postinstall `ln -s`, `systemctl`, subuid/subgid): recommend NONE in v1 — systemd/subuid setup stays a documented admin step (`README.md:86-122`) so packages install cleanly and stay rootless to BUILD. Track as a follow-up item.
  - Tests: `tests/test_nfpm_config.py`, `tests/test_asset_tree.py` (staging tree file/symlink inventory matches upstream `.podman-from-container`).
  - Gotcha: nfpm must run with `packager`-specific output names; the `.pkg.tar.zst` name is `podman-static-<VERSION>-<RELEASE>-<ARCH>.pkg.tar.zst`.

- [x] Add `make pack` / `pack-deb` / `pack-rpm` / `pack-pkg` targets producing all three packages into `out/` (Task 1). — Resolved (2026-11-26).
  - Wrap `nfpm package --config nfpm.yaml --packager <fmt> --target out/ ...`, pin the nfpm version (download a static release or run `goreleaser/nfpm` container) so the build never needs root. Record the pinned version in `AGENTS.md` Commands.
  - Emit `out/SHA256SUMS` (+ optional reuse of `signed-tar` / `verify-signature` GPG infra from `Makefile:124-152` for `.asc`); decide whether package signatures are in scope (Confirm before coding — recommend checksums in v1, signatures follow-up).
  - `make clean` = `rm -rf out/`. `make pack` depends on `build` (or the synthetic fixture for `make test`).
  - Tests: `tests/test_makefile.py` (targets exist, `--no-sync`/`--frozen` usage, dry-run of `pack`), `tests/test_deb.py`, `tests/test_rpm.py`, `tests/test_pacman.py`.
  - Verification: `make pack` produces exactly 3 files per arch in `out/`; `make all` green.

- [x] Black-box tests for each package format (Task 1 tests; no host packaging tools by default). — Resolved (2026-11-26).
  - `test_deb.py`: `ar` structure (`debian-binary`, `control.tar.*`, `data.tar.*`), `control` fields (Package/Version/Architecture/Maintainer/Section), `conffiles` lists `/etc/containers/*`, `data.tar` file list + symlink preservation, no root-owned temp paths.
  - `test_rpm.py`: filename `<name>-<version>-<release>.<arch>.rpm` with `x86_64`/`aarch64`, metadata (name/version/release/arch/license) via `rpm -qip` when available else `rpm2cpio`/`bsdtar` extraction + header sanity, payload file list.
  - `test_pacman.py`: `.pkg.tar.zst` naming, presence of `.PKGINFO` / `.BUILDINFO` / `.MTREE`, `pkgname`/`pkgver`/`pkgarch`/`license`/`backup` fields, file list, zstd integrity, symlinks preserved.
  - `test_pack_common.py`: identical file/symlink inventory across all three formats, no stray `out/`/`build/` paths, all binaries present (`podman`, `crun`, `runc`, `conmon`, `netavark`, `aardvark-dns`, `passt`/`pasta`, `fuse-overlayfs`, `catatonit`, `rootlessport`, `quadlet`).
  - Real `dpkg -i` / `rpm -i` / `pacman -U` installs are the VM harness's job, not the fast suite.

- [x] Attach the new packages to release/CI and documentation (Task 1). — Resolved (2026-11-26; docs + `print-release-assets` landed; CI wiring deferred per the "leave upstream untouched" locked decision).
  - Mirror `.github/workflows/workflow.yml:60-64` (`github-release-files`) — add the 6 package files (3 formats × 2 arches) + `SHA256SUMS` to the release asset list, and add a `make pack` step alongside `make clean multiarch-tar` (`:66-75`). Keep per-arch looping like `tar-all` (`Makefile:56-63`).
  - `README.md`: document `make pack`, package installation (`apt install ./…deb`, `dnf install ./…rpm`, `pacman -U ./…pkg.tar.zst`), naming/version scheme, and note upstream host-prerequisite steps still apply.
  - Tests/Docs: `tests/test_release_files.py` (every produced file is listed in CI assets), `AGENTS.md` Commands refresh.
  - Confirm before coding: whether CI is in scope for this phase at all, or only local tooling (workflow.yml lives in the vendored upstream and would mean editing it — remember "leave upstream untouched").

- [x] Audit hardcoded absolute paths in the asset tree (Task 2, do first for Task 2). — Resolved (2026-11-26).
  - Inventory from research: `quadlet` binary has `_binDir=/usr/local/bin` **compiled in** (`Dockerfile:51`) — cannot be rewritten in the payload; `storage.conf.d/00-podman-static.conf:8` `mount_program = "/usr/local/bin/fuse-overlayfs"`; `/usr/bin/docker` symlink (`Dockerfile:188`); `seccomp.json` at `/etc/containers/seccomp.json` (`Dockerfile:40-42`); systemd units under `/usr/local/lib/systemd/` (`Makefile:116-121`, `Dockerfile:61-63,217-219`); `helper_binaries_dir` default `/usr/local/lib/podman`.
  - Decision: for a `$HOME` install, systemd units + quadlet generators are root/systemd-bound and are **excluded** from the user payload (upstream is explicitly "without systemd support", `README.md:3`); document that quadlet/systemd stays system-package-only. Confirm before coding (alternative: ship a quadlet shim that rewrites `_binDir` via a wrapper).
  - Config knobs to generate at install time: `mount_program`, `graphroot`/`runroot` (the drop-in deliberately omits them, `00-podman-static.conf:2-4` — podman 6 resolves rootless paths from `$HOME`/`$XDG_DATA_HOME`), `seccomp_profile`, `helper_binaries_dir`, `runtime`/`runtime_path`.
  - Record findings in `INFO.md`; add a `Gotchas` section in `AGENTS.md`.
  - Tests: `tests/test_path_audit.py` (greps the staged tree for `/usr/local`, `/etc/containers`, `/usr/bin` and asserts each occurrence is either rewritten or explicitly allow-listed/excluded).

- [x] Build the relocatable user payload (`scripts/pack-user.sh`, Task 2). — Resolved (2026-11-26).
  - From `out/asset/...` produce `out/podman-static-<VERSION>-<ARCH>-user.tar.gz` with a top-level `podman-static-user/` dir: `bin/`, `lib/podman/`, `libexec/podman/` (no quadlet), `share/` (completions + `seccomp.json`), `etc/containers/` templates, `install.sh`, `uninstall.sh`, `env.sh`, `README.md`.
  - Parameterize config templates with a placeholder (e.g. `@PREFIX@`) that `install.sh` substitutes — never emit a real absolute path into the tarball. Strip the two quadlet-generator symlinks and `/usr/local/lib/systemd` from this payload.
  - Makefile target `pack-user` (depends on `build`), included in `make pack`.
  - Tests: `tests/test_relocatable_payload.py` (tarball has zero absolute `/usr`/`/etc` path strings, all expected files/symlinks present, `@PREFIX@` placeholders present, no `setuid`/root-owned files).
  - Verification: `tar -tzf` + `grep` audit; `make pack` emits the user tarball alongside the 3 packages.

- [x] Write `install.sh` / `uninstall.sh` and the env shim (Task 2 core). — Resolved (2026-11-26).
  - `install.sh`: `PREFIX=${PREFIX:-$HOME/.local}`; refuse if `id -u == 0` and confirm-no-root; refuse prefixes not writable by the current user; extract `bin/ lib/ libexec/ share/ etc/containers/` into `$PREFIX`; substitute `@PREFIX@` in generated `containers.conf` + `storage.conf.d/00-podman-static.conf` (`mount_program = "$PREFIX/bin/fuse-overlayfs"`, `seccomp_profile`, `helper_binaries_dir`); emit `$PREFIX/etc/containers/` and `$PREFIX/bin/podman-env.sh` exporting `PATH="$PREFIX/bin:$PATH"`, `CONTAINERS_CONF`, `CONTAINERS_STORAGE_CONF`, `XDG_DATA_HOME`/`XDG_CONFIG_HOME` where relevant; print a `podman run alpine echo hello` smoke command. Zero writes outside `$PREFIX`.
  - `uninstall.sh`: mirror `README.md:142-159` but scoped to `$PREFIX` (remove installed tree + env shim; warn about `podman system reset` for the user store).
  - Tests: `tests/test_install_sh.py` (install into `tmp_home` as non-root, assert success, no writes outside prefix, config paths rewritten to the prefix, `podman-env.sh` exports correct vars, `podman --version` resolves from `$PREFIX/bin`, `uninstall.sh` restores a clean prefix), `tests/test_install_guard.py` (refuses root / unwritable prefix / path traversal).
  - Shellcheck clean (`shellcheck -x -S warning`).

- [x] Handle host prerequisites that a no-root install still needs (Task 2 gotcha). — Resolved (2026-11-26; warn-only).
  - From `README.md:86-106`: `nftables`, `nsenter`, `shadow`'s `newuidmap`/`newgidmap` (setuid-root or `cap_setuid=ep`/`cap_setgid=ep` file caps), `/etc/subuid`+`/etc/subgid` delegation for the user, apparmor profile fix, optional `docker` symlink. Subuid/subgid delegation normally needs root — a genuinely root-free install assumes the admin already delegated ranges.
  - `install.sh` must **detect and WARN**, never fail hard: probe subuid/subgid ranges, `newuidmap`/`newgidmap`, `nftables`/`nsenter`; offer a documented degraded single-UID/`--userns` mode when no ranges exist; print an actionable preflight report (similar in spirit to `pinp`'s `pinp-check --json`).
  - Decide whether to vendor/skip helpers or rely on host `shadow`; document the boundary clearly in `README.md` and `INFO.md`.
  - Tests: `tests/test_preflight.py` (WARN matrix over missing helpers/ranges, degraded mode output), stub the probes via env overrides like `pinp`'s `PINP_*` hooks.
  - Confirm before coding: degraded-mode semantics (recommend WARN + docs only in v1, no bundled helpers).

- [ ] Add the single generic non-SELinux VM harness under `tests/vm/` (opt-in, mirror `pinp/tests/selinux/`).
  - Layout: `README.md`, `test_matrix.py`, `lib.sh`, `prepare-image.sh`, `prepare-guest.sh`, `boot.sh`, `run-matrix.sh`, `summarize.sh`, `guest/{setup.sh,run-case.sh}`, `results/` (gitignored). Cache in `.vm-cache/` (override via `PODMAN_STATIC_VM_CACHE`), on-disk not tmpfs.
  - Reuse `pinp`'s mechanism: pre-installed cloud qcow2 (download + published SHA256 verify), `qemu-img create -b` COW overlays, `virt-customize --ssh-inject`, `guestfish` kernel/initrd extraction for QEMU direct kernel boot, `-netdev user,hostfwd=tcp::2222-:22`, SSH control channel, KVM-or-TCG detection, `wait_ssh`, `vm_stop`.
  - **Non-SELinux**: recommend Debian genericcloud (SELinux absent entirely) with `selinux=0`/no LSM on the cmdline; NO `semodule -DB`, `ausearch`, `audit2allow`, `auditd`, `:z`/`:Z` relabeling, or label gating. No bind-mounting host dirs into the guest (avoids xattr issues that `pinp/README.md:82` hit). Only small files (scripts + the built packages) are `scp`'d in.
  - One guest validates all three formats: `dpkg -i` for `.deb` (native), `rpm -i`/`rpm2cpio`+`bsdtar` for `.rpm`, `bsdtar`/`zstd` extraction + `.PKGINFO`/`.MTREE` verification for `.pkg.tar.zst` (pacman isn't packaged on Debian). Plus an unprivileged `tester` user runs the Task 2 `install.sh` into `$HOME/.local` and `podman info` / `podman run alpine echo hello` as the real end-to-end smoke.
  - `tests/vm/test_matrix.py`: `pytestmark = [pytest.mark.vm, pytest.mark.skipif(PODMAN_STATIC_VM_TEST != "1")]`; asserts the three packages + user tarball exist, runs `bash run-matrix.sh` via `subprocess`, asserts `RESULTS.md` contains per-format PASS lines and `results/{deb,rpm,pkg,user}/` evidence files.
  - `make vm-test` = `PODMAN_STATIC_VM_TEST=1 $(UV_RUN) pytest -q -s -c $(PYTEST_CONFIG) -m vm tests/vm/test_matrix.py` (like `pinp/Makefile:34-35`). Not part of `make all`.
  - Confirm before coding: guest distro (recommend Debian 13 genericcloud; alternative Fedora Cloud with `selinux=0` gives native `rpm` + `dnf` and `dpkg`/`pacman` from repos) and whether native `pacman -U` is required (recommend extraction+verify to keep one generic guest).

- [ ] Final wiring, docs, and verification.
  - `make all` = `tools-image` + `_pack-fixture` (synthetic fixture) + `_test` (pytest) + `_lint` (ruff check/format + shellcheck), all inside the tooling image; pinned nfpm v2.49.0 + `uv sync --project /opt/tests-deps --frozen` baked into `Containerfile.tools`; `AGENTS.md` conventions + `Gotchas` refreshed, `INFO.md` background updated.
  - Verification commands: `make tools-image`, `make all`, `make fetch build pack` (real podman build), `make vm-test` (opt-in, needs QEMU + network, ~600 MB download), `shellcheck -x -S warning scripts/*.sh`, `ruff format --check --config tests/pyproject.toml .` inside the tooling image.
  - Docs: `README.md` replaces the manual prose at `.cache/upstream/README.md:79-80` with the automated `install.sh` flow; `TODO.md` items marked `[x]` with `Resolved (date)` notes as each lands (pinp style).
  - Register `vm` / `e2e` markers in `tests/pyproject.toml`; ensure `norecursedirs` excludes `vm/results` so the default suite never tries to boot a VM.
