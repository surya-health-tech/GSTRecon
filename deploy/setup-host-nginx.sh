#!/usr/bin/env bash
# Add a GSTRecon nginx vhost on the shared server (PracticeFlow, InvoiceAI, etc.).
# Does NOT remove or replace other sites or default_server.
#
# Subdomain (recommended when DNS is available):
#   SERVER_NAME=gstrecon.yourdomain.com bash deploy/setup-host-nginx.sh
#
# Requires GSTRecon Docker web on 127.0.0.1:HTTP_PORT (set WEB_BIND=127.0.0.1 in .env).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/GSTRecon}"
SITE_NAME="gstrecon"
TEMPLATE="$APP_DIR/deploy/nginx-host.conf.template"
SITE_DEST="/etc/nginx/sites-available/$SITE_NAME"
ENV_FILE="$APP_DIR/.env"

HTTP_PORT="${HTTP_PORT:-8080}"
SERVER_NAME="${SERVER_NAME:-}"

if [[ -f "$ENV_FILE" ]]; then
  env_port="$(grep -E '^HTTP_PORT=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r' || true)"
  env_name="$(grep -E '^SERVER_NAME=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r' || true)"
  [[ -n "$env_port" ]] && HTTP_PORT="$env_port"
  [[ -n "$env_name" ]] && SERVER_NAME="$env_name"
fi

if [[ -z "$SERVER_NAME" ]]; then
  echo "SERVER_NAME is required (subdomain for GSTRecon)." >&2
  echo "Example: SERVER_NAME=gstrecon.example.com bash deploy/setup-host-nginx.sh" >&2
  echo "" >&2
  echo "If you only have the shared IP, use a dedicated port instead (no host nginx):" >&2
  echo "  Set WEB_BIND=0.0.0.0 and HTTP_PORT=8080 in .env, then bash deploy/deploy.sh" >&2
  echo "  Open http://206.189.140.76:8080" >&2
  exit 1
fi

if [[ ! -f "$TEMPLATE" ]]; then
  echo "Missing $TEMPLATE" >&2
  exit 1
fi

if ! command -v nginx >/dev/null 2>&1; then
  echo "nginx is not installed. Use WEB_BIND=0.0.0.0 for direct port access." >&2
  exit 1
fi

sed -e "s/__SERVER_NAME__/${SERVER_NAME}/g" -e "s/__HTTP_PORT__/${HTTP_PORT}/g" "$TEMPLATE" >"$SITE_DEST"
ln -sf "$SITE_DEST" "/etc/nginx/sites-enabled/$SITE_NAME"

nginx -t
systemctl reload nginx

echo "GSTRecon nginx site enabled."
echo "  server_name: $SERVER_NAME"
echo "  proxy to:    127.0.0.1:$HTTP_PORT"
echo "  Other sites (PracticeFlow, InvoiceAI, etc.) were not modified."
echo ""
echo "Update backend/.env:"
echo "  FRONTEND_APP_URL=http://$SERVER_NAME"
echo "  CORS_ORIGINS=http://$SERVER_NAME"
