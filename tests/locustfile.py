"""
WireMetry load test — run on YOUR LOCAL machine, target the deployed server.

Models real dashboard usage: each simulated user polls a few read endpoints with
think-time (not a tight loop). Logs in ONCE and shares the token, so the per-IP
login rate limit (5/min) doesn't turn the test into a wall of HTTP 429s.

Setup (Windows PowerShell):
    pip install locust
    $env:TARGET="https://SERVER_IP:8443"
    $env:WM_USER="admin"
    $env:WM_PASS="your-password"
    locust -f tests\locustfile.py

Then open http://localhost:8089, set the number of users + spawn rate, and watch
the live charts. Headless example (no UI):
    locust -f tests\locustfile.py --headless -u 100 -r 10 -t 2m
"""
import os
import requests
import urllib3
from locust import HttpUser, task, between

urllib3.disable_warnings()  # self-signed cert on the server

TARGET = os.getenv("TARGET", "https://127.0.0.1:8443").rstrip("/")
USER = os.getenv("WM_USER", "admin")
PASS = os.getenv("WM_PASS", "changeme")

# One login at startup → shared bearer token (avoids the login rate limit).
_r = requests.post(f"{TARGET}/api/auth/login",
                   json={"username": USER, "password": PASS},
                   verify=False, timeout=10)
if _r.status_code != 200:
    raise SystemExit(f"Login failed ({_r.status_code}): {_r.text}\n"
                     f"Check TARGET / WM_USER / WM_PASS and that the server is reachable.")
TOKEN = _r.json()["token"]
print(f"[loadtest] authenticated against {TARGET} as '{USER}' — token acquired")


class MonitorUser(HttpUser):
    host = TARGET
    wait_time = between(3, 7)  # think-time: a real dashboard refreshes every few seconds

    def on_start(self):
        self.client.verify = False
        self.client.headers.update({"Authorization": f"Bearer {TOKEN}"})

    # weights ≈ how often each endpoint is hit relative to the others
    @task(3)
    def dashboard(self):
        self.client.get("/api/dashboard", name="GET /api/dashboard")

    @task(2)
    def access_points(self):
        self.client.get("/api/aps?page=1&per_page=50", name="GET /api/aps")

    @task(2)
    def clients(self):
        self.client.get("/api/clients", name="GET /api/clients")

    @task(1)
    def health(self):
        self.client.get("/api/health", name="GET /api/health")