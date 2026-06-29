#!/usr/bin/env bash
# Point Ubuntu system nginx (port 80) at the GSTRecon Docker web container (127.0.0.1:8080).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/GSTRecon}"
SITE_NAME="gstrecon"
SITE_SRC="$APP_DIR/deploy/nginx-host.conf"
SITE_DEST="/etc/nginx/sites-available/$SITE_NAME"

if [[ ! -f "$SITE_SRC" ]]; then
  echo "Missing $SITE_SRC" >&2
  exit 1
fi

if ! command -v nginx >/dev/null 2>&1; then
  echo "Installing nginx..."
  apt-get update
  apt-get install -y nginx
fi

cp "$SITE_SRC" "$SITE_DEST"
ln -sf "$SITE_DEST" "/etc/nginx/sites-enabled/$SITE_NAME"
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl enable nginx
systemctl reload nginx

echo "Host nginx configured. Public traffic :80 -> Docker web :8080"
echo "Ensure Docker is running: cd $APP_DIR && docker compose -f docker-compose.prod.yml up -d"
