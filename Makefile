SHELL := /usr/bin/env bash

UV ?= uv
UV_RUN ?= $(UV) run --project tests --no-sync
PYTEST_CONFIG ?= tests/pyproject.toml

NFPM_VERSION ?= v2.49.0
NFPM_BIN ?=
NFPM_CACHE_DIR ?= .tools

PLATFORM ?= linux/amd64
ARCH ?= $(shell echo "$(PLATFORM)" | sed -E 's!linux/([^/]+).*!\1!')

OUT_DIR ?= out
ASSET_DIR ?= $(OUT_DIR)/asset/podman-linux-$(ARCH)
DIST_DIR ?= dist/podman-static

PKG_NAME ?= podman-static
PKG_VERSION ?= $(shell ARCH='$(ARCH)' PLATFORM='$(PLATFORM)' DIST_DIR='$(DIST_DIR)' bash scripts/version.sh PKG_VERSION)
PKG_RELEASE ?= $(shell ARCH='$(ARCH)' PLATFORM='$(PLATFORM)' DIST_DIR='$(DIST_DIR)' bash scripts/version.sh PKG_RELEASE)
ARCH_DEB ?= $(shell ARCH='$(ARCH)' PLATFORM='$(PLATFORM)' DIST_DIR='$(DIST_DIR)' bash scripts/version.sh ARCH_DEB)
ARCH_RPM ?= $(shell ARCH='$(ARCH)' PLATFORM='$(PLATFORM)' DIST_DIR='$(DIST_DIR)' bash scripts/version.sh ARCH_RPM)
ARCH_PKG ?= $(shell ARCH='$(ARCH)' PLATFORM='$(PLATFORM)' DIST_DIR='$(DIST_DIR)' bash scripts/version.sh ARCH_PKG)

PACK_ENV = ASSET_DIR='$(ASSET_DIR)' OUT_DIR='$(OUT_DIR)' PLATFORM='$(PLATFORM)' ARCH='$(ARCH)' DIST_DIR='$(DIST_DIR)' PKG_NAME='$(PKG_NAME)' NFPM_VERSION='$(NFPM_VERSION)' NFPM_BIN='$(NFPM_BIN)' NFPM_CACHE_DIR='$(NFPM_CACHE_DIR)'

.PHONY: all build pack pack-deb pack-rpm pack-pkg pack-fixture checksums sync test lint vet clean vm-test print-vars print-release-assets ensure-nfpm

all: pack-fixture test lint

build:
	$(PACK_ENV) bash scripts/stage.sh

pack:
	$(PACK_ENV) bash scripts/pack.sh

pack-deb:
	$(PACK_ENV) bash scripts/pack.sh deb

pack-rpm:
	$(PACK_ENV) bash scripts/pack.sh rpm

pack-pkg:
	$(PACK_ENV) bash scripts/pack.sh archlinux

pack-fixture:
	$(MAKE) pack ASSET_DIR=tests/fixtures/asset OUT_DIR='$(OUT_DIR)'

checksums:
	$(PACK_ENV) bash scripts/pack.sh --checksums-only

ensure-nfpm:
	NFPM_VERSION='$(NFPM_VERSION)' NFPM_CACHE_DIR='$(NFPM_CACHE_DIR)' bash scripts/ensure-nfpm.sh

sync:
	$(UV) sync --project tests --frozen

test: sync
	$(UV_RUN) pytest -q -c $(PYTEST_CONFIG) tests

lint: sync
	$(UV_RUN) ruff check --config $(PYTEST_CONFIG) .
	$(UV_RUN) ruff format --check --config $(PYTEST_CONFIG) .
	shellcheck -x -S warning scripts/*.sh

vet:
	shellcheck -x -S warning scripts/*.sh

clean:
	rm -rf $(OUT_DIR)

vm-test:
	@echo "vm-test: QEMU VM harness is not implemented yet (planned for a later phase)" >&2
	@exit 1

print-vars:
	@echo "PLATFORM=$(PLATFORM)"
	@echo "ARCH=$(ARCH)"
	@echo "PKG_NAME=$(PKG_NAME)"
	@echo "PKG_VERSION=$(PKG_VERSION)"
	@echo "PKG_RELEASE=$(PKG_RELEASE)"
	@echo "ARCH_DEB=$(ARCH_DEB)"
	@echo "ARCH_RPM=$(ARCH_RPM)"
	@echo "ARCH_PKG=$(ARCH_PKG)"
	@echo "ASSET_DIR=$(ASSET_DIR)"
	@echo "OUT_DIR=$(OUT_DIR)"
	@echo "DIST_DIR=$(DIST_DIR)"
	@echo "NFPM_VERSION=$(NFPM_VERSION)"
	@bash scripts/version.sh

print-release-assets:
	@bash scripts/release-assets.sh
