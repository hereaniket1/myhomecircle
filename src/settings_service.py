FOUNDER_EMAIL = "aniketpathak1@gmail.com"

APP_TABLES = [
    "app_notifications",
    "user_badges",
    "badges",
    "points_ledger",
    "vendor_group_buy_proposals",
    "group_buy_participants",
    "group_buys",
    "vendor_reviews",
    "quotes",
    "vendors",
    "vendor_categories",
    "community_join_requests",
    "community_members",
    "community_settings",
    "communities",
    "addresses",
    "email_otp_codes",
    "auth_identities",
    "app_users",
]


def _membership_row_to_dict(row):
    return {
        "membership_id": str(row[0]),
        "community_id": str(row[1]),
        "community_name": row[2],
        "villa_number": row[3],
        "role": row[4],
        "status": row[5],
    }


def get_settings_summary(db_conn, user):
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    cm.id,
                    c.id,
                    c.name,
                    cm.villa_number,
                    cm.role,
                    cm.status
                FROM community_members cm
                JOIN communities c ON c.id = cm.community_id
                WHERE cm.app_user_id = %s
                  AND cm.status IN ('ACTIVE', 'PENDING')
                ORDER BY cm.created_at DESC
                """,
                (user["id"],),
            )
            memberships = [_membership_row_to_dict(row) for row in cur.fetchall()]
        return {
            "memberships": memberships,
            "is_founder": str(user.get("email", "")).lower() == FOUNDER_EMAIL,
        }
    finally:
        conn.close()


def leave_community(db_conn, app_user_id, community_id):
    conn = db_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM community_join_requests
                    WHERE app_user_id = %s AND community_id = %s
                    """,
                    (app_user_id, community_id),
                )
                cur.execute(
                    """
                    DELETE FROM community_members
                    WHERE app_user_id = %s AND community_id = %s
                    RETURNING id
                    """,
                    (app_user_id, community_id),
                )
                return cur.fetchone() is not None
    finally:
        conn.close()


def delete_my_data(db_conn, user):
    conn = db_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM email_otp_codes WHERE email = %s", (user["email"],))
                cur.execute("DELETE FROM app_users WHERE id = %s", (user["id"],))
        return True
    finally:
        conn.close()


def reset_all_data(db_conn, user):
    if str(user.get("email", "")).lower() != FOUNDER_EMAIL:
        raise PermissionError("Founder reset is not available for this account")

    conn = db_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tablename
                    FROM pg_tables
                    WHERE schemaname = 'public' AND tablename = ANY(%s)
                    """,
                    (APP_TABLES,),
                )
                existing_tables = [row[0] for row in cur.fetchall()]
                if not existing_tables:
                    return True
                table_list = ", ".join(existing_tables)
                cur.execute(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE")
        return True
    finally:
        conn.close()
