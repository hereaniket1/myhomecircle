import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

import psycopg2
from flask import Flask, jsonify, render_template, request, redirect, session, url_for
from authlib.integrations.flask_client import OAuth
import resend
from community_service import find_existing_communities, list_communities, register_community

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-me")
app.config["DATABASE_URL"] = os.getenv("DATABASE_URL", "")
oauth = OAuth(app)

google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

SPA_PAGES = [
    ("home", "Home"),
    ("community", "Community"),
    ("vendors", "Vendors"),
    ("quotes", "Quotes"),
    ("groups", "Group Buys"),
    ("leaderboard", "Leaderboard"),
    ("analytics", "Analytics"),
    ("messages", "Messages"),
    ("settings", "Settings"),
]

SPA_SECTIONS = {
    "home": {
        "title": "Welcome to MyHomeCircle",
        "badge": "Guest Access",
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

def create_connection():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT") or os.getenv("DB_POST"),
        database=os.getenv("DB_ROYALTY_DATABASE_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    conn.autocommit = False
    return conn


def _run_query(query, params=(), fetch=False, fetchall=False, returning=False):
    conn = db_conn()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            if fetchall:
                result = cur.fetchall()
            elif fetch or returning:
                result = cur.fetchone()
            else:
                result = None
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def db_conn():
    return create_connection()


def fetch_one(query, params=()):
    return _run_query(query, params, fetch=True)


def insert_returning(query, params=()):
    return _run_query(query, params, returning=True)


def fetch_all(query, params=()):
    return _run_query(query, params, fetchall=True) or []


def execute(query, params=()):
    _run_query(query, params)


def query_in_transaction(conn, query, params=(), fetch=False, returning=False):
    with conn.cursor() as cur:
        cur.execute(query, params)
        if fetch or returning:
            return cur.fetchone()
        return None


def serialize_user(row):
    if not row:
        return None
    return {
        "id": str(row[0]),
        "email": row[1],
        "full_name": row[2],
        "avatar_url": row[3],
        "email_verified": row[4],
        "status": row[5],
        "last_login_at": row[6].isoformat() if row[6] else None,
    }


def serialize_session_user(user):
    return {
        "id": str(user["id"]),
        "email": user["email"],
        "name": user["full_name"],
        "full_name": user["full_name"],
        "picture": user["avatar_url"],
        "avatar_url": user["avatar_url"],
    }


def current_user():
    user_id = session.get("app_user_id")
    if not user_id:
        return None
    row = fetch_one(
        """
        SELECT id, email, full_name, avatar_url, email_verified, status, last_login_at
        FROM app_users
        WHERE id = %s
        """,
        (user_id,),
    )
    if not row:
        return None
    user = serialize_user(row)
    session["current_user"] = user
    return user


def set_session_user(user):
    session["app_user_id"] = user["id"]
    session["current_user"] = serialize_session_user(user)


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
    return redirect(url_for("google_login", next=request.args.get("next", "/")))


@app.get("/auth/google/login")
def google_login():
    next_path = request.args.get("next", "/")
    is_popup = request.args.get("popup") == "true"
    session["next_url"] = next_path
    session["oauth_popup"] = is_popup
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI") or url_for("google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.get("/auth/google/callback")
def google_callback():
    token = google.authorize_access_token()
    user_info = token.get("userinfo") or google.userinfo()
    user = upsert_google_user(user_info)
    if not user:
        return jsonify(error="Could not complete Google login"), 500
    set_session_user(user)

    if session.pop("oauth_popup", False):
        return render_template("popup_callback.html")

    next_url = session.pop("next_url", "/")
    return redirect(next_url)


@app.get("/auth/me")
def auth_me():
    user = current_user()
    if not user:
        return jsonify(authenticated=False)
    return jsonify(authenticated=True, user=serialize_session_user(user))


@app.get("/logout")
def logout():
    session.pop("app_user_id", None)
    session.pop("current_user", None)
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


@app.get("/api/communities")
def api_communities():
    search = request.args.get("q", "")
    communities = list_communities(db_conn, search=search)
    return jsonify(ok=True, communities=communities)


@app.post("/api/communities/search-existing")
def api_communities_search_existing():
    payload = request.get_json(force=True) or {}
    matches = find_existing_communities(db_conn, payload)
    return jsonify(ok=True, matches=matches)


@app.post("/api/communities")
def api_communities_register():
    if not current_user():
        return jsonify(error="Login is required to register a community"), 401
    payload = request.get_json(force=True) or {}
    try:
        result = register_community(db_conn, payload)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    if not result.get("created"):
        return jsonify(
            error="A matching community may already exist",
            matches=result.get("matches", []),
        ), 409
    return jsonify(ok=True, community=result["community"]), 201


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return "pbkdf2_sha256$120000$%s$%s" % (
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_b64, digest_b64 = stored.split("$", 3)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def generate_otp():
    return f"{secrets.randbelow(1_000_000):06d}"


def send_email_otp(email: str, full_name: str, otp_code: str):
    resend.api_key = os.environ["RESEND_API_KEY"]
    from_email = os.getenv("RESEND_FROM_EMAIL", "MyHomeCircle <no-reply@myhomecircle.app>")
    params = {
        "from": from_email,
        "to": [email],
        "subject": "Your MyHomeCircle verification code",
        "html": f"""
            <div style="font-family: Arial, sans-serif; color: #1c2430;">
              <h2 style="margin: 0 0 12px;">Hi {full_name},</h2>
              <p style="margin: 0 0 12px;">Your email verification code for MyHomeCircle is:</p>
              <div style="font-size: 28px; font-weight: 700; letter-spacing: 4px; margin: 16px 0; padding: 16px 20px; background: #f4f7f5; border-radius: 12px; display: inline-block;">
                {otp_code}
              </div>
              <p style="margin: 12px 0 0;">This code expires in 10 minutes.</p>
            </div>
        """,
    }
    return resend.Emails.send(params)


def render_auth_error(message: str, status: int = 400):
    return jsonify(error=message), status


def upsert_google_user(user_info):
    email = (user_info.get("email") or "").strip().lower()
    full_name = (user_info.get("name") or "Google User").strip()
    avatar_url = user_info.get("picture")
    provider_user_id = user_info.get("sub") or email

    conn = db_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT app_user_id
                    FROM auth_identities
                    WHERE provider = 'GOOGLE' AND provider_user_id = %s
                    """,
                    (provider_user_id,),
                )
                identity = cur.fetchone()

                if identity:
                    user_id = identity[0]
                    cur.execute(
                        """
                        UPDATE app_users
                        SET email = COALESCE(%s, email),
                            full_name = COALESCE(%s, full_name),
                            avatar_url = COALESCE(%s, avatar_url),
                            email_verified = TRUE,
                            last_login_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (email or None, full_name, avatar_url, user_id),
                    )
                    cur.execute(
                        """
                        UPDATE auth_identities
                        SET provider_email = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE provider = 'GOOGLE' AND provider_user_id = %s
                        """,
                        (email or None, provider_user_id),
                    )
                else:
                    cur.execute(
                        "SELECT id FROM app_users WHERE email = %s",
                        (email,),
                    )
                    existing = cur.fetchone()
                    if existing:
                        user_id = existing[0]
                        cur.execute(
                            """
                            UPDATE app_users
                            SET full_name = COALESCE(%s, full_name),
                                avatar_url = COALESCE(%s, avatar_url),
                                email_verified = TRUE,
                                last_login_at = CURRENT_TIMESTAMP,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                            """,
                            (full_name, avatar_url, user_id),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO app_users (email, full_name, avatar_url, email_verified, status, last_login_at)
                            VALUES (%s, %s, %s, TRUE, 'ACTIVE', CURRENT_TIMESTAMP)
                            RETURNING id
                            """,
                            (email, full_name, avatar_url),
                        )
                        user_id = cur.fetchone()[0]

                    cur.execute(
                        """
                        INSERT INTO auth_identities (app_user_id, provider, provider_user_id, provider_email)
                        VALUES (%s, 'GOOGLE', %s, %s)
                        ON CONFLICT (provider, provider_user_id) DO UPDATE
                        SET app_user_id = EXCLUDED.app_user_id,
                            provider_email = EXCLUDED.provider_email,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (user_id, provider_user_id, email or None),
                    )

                cur.execute(
                    "SELECT id, email, full_name, avatar_url, email_verified, status, last_login_at FROM app_users WHERE id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
        return serialize_user(row)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.get("/signup")
def signup_page():
    return render_template("spa.html", page_title="Sign up", auth_prompt=True, auth_mode="signup")


@app.get("/login")
def login_page():
    return render_template("spa.html", page_title="Log in", auth_prompt=True, auth_mode="login")


@app.post("/api/auth/signup")
def api_signup():
    payload = request.get_json(force=True)
    full_name = payload.get("full_name", "").strip()
    email = payload.get("email", "").strip().lower()
    password = payload.get("password", "")
    accepted = bool(payload.get("accepted_terms"))
    if not full_name or not email or not password or not accepted:
        return jsonify(error="name, email, password, and accepted terms are required"), 400

    password_hash = hash_password(password)

    conn = db_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM app_users WHERE email = %s", (email,))
                existing = cur.fetchone()
                if existing:
                    return jsonify(error="An account with this email already exists"), 409

                cur.execute(
                    """
                    INSERT INTO app_users (email, full_name, email_verified, status)
                    VALUES (%s, %s, FALSE, 'PENDING')
                    RETURNING id
                    """,
                    (email, full_name),
                )
                user_id = cur.fetchone()[0]
                cur.execute(
                    """
                    INSERT INTO auth_identities (app_user_id, provider, provider_user_id, provider_email, password_hash)
                    VALUES (%s, 'LOCAL_PASSWORD', %s, %s, %s)
                    """,
                    (user_id, email, email, password_hash),
                )
                otp_code = generate_otp()
                expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
                cur.execute(
                    """
                    INSERT INTO email_otp_codes (email, otp_code, purpose, expires_at)
                    VALUES (%s, %s, 'EMAIL_VERIFY', %s)
                    """,
                    (email, otp_code, expires_at),
                )
        send_email_otp(email=email, full_name=full_name, otp_code=otp_code)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    session["pending_signup"] = {"email": email}
    return jsonify(
        ok=True,
        message="OTP generated",
        demo_otp=otp_code,
        email=email,
    )


@app.post("/api/auth/resend-otp")
def api_resend_otp():
    payload = request.get_json(force=True)
    email = payload.get("email", "").strip().lower()
    if not email:
        return render_auth_error("email is required")

    conn = db_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, full_name, email_verified FROM app_users WHERE email = %s",
                    (email,),
                )
                user = cur.fetchone()
                if not user:
                    return render_auth_error("No signup found for this email", 404)
                if user[2]:
                    return render_auth_error("This email is already verified")

                otp_code = generate_otp()
                expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
                cur.execute(
                    """
                    INSERT INTO email_otp_codes (email, otp_code, purpose, expires_at)
                    VALUES (%s, %s, 'EMAIL_VERIFY', %s)
                    """,
                    (email, otp_code, expires_at),
                )
        send_email_otp(email=email, full_name=user[1] or "there", otp_code=otp_code)
        return jsonify(ok=True, message="OTP resent")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.post("/api/auth/verify-email")
def api_verify_email():
    payload = request.get_json(force=True)
    email = payload.get("email", "").strip().lower()
    otp_code = payload.get("otp_code", "").strip()
    if not email or not otp_code:
        return jsonify(error="email and otp_code are required"), 400

    otp_row = fetch_one(
        """
        SELECT id, used_at, expires_at, attempt_count, max_attempts
        FROM email_otp_codes
        WHERE email = %s AND purpose = 'EMAIL_VERIFY' AND otp_code = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (email, otp_code),
    )
    if not otp_row:
        return jsonify(error="Invalid OTP"), 400
    if otp_row[1] is not None:
        return jsonify(error="OTP already used"), 400
    if otp_row[2] < datetime.now(timezone.utc):
        return jsonify(error="OTP expired"), 400
    if otp_row[3] >= otp_row[4]:
        return jsonify(error="Too many OTP attempts"), 400

    conn = db_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE email_otp_codes SET used_at = CURRENT_TIMESTAMP WHERE id = %s", (otp_row[0],))
                cur.execute("UPDATE app_users SET email_verified = TRUE, status = 'ACTIVE', updated_at = CURRENT_TIMESTAMP WHERE email = %s", (email,))
                cur.execute("UPDATE app_users SET last_login_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE email = %s", (email,))
                cur.execute(
                    "SELECT id, email, full_name, avatar_url, email_verified, status, last_login_at FROM app_users WHERE email = %s",
                    (email,),
                )
                user = cur.fetchone()
        user_data = serialize_user(user)
        set_session_user(user_data)
        return jsonify(ok=True, user=user_data)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@app.post("/api/auth/login")
def api_login():
    payload = request.get_json(force=True)
    email = payload.get("email", "").strip().lower()
    password = payload.get("password", "")
    if not email or not password:
        return jsonify(error="email and password are required"), 400

    user_row = fetch_one(
        "SELECT id, email, full_name, avatar_url, email_verified, status, last_login_at FROM app_users WHERE email = %s",
        (email,),
    )
    if not user_row:
        return jsonify(error="Invalid credentials"), 400
    identity = fetch_one(
        "SELECT password_hash FROM auth_identities WHERE app_user_id = %s AND provider = 'LOCAL_PASSWORD'",
        (user_row[0],),
    )
    if not identity or not verify_password(password, identity[0]):
        return render_auth_error("Invalid credentials")
    conn = db_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE app_users SET last_login_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (user_row[0],))
                cur.execute(
                    "SELECT id, email, full_name, avatar_url, email_verified, status, last_login_at FROM app_users WHERE id = %s",
                    (user_row[0],),
                )
                user_row = cur.fetchone()
        user_data = serialize_user(user_row)
        set_session_user(user_data)
        return jsonify(ok=True, user=user_data)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    app.run(debug=True)
