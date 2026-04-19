# Phase 2 — Run Instructions

Step-by-step guide for running, testing, and verifying the Phase 2 backend.
Everything in Phase 1 still works the same way; this doc covers what Phase 2
added.

---

## 0. What Phase 2 added, in one paragraph

The backend now sends real transactional emails (verification, password reset,
invitations) through Resend, or logs them to the console if no Resend key is
configured. There are four new auth endpoints (verify-email, resend-verification,
password-reset/request, password-reset/confirm). Rate limiting is in place on
signup, login, and password-reset. There's a full metric ingestion pipeline:
a Celery worker fetches platform data through a pluggable provider (mock /
Windsor / Supermetrics), a normalization layer maps raw platform fields into
one unified vocabulary, and the data lands in `unified_metrics_cache`. Celery
Beat runs a full sync every day at 3 AM UTC. Three new read APIs expose the
data: list / timeseries / summary. And one new write API lets the frontend
trigger an on-demand sync for a specific client. Plus row-level security is
now active at the Postgres layer as defense-in-depth.

---

## 1. Prerequisites

You should already have from Phase 1:

- Docker Desktop installed and running
- The project folder at:
  `C:\Users\S.PRAVEEN KUMAR\Downloads\Digital Marketing\online-smart-pick-ecosystem\online-smart-pick-ecosystem-phase1\online-smart-pick-ecosystem`
- A working `backend/.env` file with real `JWT_SECRET_KEY` and `ENCRYPTION_KEY`

If your `.env` came from Phase 1, the Phase 2 zip appended the new keys to the
bottom of it already. If you're starting from a clean `.env.example`, copy it
to `.env` and regenerate secrets:

```bash
# In a terminal, in the backend folder:
python -c "import secrets; print(secrets.token_urlsafe(64))"
# → paste the output as JWT_SECRET_KEY

python -c "from cryptography.hazmat.primitives.ciphers.aead import AESGCM; import base64; print(base64.urlsafe_b64encode(AESGCM.generate_key(bit_length=256)).decode())"
# → paste the output as ENCRYPTION_KEY
```

---

## 2. Install the new dependencies

Phase 2 added one Python package: `slowapi` (rate limiting). Everything else is
the same.

If you use Docker (recommended — this is what the rest of the guide assumes),
the next `docker compose build` picks up the new `requirements.txt`
automatically. You don't need to run `pip install` by hand.

If you're running the backend outside Docker:

```bash
cd backend
pip install -r requirements.txt
```

---

## 3. Start everything

```bash
# from the project root (the folder that has docker-compose.yml)
docker compose down         # stop any Phase 1 containers still running
docker compose build        # rebuild image with slowapi
docker compose up -d        # start all 5 services in the background
```

You should see **5 containers** running now (Phase 1 had 3):

```bash
docker compose ps
```

Expected:

| Service            | Role                                  |
| ------------------ | ------------------------------------- |
| smartpick_postgres | PostgreSQL 16                         |
| smartpick_redis    | Redis 7                               |
| smartpick_backend  | FastAPI app (port 8000)               |
| smartpick_worker   | Celery worker (runs sync tasks)       |
| smartpick_beat     | Celery Beat (schedules the nightly sync) |

Tail logs for each in its own terminal:

```bash
docker compose logs -f backend
docker compose logs -f worker
docker compose logs -f beat
```

---

## 4. Apply the database schema

The Phase 2 build did NOT add a new Alembic migration (the Phase 1 schema
already has every column Phase 2 needs). So this is just making sure Phase 1's
migration is applied:

```bash
docker compose exec backend alembic upgrade head
```

Expected output ends with:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, initial schema
```

If it says "Already at head" — you're fine, schema is current.

---

## 5. Confirm the app is healthy

```bash
curl http://localhost:8000/
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/health/db
```

All three should return JSON with `"status": "ok"`.

Open the Swagger docs in your browser: http://localhost:8000/docs
You should see the new `auth` verify/reset endpoints, plus `metrics`
and `data-sync` tags.

---

## 6. Test the new auth endpoints with curl

> **Windows note:** On Windows, use PowerShell (not CMD) and prefer
> double-quotes around JSON bodies, escaping inner quotes with a backslash.
> Or install `curl.exe` from Git Bash and use regular Unix-style quoting.

### 6.1 Sign up (this will now also send a verification email)

```bash
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "agency_name":"Praveen Test Agency",
    "full_name":"Praveen Kumar",
    "email":"praveen.test@example.com",
    "password":"TestPass123"
  }'
