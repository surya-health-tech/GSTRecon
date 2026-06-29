# Deploying GSTRecon on DigitalOcean

Production path: **`/opt/GSTRecon`**

Repository: [github.com/surya-health-tech/GSTRecon](https://github.com/surya-health-tech/GSTRecon)

## Shared server (PracticeFlow, InvoiceAI, etc.)

This server already runs **other apps on port 80**. GSTRecon must **not** take over `default_server` or remove `/etc/nginx/sites-enabled/default`.

Choose **one** access method:

### Option A — Dedicated port (simplest, no DNS)

Best when all apps share **`206.189.140.76`** and each uses its own port.

In `/opt/GSTRecon/.env`:

```env
HTTP_PORT=8092
WEB_BIND=0.0.0.0
```

In `/opt/GSTRecon/backend/.env`:

```env
FRONTEND_APP_URL=http://206.189.140.76:8092
CORS_ORIGINS=http://206.189.140.76:8092
```

Deploy:

```bash
bash /opt/GSTRecon/deploy/deploy.sh
```

Open: **http://206.189.140.76:8092/login**

Ensure DigitalOcean firewall allows **TCP 8092**. Port **8080** is often already used by other apps on this server.

### Option B — Subdomain on port 80 (recommended with DNS)

Best when you can add DNS e.g. `gstrecon.yourdomain.com` → `206.189.140.76`.

In `/opt/GSTRecon/.env`:

```env
HTTP_PORT=8080
WEB_BIND=127.0.0.1
SERVER_NAME=gstrecon.yourdomain.com
```

In `backend/.env`:

```env
FRONTEND_APP_URL=http://gstrecon.yourdomain.com
CORS_ORIGINS=http://gstrecon.yourdomain.com
```

```bash
bash /opt/GSTRecon/deploy/deploy.sh
SERVER_NAME=gstrecon.yourdomain.com bash /opt/GSTRecon/deploy/setup-host-nginx.sh
```

Open: **http://gstrecon.yourdomain.com/login**

Host nginx adds a **new** site only; PracticeFlow and InvoiceAI configs are untouched.

---

## Architecture

| Service | Role |
|---------|------|
| **web** | Nginx in Docker — React build + `/api` proxy |
| **backend** | FastAPI — migrations on start, uploads in volume |
| **db** | PostgreSQL 16 |

Docker web listens on **`WEB_BIND:HTTP_PORT`** (default `127.0.0.1:8080` or `0.0.0.0:8080`).

## First-time server setup

```bash
git clone https://github.com/surya-health-tech/GSTRecon.git /opt/GSTRecon
cd /opt/GSTRecon
bash deploy/bootstrap.sh
```

Edit `/opt/GSTRecon/.env` and `backend/.env`, then:

```bash
bash deploy/deploy.sh
```

## Redeploy

```bash
git push origin main          # from your PC
bash /opt/GSTRecon/deploy/deploy.sh   # on server
```

## Useful commands

```bash
cd /opt/GSTRecon
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f web backend
```

## HTTPS

Add a cert for your GSTRecon subdomain (Certbot on host nginx). Update `FRONTEND_APP_URL` and `CORS_ORIGINS` to `https://...`.

Do **not** commit `.env` or `backend/.env` to git.
