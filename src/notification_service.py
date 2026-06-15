from threading import Lock
from typing import Any

_notifications_table_ready = False
_notifications_table_lock = Lock()

def ensure_notifications_table(db_conn):
    global _notifications_table_ready
    if _notifications_table_ready:
        return
    with _notifications_table_lock:
        if _notifications_table_ready:
            return
        conn = db_conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS app_notifications (
                            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                            app_user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                            notification_type VARCHAR(50) NOT NULL,
                            title VARCHAR(200) NOT NULL,
                            body TEXT,
                            action_url TEXT,
                            reference_type VARCHAR(50),
                            reference_id UUID,
                            read_at TIMESTAMPTZ,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                    cur.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_app_notifications_user_created
                        ON app_notifications(app_user_id, created_at DESC)
                        """
                    )
                    cur.execute(
                        """
                        CREATE UNIQUE INDEX IF NOT EXISTS idx_app_notifications_unique_reference
                        ON app_notifications(app_user_id, notification_type, reference_type, reference_id)
                        WHERE reference_id IS NOT NULL
                        """
                    )
            _notifications_table_ready = True
        finally:
            conn.close()


def _notification_row_to_dict(row):
    return {
        "id": str(row[0]),
        "type": row[1],
        "title": row[2],
        "body": row[3],
        "action_url": row[4],
        "reference_type": row[5],
        "reference_id": str(row[6]) if row[6] else None,
        "read_at": row[7].isoformat() if row[7] else None,
        "created_at": row[8].isoformat() if row[8] else None,
    }


def list_notifications(db_conn, app_user_id, limit: int = 20):
    ensure_notifications_table(db_conn)
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, notification_type, title, body, action_url, reference_type, reference_id, read_at, created_at
                FROM app_notifications
                WHERE app_user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (app_user_id, limit),
            )
            notifications = [_notification_row_to_dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                SELECT COUNT(*)
                FROM app_notifications
                WHERE app_user_id = %s AND read_at IS NULL
                """,
                (app_user_id,),
            )
            unread_count = cur.fetchone()[0]
            return {"notifications": notifications, "unread_count": unread_count}
    finally:
        conn.close()


def mark_notification_read(db_conn, notification_id, app_user_id):
    ensure_notifications_table(db_conn)
    conn = db_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT notification_type, reference_type, reference_id
                    FROM app_notifications
                    WHERE id = %s AND app_user_id = %s
                    """,
                    (notification_id, app_user_id),
                )
                row = cur.fetchone()
                if not row:
                    return False

                notification_type, reference_type, reference_id = row
                if notification_type == "JOIN_APPROVAL" and reference_type == "community_join_requests" and reference_id:
                    cur.execute(
                        """
                        UPDATE app_notifications
                        SET read_at = COALESCE(read_at, CURRENT_TIMESTAMP)
                        WHERE notification_type = 'JOIN_APPROVAL'
                          AND reference_type = 'community_join_requests'
                          AND reference_id = %s
                        """,
                        (reference_id,),
                    )
                    return True

                cur.execute(
                    """
                    UPDATE app_notifications
                    SET read_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND app_user_id = %s
                    RETURNING id
                    """,
                    (notification_id, app_user_id),
                )
                return cur.fetchone() is not None
    finally:
        conn.close()


def get_join_request_admin_context(db_conn, join_request_id):
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    jr.id,
                    jr.community_id,
                    jr.villa_number,
                    jr.status,
                    c.name,
                    requester.full_name,
                    requester.email,
                    admin_user.id,
                    admin_user.email,
                    admin_user.full_name
                FROM community_join_requests jr
                JOIN communities c ON c.id = jr.community_id
                JOIN app_users requester ON requester.id = jr.app_user_id
                JOIN community_members admin_member
                    ON admin_member.community_id = jr.community_id
                    AND admin_member.role = 'ADMIN'
                    AND admin_member.status = 'ACTIVE'
                JOIN app_users admin_user ON admin_user.id = admin_member.app_user_id
                WHERE jr.id = %s
                ORDER BY admin_user.email
                """,
                (join_request_id,),
            )
            rows = cur.fetchall()
            if not rows:
                return None
            first = rows[0]
            admins = [
                {
                    "id": str(row[7]),
                    "email": row[8],
                    "full_name": row[9],
                }
                for row in rows
            ]
            return {
                "request_id": str(first[0]),
                "community_id": str(first[1]),
                "villa_number": first[2],
                "status": first[3],
                "community_name": first[4],
                "requester_name": first[5] or first[6],
                "requester_email": first[6],
                "admins": admins,
            }
    finally:
        conn.close()