```

You get back `{access_token, refresh_token, user, ...}`. **Check the
backend logs** — you'll see the verification email logged in console mode:

```
docker compose logs backend | grep "EMAIL"
```

Copy the token from inside the `verify-email?token=...` link in the logged
email. You'll use it in the next step.

### 6.2 Verify the email

```bash
curl -X POST http://localhost:8000/api/v1/auth/verify-email \
  -H "Content-Type: application/json" \
  -d '{"token":"PASTE_TOKEN_HERE"}'
```

Response: `{"message": "Email verified successfully."}`

Calling `/auth/me` with your access token now returns
`"is_email_verified": true`.

### 6.3 Resend the verification email (auth required)

```bash
curl -X POST http://localhost:8000/api/v1/auth/resend-verification \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

If the email is already verified, you get `400 Email is already verified.`

### 6.4 Password reset — request

```bash
curl -X POST http://localhost:8000/api/v1/auth/password-reset/request \
  -H "Content-Type: application/json" \
  -d '{"email":"praveen.test@example.com"}'
```

Always returns success, even for unknown emails (anti-enumeration). Check the
logs again to grab the reset token from the email.

### 6.5 Password reset — confirm

```bash
curl -X POST http://localhost:8000/api/v1/auth/password-reset/confirm \
  -H "Content-Type: application/json" \
  -d '{"token":"PASTE_RESET_TOKEN","new_password":"NewPass123"}'
```

Response: `{"message": "Password updated. Please log in with your new password."}`

Now try `/auth/login` with the new password — it works, and the old password
doesn't.

### 6.6 Rate limiting — try to trip it

Repeat `/auth/login` 11 times in a minute:

```bash
for i in {1..11}; do
  curl -X POST http://localhost:8000/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"wrong@example.com","password":"wrong"}' \
    -w " → HTTP %{http_code}\n"
done
```

The 11th call should return HTTP 429 "Too Many Requests". That's slowapi
blocking a brute-force attempt.

---

## 7. Test the metric pipeline end-to-end

This is the big Phase 2 milestone.

### 7.1 Log in and save your access token

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"praveen.test@example.com","password":"NewPass123"}'
```

Copy the `access_token` from the response.

### 7.2 Create a client

```bash
curl -X POST http://localhost:8000/api/v1/clients \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Sarah Boutique","industry":"Retail"}'
```

Save the returned `id` — this is your `CLIENT_ID`.

### 7.3 Connect two platforms for that client

```bash
# Meta Ads
curl -X POST http://localhost:8000/api/v1/clients/CLIENT_ID/connections \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "platform_type":"meta_ads",
    "account_name":"Sarah Boutique Meta",
    "credentials":{"access_token":"fake-token-meta","ad_account_id":"act_123"}
  }'

# Google Ads
curl -X POST http://localhost:8000/api/v1/clients/CLIENT_ID/connections \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "platform_type":"google_ads",
    "account_name":"Sarah Boutique Google",
    "credentials":{"developer_token":"fake-token-gads","customer_id":"123-456-7890"}
  }'
```

Because `DATA_PROVIDER=mock` in your `.env`, these fake credentials are fine.
The mock provider ignores them.

### 7.4 Trigger a sync

```bash
curl -X POST http://localhost:8000/api/v1/data/sync/CLIENT_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response: `{"client_id": "...", "task_id": "abc-123", "status": "queued", ...}`

### 7.5 Watch the worker process the task

In another terminal:

```bash
docker compose logs -f worker
```

Within a few seconds you should see:

```
[sync_client_metrics] client=... window=2026-03-19→2026-04-18 lookback=30
[sync_client_metrics] connection ... platform=meta_ads rows_written=372
[sync_client_metrics] connection ... platform=google_ads rows_written=434
```

Numbers vary because each platform produces different metrics, but you should
see **hundreds of rows per connection** (2 campaigns × 30 days × many
metrics per row).

