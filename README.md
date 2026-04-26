# Room Bill Splitter — Production Build

A neo-brutalist single-page bill splitter with a custom JWT-authenticated
FastAPI backend (PostgreSQL) and a static HTML/Tailwind frontend.

## Features

- Custom username/password login (no Supabase Auth)
- JWT (HS256) issued by FastAPI; stored in `localStorage`
- Protected `POST /api/calculate` endpoint enforces Bearer token
- Mobile-responsive login screen
- Bill split calculation, history (localStorage), saved roommate groups,
  CSV export, print-to-PDF

## Stack

| Layer | Tech |
| --- | --- |
| Backend | Python 3.11+, FastAPI, Uvicorn, bcrypt, python-jose, psycopg2-binary |
| Database | PostgreSQL (Supabase Postgres in production) |
| Frontend | Single HTML file (Tailwind CDN, vanilla JS) |

## Backend Layout

```
backend/
  app/
    main.py              # FastAPI entry point, mounts /api router, seeds admin
    routes/
      auth.py            # POST /api/login
      calculate.py       # POST /api/calculate (protected)
    core/
      security.py        # bcrypt + JWT helpers, get_current_user dependency
      config.py          # env-backed settings
    db/
      client.py          # psycopg2 connection pool, schema bootstrap, queries
  requirements.txt
  server.py              # local supervisor entry: re-exports app.main:app
```

## Database Schema

Auto-created on first boot (`init_schema()` runs at startup):

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE IF NOT EXISTS users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username      TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

## API

### POST `/api/login`
Request:
```json
{ "username": "admin", "password": "admin123" }
```
Response (200):
```json
{ "access_token": "<jwt>", "token_type": "bearer", "user_id": "<uuid>", "username": "admin" }
```
Errors: `401 Invalid username or password`

### POST `/api/calculate` (protected)
Header: `Authorization: Bearer <jwt>`
Request:
```json
{
  "total_bill": 1500,
  "total_days": 30,
  "roommates": [
    { "name": "Alice", "days": 20 },
    { "name": "Bob",   "days": 10 }
  ]
}
```
Response (200):
```json
{
  "total_bill": 1500.0,
  "total_days": 30,
  "total_days_present": 30.0,
  "roommates": [
    { "name": "Alice", "days": 20.0, "percentage": 66.6667, "amount": 1000.0 },
    { "name": "Bob",   "days": 10.0, "percentage": 33.3333, "amount": 500.0 }
  ]
}
```
Errors: `401 Missing/invalid token`, `400 validation error`

## Environment Variables

`backend/.env`:

| Var | Required | Notes |
| --- | --- | --- |
| `DATABASE_URL` | yes | Postgres connection string. Use the *Connection pooler* URL from Supabase → Project Settings → Database. |
| `JWT_SECRET` | yes | Random 64-char hex. Render's blueprint auto-generates one. |
| `JWT_EXPIRE_MINUTES` | no | Defaults to `1440` (24 h). |
| `ADMIN_USERNAME` | no | Defaults to `admin`. Seeded on first boot. |
| `ADMIN_PASSWORD` | yes | Used to seed the admin user. Update keeps the hash in sync. |
| `CORS_ORIGINS` | no | Comma-separated origins. Defaults to `*`. |

## Local Development

The Emergent preview ships with a local Postgres instance pre-seeded:

```bash
sudo supervisorctl restart backend frontend
curl http://localhost:8001/api/health
```

The frontend lives in `frontend/public/index.html` (served via CRA dev server)
and uses same-origin `/api/...` calls, so the Kubernetes ingress routes them to
the FastAPI backend on port 8001.

## Deploy to Render

1. Push this repo to GitHub.
2. In Render, create a **New Blueprint** and point it at the repo.
   `render.yaml` at the repo root configures the web service automatically.
3. In the Render dashboard, set the two `sync: false` secrets:
   - `DATABASE_URL` — your Supabase Postgres connection string.
   - `ADMIN_PASSWORD` — the password you want for the seeded admin user.
4. Deploy. The startup hook auto-creates the `users` table and seeds the admin.

The service runs:

```
uvicorn app.main:app --host 0.0.0.0 --port 10000
```

## Default Credentials (preview only)

- Username: `admin`
- Password: `admin123`

Change `ADMIN_PASSWORD` before going to production.

## License

Copyright (c) 2026 Sahil. All rights reserved.
