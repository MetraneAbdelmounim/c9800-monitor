# Licensing & Code Protection

WireMetry ships as a **bytecode-only** Docker image (no Python source) and requires a
**signed license** to run in production. Together these deter casual code theft and let
you sell time-limited / per-customer deployments.

> Reality check: no client-side scheme is unbreakable. This raises the bar significantly;
> the enforceable protection for a sale is still the **license agreement / contract**.

---

## 1. Code protection (bytecode)

The image is built in stages (`Dockerfile`):
1. a stage compiles the backend to `.pyc` and **deletes every `.py`**;
2. the runtime stage copies **only** the compiled bytecode.

Because the strip happens in a separate stage, the source never exists in a layer of the
final image — so `docker history` / layer extraction can't recover it. Verify after a build:

```bash
docker compose exec backend sh -c "find . -name '*.py' | head"   # → (empty)
docker compose exec backend sh -c "find . -name '*.pyc' | wc -l" # → many
```

> The `.pyc` magic number is tied to the interpreter, so the compile and runtime stages
> both use `python:3.12-slim`. Don't change one without the other.

---

## 2. The license system

Ed25519-signed token. The **public key is embedded** in the app
(`backend/services/licensing.py`); the **private signing key stays with you**
(`tools/license_private_key.pem`, git-ignored, never shipped).

A license carries: `customer`, `issued`, `expires`, `edition`, and an optional
`machine_id` binding. The app verifies signature + expiry (+ machine, if set) at startup.

### Issue a license (vendor side)
```bash
# 1 year from today
python tools/gen_license.py --customer "American School of Benguerir" --days 365 --out license.key

# explicit date + bind to one machine
python tools/gen_license.py --customer "ACME" --expires 2027-12-31 \
       --machine-id "$(cat /etc/machine-id)" --out acme.key
```
The first run auto-creates the keypair. **Back up `tools/license_private_key.pem`** — if you
lose it you can't issue licenses that existing builds accept (you'd have to re-key + rebuild).

### Deliver to the client
Give them the issued `license.key`. They provide it one of two ways:
- **Mount it** (default): place it next to `docker-compose.yml`; it's mounted read-only to
  `/app/license.key`. Already wired in `docker-compose.yml`.
- **Env var**: set `LICENSE_KEY=<token>` in `.env`.

### Behaviour
- **Production** (`FLASK_DEBUG=false`): a missing/invalid/expired license **stops startup**
  with a clear log message. (`LICENSE_ENFORCE` defaults to on in production.)
- **Dev** (`FLASK_DEBUG=true`): it's a warning only, so local work isn't blocked.
- Override anytime with `LICENSE_ENFORCE=true|false`.
- Within 30 days of expiry the backend logs a renewal warning. License status is also
  returned by `GET /api/setup/status` (`license` field) for a future GUI badge.

### Renew / revoke
- **Renew**: issue a new `license.key` with a later expiry; client swaps the file and
  restarts. (No rebuild needed.)
- **Revoke**: licenses are offline-verified, so there's no live kill switch — use a short
  expiry (e.g. 12 months) and machine-binding for control. Re-keying (new keypair + rebuilt
  image) invalidates all old licenses if needed.

### Machine binding (optional)
If a license has a `machine_id`, the app compares it to this host's fingerprint —
`LICENSE_MACHINE_ID` env if set, else `/etc/machine-id`. To bind in Docker, set
`LICENSE_MACHINE_ID` on the service and issue the license with that same value.

---

## Files
| File | Role | Ship to client? |
|---|---|---|
| `backend/services/licensing.py` | verifier (public key embedded) | yes (as bytecode) |
| `tools/gen_license.py` | license generator | **no** |
| `tools/license_private_key.pem` | signing key | **NO — secret** |
| `license.key` | an issued license | yes (their own) |