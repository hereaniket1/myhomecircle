# myhomecircle

Single-page application scaffold for a FastAPI + Postgres + React stack.

## Stack

- Backend: FastAPI, SQLAlchemy 2.x, Alembic, Pydantic Settings
- Database: PostgreSQL
- Frontend: React, Vite, TypeScript
- Tooling: Docker Compose, lint-friendly project layout, environment-based config

## Layout

- `backend/` FastAPI app, domain modules, database, and migration hooks
- `frontend/` React SPA shell
- `docker-compose.yml` Local app + Postgres orchestration
- `.env.example` Shared environment template

## Next steps

This scaffold is intentionally minimal. The next layer would usually add:

- auth
- user/session models
- API routers for business features
- frontend routing, state, and data fetching
- tests and CI