def create_join_approval_notifications(db_conn, context: dict[str, Any], approval_url: str):
    ensure_notifications_table(db_conn)
    title = f"Approve {context['requester_name']}?"
    body = f"{context['requester_name']} requested to join {context['community_name']} as {context['villa_number']}."
    conn = db_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                for admin in context["admins"]:
                    cur.execute(
                        """
                        INSERT INTO app_notifications (
                            app_user_id,
                            notification_type,
                            title,
                            body,
                            action_url,
                            reference_type,
                            reference_id
                        )
                        VALUES (%s, 'JOIN_APPROVAL', %s, %s, %s, 'community_join_requests', %s)
                        ON CONFLICT (app_user_id, notification_type, reference_type, reference_id)
                        WHERE reference_id IS NOT NULL
                        DO UPDATE SET
                            title = EXCLUDED.title,
                            body = EXCLUDED.body,
                            action_url = EXCLUDED.action_url,
                            read_at = NULL,
                            created_at = CURRENT_TIMESTAMP
                        """,
                        (admin["id"], title, body, approval_url, context["request_id"]),
                    )
    finally:
        conn.close()


def list_pending_join_requests(db_conn, community_id, admin_user_id):
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM community_members
                WHERE community_id = %s
                  AND app_user_id = %s
                  AND role = 'ADMIN'
                  AND status = 'ACTIVE'
                """,
                (community_id, admin_user_id),
            )
            if not cur.fetchone():
                return {"can_manage": False, "requests": []}

            cur.execute(
                """
                WITH pending_requests AS (
                    SELECT
                        jr.id::text AS request_key,
                        jr.villa_number,
                        jr.requested_at,
                        jr.status,
                        requester.full_name,
                        requester.email,
                        'join_request' AS source
                    FROM community_join_requests jr
                    JOIN app_users requester ON requester.id = jr.app_user_id
                    WHERE jr.community_id = %s AND jr.status = 'PENDING'
                ),
                pending_members AS (
                    SELECT
                        'member:' || cm.id::text AS request_key,
                        cm.villa_number,
                        cm.created_at AS requested_at,
                        cm.status,
                        requester.full_name,
                        requester.email,
                        'member' AS source
                    FROM community_members cm
                    JOIN app_users requester ON requester.id = cm.app_user_id
                    WHERE cm.community_id = %s
                      AND cm.status = 'PENDING'
                      AND NOT EXISTS (
                          SELECT 1
                          FROM community_join_requests jr
                          WHERE jr.community_id = cm.community_id
                            AND jr.app_user_id = cm.app_user_id
                            AND jr.status = 'PENDING'
                      )
                )
                SELECT *
                FROM (
                    SELECT * FROM pending_requests
                    UNION ALL
                    SELECT * FROM pending_members
                ) pending
                ORDER BY requested_at ASC
                """,
                (community_id, community_id),
            )
            pending_rows = cur.fetchall()
            cur.execute(
                """
                SELECT
                    cm.id,
                    cm.villa_number,
                    cm.created_at,
                    cm.status,
                    requester.full_name,
                    requester.email,
                    cm.role
                FROM community_members cm
                JOIN app_users requester ON requester.id = cm.app_user_id
                WHERE cm.community_id = %s
                  AND NOT (cm.role = 'ADMIN' AND cm.status = 'ACTIVE')
                ORDER BY
                    CASE cm.status WHEN 'PENDING' THEN 0 WHEN 'ACTIVE' THEN 1 ELSE 2 END,
                    cm.created_at DESC
                LIMIT 10
                """,
                (community_id,),
            )
            member_rows = cur.fetchall()
            return {
                "can_manage": True,
                "requests": [
                    {
                        "id": row[0],
                        "villa_number": row[1],
                        "requested_at": row[2].isoformat() if row[2] else None,
                        "status": row[3],
                        "requester_name": row[4] or row[5],
                        "requester_email": row[5],
                        "source": row[6],
                    }
                    for row in pending_rows
                ],
                "members": [
                    {
                        "id": str(row[0]),
                        "villa_number": row[1],
                        "created_at": row[2].isoformat() if row[2] else None,
                        "status": row[3],
                        "requester_name": row[4] or row[5],
                        "requester_email": row[5],
                        "role": row[6],
                    }
                    for row in member_rows
                ],
            }
    finally:
        conn.close()


def _resolve_member_request_for_admin(cur, member_request_id, admin_user_id):
    member_id = member_request_id.split("member:", 1)[1]
    cur.execute(
        """
        SELECT
            cm.app_user_id,
            cm.community_id,
            cm.villa_number,
            cm.status,
            admin_member.id
        FROM community_members cm
        JOIN community_members admin_member
            ON admin_member.community_id = cm.community_id
            AND admin_member.app_user_id = %s
            AND admin_member.role = 'ADMIN'
            AND admin_member.status = 'ACTIVE'
        WHERE cm.id = %s
        """,
        (admin_user_id, member_id),
    )
    row = cur.fetchone()
    if not row:
        raise PermissionError("Only an active community admin can manage this request")
    return row


def _resolve_join_request_for_admin(cur, join_request_id, admin_user_id):
    if str(join_request_id).startswith("member:"):
        return _resolve_member_request_for_admin(cur, join_request_id, admin_user_id)
    cur.execute(
        """
        SELECT
            jr.app_user_id,
            jr.community_id,
            jr.villa_number,
            jr.status,
            admin_member.id
        FROM community_join_requests jr
        JOIN community_members admin_member
            ON admin_member.community_id = jr.community_id
            AND admin_member.app_user_id = %s
            AND admin_member.role = 'ADMIN'
            AND admin_member.status = 'ACTIVE'
        WHERE jr.id = %s
        """,
        (admin_user_id, join_request_id),
    )
    row = cur.fetchone()
    if not row:
        raise PermissionError("Only an active community admin can manage this request")
    return row


def approve_join_request(db_conn, join_request_id, admin_user_id):
    ensure_notifications_table(db_conn)
    conn = db_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                is_member_request = str(join_request_id).startswith("member:")
                row = _resolve_join_request_for_admin(cur, join_request_id, admin_user_id)
                requester_user_id, community_id, villa_number, status, admin_member_id = row
                if status == "APPROVED":
                    return {"already_approved": True}
                if status != "PENDING":
                    raise ValueError(f"Join request is {status.lower()}")

                cur.execute(
                    """
                    UPDATE community_members
                    SET status = 'ACTIVE',
                        villa_number = COALESCE(%s, villa_number),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE app_user_id = %s AND community_id = %s
                    """,
                    (villa_number, requester_user_id, community_id),
                )
                if not is_member_request:
                    cur.execute(
                        """
                        UPDATE community_join_requests
                        SET status = 'APPROVED',
                            approved_by_member_id = %s,
                            approved_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (admin_member_id, join_request_id),
                    )
                    cur.execute(
                        """
                        UPDATE app_notifications
                        SET read_at = CURRENT_TIMESTAMP
                        WHERE reference_type = 'community_join_requests'
                          AND reference_id = %s
                          AND notification_type = 'JOIN_APPROVAL'
                        """,
                        (join_request_id,),
                    )
                    cur.execute(
                        """
                        INSERT INTO app_notifications (
                            app_user_id,
                            notification_type,
                            title,
                            body,
                            action_url,
                            reference_type,
                            reference_id
                        )
                        VALUES (
                            %s,
                            'JOIN_APPROVED',
                            'Community request approved',
                            'Your community join request has been approved.',
                            '/community',
                            'community_join_requests',
                            %s
                        )
                        ON CONFLICT (app_user_id, notification_type, reference_type, reference_id)
                        WHERE reference_id IS NOT NULL
                        DO UPDATE SET
                            read_at = NULL,
                            created_at = CURRENT_TIMESTAMP
                        """,
                        (requester_user_id, join_request_id),
                    )
        return {"already_approved": False}
    finally:
        conn.close()


