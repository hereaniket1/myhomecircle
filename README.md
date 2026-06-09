# myhomecircle

Minimal Flask single-page app scaffold for Render.

## Stack

- Backend: Flask
- Database: Postgres
- Deployment: Render web service
- Install: `requirements.txt`

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

## Render

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app --bind 0.0.0.0:$PORT`
- Add a Postgres database and set `DATABASE_URL`

## Files to keep

- `app.py`
- `requirements.txt`
- `README.md`
- `.env.example`
