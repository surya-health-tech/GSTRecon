#!/usr/bin/env bash
# Reset platform admin password from backend/.env (one-time fix).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/GSTRecon}"
cd "$APP_DIR"

if [[ ! -f backend/.env ]]; then
  echo "Missing backend/.env" >&2
  exit 1
fi

echo "Resetting platform admin password from backend/.env ..."
docker compose -f docker-compose.prod.yml exec \
  -e FORCE_RESET_PLATFORM_ADMIN_PASSWORD=true \
  backend python -m app.scripts.seed_platform_admin

echo ""
grep '^PLATFORM_ADMIN_EMAIL=' backend/.env || true
echo "Password reset to value of PLATFORM_ADMIN_PASSWORD in backend/.env"
echo "Sign in at: http://206.189.140.76:8092/login"
