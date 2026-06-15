import base64
import atexit
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from flask import Flask, jsonify, render_template, request, redirect, session, url_for, g
from authlib.integrations.flask_client import OAuth
import resend
try:
    from .community_service import (
        find_existing_communities,
        get_community_detail,
        get_user_home_summary,
        join_community,
        list_communities,
        register_community,
    )
    from .settings_service import delete_my_data, get_settings_summary, leave_community, reset_all_data
    from .latency_service import get_latency_dashboard, now_ms, record_api_latency
    from .notification_service import (
        approve_join_request,
        create_join_approval_notifications,
        get_join_request_admin_context,
        list_pending_join_requests,
        list_notifications,
        mark_notification_read,
        promote_member_to_admin,
        reject_join_request,
    )
except ImportError:
    from community_service import (
        find_existing_communities,
        get_community_detail,
        get_user_home_summary,
        join_community,
        list_communities,
        register_community,
    )
    from settings_service import delete_my_data, get_settings_summary, leave_community, reset_all_data
    from latency_service import get_latency_dashboard, now_ms, record_api_latency
    from notification_service import (
        approve_join_request,
        create_join_approval_notifications,
        get_join_request_admin_context,
        list_pending_join_requests,
        list_notifications,
        mark_notification_read,
        promote_member_to_admin,
        reject_join_request,
    )

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-me")
app.config["DATABASE_URL"] = os.getenv("DATABASE_URL", "")
oauth = OAuth(app)
_db_pool = None

google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@app.before_request
def start_api_latency_timer():
    if request.path.startswith("/api/"):
        g.api_latency_started_ms = now_ms()


@app.after_request
def record_api_latency_timer(response):
    started_ms = getattr(g, "api_latency_started_ms", None)
    if started_ms is not None:
        record_api_latency(
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            duration_ms=now_ms() - started_ms,
        )
    return response

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

