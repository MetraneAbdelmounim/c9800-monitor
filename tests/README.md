# Load testing (Locust)

Run from **your local machine**, pointing at the **deployed server**. Keeping the
load generator off the server gives accurate numbers (it doesn't compete for CPU).

## 1. Install (once)
```powershell
pip install locust
```

## 2. Point it at your server + credentials
```powershell
$env:TARGET="https://SERVER_IP:8443"
$env:WM_USER="admin"
$env:WM_PASS="your-password"
```

## 3. Run with the live web UI
```powershell
locust -f tests\locustfile.py
```
Open **http://localhost:8089**, enter the **number of users** (e.g. 200) and
**spawn rate** (e.g. 10/s), and start. Watch requests/sec, response times and
failures live. Stop, then check the **Charts** tab for p50/p95/p99.

## Headless (no UI, for a scripted run)
```powershell
locust -f tests\locustfile.py --headless -u 100 -r 10 -t 2m
```
`-u` users, `-r` spawn rate, `-t` duration.

## Reading the results
- **Failures > 0 / timeouts** → past capacity for the current config.
- **p95 latency climbs while server CPU is low** (`docker stats` on the server) →
  the **WLC controller** is the bottleneck (read endpoints query it live), not the app.

## Tuning levers if you hit a ceiling
1. More gunicorn threads (Dockerfile `--threads`).
2. Web/worker split: `docker-compose.scale.yml`.
3. Serve dashboard/AP/client reads from MongoDB snapshots instead of live WLC calls.

> Note: the test logs in **once** and reuses the token on purpose — the server
> rate-limits `/api/auth/login` to 5/min per IP, so per-user logins would just
> return HTTP 429.