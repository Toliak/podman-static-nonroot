SHELL := /usr/bin/env bash

PODMAN ?= podman

PROXY ?= $(or $(ALL_PROXY),$(all_proxy),$(HTTPS_PROXY),$(https_proxy),$(HTTP_PROXY),$(http_proxy))

ifneq ($(strip $(PROXY)),)
PROXY_ENV = ALL_PROXY='$(PROXY)' HTTPS_PROXY='$(PROXY)' HTTP_PROXY='$(PROXY)' NO_PROXY='$(NO_PROXY)'
PROXY_NETWORK = --network=host
else
PROXY_ENV =
PROXY_NETWORK =
endif

PODMAN_BUILD = $(PROXY_ENV) $(PODMAN) build $(PROXY_NETWORK)

NFPM_VERSION ?= v2.49.0
NFPM_BIN ?=

UPSTREAM_REPO ?= https://github.com/mgoltzsche/podman-static
UPSTREAM_REF ?= c55c0fbb9ede2937f71536a394d5cccc5efafcfe
UPSTREAM_VERSION ?= v6.2.0

CACHE_DIR ?= .cache
TOOLS_IMAGE ?= localhost/podman-static-nonroot-tools:$(NFPM_VERSION)

PLATFORM ?= linux/amd64
ARCH ?= $(shell echo "$(PLATFORM)" | sed -E 's!linux/([^/]+).*!\1!')

OUT_DIR ?= out
ASSET_DIR ?= $(OUT_DIR)/asset/podman-linux-$(ARCH)

PKG_NAME ?= podman-static
PKG_VERSION ?= $(shell ARCH='$(ARCH)' PLATFORM='$(PLATFORM)' UPSTREAM_VERSION='$(UPSTREAM_VERSION)' bash scripts/version.sh PKG_VERSION)
PKG_RELEASE ?= $(shell ARCH='$(ARCH)' PLATFORM='$(PLATFORM)' UPSTREAM_VERSION='$(UPSTREAM_VERSION)' bash scripts/version.sh PKG_RELEASE)
ARCH_DEB ?= $(shell ARCH='$(ARCH)' PLATFORM='$(PLATFORM)' UPSTREAM_VERSION='$(UPSTREAM_VERSION)' bash scripts/version.sh ARCH_DEB)
ARCH_RPM ?= $(shell ARCH='$(ARCH)' PLATFORM='$(PLATFORM)' UPSTREAM_VERSION='$(UPSTREAM_VERSION)' bash scripts/version.sh ARCH_RPM)
ARCH_PKG ?= $(shell ARCH='$(ARCH)' PLATFORM='$(PLATFORM)' UPSTREAM_VERSION='$(UPSTREAM_VERSION)' bash scripts/version.sh ARCH_PKG)
USER_FILE ?= $(shell ARCH='$(ARCH)' PLATFORM='$(PLATFORM)' UPSTREAM_VERSION='$(UPSTREAM_VERSION)' bash scripts/version.sh USER_FILE)

PACK_ENV = ASSET_DIR='$(ASSET_DIR)' OUT_DIR='$(OUT_DIR)' PLATFORM='$(PLATFORM)' ARCH='$(ARCH)' CACHE_DIR='$(CACHE_DIR)' PKG_NAME='$(PKG_NAME)' NFPM_VERSION='$(NFPM_VERSION)' NFPM_BIN='$(NFPM_BIN)' UPSTREAM_REPO='$(UPSTREAM_REPO)' UPSTREAM_REF='$(UPSTREAM_REF)' UPSTREAM_VERSION='$(UPSTREAM_VERSION)'

PODMAN_ENV = -e PLATFORM='$(PLATFORM)' -e ARCH='$(ARCH)' -e OUT_DIR='$(OUT_DIR)' -e ASSET_DIR='$(ASSET_DIR)' -e CACHE_DIR='$(CACHE_DIR)' -e PKG_NAME='$(PKG_NAME)' -e PKG_VERSION='$(PKG_VERSION)' -e PKG_RELEASE='$(PKG_RELEASE)' -e NFPM_VERSION='$(NFPM_VERSION)' -e NFPM_BIN='$(NFPM_BIN)' -e UPSTREAM_REPO='$(UPSTREAM_REPO)' -e UPSTREAM_REF='$(UPSTREAM_REF)' -e UPSTREAM_VERSION='$(UPSTREAM_VERSION)' -e PODMAN_STATIC_E2E='$(PODMAN_STATIC_E2E)'

PODMAN_RUN = $(PODMAN) run --rm --userns=keep-id -v "$(CURDIR):/work" -w /work $(PODMAN_ENV) $(TOOLS_IMAGE)

.PHONY: all fetch tools-image build stage pack pack-user pack-deb pack-rpm pack-pkg pack-fixture checksums test lint vet clean distclean vm-test print-vars print-release-assets register-qemu _all _stage _pack _pack-user _pack-deb _pack-rpm _pack-pkg _pack-fixture _checksums _test _lint _vet

