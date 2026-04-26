# Room Bill Splitter — PRD

## Original Problem Statement
Convert an existing single-file HTML bill splitter (which used Supabase Auth)
into a full production-ready system with:

- Python FastAPI backend with custom JWT login (no Supabase Auth)
- bcrypt password hashing, python-jose for JWT
- PostgreSQL `users` table (id uuid, username unique, password_hash)
- `POST /login` returning JWT
- Protected `POST /calculate` requiring Bearer token
- Mobile-responsive login page
- Render-deployable

## Architecture

```
/app
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI app, CORS, /api router, admin seeding
│   │   ├── routes/
│   │   │   ├── auth.py          POST /api/login
│   │   │   └── calculate.py     POST /api/calculate (JWT-protected)
│   │   ├── core/
│   │   │   ├── security.py      bcrypt, JWT (HS256), get_current_user
│   │   │   └── config.py        env-backed settings
│   │   └── db/
│   │       └── client.py        psycopg2 pool, schema bootstrap
│   ├── requirements.txt         fastapi, uvicorn, bcrypt, python-jose, psycopg2-binary, python-dotenv, pydantic
│   ├── server.py                Re-exports app.main:app for supervisor
│   └── .env                     DATABASE_URL, JWT_SECRET, ADMIN_USERNAME, ADMIN_PASSWORD
├── frontend/public/index.html   Single-page bill splitter (no Supabase, JWT in localStorage)
├── render.yaml                  Render Blueprint
└── README.md
```

## User Personas
1. Roommates splitting electricity bills by occupancy days
2. Hostel wardens / property managers tracking shared utility costs

## Core Requirements (static)
- Single login screen with username + password (mobile responsive)
- JWT stored in `localStorage`, sent as `Authorization: Bearer <jwt>`
- Logout clears token + returns to login screen
- Calculate endpoint runs server-side and is JWT-protected
- Existing UX (neo-brutalist design, history, saved groups, CSV, print) preserved

## What's Implemented (2026-04-26)
| Feature | Status |
|---|---|
| FastAPI backend with `/api/login` returning JWT | Done |
| bcrypt password hashing | Done |
| Protected `/api/calculate` endpoint | Done |
| PostgreSQL `users` table auto-created on boot | Done |
| Admin user (`admin` / `admin123`) seeded from env | Done |
| Username/password login form (mobile responsive) | Done |
| JWT stored in localStorage; sent as Bearer header | Done |
| Logout clears token and returns to login | Done |
| Removed all Supabase auth code from frontend | Done |
| History + saved groups now use localStorage | Done |
| CSS override for CRA's shadcn-tailwind color clash | Done |
| `render.yaml` blueprint + `/app/memory/test_credentials.md` | Done |
| Backend tested end-to-end (19/19 pytest tests pass) | Done |
| Frontend smoke-tested: login/calculate/logout all work | Done |

## Test Coverage
Backend regression suite at `/app/backend/tests/test_billsplitter_api.py`
covers `/api/health`, login (success/wrong pwd/unknown user/422 validation/case-insensitivity),
JWT structure (HS256, user_id + username claims), calculate (auth, classic
20/10 split for ₹1500, 400/422 validation), and DB seed (bcrypt `$2b$` hash).

## Backlog
### P1
- Brute-force lockout / rate-limiting on `/api/login`
- `/api/register` + admin UI for adding new users
- Cloud-synced history & groups (currently localStorage only)
- Tighten CORS_ORIGINS (currently `*`)
- Switch psycopg2 SimpleConnectionPool → ThreadedConnectionPool when scaling

### P2
- Multiple currency support
- Dark mode toggle
- WhatsApp share / email share of split
- PWA offline support

## Render Deployment
1. Push repo to GitHub
2. Render → New Blueprint → select repo (uses `/app/render.yaml`)
3. Set in Render dashboard:
   - `DATABASE_URL` = Supabase Postgres connection string
   - `ADMIN_PASSWORD` = your admin password
4. Deploy. Schema and admin auto-created on first boot.

Start command: `uvicorn app.main:app --host 0.0.0.0 --port 10000`
