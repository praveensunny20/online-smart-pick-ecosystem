# Online Smart Pick Ecosystem

Multi-tenant SaaS marketing intelligence platform. Phase 1 delivers the foundation: authentication, client management, platform-connection scaffolding, row-level security, and Docker-based local development.

**Stack:** FastAPI (Python 3.12) · PostgreSQL 16 · Redis 7 · Next.js 15 · TypeScript · Tailwind CSS.

---

## What's in Phase 1

- Complete monorepo (`backend/` + `frontend/`)
- PostgreSQL schema with 7 tables + row-level security policies
- AES-256-GCM encryption for platform credentials at rest
- JWT authentication (access + refresh tokens)
- Agency signup, login, token refresh, team invites
- Full client CRUD (create, read, update, delete) scoped to agency
- Platform-connection CRUD with encrypted credential storage
- Docker Compose development environment
- Next.js 15 frontend with login, signup, and client-management dashboard

---

## Prerequisites (Windows)

Install these **once**:

### 1. Docker Desktop
Download from <https://www.docker.com/products/docker-desktop/>. After install, open it and wait for the whale icon in your system tray to be solid (not animating). Docker Desktop includes `docker` and `docker compose`.

> **WSL 2 note:** Docker Desktop on Windows runs through WSL 2. If the installer prompts you to "Install WSL", click through — it's required.

### 2. Python 3.12
Download from <https://www.python.org/downloads/>. On the first installer screen, **check the box "Add python.exe to PATH"** before clicking "Install Now".

Verify in a new PowerShell or Command Prompt window:
```powershell
python --version
```
You should see `Python 3.12.x`.

### 3. Node.js 20 LTS
Download from <https://nodejs.org/en/download> and install with default options.

Verify:
```powershell
node --version
npm --version
```
You should see `v20.x.x` and an npm version.

### 4. Git (optional but recommended)
Download from <https://git-scm.com/download/win>.

---

## First-time setup (copy-paste, step by step)

Open **PowerShell** (search for "PowerShell" in the Start menu). The commands below assume you unzipped the project to `C:\Users\YourName\online-smart-pick-ecosystem`. Adjust that path if yours is different.

### Step 1 — Enter the project folder

```powershell
cd C:\Users\YourName\online-smart-pick-ecosystem
```

### Step 2 — Create Python virtual environment and generate secrets

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
python -m scripts.generate_secrets
```

You'll see output like this:

```
======================================================================
  GENERATED SECRETS — copy these into backend/.env
======================================================================

JWT_SECRET_KEY=xYz...very-long-string...
ENCRYPTION_KEY=aBc...44-char-base64...
```

**Keep this window open** — you'll paste these values in the next step.

### Step 3 — Create the `.env` file

Still inside `backend\`, copy the example file:

```powershell
copy .env.example .env
```

Open `backend\.env` in Notepad (or any editor):

```powershell
notepad .env
```

Find these two lines and replace their values with what Step 2 printed:

```env
JWT_SECRET_KEY=CHANGE_ME_TO_A_RANDOM_64_CHAR_STRING_USE_SECRETS_MODULE
ENCRYPTION_KEY=CHANGE_ME_TO_A_FERNET_KEY_44_CHAR_BASE64
```

So they look like:

```env
JWT_SECRET_KEY=xYz...very-long-string...
ENCRYPTION_KEY=aBc...44-char-base64...
```

Save and close Notepad.

> ⚠️ **Important:** Never share these values or commit them to git. If you lose `ENCRYPTION_KEY`, all encrypted platform credentials become unrecoverable.

### Step 4 — Go back to the project root and start Docker services

```powershell
cd ..
docker compose up --build -d
```

This downloads Postgres 16, Redis 7, and builds the backend image. First run takes 2–5 minutes. When it finishes, you'll see three containers: `smartpick_postgres`, `smartpick_redis`, `smartpick_backend`.

Verify all three are healthy:

```powershell
docker compose ps
```

All three should show `running` (backend shows `healthy` after ~15 seconds).

### Step 5 — Run the database migration

```powershell
docker compose exec backend alembic upgrade head
```

Expected output: `Running upgrade  -> 20260418_0001, Initial schema - all tables + row-level security`.

### Step 6 — Seed the database with sample data

```powershell
docker compose exec backend python -m scripts.init_db
```

Expected output includes:

```
  Login email:    admin@onlinesmartpick.com
  Login password: ChangeMe123!
```

### Step 7 — Verify the backend

Open <http://localhost:8000/docs> in your browser. You should see the FastAPI interactive Swagger UI with endpoints for `auth`, `clients`, `platform-connections`, and `health`.

Quick sanity check: <http://localhost:8000/api/v1/health> should return `{"status":"ok","app":"Online Smart Pick Ecosystem","env":"development"}`.

### Step 8 — Install and start the frontend

Open a **new** PowerShell window (keep the backend running in the first one).

```powershell
cd C:\Users\YourName\online-smart-pick-ecosystem\frontend
copy .env.local.example .env.local
npm install
npm run dev
```

The first `npm install` takes 1–3 minutes. When done, `npm run dev` prints:

```
 ▲ Next.js 15.0.3
 - Local:        http://localhost:3000
