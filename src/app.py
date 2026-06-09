import os
from functools import wraps

from flask import Flask, jsonify, render_template, request, redirect, session, url_for

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-me")

SPA_PAGES = [
    ("home", "Home"),
    ("vendors", "Vendors"),
    ("groups", "Groups"),
    ("quotes", "Quotes"),
    ("profile", "Profile"),
]

SPA_SECTIONS = {
    "home": {
        "title": "Hello, Aniket!",
        "badge": "Gold • 2,450",
        "hero": "Trusted vendors. Real prices. Buy together.",
        "stats": [
            {"value": "3", "label": "Active Groups"},
            {"value": "12", "label": "Vendors"},
            {"value": "8", "label": "Quotes"},
            {"value": "4.2", "label": "Avg Rating"},
        ],
        "vendors": [
            {"name": "SolarBright Energy", "category": "Solar Installation", "rating": "4.5", "uses": "32 used"},
            {"name": "Home Interior Studio", "category": "Interior Design", "rating": "4.3", "uses": "18 used"},
            {"name": "AquaPure Water", "category": "Water Softener", "rating": "4.2", "uses": "15 used"},
        ],
    },
    "vendors": {
        "title": "Vendors",
        "subtitle": "Search by category and compare trusted providers.",
    },
    "groups": {
        "title": "Group Buys",
        "subtitle": "Active and upcoming group deals.",
    },
    "quotes": {
        "title": "Quotes",
        "subtitle": "Community uploaded price quotes.",
    },
    "profile": {
        "title": "Profile",
        "subtitle": "User profile and contribution summary.",
    },
    "requirements": {
        "title": "MVP 1 - Requirements Document",
        "subtitle": "Product scope, modules, and success metrics.",
    },
}


def current_user():
    return session.get("google_user")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user():
            return view(*args, **kwargs)
        next_path = request.path
        return redirect(url_for("login_google", next=next_path))

    return wrapped


@app.context_processor
def inject_nav():
    return {
        "nav_pages": SPA_PAGES,
        "spa_sections": SPA_SECTIONS,
        "current_user": current_user(),
        "login_enabled": os.getenv("GOOGLE_OAUTH_ENABLED", "false").lower() == "true",
    }


@app.get("/")
def index():
    return render_template("spa.html", page_title="myhomecircle")


@app.get("/<path:any_path>")
def spa_fallback(any_path: str):
    if any_path.startswith("api/"):
        return jsonify(error="not found"), 404
    return render_template("spa.html", page_title="myhomecircle")


@app.get("/login/google")
def login_google():
    next_path = request.args.get("next", "/")
    if os.getenv("GOOGLE_OAUTH_ENABLED", "false").lower() == "true":
        # Hook your Google OAuth redirect here later.
        return render_template("spa.html", page_title="Google Login", auth_prompt=True, next_path=next_path)

    session["google_user"] = {
        "name": os.getenv("DEFAULT_USER_NAME", "Aniket Pathak"),
        "email": os.getenv("DEFAULT_USER_EMAIL", "aniket@example.com"),
    }
    return redirect(next_path or "/")


@app.get("/auth/google/callback")
def google_callback():
    # Lightweight dev-only callback scaffold.
    session["google_user"] = {
        "name": request.args.get("name", "Aniket Pathak"),
        "email": request.args.get("email", "aniket@example.com"),
    }
    return redirect(request.args.get("next", "/"))


@app.get("/logout")
def logout():
    session.pop("google_user", None)
    return redirect("/")


@app.get("/api/health")
def health():
    return jsonify(status="ok")


@app.get("/api/echo")
def echo():
    return jsonify(message=request.args.get("message", "hello from myhomecircle"))


@app.get("/api/me")
def me():
    user = current_user()
    if not user:
        return jsonify(authed=False), 401
    return jsonify(authed=True, user=user)


@app.get("/api/login-status")
def login_status():
    return jsonify(authed=bool(current_user()), user=current_user())


if __name__ == "__main__":
    app.run(debug=True)