def reject_join_request(db_conn, join_request_id, admin_user_id):
    ensure_notifications_table(db_conn)
    conn = db_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                is_member_request = str(join_request_id).startswith("member:")
                row = _resolve_join_request_for_admin(cur, join_request_id, admin_user_id)
                requester_user_id, community_id, _villa_number, status, admin_member_id = row
                if status == "REJECTED":
                    return {"already_rejected": True}
                if status != "PENDING":
                    raise ValueError(f"Join request is {status.lower()}")

                cur.execute(
                    """
                    UPDATE community_members
                    SET status = 'REJECTED',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE app_user_id = %s AND community_id = %s
                    """,
                    (requester_user_id, community_id),
                )
                if not is_member_request:
                    cur.execute(
                        """
                        UPDATE community_join_requests
                        SET status = 'REJECTED',
                            approved_by_member_id = %s,
                            approved_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (admin_member_id, join_request_id),
                    )
                    cur.execute(
                        """
                        UPDATE app_notifications
                        SET read_at = CURRENT_TIMESTAMP
                        WHERE reference_type = 'community_join_requests'
                          AND reference_id = %s
                          AND notification_type = 'JOIN_APPROVAL'
                        """,
                        (join_request_id,),
                    )
                    cur.execute(
                        """
                        INSERT INTO app_notifications (
                            app_user_id,
                            notification_type,
                            title,
                            body,
                            action_url,
                            reference_type,
                            reference_id
                        )
                        VALUES (
                            %s,
                            'JOIN_REJECTED',
                            'Community request rejected',
                            'Your community join request was rejected.',
                            '/community',
                            'community_join_requests',
                            %s
                        )
                        ON CONFLICT (app_user_id, notification_type, reference_type, reference_id)
                        WHERE reference_id IS NOT NULL
                        DO UPDATE SET
                            read_at = NULL,
                            created_at = CURRENT_TIMESTAMP
                        """,
                        (requester_user_id, join_request_id),
                    )
        return {"already_rejected": False}
    finally:
        conn.close()


def promote_member_to_admin(db_conn, member_id, admin_user_id):
    conn = db_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        target.id,
                        target.community_id,
                        target.role,
                        target.status
                    FROM community_members target
                    JOIN community_members admin_member
                        ON admin_member.community_id = target.community_id
                        AND admin_member.app_user_id = %s
                        AND admin_member.role = 'ADMIN'
                        AND admin_member.status = 'ACTIVE'
                    WHERE target.id = %s
                    """,
                    (admin_user_id, member_id),
                )
                row = cur.fetchone()
                if not row:
                    raise PermissionError("Only an active community admin can promote members")
                _target_id, _community_id, role, status = row
                if role == "ADMIN":
                    return {"already_admin": True}
                if status != "ACTIVE":
                    raise ValueError("Only active members can be promoted to admin")

                cur.execute(
                    """
                    UPDATE community_members
                    SET role = 'ADMIN',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (member_id,),
                )
        return {"already_admin": False}
    finally:
        conn.close()
