# Deploying GSTRecon on DigitalOcean

Production path: **`/opt/GSTRecon`**

Repository: [github.com/surya-health-tech/GSTRecon](https://github.com/surya-health-tech/GSTRecon)

## Architecture

| Service | Role |
|---------|------|
| **web** | Nginx — serves React build, proxies `/api` to backend |
| **backend** | FastAPI — runs migrations on start, stores uploads in Docker volume |
| **db** | PostgreSQL 16 — data in Docker volume `gst_pg` |

Default public port: **80** (configurable via `.env` → `HTTP_PORT`).

## First-time server setup

SSH into the droplet as root (or sudo user with Docker access):

```bash
git clone https://github.com/surya-health-tech/GSTRecon.git /opt/GSTRecon
cd /opt/GSTRecon
bash deploy/bootstrap.sh
```

Or if Docker is not installed yet, `bootstrap.sh` installs Docker and clones the repo.

### Configure secrets

**`/opt/GSTRecon/.env`** (compose / database):

```bash
cp deploy/.env.example .env
nano .env
```

Set at minimum:

- `POSTGRES_PASSWORD` — strong random password

**`/opt/GSTRecon/backend/.env`** (application):

```bash
cp deploy/backend.env.example backend/.env
nano backend/.env
```

Set at minimum:

- `JWT_SECRET_KEY` — e.g. `openssl rand -hex 32`
- `FRONTEND_APP_URL` — `http://206.189.140.76` (or your domain when using HTTPS)
- `CORS_ORIGINS` — `http://206.189.140.76`
- `PLATFORM_ADMIN_EMAIL` / `PLATFORM_ADMIN_PASSWORD` — first login only; password is **not** reset on redeploy

### Start

```bash
cd /opt/GSTRecon
bash deploy/deploy.sh
```

Open `FRONTEND_APP_URL` in a browser and sign in as platform admin.

## Redeploy (after code changes)

From your laptop, push to GitHub:

```bash
git push origin main
```

On the server:

```bash
bash /opt/GSTRecon/deploy/deploy.sh
```

This pulls `main`, rebuilds images, runs migrations, and restarts containers. Database and upload volumes are preserved.

## Useful commands

```bash
cd /opt/GSTRecon

# Status
docker compose -f docker-compose.prod.yml ps

# Logs
docker compose -f docker-compose.prod.yml logs -f web backend

# Stop
docker compose -f docker-compose.prod.yml down

# Reset platform admin password (one-time)
# Add to backend/.env: FORCE_RESET_PLATFORM_ADMIN_PASSWORD=true
# Redeploy, then remove that line.
```

## HTTPS (optional)

Point a domain A record to the droplet, then terminate TLS with:

- **Certbot** on the host proxying to `HTTP_PORT`, or
- A load balancer / Cloudflare in front of port 80

Update `FRONTEND_APP_URL` and `CORS_ORIGINS` to `https://your-domain`.

## Local development vs production

| | Development | Production |
|---|-------------|------------|
| Compose file | `docker-compose.yml` | `docker-compose.prod.yml` |
| Frontend | Vite dev server :5175 | Nginx static build :80 |
| API | :8002 | proxied at `/api` |

Do **not** commit `.env` or `backend/.env` to git.