def _db_connect_kwargs():
    return {
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT") or os.getenv("DB_POST"),
        "database": os.getenv("DB_ROYALTY_DATABASE_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
        "application_name": os.getenv("DB_APPLICATION_NAME", "myhomecircle"),
    }


def create_connection():
    conn = psycopg2.connect(**_db_connect_kwargs())
    conn.autocommit = False
    return conn


class PooledConnection:
    def __init__(self, pool, conn):
        self._pool = pool
        self._conn = conn
        self._closed = False

    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        if self._closed:
            return
        try:
            if self._conn.status != psycopg2.extensions.STATUS_READY:
                self._conn.rollback()
        finally:
            self._pool.putconn(self._conn)
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        return False


def get_db_pool():
    global _db_pool
    if _db_pool is None:
        min_conn = int(os.getenv("DB_POOL_MIN_CONN", "1"))
        max_conn = int(os.getenv("DB_POOL_MAX_CONN", "5"))
        _db_pool = ThreadedConnectionPool(min_conn, max_conn, **_db_connect_kwargs())
    return _db_pool


@atexit.register
def close_db_pool():
    if _db_pool is not None:
        _db_pool.closeall()


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
    pool = get_db_pool()
    conn = pool.getconn()
    conn.autocommit = False
    return PooledConnection(pool, conn)


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
    return google.authorize_redirect(redirect_uri, prompt="select_account")


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
    session.clear()
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


@app.get("/api/me/home")
def me_home():
    user = current_user()
    if not user:
        return jsonify(authed=False), 401
    return jsonify(authed=True, home=get_user_home_summary(db_conn, user["id"]))


@app.get("/api/login-status")
def login_status():
    user = current_user()
    return jsonify(authed=bool(user), user=user)


@app.get("/api/notifications")
def api_notifications():
    user = current_user()
    if not user:
        return jsonify(error="Login is required"), 401
    return jsonify(ok=True, **list_notifications(db_conn, user["id"]))


@app.post("/api/notifications/<notification_id>/read")
def api_notification_read(notification_id):
    user = current_user()
    if not user:
        return jsonify(error="Login is required"), 401
    if not mark_notification_read(db_conn, notification_id, user["id"]):
        return jsonify(error="Notification not found"), 404
    return jsonify(ok=True)


@app.post("/api/join-requests/<request_id>/approve")
def api_join_request_approve(request_id):
    user = current_user()
    if not user:
        return jsonify(error="Login is required"), 401
    try:
        result = approve_join_request(db_conn, request_id, user["id"])
    except PermissionError as exc:
        return jsonify(error=str(exc)), 403
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(ok=True, message="Join request approved", **result)


@app.post("/api/join-requests/<request_id>/reject")
def api_join_request_reject(request_id):
    user = current_user()
    if not user:
        return jsonify(error="Login is required"), 401
    try:
        result = reject_join_request(db_conn, request_id, user["id"])
    except PermissionError as exc:
        return jsonify(error=str(exc)), 403
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(ok=True, message="Join request rejected", **result)


@app.post("/api/community-members/<member_id>/promote-admin")
def api_promote_member_admin(member_id):
    user = current_user()
    if not user:
        return jsonify(error="Login is required"), 401
    try:
        result = promote_member_to_admin(db_conn, member_id, user["id"])
    except PermissionError as exc:
        return jsonify(error=str(exc)), 403
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(ok=True, message="Member promoted to admin", **result)


@app.get("/approve/join/<request_id>")
def approve_join_link(request_id):
    if not current_user():
        return redirect(url_for("login_google", next=request.path))
    context = get_join_request_admin_context(db_conn, request_id)
    if not context:
        return redirect("/community?approval=failed")
    return redirect(f"/community?community_id={context['community_id']}&join_request_id={request_id}")


@app.get("/api/settings")
def api_settings():
    user = current_user()
    if not user:
        return jsonify(error="Login is required"), 401
    return jsonify(ok=True, settings=get_settings_summary(db_conn, user))


@app.get("/api/settings/latency")
def api_settings_latency():
    user = current_user()
    if not user:
        return jsonify(error="Login is required"), 401
    settings = get_settings_summary(db_conn, user)
    if not settings.get("is_founder"):
        return jsonify(error="Founder access required"), 403
    return jsonify(ok=True, latency=get_latency_dashboard())


@app.post("/api/settings/leave-community")
def api_leave_community():
    user = current_user()
    if not user:
        return jsonify(error="Login is required"), 401
    payload = request.get_json(force=True) or {}
    community_id = payload.get("community_id")
    if not community_id:
        return jsonify(error="community_id is required"), 400
    deleted = leave_community(db_conn, user["id"], community_id)
    if not deleted:
        return jsonify(error="Community membership not found"), 404
    return jsonify(ok=True, message="You have left this community")


@app.post("/api/settings/delete-my-data")
def api_delete_my_data():
    user = current_user()
    if not user:
        return jsonify(error="Login is required"), 401
    payload = request.get_json(force=True) or {}
    if payload.get("confirm") != "DELETE":
        return jsonify(error="Type DELETE to confirm account deletion"), 400
    delete_my_data(db_conn, user)
    session.clear()
    return jsonify(ok=True, message="Your account data has been deleted")


@app.post("/api/settings/kill-all-data")
def api_kill_all_data():
    user = current_user()
    if not user:
        return jsonify(error="Login is required"), 401
    payload = request.get_json(force=True) or {}
    if payload.get("confirm") != "RESET":
        return jsonify(error="Type RESET to confirm founder reset"), 400
    try:
        reset_all_data(db_conn, user)
    except PermissionError as exc:
        return jsonify(error=str(exc)), 403
    session.clear()
    return jsonify(ok=True, message="All app data has been erased")


@app.get("/api/communities")
def api_communities():
    search = request.args.get("q", "")
    communities = list_communities(db_conn, search=search, limit=10)
    return jsonify(ok=True, communities=communities)


@app.post("/api/communities/search-existing")
def api_communities_search_existing():
    payload = request.get_json(force=True) or {}
    matches = find_existing_communities(db_conn, payload)
    return jsonify(ok=True, matches=matches)


@app.get("/api/communities/<community_id>")
def api_community_detail(community_id):
    user = current_user()
    community = get_community_detail(db_conn, community_id, user["id"] if user else None)
    if not community:
        return jsonify(error="Community not found"), 404
    return jsonify(ok=True, community=community)


@app.get("/api/communities/<community_id>/join-requests")
def api_community_join_requests(community_id):
    user = current_user()
    if not user:
        return jsonify(error="Login is required"), 401
    return jsonify(ok=True, **list_pending_join_requests(db_conn, community_id, user["id"]))


@app.post("/api/communities/<community_id>/join")
def api_community_join(community_id):
    user = current_user()
    if not user:
        return jsonify(error="Login is required to join a community"), 401
    payload = request.get_json(force=True) or {}
    try:
        result = join_community(db_conn, community_id, user["id"], payload)
    except LookupError as exc:
        return jsonify(error=str(exc)), 404
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    if result.get("join_request_id"):
        context = get_join_request_admin_context(db_conn, result["join_request_id"])
        if context:
            approval_url = url_for(
                "spa_fallback",
                any_path="community",
                community_id=context["community_id"],
                join_request_id=result["join_request_id"],
                _external=True,
            )
            create_join_approval_notifications(db_conn, context, approval_url)
            for admin in context["admins"]:
                try:
                    send_join_approval_email(admin["email"], admin["full_name"], context, approval_url)
                except Exception:
                    app.logger.exception("Could not send join approval email to %s", admin["email"])
    return jsonify(ok=True, **result)


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


def send_join_approval_email(admin_email: str, admin_name: str, context: dict, approval_url: str):
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        return None
    resend.api_key = api_key
    from_email = os.getenv("RESEND_FROM_EMAIL", "MyHomeCircle <no-reply@myhomecircle.app>")
    params = {
        "from": from_email,
        "to": [admin_email],
        "subject": f"Approval needed: {context['requester_name']} wants to join {context['community_name']}",
        "html": f"""
            <div style="font-family: Arial, sans-serif; color: #1c2430;">
              <h2 style="margin: 0 0 12px;">Hi {admin_name or 'there'},</h2>
              <p style="margin: 0 0 12px;">
                {context['requester_name']} ({context['requester_email']}) requested to join
                <strong>{context['community_name']}</strong> as <strong>{context['villa_number']}</strong>.
              </p>
              <p style="margin: 0 0 18px;">Open this approval link while logged in as a community admin:</p>
              <p>
                <a href="{approval_url}" style="display: inline-block; padding: 12px 18px; border-radius: 999px; background: #173f6b; color: #ffffff; text-decoration: none; font-weight: 700;">
                  Approve member
                </a>
              </p>
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
