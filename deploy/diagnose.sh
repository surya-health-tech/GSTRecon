#!/usr/bin/env bash
# Quick health check for GSTRecon on a shared server.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/GSTRecon}"
cd "$APP_DIR"

echo "=== GSTRecon diagnose ==="
echo ""

if [[ -f .env ]]; then
  echo "--- /opt/GSTRecon/.env ---"
  grep -E '^(HTTP_PORT|WEB_BIND|POSTGRES_)' .env 2>/dev/null || true
  echo ""
fi

if [[ -f backend/.env ]]; then
  echo "--- backend/.env (public URLs) ---"
  grep -E '^(FRONTEND_APP_URL|CORS_ORIGINS)=' backend/.env 2>/dev/null || true
  echo ""
fi

echo "--- Docker containers ---"
docker compose -f docker-compose.prod.yml ps 2>/dev/null || echo "compose not running"
echo ""

echo "--- Listening ports (80, 8080-8099) ---"
ss -tlnp 2>/dev/null | grep -E ':80 |:808[0-9]|:809[0-9]' || echo "(none matched)"
echo ""

HTTP_PORT="$(grep -E '^HTTP_PORT=' .env 2>/dev/null | cut -d= -f2- | tr -d '\r' || echo 8092)"
WEB_BIND="$(grep -E '^WEB_BIND=' .env 2>/dev/null | cut -d= -f2- | tr -d '\r' || echo 0.0.0.0)"

if docker compose -f docker-compose.prod.yml ps web 2>/dev/null | grep -q 'Up'; then
  echo "OK: gstrecon-web is running"
  if [[ "$WEB_BIND" == "0.0.0.0" ]]; then
    echo "Try: http://206.189.140.76:${HTTP_PORT}/login"
  else
    echo "WEB_BIND=$WEB_BIND — not public. Set WEB_BIND=0.0.0.0 or use setup-host-nginx.sh"
  fi
else
  echo "PROBLEM: gstrecon-web is NOT running"
  echo "Common fix:"
  echo "  1. Pick a free port: ss -tlnp | grep 809"
  echo "  2. nano .env  → HTTP_PORT=8092  WEB_BIND=0.0.0.0"
  echo "  3. nano backend/.env → FRONTEND_APP_URL=http://206.189.140.76:8092"
  echo "  4. bash deploy/deploy.sh"
  echo "  5. ufw allow 8092/tcp  (if ufw enabled)"
fi
