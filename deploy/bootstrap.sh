#!/usr/bin/env bash
# First-time setup on Ubuntu/Debian DigitalOcean droplet.
# Run as root: bash deploy/bootstrap.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/GSTRecon}"
REPO_URL="${REPO_URL:-https://github.com/surya-health-tech/GSTRecon.git}"
BRANCH="${BRANCH:-main}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker..."
  apt-get update
  apt-get install -y ca-certificates curl git
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "${VERSION_CODENAME:-$VERSION_ID}") stable" \
    | tee /etc/apt/sources.list.d/docker.list >/dev/null
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi

mkdir -p "$(dirname "$APP_DIR")"
if [[ ! -d "$APP_DIR/.git" ]]; then
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
else
  echo "Repository already exists at $APP_DIR"
fi

cd "$APP_DIR"

if [[ ! -f .env ]]; then
  cp deploy/.env.example .env
  echo "Created $APP_DIR/.env — edit POSTGRES_PASSWORD before starting."
fi

if [[ ! -f backend/.env ]]; then
  cp deploy/backend.env.example backend/.env
  echo "Created backend/.env — set JWT_SECRET_KEY, FRONTEND_APP_URL, and admin credentials."
fi

echo ""
echo "Bootstrap complete."
echo "  1. Edit $APP_DIR/.env (database password)"
echo "  2. Edit $APP_DIR/backend/.env (JWT, public URL, admin)"
echo "  3. Run: cd $APP_DIR && bash deploy/deploy.sh"
