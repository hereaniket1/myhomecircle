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
