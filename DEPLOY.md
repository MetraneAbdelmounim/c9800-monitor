# Deploying C9800 Monitor (Docker · Ubuntu)

Three containers via Docker Compose:

```
        :8443 (HTTPS, self-signed)
browser ───────────────▶  nginx  ──▶  backend (gunicorn + Flask)  ──▶  mongo
                                       └ serves the built Angular SPA
```

- **nginx** terminates TLS on **8443** and reverse-proxies everything to the backend.
- **backend** (gunicorn/Flask) serves both the JSON API *and* the compiled Angular app — the frontend is built **into** the backend image (multi-stage build).
- The SPA uses **hash routing** (`/#/dashboard`) and **hashed asset filenames** (cache-busting), so no nginx rewrite rules are needed.
- **mongo** persists users, settings, tracking history, and floor-plan maps.

## Prerequisites (Ubuntu)

```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin openssl
sudo usermod -aG docker "$USER"   # log out/in afterwards
```

## 1. Configure

```bash
cp .env.example .env
nano .env          # set JWT_SECRET, BOOTSTRAP_ADMIN_PASS, WLC_* …
```

## 2. Generate the self-signed certificate

Pass the server's hostname or IP so the cert's SAN matches the URL you'll use:

```bash
chmod +x deploy/gen-cert.sh
./deploy/gen-cert.sh 192.168.100.50      # or your DNS name, e.g. wifi.asb.ma
```

Writes `deploy/nginx/certs/server.{crt,key}`.

## 3. Build & run

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f backend     # watch first-run bootstrap
```

Open **https://<server>:8443/** — accept the self-signed warning, then log in with
`BOOTSTRAP_ADMIN_USER` / `BOOTSTRAP_ADMIN_PASS` (you'll be forced to change the password).

## Operations

| Task | Command |
|------|---------|
| Update after code changes | `docker compose up -d --build` |
| Stop | `docker compose down` |
| Stop **and wipe data** | `docker compose down -v` |
| Backend logs | `docker compose logs -f backend` |
| Mongo shell | `docker compose exec mongo mongosh c9800_monitor` |
| Rotate cert | re-run `gen-cert.sh`, then `docker compose restart nginx` |

## Notes

- **Single gunicorn worker** is intentional — the app runs an in-process background
  collector thread and holds the live RESTCONF client; multiple workers would poll
  the WLC in duplicate. Request concurrency is handled by threads.
- The backend reaches the WLC over the host network; ensure the Docker host can
  route to `WLC_HOST`. (Containers use the default bridge, which can reach the LAN.)
- To change the published port, edit the `nginx` `ports:` mapping in
  `docker-compose.yml` (e.g. `"443:8443"`); the in-container port stays 8443.
- For a CA-signed cert later, drop your `server.crt`/`server.key` into
  `deploy/nginx/certs/` and restart nginx.
