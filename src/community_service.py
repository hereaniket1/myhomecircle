from typing import Any


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _community_row_to_dict(row):
    if not row:
        return None
    return {
        "id": str(row[0]),
        "name": row[1],
        "status": row[2],
        "created_at": row[3].isoformat() if row[3] else None,
        "address": {
            "id": str(row[4]) if row[4] else None,
            "address_line_1": row[5],
            "address_line_2": row[6],
            "locality": row[7],
            "city": row[8],
            "state": row[9],
            "postal_code": row[10],
            "country": row[11],
        },
    }


def _member_row_to_dict(row):
    if not row:
        return None
    return {
        "id": str(row[0]),
        "app_user_id": str(row[1]),
        "community_id": str(row[2]),
        "villa_number": row[3],
        "role": row[4],
        "status": row[5],
        "created_at": row[6].isoformat() if row[6] else None,
    }


def get_user_home_summary(db_conn, app_user_id: str):
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    cm.villa_number,
                    cm.role,
                    cm.status,
                    c.id,
                    c.name
                FROM community_members cm
                JOIN communities c ON c.id = cm.community_id
                WHERE cm.app_user_id = %s
                ORDER BY
                    CASE cm.status WHEN 'ACTIVE' THEN 0 WHEN 'PENDING' THEN 1 ELSE 2 END,
                    cm.created_at DESC
                LIMIT 1
                """,
                (app_user_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "villa_number": row[0],
                "role": row[1],
                "status": row[2],
                "community": {
                    "id": str(row[3]),
                    "name": row[4],
                },
            }
    finally:
        conn.close()


def list_communities(db_conn, search: str = "", limit: int = 50):
    search = _clean(search)
    limit = max(1, min(int(limit or 50), 100))

    where = ""
    params = []
    if search:
        like = f"%{search}%"
        where = """
            WHERE c.name ILIKE %s
               OR a.address_line_1 ILIKE %s
               OR COALESCE(a.address_line_2, '') ILIKE %s
               OR COALESCE(a.locality, '') ILIKE %s
               OR COALESCE(a.city, '') ILIKE %s
               OR COALESCE(a.state, '') ILIKE %s
               OR COALESCE(a.postal_code, '') ILIKE %s
        """
        params.extend([like, like, like, like, like, like, like])

    query = f"""
        SELECT
            c.id,
            c.name,
            c.status,
            c.created_at,
            a.id,
            a.address_line_1,
            a.address_line_2,
            a.locality,
            a.city,
            a.state,
            a.postal_code,
            a.country
        FROM communities c
        LEFT JOIN addresses a ON a.id = c.address_id
        {where}
        ORDER BY c.created_at DESC, c.name ASC
        LIMIT %s
    """
    params.append(limit)

    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            return [_community_row_to_dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def get_community_detail(db_conn, community_id: str, app_user_id: str | None = None):
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    c.id,
                    c.name,
                    c.status,
                    c.created_at,
                    a.id,
                    a.address_line_1,
                    a.address_line_2,
                    a.locality,
                    a.city,
                    a.state,
                    a.postal_code,
                    a.country
                FROM communities c
                LEFT JOIN addresses a ON a.id = c.address_id
                WHERE c.id = %s
                """,
                (community_id,),
            )
            community = _community_row_to_dict(cur.fetchone())
            if not community:
                return None

            cur.execute(
                """
                SELECT
                    COALESCE(cs.require_admin_approval, TRUE),
                    COALESCE(cs.allow_anonymous_reviews, TRUE),
                    COALESCE(cs.allow_vendor_visibility, TRUE),
                    COALESCE(cs.points_enabled, TRUE),
                    COUNT(cm.id) FILTER (WHERE cm.role = 'ADMIN' AND cm.status = 'ACTIVE') AS active_admin_count,
                    COUNT(cm.id) FILTER (WHERE cm.status = 'ACTIVE') AS active_member_count
                FROM communities c
                LEFT JOIN community_settings cs ON cs.community_id = c.id
                LEFT JOIN community_members cm ON cm.community_id = c.id
                WHERE c.id = %s
                GROUP BY cs.require_admin_approval, cs.allow_anonymous_reviews, cs.allow_vendor_visibility, cs.points_enabled
                """,
                (community_id,),
            )
            settings = cur.fetchone()
            active_admin_count = settings[4] if settings else 0
            community["settings"] = {
                "require_admin_approval": settings[0] if settings else True,
                "allow_anonymous_reviews": settings[1] if settings else True,
                "allow_vendor_visibility": settings[2] if settings else True,
                "points_enabled": settings[3] if settings else True,
            }
            community["active_admin_count"] = active_admin_count
            community["active_member_count"] = settings[5] if settings else 0
            community["can_choose_admin"] = active_admin_count == 0

            community["current_member"] = None
            if app_user_id:
                cur.execute(
                    """
                    SELECT id, app_user_id, community_id, villa_number, role, status, created_at
                    FROM community_members
                    WHERE community_id = %s AND app_user_id = %s
                    """,
                    (community_id, app_user_id),
                )
                community["current_member"] = _member_row_to_dict(cur.fetchone())
            return community
    finally:
        conn.close()


