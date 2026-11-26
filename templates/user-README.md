# podman-static (non-root user install)

Relocatable, `$HOME`-scoped install of the statically linked (musl) rootless
podman binaries from `mgoltzsche/podman-static`.

## Install

```sh
tar -xzf podman-static-<version>-<release>-<arch>-user.tar.gz
./podman-static-user/install.sh --prefix "$HOME/.local/opt/podman-static"
. "$HOME/.local/opt/podman-static/bin/podman-env.sh"
podman --version
podman run --rm docker.io/library/alpine echo hello
```

`--prefix` defaults to `$HOME/.local/opt/podman-static` (or
`$PODMAN_STATIC_PREFIX`). The prefix must be an absolute, writable path; spaces
are supported. Installing as root is refused.

The installer writes only inside the prefix and prints warnings (never errors)
for missing host prerequisites. The prefix must be on a filesystem that supports
user namespaces and overlay-on-fuse; container images and volumes are kept in
`<prefix>/var` and survive `uninstall.sh`.

## Activate

Sourcing `bin/podman-env.sh` prepends `<prefix>/bin` to `PATH` and points
`CONTAINERS_CONF`, `CONTAINERS_STORAGE_CONF` and `CONTAINERS_REGISTRIES_CONF` at
the prefix. Shell startup files are never modified. The activation is
idempotent; source it from your shell rc if desired.

## Uninstall

```sh
"<prefix>/bin/podman-static-uninstall.sh"
```

Only files recorded by the installer and still unchanged are removed. Modified
files, unrelated files and everything under `<prefix>/var` are preserved and
reported. Use `--prefix` when running `uninstall.sh` from the extracted tarball.

## Not included

systemd units, quadlet generators and the `docker` alias are system-package only.
Host prerequisites (subuid/subgid delegation, `newuidmap`/`newgidmap`, `nftables`,
`nsenter`, `/dev/fuse`, AppArmor profile) remain the host administrator's job;
`install.sh` only warns about them.