all: tools-image
	$(PODMAN_RUN) make _all

_all: _pack-fixture _test _lint

tools-image:
	$(PODMAN_BUILD) -f Containerfile.tools -t '$(TOOLS_IMAGE)' --build-arg NFPM_VERSION='$(NFPM_VERSION)' .

fetch:
	mkdir -p '$(CACHE_DIR)'
	$(PODMAN_BUILD) -f Containerfile --target export --build-arg UPSTREAM_REPO='$(UPSTREAM_REPO)' --build-arg UPSTREAM_REF='$(UPSTREAM_REF)' -o type=local,dest='$(CACHE_DIR)/upstream' .
	UPSTREAM_REF='$(UPSTREAM_REF)' UPSTREAM_VERSION='$(UPSTREAM_VERSION)' CACHE_DIR='$(CACHE_DIR)' bash scripts/verify-upstream.sh

build: fetch tools-image
	$(PODMAN_BUILD) -f '$(CACHE_DIR)/upstream/Dockerfile' --target tar-archive --platform 'linux/$(ARCH)' -o type=local,dest='$(CACHE_DIR)/rootfs' '$(CACHE_DIR)/upstream'
	$(PODMAN_RUN) make _stage

stage: tools-image
	$(PODMAN_RUN) make _stage

_stage:
	$(PACK_ENV) bash scripts/stage.sh

pack: tools-image
	$(PODMAN_RUN) make _pack

_pack:
	$(PACK_ENV) bash scripts/pack.sh
	$(PACK_ENV) bash scripts/pack-user.sh

pack-user: tools-image
	$(PODMAN_RUN) make _pack-user

_pack-user:
	$(PACK_ENV) bash scripts/pack-user.sh

pack-deb: tools-image
	$(PODMAN_RUN) make _pack-deb

_pack-deb:
	$(PACK_ENV) bash scripts/pack.sh deb

pack-rpm: tools-image
	$(PODMAN_RUN) make _pack-rpm

_pack-rpm:
	$(PACK_ENV) bash scripts/pack.sh rpm

pack-pkg: tools-image
	$(PODMAN_RUN) make _pack-pkg

_pack-pkg:
	$(PACK_ENV) bash scripts/pack.sh archlinux

pack-fixture: tools-image
	$(PODMAN_RUN) make _pack-fixture

_pack-fixture:
	$(MAKE) _pack ASSET_DIR=tests/fixtures/asset OUT_DIR='$(OUT_DIR)'

checksums: tools-image
	$(PODMAN_RUN) make _checksums

_checksums:
	$(PACK_ENV) bash scripts/pack.sh --checksums-only

test: tools-image
	$(PODMAN_RUN) make _test

_test:
	pytest -q -c tests/pyproject.toml tests

lint: tools-image
	$(PODMAN_RUN) make _lint

_lint:
	ruff check --config tests/pyproject.toml .
	ruff format --check --config tests/pyproject.toml .
	shellcheck -x -S warning scripts/*.sh templates/*.sh

vet: tools-image
	$(PODMAN_RUN) make _vet

_vet:
	shellcheck -x -S warning scripts/*.sh templates/*.sh

clean:
	rm -rf $(OUT_DIR) $(CACHE_DIR)/rootfs

distclean: clean
	rm -rf $(CACHE_DIR)

vm-test:
	@echo "vm-test: QEMU VM harness is not implemented yet (planned for a later phase)" >&2
	@exit 1

register-qemu:
	$(PODMAN) run --rm --privileged docker.io/multiarch/qemu-user-static:7.0.0-7 --reset -p yes

print-vars:
	@echo "PODMAN=$(PODMAN)"
	@echo "PLATFORM=$(PLATFORM)"
	@echo "ARCH=$(ARCH)"
	@echo "PKG_NAME=$(PKG_NAME)"
	@echo "PKG_VERSION=$(PKG_VERSION)"
	@echo "PKG_RELEASE=$(PKG_RELEASE)"
	@echo "ARCH_DEB=$(ARCH_DEB)"
	@echo "ARCH_RPM=$(ARCH_RPM)"
	@echo "ARCH_PKG=$(ARCH_PKG)"
	@echo "USER_FILE=$(USER_FILE)"
	@echo "ASSET_DIR=$(ASSET_DIR)"
	@echo "OUT_DIR=$(OUT_DIR)"
	@echo "CACHE_DIR=$(CACHE_DIR)"
	@echo "UPSTREAM_REPO=$(UPSTREAM_REPO)"
	@echo "UPSTREAM_REF=$(UPSTREAM_REF)"
	@echo "UPSTREAM_VERSION=$(UPSTREAM_VERSION)"
	@echo "NFPM_VERSION=$(NFPM_VERSION)"
	@echo "TOOLS_IMAGE=$(TOOLS_IMAGE)"
	@bash scripts/version.sh

print-release-assets:
	@bash scripts/release-assets.sh