### 7.6 Verify the data actually landed

```bash
docker compose exec postgres psql -U smartpick -d smartpick_db -c \
  "SELECT platform_type, metric_name, COUNT(*) FROM unified_metrics_cache GROUP BY 1,2 ORDER BY 1,2;"
```

You should see a table like:

```
 platform_type | metric_name      | count
---------------+------------------+-------
 google_ads    | clicks           |    60
 google_ads    | conversions      |    60
 google_ads    | cost_per_click   |    60
 google_ads    | ctr              |    60
 google_ads    | impressions      |    60
 google_ads    | revenue_usd      |    60
 google_ads    | spend_usd        |    60
 meta_ads      | clicks           |    60
 meta_ads      | conversions      |    60
 meta_ads      | ctr              |    60
 meta_ads      | cost_per_click   |    60
 meta_ads      | engagements      |    60
 meta_ads      | impressions      |    60
 meta_ads      | reach            |    60
 meta_ads      | revenue_usd      |    60
 meta_ads      | spend_usd        |    60
```

60 = 2 campaigns × 30 days. **That's proof the full pipeline works**:
raw rows from the mock provider → normalization layer → unified_metrics_cache.

### 7.7 Query the data through the API

```bash
# All Meta Ads impressions for this client
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8000/api/v1/clients/CLIENT_ID/metrics?platform=meta_ads&metric_name=impressions"

# Daily spend_usd across all platforms (chart-ready)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8000/api/v1/clients/CLIENT_ID/metrics/timeseries?metric_name=spend_usd"

# High-level summary for dashboard cards
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8000/api/v1/clients/CLIENT_ID/metrics/summary"
```

---

## 8. Verify the nightly schedule is registered

```bash
docker compose exec beat celery -A app.workers.celery_app inspect scheduled
# or check beat's own log:
docker compose logs beat | grep -i "nightly-sync"
```

You should see the `nightly-sync-all-clients` entry pointing at 3:00 UTC.

To simulate the nightly run without waiting 24 hours, invoke the task
directly:

```bash
docker compose exec worker celery -A app.workers.celery_app call app.workers.sync_tasks.sync_all_clients
```

This fans out to every active client and runs a sync for each.

---

## 9. Switch to the real Resend provider (optional)

When you're ready to send real emails:

1. Sign up at https://resend.com (free tier is 3,000 emails/month).
2. Verify a sending domain — for dev, use their onboarding domain
   `onboarding@resend.dev`.
3. Copy your API key (starts with `re_`).
4. Edit `backend/.env`:
   ```
   RESEND_API_KEY=re_your_real_key
   EMAIL_FROM_ADDRESS=onboarding@resend.dev
   ```
5. Restart the backend:
   ```bash
   docker compose restart backend
   ```

From that point on, verification and password-reset emails go through Resend
instead of the console. Nothing else changes.

---

## 10. Troubleshooting

**`docker compose up` hangs on "Waiting for postgres"**
The postgres health check needs a few seconds on first boot. Give it 30 seconds.

**`slowapi` errors about "no Request parameter"**
If you added a new `@limiter.limit(...)` route, the route function MUST have
`request: Request` as its first (or any positional) parameter. Without it,
slowapi can't read the client IP and the decorator throws.

**Worker logs "NotImplementedError" and marks connections ERROR**
You have `DATA_PROVIDER=windsor` or `supermetrics` in your `.env`, but those
providers are Phase 3. Switch back to `DATA_PROVIDER=mock` and restart:
```bash
docker compose restart worker beat backend
```

**`ENCRYPTION_KEY must decode to exactly 32 bytes`**
Your key isn't valid base64 or isn't the right length. Regenerate with:
```bash
python -c "from cryptography.hazmat.primitives.ciphers.aead import AESGCM; import base64; print(base64.urlsafe_b64encode(AESGCM.generate_key(bit_length=256)).decode())"
```

**Email not appearing in logs**
Check you're tailing backend logs, not worker. Email sending happens inside
the FastAPI app, not the Celery worker.
```bash
docker compose logs backend | grep "📧"
```

**"relation unified_metrics_cache does not exist"**
You skipped `alembic upgrade head`. Run step 4.
