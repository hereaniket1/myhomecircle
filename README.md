# myhomecircle

Flask app scaffold with separate HTML pages for the requirements document and the screen mockups.

## What is included

- `src/app.py` Flask routes for the requirements page, dashboard, vendors, quotes, group buys, leaderboard, and profile
- `src/templates/` HTML pages rendered by Flask
- `src/static/styles.css` shared styling for all pages
- `requirements.txt` minimal dependency list for Render
- `.env.example` local environment template

## Local run

```bash
pip install -r requirements.txt
python src/app.py
```

Open:

- `http://localhost:5000/` requirements page
- `http://localhost:5000/dashboard`
- `http://localhost:5000/vendors`
- `http://localhost:5000/quotes`
- `http://localhost:5000/group-buys`
- `http://localhost:5000/leaderboard`
- `http://localhost:5000/profile`

## Render

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn src.app:app --bind 0.0.0.0:$PORT`
- Add a Postgres database if you want to persist data later
- Set `SECRET_KEY` in your Render environment variables

## Notes

- I did not add React yet. The `frontend/` folder is just a placeholder for later if you want to rebuild the screens as React pages.
- This version focuses on shipping the structure quickly.