def join_community(db_conn, community_id: str, app_user_id: str, payload: dict[str, Any]):
    requested_role = _clean(payload.get("role")).upper() or "RESIDENT"
    villa_number = _clean(payload.get("villa_number")) or None
    require_admin_approval = bool(payload.get("require_admin_approval", True))
    allow_anonymous_reviews = bool(payload.get("allow_anonymous_reviews", True))
    allow_vendor_visibility = bool(payload.get("allow_vendor_visibility", True))
    points_enabled = bool(payload.get("points_enabled", True))
    if requested_role not in {"RESIDENT", "ADMIN"}:
        raise ValueError("role must be RESIDENT or ADMIN")
    if not villa_number:
        raise ValueError("Villa / flat number is required")

    conn = db_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM communities WHERE id = %s", (community_id,))
                if not cur.fetchone():
                    raise LookupError("Community not found")

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM community_members
                    WHERE community_id = %s AND role = 'ADMIN' AND status = 'ACTIVE'
                    """,
                    (community_id,),
                )
                has_admin = cur.fetchone()[0] > 0
                role = "ADMIN" if requested_role == "ADMIN" and not has_admin else "RESIDENT"

                cur.execute(
                    """
                    INSERT INTO community_settings (
                        community_id,
                        require_admin_approval,
                        allow_anonymous_reviews,
                        allow_vendor_visibility,
                        points_enabled
                    )
                    VALUES (%s, TRUE, TRUE, TRUE, TRUE)
                    ON CONFLICT (community_id) DO NOTHING
                    """,
                    (community_id,),
                )
                if role == "ADMIN":
                    status = "ACTIVE"
                    cur.execute(
                        """
                        UPDATE community_settings
                        SET require_admin_approval = %s,
                            allow_anonymous_reviews = %s,
                            allow_vendor_visibility = %s,
                            points_enabled = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE community_id = %s
                        """,
                        (
                            require_admin_approval,
                            allow_anonymous_reviews,
                            allow_vendor_visibility,
                            points_enabled,
                            community_id,
                        ),
                    )
                else:
                    cur.execute(
                        "SELECT require_admin_approval FROM community_settings WHERE community_id = %s",
                        (community_id,),
                    )
                    approval_required = cur.fetchone()[0]
                    status = "PENDING" if approval_required and has_admin else "ACTIVE"

                cur.execute(
                    """
                    INSERT INTO community_members (app_user_id, community_id, villa_number, role, status)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (app_user_id, community_id) DO UPDATE
                    SET villa_number = EXCLUDED.villa_number,
                        status = EXCLUDED.status,
                        role = EXCLUDED.role,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id, app_user_id, community_id, villa_number, role, status, created_at
                    """,
                    (app_user_id, community_id, villa_number, role, status),
                )
                member = _member_row_to_dict(cur.fetchone())

                join_request_id = None
                if status == "PENDING":
                    cur.execute(
                        """
                        INSERT INTO community_join_requests (app_user_id, community_id, villa_number, status)
                        VALUES (%s, %s, %s, 'PENDING')
                        ON CONFLICT (app_user_id, community_id) DO UPDATE
                        SET villa_number = EXCLUDED.villa_number,
                            status = 'PENDING',
                            updated_at = CURRENT_TIMESTAMP
                        RETURNING id
                        """,
                        (app_user_id, community_id, villa_number),
                    )
                    join_request_id = cur.fetchone()[0]
        return {
            "member": member,
            "join_request_id": str(join_request_id) if join_request_id else None,
            "message": "You are now an admin for this community."
            if member["role"] == "ADMIN"
            else ("Your join request is pending admin approval." if member["status"] == "PENDING" else "You have joined this community."),
        }
    finally:
        conn.close()


def find_existing_communities(db_conn, payload: dict[str, Any], limit: int = 10):
    name = _clean(payload.get("name"))
    address_line_1 = _clean(payload.get("address_line_1"))
    locality = _clean(payload.get("locality"))
    city = _clean(payload.get("city"))
    state = _clean(payload.get("state"))
    postal_code = _clean(payload.get("postal_code"))

    terms = [term for term in [name, address_line_1, locality, city, state, postal_code] if term]
    if not terms:
        return []

    clauses = []
    params = []
    if name:
        clauses.append("(LOWER(c.name) = LOWER(%s) OR c.name ILIKE %s)")
        params.extend([name, f"%{name}%"])
    if address_line_1:
        clauses.append("a.address_line_1 ILIKE %s")
        params.append(f"%{address_line_1}%")
    if locality and city:
        clauses.append("(COALESCE(a.locality, '') ILIKE %s AND COALESCE(a.city, '') ILIKE %s)")
        params.extend([f"%{locality}%", f"%{city}%"])
    if postal_code:
        clauses.append("COALESCE(a.postal_code, '') = %s")
        params.append(postal_code)
    if not clauses:
        return []

    params.append(max(1, min(int(limit or 10), 25)))
    query = f"""
        SELECT
            c.id,
            c.name,
            c.status,
            c.created_at,
            a.id,
            a.address_line_1,
            a.address_line_2,
            a.locality,
            a.city,
            a.state,
            a.postal_code,
            a.country
        FROM communities c
        LEFT JOIN addresses a ON a.id = c.address_id
        WHERE {" OR ".join(clauses)}
        ORDER BY
            CASE WHEN LOWER(c.name) = LOWER(%s) THEN 0 ELSE 1 END,
            c.created_at DESC
        LIMIT %s
    """
    params.insert(-1, name or "")

    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            return [_community_row_to_dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def register_community(db_conn, payload: dict[str, Any]):
    name = _clean(payload.get("name"))
    address_line_1 = _clean(payload.get("address_line_1"))
    address_line_2 = _clean(payload.get("address_line_2"))
    locality = _clean(payload.get("locality"))
    city = _clean(payload.get("city"))
    state = _clean(payload.get("state"))
    postal_code = _clean(payload.get("postal_code"))
    country = _clean(payload.get("country")) or "India"

    if not name or not address_line_1 or not city or not state or not postal_code:
        raise ValueError("community name, address line 1, city, state, and postal code are required")

    existing = find_existing_communities(db_conn, payload, limit=5)
    if existing:
        return {"created": False, "matches": existing}

    conn = db_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO addresses (
                        address_line_1,
                        address_line_2,
                        locality,
                        city,
                        state,
                        postal_code,
                        country
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        address_line_1,
                        address_line_2 or None,
                        locality or None,
                        city,
                        state,
                        postal_code,
                        country,
                    ),
                )
                address_id = cur.fetchone()[0]
                cur.execute(
                    """
                    INSERT INTO communities (name, address_id, status)
                    VALUES (%s, %s, 'ACTIVE')
                    RETURNING id
                    """,
                    (name, address_id),
                )
                community_id = cur.fetchone()[0]
                cur.execute(
                    """
                    SELECT
                        c.id,
                        c.name,
                        c.status,
                        c.created_at,
                        a.id,
                        a.address_line_1,
                        a.address_line_2,
                        a.locality,
                        a.city,
                        a.state,
                        a.postal_code,
                        a.country
                    FROM communities c
                    LEFT JOIN addresses a ON a.id = c.address_id
                    WHERE c.id = %s
                    """,
                    (community_id,),
                )
                community = _community_row_to_dict(cur.fetchone())
        return {"created": True, "community": community}
    finally:
        conn.close()
