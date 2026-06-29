#!/usr/bin/env bash
# Redeploy GSTRecon on the server (pull latest + rebuild + restart).
# Run from anywhere: bash /opt/GSTRecon/deploy/deploy.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/GSTRecon}"
COMPOSE_FILE="docker-compose.prod.yml"
BRANCH="${BRANCH:-main}"

cd "$APP_DIR"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Missing $APP_DIR/$COMPOSE_FILE" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "Missing $APP_DIR/.env — copy from deploy/.env.example" >&2
  exit 1
fi

if [[ ! -f backend/.env ]]; then
  echo "Missing backend/.env — copy from deploy/backend.env.example" >&2
  exit 1
fi

echo "==> Pulling latest code ($BRANCH)..."
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull origin "$BRANCH"

echo "==> Building and starting containers..."
docker compose -f "$COMPOSE_FILE" build --pull
docker compose -f "$COMPOSE_FILE" up -d

echo "==> Waiting for backend..."
sleep 5
docker compose -f "$COMPOSE_FILE" ps

echo "==> Pruning dangling images..."
docker image prune -f >/dev/null 2>&1 || true

HTTP_PORT="$(grep -E '^HTTP_PORT=' .env 2>/dev/null | cut -d= -f2- || echo 8080)"
if ss -tlnp 2>/dev/null | grep -q ':80 .*nginx' && ! docker compose -f "$COMPOSE_FILE" ps web 2>/dev/null | grep -q 'Up'; then
  echo ""
  echo "NOTE: Host nginx is using port 80. Run: bash deploy/setup-host-nginx.sh"
fi

echo ""
echo "Deploy complete."
echo "  App URL: http://206.189.140.76 (after setup-host-nginx.sh if needed)"
echo "  Docker web listens on 127.0.0.1:${HTTP_PORT:-8080}"
echo "  Logs:    docker compose -f $COMPOSE_FILE logs -f --tail=100"