```

### Step 9 — Log in

Open <http://localhost:3000> in your browser. You'll be redirected to `/login`. Sign in with the seed credentials:

- Email: `admin@onlinesmartpick.com`
- Password: `ChangeMe123!`

You should land on the dashboard and see two sample clients (Acme Corp, Sarah's Boutique). Try adding a new client using the **+ Add client** button.

🎉 **Phase 1 is working!**

---

## Daily workflow (after first-time setup)

Start everything:

```powershell
cd C:\Users\YourName\online-smart-pick-ecosystem
docker compose up -d
cd frontend
npm run dev
```

Stop everything:

```powershell
# In the frontend window — press Ctrl+C
# Then, in the project root:
docker compose down
```

> `docker compose down` keeps your database. `docker compose down -v` **wipes it**.

---

## Useful commands

| Task | Command |
|------|---------|
| View backend logs | `docker compose logs -f backend` |
| View Postgres logs | `docker compose logs -f postgres` |
| Restart backend only | `docker compose restart backend` |
| Rebuild backend after code change | `docker compose up --build -d backend` |
| Open a Postgres shell | `docker compose exec postgres psql -U smartpick -d smartpick_db` |
| Run a new migration | `docker compose exec backend alembic revision --autogenerate -m "message"` |
| Re-seed database | `docker compose exec backend python -m scripts.init_db` |
| Frontend type-check | `cd frontend && npm run type-check` |
| Frontend production build | `cd frontend && npm run build` |

---

## Project structure

```
online-smart-pick-ecosystem/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI route handlers (auth, clients, connections, health)
│   │   ├── core/          # config, security (JWT/bcrypt), encryption (AES-256-GCM)
│   │   ├── db/            # Async SQLAlchemy engine + session
│   │   ├── models/        # ORM models (7 tables)
│   │   ├── schemas/       # Pydantic request/response schemas
│   │   ├── services/      # Business logic (auth_service, client_service, connection_service)
│   │   ├── utils/         # Helpers (slug, password generators)
│   │   └── main.py        # FastAPI app entry point
│   ├── alembic/           # Database migrations (RLS included)
│   ├── scripts/
│   │   ├── generate_secrets.py    # One-off: creates JWT + encryption keys
│   │   └── init_db.py             # Seeds sample data
│   ├── .env.example
│   ├── Dockerfile
│   ├── postgres-init.sql  # Enables pgcrypto extension
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/           # Next.js 15 App Router (layout, page, login, signup, dashboard)
│   │   ├── lib/           # api.ts — typed API client with JWT + auto-refresh
│   │   └── styles/        # globals.css with Tailwind + brand tokens
│   ├── tailwind.config.js
│   ├── next.config.js
│   ├── tsconfig.json
│   └── package.json
├── docker-compose.yml     # Postgres 16 + Redis 7 + backend
├── .gitignore
└── README.md              # You are here
```

---

## Brand palette

| Role | Color | Hex |
|------|-------|-----|
| Background | White | `#FFFFFF` |
| Primary | Deep Blue | `#1E3A5F` |
| Success / Accent | Green | `#10B981` |

Defined in `frontend/tailwind.config.js` as `brand.blue` and `brand.green` with 10-step scales, and as CSS variables in `frontend/src/styles/globals.css`.

---

## Troubleshooting

### "Cannot reach the backend. Is it running on http://localhost:8000/api/v1?"
- Run `docker compose ps` — all three services must be running.
- Check backend logs: `docker compose logs backend | tail -50`.

### "An account with this email already exists" on signup
- The seed script already created `admin@onlinesmartpick.com`. Either use that one, or sign up with a different email.

### `alembic upgrade head` says "No such file or directory"
- You forgot Step 4. Run `docker compose up --build -d` first.

### `docker compose up` fails with "port is already allocated"
- Ports 5432 (Postgres), 6379 (Redis), or 8000 (backend) are already in use on your machine. Either stop whatever's using them, or edit the `ports:` sections in `docker-compose.yml`.

### `npm install` is slow or hangs
- Normal on the first run. Give it 3–5 minutes.
- If it truly hangs: `Ctrl+C`, delete `frontend\node_modules` and `frontend\package-lock.json`, then run `npm install` again.

### "Invalid or expired token" errors after logging in
- Clear your browser's localStorage for `localhost:3000` (DevTools → Application → Local Storage → clear) and log in again.

### Reset everything from scratch
```powershell
docker compose down -v          # Wipes database
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.init_db
```

---

## What's next

**Phase 2** will add: OAuth flows for connecting real marketing platforms (Google Ads, Meta Ads, GA4, GSC, LinkedIn), email verification, password reset, and the agency settings page.

**Phase 3** will add: Nightly Celery-based data sync jobs, metric normalization across platforms, and unified metrics dashboards.

**Phase 4** integrates Claude AI to generate Smart Picks and answer natural-language questions.

**Phase 5** adds automated PPTX / PDF / HTML report generation.

**Phase 6** deploys the backend to Railway and the frontend to Vercel, with the production database on Railway Postgres.

---

## License

Proprietary. © Saggurthi Praveen Kumar / onlinesmartpick.com
