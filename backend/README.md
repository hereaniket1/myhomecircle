# Backend

FastAPI service scaffold.

## What lives here

- `app/main.py` application entrypoint
- `app/api/` versioned routes
- `app/core/` configuration and security helpers
- `app/db/` database engine, session, and base model plumbing
- `app/models/` SQLAlchemy ORM models
- `app/schemas/` Pydantic request/response contracts
- `app/services/` business logic
- `alembic/` migration environment

## Common commands

- `uvicorn app.main:app --reload`
- `alembic revision --autogenerate -m "init"`
- `alembic upgrade head`
