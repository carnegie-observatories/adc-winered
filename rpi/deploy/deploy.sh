#!/usr/bin/env bash
# Copy this directory's project to the Pi and install it as a service.
# Runs from a workstation:
#
#   rpi/deploy/deploy.sh            # deploys to wr-pi
#   rpi/deploy/deploy.sh other-host
#
# Needs SSH access to the host and sudo there. Everything Pi-side happens in
# install.sh, which this script invokes over SSH.
set -euo pipefail

HOST=${1:-wr-pi}
STAGING=${STAGING:-wr-mechanisms-src}
SRC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

echo "==> deploying $SRC_DIR -> $HOST:~/$STAGING"

if ! compgen -G "$SRC_DIR/deploy/wheels/websockets-*.whl" >/dev/null; then
  echo "!! no websockets wheel in deploy/wheels/ — the Pi has no route to PyPI" >&2
  echo "   and cannot fetch one itself. From a machine with network:" >&2
  echo "   pip download --only-binary=:all: --implementation py --abi none \\" >&2
  echo "     --platform any --no-deps -d $SRC_DIR/deploy/wheels websockets" >&2
  exit 1
fi

# -L resolves wr_mechanisms/static/mechanisms.html, which is a symlink to the
# repo's web/mechanisms.html, into a real file on the Pi.
rsync -azL --delete \
  --exclude '__pycache__' --exclude '.pytest_cache' --exclude '*.pyc' \
  --exclude '.venv' --exclude 'venv' \
  "$SRC_DIR/" "$HOST:$STAGING/"

# -t so sudo can prompt for a password. install.sh picks the service user up
# from SUDO_USER; override with RUN_USER=<name> in the environment there.
ssh -t "$HOST" "sudo bash ~/$STAGING/deploy/install.sh"

echo
echo "==> deployed. The panel is served by the service itself:"
echo "    http://$HOST:52403/"
