#!/usr/bin/env bash
# Install (or upgrade) wr-mechanisms as a systemd service. Runs *on the Pi*, as
# root, against a source tree already copied there — deploy.sh does the copying.
# Safe to re-run: the venv is reused and /etc/default is left alone.
#
# Assumes no internet. wr-pi cannot reach deb.debian.org or pypi.org, so this
# script never runs `apt-get update` and never installs from PyPI: gpiozero and
# lgpio must already be present from apt, and `websockets` is installed from the
# pure-Python wheel carried along in deploy/wheels/.
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/wr-mechanisms}
SERVICE=wr-mechanisms
ENV_FILE=/etc/default/${SERVICE}
UNIT_FILE=/etc/systemd/system/${SERVICE}.service

SRC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
RUN_USER=${RUN_USER:-${SUDO_USER:-$(id -un)}}

if [[ $EUID -ne 0 ]]; then
  echo "install.sh must run as root (try: sudo $0)" >&2
  exit 1
fi
if ! id -u "$RUN_USER" >/dev/null 2>&1; then
  echo "user '$RUN_USER' does not exist; set RUN_USER=<name>" >&2
  exit 1
fi

echo "==> source:  $SRC_DIR"
echo "==> install: $APP_DIR (service user: $RUN_USER)"

echo "==> checking system packages"
if ! python3 -c "import gpiozero, lgpio" 2>/dev/null; then
  echo "    missing gpiozero/lgpio. Install them first:" >&2
  echo "      sudo apt-get install -y python3-gpiozero python3-lgpio" >&2
  exit 1
fi
if ! id -nG "$RUN_USER" | tr ' ' '\n' | grep -qx gpio; then
  echo "    warning: user '$RUN_USER' is not in the 'gpio' group;" >&2
  echo "    the service may fail to claim /dev/gpiochip0" >&2
fi

echo "==> syncing source"
mkdir -p "$APP_DIR"
rsync -a --delete \
  --exclude '__pycache__' --exclude '.pytest_cache' --exclude '*.pyc' \
  --exclude 'venv' \
  "$SRC_DIR/" "$APP_DIR/src/"

echo "==> venv"
if [[ ! -x "$APP_DIR/venv/bin/python" ]]; then
  # --system-site-packages is what lets the venv see the apt-installed
  # gpiozero and lgpio.
  python3 -m venv --system-site-packages "$APP_DIR/venv"
fi

if "$APP_DIR/venv/bin/python" -c "import websockets" 2>/dev/null; then
  echo "==> websockets $("$APP_DIR/venv/bin/python" -c 'import websockets; print(websockets.__version__)') already installed"
else
  echo "==> installing websockets from the bundled wheel"
  if ! compgen -G "$APP_DIR/src/deploy/wheels/websockets-*.whl" >/dev/null; then
    echo "    no wheel in $APP_DIR/src/deploy/wheels — re-run deploy.sh from a" >&2
    echo "    workstation, which fetches it" >&2
    exit 1
  fi
  "$APP_DIR/venv/bin/pip" install --quiet --no-index \
    --find-links "$APP_DIR/src/deploy/wheels" websockets
fi

# The package itself is run from source (PYTHONPATH below) rather than
# pip-installed: a build backend would have to come from PyPI, and this box has
# no route to it.

if [[ -f "$ENV_FILE" ]]; then
  echo "==> keeping existing $ENV_FILE"
else
  echo "==> writing $ENV_FILE"
  install -m 0644 "$APP_DIR/src/deploy/wr-mechanisms.env" "$ENV_FILE"
fi

echo "==> installing $UNIT_FILE"
sed -e "s|__APP_DIR__|$APP_DIR|g" -e "s|__USER__|$RUN_USER|g" \
  "$APP_DIR/src/deploy/${SERVICE}.service" > "$UNIT_FILE"
chmod 0644 "$UNIT_FILE"

systemctl daemon-reload
systemctl enable "$SERVICE"
systemctl restart "$SERVICE"

sleep 1
systemctl --no-pager --lines=15 status "$SERVICE" || true
echo
echo "Done. Panel: http://$(hostname):$(grep -oP '(?<=^WR_WS_PORT=)\d+' "$ENV_FILE" 2>/dev/null || echo 52403)/"
echo "Logs:  journalctl -u $SERVICE -f"
