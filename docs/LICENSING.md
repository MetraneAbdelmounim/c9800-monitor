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

### Deliver to the client (upload flow)
Give them the issued `license.key`. The app **boots locked** and the client activates it
**in the UI**:
1. The client opens the app and logs in as an **admin**.
2. They're sent to the **Licensing page** (the rest of the app is locked).
3. They **choose the `license.key` file** (or paste the token) and click **Activate**.
4. The token is verified and **stored in MongoDB**; the app unlocks immediately and stays
   licensed across restarts.

Optional automated install: set `LICENSE_KEY=<token>` in `.env` and it auto-activates on
first boot (no manual upload).

### Behaviour
- **Locked until activated**: every `/api/*` call returns `402 license_required` except
  login, the license endpoints, and health — so an admin can sign in and activate, but no
  data loads and settings can't change. The frontend redirects to `/licensing`.
- **Persisted**: stored in Mongo (`settings._id="license"`); re-loaded each startup.
- **Expiry**: enforced live — an expired license re-locks the app. Within 30 days the
  backend logs a renewal warning.
- `LICENSE_ENFORCE=false` disables the lock entirely (internal use).
- Status API: `GET /api/license` (and the `license` field of `GET /api/setup/status`).
- Activate API (admin): `POST /api/license` with `{ "key": "WMLIC1...." }`.

### Renew / revoke
- **Renew**: issue a new `license.key` with a later expiry; the client re-uploads it on the
  Licensing page — it overwrites the stored one, no restart needed.
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