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
nano .env
```

**Required for production** (the backend refuses to start otherwise):

```bash
# strong JWT secret
python3 -c "import secrets;print('JWT_SECRET='+secrets.token_urlsafe(48))"
```
Then in `.env` set:
- `JWT_SECRET=` … (the generated value, ≥ 24 chars)
- `BOOTSTRAP_ADMIN_PASS=` … (strong; not `admin`/`change-me`)
- `MONGO_USER=` / `MONGO_PASS=` … (Mongo runs with auth; pick a strong pass)
- `CORS_ORIGINS=https://<your-host>:8443` (the real URL, not `*`)
- `WLC_HOST/PORT/USERNAME/PASSWORD` and `WLC_VENDOR` (`cisco` or `ruckus`)

## 🔒 Production security checklist
The backend enforces the first two automatically (won't boot in production without them):
- [x] **Strong `JWT_SECRET`** (≥ 24 random chars) — enforced.
- [x] **Non-default `BOOTSTRAP_ADMIN_PASS`** — enforced; you're forced to change it on first login too.
- [x] **MongoDB authentication** — enabled in compose via `MONGO_USER`/`MONGO_PASS`; Mongo is **not published** externally (only the backend reaches it on the internal network).
- [x] **WLC password encrypted at rest** — Fernet (`services/crypto.py`); stored as ciphertext, decrypted only in memory.
- [x] **Login rate-limiting** — 5/min + 30/hr per IP on `/api/auth/login`.
- [x] **Container runs as non-root** (`appuser`, uid 10001).
- [x] **Security headers** — HSTS, CSP, X-Frame-Options DENY, nosniff, Referrer-Policy at nginx.
- [x] **CORS locked** to `CORS_ORIGINS` (set it to your URL).
- [ ] **TLS cert** — replace the self-signed cert with a CA-signed one for client-facing use (drop `server.crt`/`server.key` into `deploy/nginx/certs/`). `WLC_VERIFY_SSL` stays `false` only if your controller uses a self-signed cert you trust.
- [ ] **Back up MongoDB** (`mongo_data` volume) — it holds users, settings, floor-plan maps, and history. e.g. `docker compose exec mongo mongodump --username "$MONGO_USER" --password "$MONGO_PASS" --authenticationDatabase admin --archive` .
- [ ] **Validate against the client's actual controllers** — adapter field names can differ across IOS-XE / SmartZone versions.
- [ ] **Privacy/retention** — the app stores client MACs, hostnames, usernames, IPs. Set the data-retention/cleanup schedule in Settings to match policy.

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

## Scaling

The default single container does everything (web + polling) and suits most sites —
**scale it vertically first** (bigger VM per the sizing table) since the workload is
I/O-bound. When you need to scale the web tier or want background work isolated from
request handling, split into a **web tier** and a **single background worker**:

```bash
docker compose -f docker-compose.yml -f docker-compose.scale.yml up -d --build
```

This sets `backend` to `RUN_WORKERS=false` (web/API only) and adds a `worker`
service (`RUN_WORKERS=true`) that is the sole instance polling the WLC, evaluating
events and running cleanup. Settings edited in the UI propagate to the worker
automatically (a `SettingsWatcher` re-reads MongoDB), so no restart is needed.

- **Keep the worker at one replica** — duplicating it duplicates WLC polling.
- **Scaling the web tier to N replicas** (`--scale backend=3`) additionally needs:
  (1) an nginx `resolver` tweak so it round-robins across replicas, and
  (2) Redis for a shared login rate-limit counter (`RATELIMIT_STORAGE=redis://…`).
  Both are documented at the top of `docker-compose.scale.yml`.

## Notes

- **Single gunicorn worker** is intentional in the all-in-one container — it runs the
  in-process background collector thread and holds the live WLC client; multiple
  workers would poll the WLC in duplicate. Request concurrency is handled by threads.
  To scale, use the web/worker split above rather than raising `--workers`.
- The backend reaches the WLC over the host network; ensure the Docker host can
  route to `WLC_HOST`. (Containers use the default bridge, which can reach the LAN.)
- To change the published port, edit the `nginx` `ports:` mapping in
  `docker-compose.yml` (e.g. `"443:8443"`); the in-container port stays 8443.
- For a CA-signed cert later, drop your `server.crt`/`server.key` into
  `deploy/nginx/certs/` and restart nginx.
