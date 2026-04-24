import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from export_pack import sha256_bytes

DB_PATH = Path("gallop.db")
FILES_ROOT = Path("data_files")

MODE_ALIASES = {
    "sealed": "source_fact",
    "non_sealed": "narrative",
}


def normalize_integrity_mode(mode: str | None) -> str:
    return MODE_ALIASES.get((mode or "").strip(), (mode or "").strip())


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str):
    if column not in _table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
    

def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS orgs (
                org_id TEXT PRIMARY KEY,
                org_name TEXT NOT NULL UNIQUE,
                org_type TEXT
            );

            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                org_id TEXT NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (org_id) REFERENCES orgs(org_id)
            );

            CREATE TABLE IF NOT EXISTS records (
                record_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                case_title TEXT NOT NULL,
                owner_org_id TEXT NOT NULL,
                review_coordinator_name TEXT,
                review_coordinator_email TEXT,
                review_coordinator_note TEXT,
                integrity_mode TEXT NOT NULL,
                mode_origin TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_activity_at TEXT,
                submitted_at TEXT,
                sealed_at TEXT,
                manifest_hash TEXT,
                downgraded_at TEXT,
                downgraded_by TEXT,
                downgrade_reason TEXT,
                supersedes_record_id TEXT,
                superseded_at TEXT,
                FOREIGN KEY (owner_org_id) REFERENCES orgs(org_id)
            );

            CREATE TABLE IF NOT EXISTS evidences (
                evidence_id TEXT PRIMARY KEY,
                record_id TEXT NOT NULL,
                evidence_type TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                link_type TEXT NOT NULL,
                link_id TEXT,
                FOREIGN KEY (record_id) REFERENCES records(record_id)
            );
            -- geo anchors table (record-scoped for MVP)
            CREATE TABLE IF NOT EXISTS geos (
                geo_id TEXT PRIMARY KEY,
                record_id TEXT NOT NULL,

                anchor_type TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY (record_id) REFERENCES records(record_id)
            );
            -- nodes table (record-scoped for MVP)
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                record_id TEXT NOT NULL,

                name TEXT NOT NULL,
                registration_number TEXT,
                type TEXT,
                country TEXT,
                batch_method TEXT,
                third_party_cert TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY (record_id) REFERENCES records(record_id)
            );
            -- txns table (schema-aligned, minimal but expandable)
            CREATE TABLE IF NOT EXISTS txns (
                txn_id TEXT PRIMARY KEY,
                record_id TEXT NOT NULL,

                -- Row 1: Sales / Output
                product_name TEXT,
                output_node_name TEXT,
                species_common TEXT,
                species_latin TEXT,
                product_weight REAL,
                product_volume REAL,
                geo_id TEXT,

                -- Row 2: Procurement & Production
                input_node_name TEXT,
                reporting_node_name TEXT,
                quantity_unit TEXT,
                input_quantity REAL,
                output_quantity REAL,
                production_start_date TEXT,
                production_end_date TEXT,
                batch_label TEXT,

                -- Row 3: Assessment
                assessment_risk_level TEXT,
                assessment_conclusion TEXT,

                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY (record_id) REFERENCES records(record_id)
            );
            """
        )
        _ensure_column(conn, "records", "mode_origin", "TEXT")
        _ensure_column(conn, "orgs", "org_type", "TEXT")
        _ensure_column(conn, "records", "review_coordinator_name", "TEXT")
        _ensure_column(conn, "records", "review_coordinator_email", "TEXT")
        _ensure_column(conn, "records", "review_coordinator_note", "TEXT")
        _ensure_column(conn, "records", "last_activity_at", "TEXT")
        _ensure_column(conn, "records", "submitted_at", "TEXT")
        _ensure_column(conn, "records", "downgraded_at", "TEXT")
        _ensure_column(conn, "records", "downgraded_by", "TEXT")
        _ensure_column(conn, "records", "downgrade_reason", "TEXT")
        _ensure_column(conn, "records", "supersedes_record_id", "TEXT")
        _ensure_column(conn, "records", "superseded_at", "TEXT")
        _ensure_column(conn, "txns", "output_node_name", "TEXT")
        _ensure_column(conn, "txns", "species_latin", "TEXT")
        _ensure_column(conn, "txns", "product_weight", "REAL")
        _ensure_column(conn, "txns", "product_volume", "REAL")
        _ensure_column(conn, "txns", "input_node_name", "TEXT")
        _ensure_column(conn, "txns", "reporting_node_name", "TEXT")
        _ensure_column(conn, "txns", "quantity_unit", "TEXT")
        _ensure_column(conn, "txns", "input_quantity", "REAL")
        _ensure_column(conn, "txns", "output_quantity", "REAL")
        _ensure_column(conn, "txns", "production_start_date", "TEXT")
        _ensure_column(conn, "txns", "production_end_date", "TEXT")
        _ensure_column(conn, "txns", "batch_label", "TEXT")
        _ensure_column(conn, "txns", "assessment_risk_level", "TEXT")
        _ensure_column(conn, "txns", "assessment_conclusion", "TEXT")
        _ensure_column(conn, "txns", "input_node_id", "TEXT")
        _ensure_column(conn, "txns", "reporting_node_id", "TEXT")
        _ensure_column(conn, "txns", "output_node_id", "TEXT")
        _ensure_column(conn, "nodes", "address_production", "TEXT")
        _ensure_column(conn, "nodes", "address_registration", "TEXT")

        conn.execute(
            """
            UPDATE records
            SET integrity_mode = CASE
                WHEN integrity_mode = 'sealed' THEN 'source_fact'
                WHEN integrity_mode = 'non_sealed' THEN 'narrative'
                ELSE integrity_mode
            END
            """
        )
        conn.execute(
            """
            UPDATE records
            SET mode_origin = COALESCE(
                mode_origin,
                CASE
                    WHEN integrity_mode IN ('source_fact', 'narrative') THEN integrity_mode
                    ELSE 'narrative'
                END
            )
            """
        )
        conn.execute(
            """
            UPDATE records
            SET last_activity_at = COALESCE(last_activity_at, created_at)
            """
        )


def touch_record_activity(record_id: str, conn: sqlite3.Connection | None = None):
    activity_ts = now_iso()
    if conn is not None:
        conn.execute(
            "UPDATE records SET last_activity_at=? WHERE record_id=?",
            (activity_ts, record_id),
        )
        return

    with get_conn() as own_conn:
        own_conn.execute(
            "UPDATE records SET last_activity_at=? WHERE record_id=?",
            (activity_ts, record_id),
        )

def seed_demo_data(hash_password_fn):
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
        if row["c"] > 0:
            return

        conn.execute(
            "INSERT OR IGNORE INTO orgs(org_id, org_name, org_type) VALUES (?,?,?)",
            ("ORG_BUYER", "Buyer Org", "trader"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO orgs(org_id, org_name, org_type) VALUES (?,?,?)",
            ("ORG_OTHER", "Other Org", "processor"),
        )

        pw = hash_password_fn("demo123")
        users = [
            ("buyer@demo", "Buyer User", "ORG_BUYER", "participant"),
            ("viewer@demo", "DDS Viewer", "ORG_BUYER", "dds_viewer"),
            ("other@demo", "Other Org User", "ORG_OTHER", "participant"),
        ]
        for email, name, org, role in users:
            conn.execute(
                "INSERT INTO users VALUES (?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), email, name, pw, org, role, "active", now_iso()),
            )


def get_user_by_email(email: str):
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT u.*, o.org_name, o.org_type
            FROM users u
            LEFT JOIN orgs o ON o.org_id = u.org_id
            WHERE u.email=?
            """,
            (email.strip().lower(),),
        ).fetchone()


def list_orgs():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM orgs ORDER BY org_name ASC"
        ).fetchall()


def list_users():
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT u.*, o.org_name, o.org_type
            FROM users u
            LEFT JOIN orgs o ON o.org_id = u.org_id
            ORDER BY u.created_at DESC
            """
        ).fetchall()


def create_user(email: str, name: str, password_hash: str, org_id: str, role: str, status: str = "active") -> str:
    user_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO users(user_id, email, name, password_hash, org_id, role, status, created_at)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                user_id,
                email.strip().lower(),
                name.strip(),
                password_hash,
                org_id,
                role,
                status,
                now_iso(),
            ),
        )
    return user_id


def ensure_org(org_id: str, org_name: str, org_type: str | None = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO orgs(org_id, org_name, org_type) VALUES (?, ?, ?)",
            (org_id, org_name, org_type),
        )
        if org_type is not None:
            conn.execute(
                "UPDATE orgs SET org_type=? WHERE org_id=?",
                (org_type, org_id),
            )


def update_org_type(org_id: str, org_type: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE orgs SET org_type=? WHERE org_id=?",
            (org_type or None, org_id),
        )


def admin_exists() -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE role='admin'"
        ).fetchone()
        return bool(row["c"])


def update_user_status(user_id: str, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET status=? WHERE user_id=?",
            (status, user_id),
        )


def update_user_password(user_id: str, password_hash: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET password_hash=? WHERE user_id=?",
            (password_hash, user_id),
        )


def delete_user(user_id: str):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM users WHERE user_id=?",
            (user_id,),
        )


def list_records_for_org(org_id: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM records WHERE owner_org_id=? ORDER BY created_at DESC",
            (org_id,),
        ).fetchall()


def get_record_for_org(record_id: str, org_id: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM records WHERE record_id=? AND owner_org_id=?",
            (record_id, org_id),
        ).fetchone()


def create_record(case_title: str, integrity_mode: str, org_id: str) -> str:
    record_id = str(uuid.uuid4())
    case_id = str(uuid.uuid4())
    normalized_mode = normalize_integrity_mode(integrity_mode)
    case_title = (case_title or "").strip() or "Regular DDS Package"

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO records(
                record_id,
                case_id,
                case_title,
                owner_org_id,
                review_coordinator_name,
                review_coordinator_email,
                review_coordinator_note,
                integrity_mode,
                mode_origin,
                status,
                created_at,
                last_activity_at,
                submitted_at,
                sealed_at,
                manifest_hash,
                downgraded_at,
                downgraded_by,
                downgrade_reason,
                supersedes_record_id,
                superseded_at
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                record_id,
                case_id,
                case_title,
                org_id,
                None,
                None,
                None,
                normalized_mode,
                normalized_mode,
                "draft",
                now_iso(),
                now_iso(),
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            ),
        )
    return record_id


def update_record_contact(record_id: str, org_id: str, coordinator_name: str, coordinator_email: str, coordinator_note: str):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE records
            SET
                review_coordinator_name=?,
                review_coordinator_email=?,
                review_coordinator_note=?,
                last_activity_at=?
            WHERE record_id=? AND owner_org_id=?
            """,
            (
                (coordinator_name or "").strip() or None,
                (coordinator_email or "").strip() or None,
                (coordinator_note or "").strip() or None,
                now_iso(),
                record_id,
                org_id,
            ),
        )


def list_txns(record_id: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM txns WHERE record_id=? ORDER BY created_at ASC",
            (record_id,),
        ).fetchall()

def replace_txns(record_id: str, rows: list[dict]):
    """
    MVP approach: replace all txns under this record with provided rows.
    """
    now = now_iso()
    with get_conn() as conn:
        conn.execute("DELETE FROM txns WHERE record_id=?", (record_id,))
        for r in rows:
            txn_id = r.get("txn_id") or str(uuid.uuid4())

            # Minimal guard: if user leaves everything blank, skip row
            if not ((r.get("product_name") or "").strip() or (r.get("output_node_name") or "").strip()):
                continue

            conn.execute(
                """
                INSERT INTO txns(
                    txn_id, record_id,
                    product_name, output_node_name, species_common, species_latin,
                    product_weight, product_volume, geo_id,
                    input_node_name, reporting_node_name, input_node_id, reporting_node_id, output_node_id, quantity_unit, input_quantity, output_quantity,
                    production_start_date, production_end_date, batch_label,
                    assessment_risk_level, assessment_conclusion,
                    created_at, updated_at
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    txn_id, record_id,
                    (r.get("product_name") or "").strip() or None,
                    (r.get("output_node_name") or "").strip() or None,
                    (r.get("species_common") or "").strip() or None,
                    (r.get("species_latin") or "").strip() or None,
                    r.get("product_weight"),
                    r.get("product_volume"),
                    (r.get("geo_id") or "").strip() or None,
                    (r.get("input_node_name") or "").strip() or None,
                    (r.get("reporting_node_name") or "").strip() or None,
                    (r.get("input_node_id") or "").strip() or None,
                    (r.get("reporting_node_id") or "").strip() or None,
                    (r.get("output_node_id") or "").strip() or None,
                    (r.get("quantity_unit") or "").strip() or None,
                    r.get("input_quantity"),
                    r.get("output_quantity"),
                    (r.get("production_start_date") or "").strip() or None,
                    (r.get("production_end_date") or "").strip() or None,
                    (r.get("batch_label") or "").strip() or None,
                    (r.get("assessment_risk_level") or "").strip() or None,
                    (r.get("assessment_conclusion") or "").strip() or None,
                    now,
                    now,
                ),
            )
        touch_record_activity(record_id, conn)


def list_nodes(record_id: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM nodes WHERE record_id=? ORDER BY created_at ASC",
            (record_id,),
        ).fetchall()

def update_nodes(record_id: str, rows: list[dict]):
    """
    Update editable node fields for nodes under this record.
    """
    now = now_iso()
    with get_conn() as conn:
        for r in rows:
            node_id = (r.get("node_id") or "").strip()
            if not node_id:
                continue

            conn.execute(
                """
                UPDATE nodes
                SET
                    registration_number=?,
                    type=?,
                    address_production=?,
                    address_registration=?,
                    country=?,
                    batch_method=?,
                    third_party_cert=?,
                    updated_at=?
                WHERE node_id=? AND record_id=?
                """,
                (
                    (r.get("registration_number") or "").strip() or None,
                    (r.get("type") or "").strip() or None,
                    (r.get("address_production") or "").strip() or None,
                    (r.get("address_registration") or "").strip() or None,
                    (r.get("country") or "").strip() or None,
                    (r.get("batch_method") or "").strip() or None,
                    (r.get("third_party_cert") or "").strip() or None,
                    now,
                    node_id,
                    record_id,
                ),
            )
        touch_record_activity(record_id, conn)

def create_node(record_id: str, name: str) -> str:
    nm = (name or "").strip()
    if not nm:
        return ""

    node_id = str(uuid.uuid4())
    now = now_iso()

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO nodes(node_id, record_id, name, registration_number, type, country, batch_method, third_party_cert, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (node_id, record_id, nm, None, None, None, None, None, now, now),
        )

    return node_id


def upsert_node_by_name(record_id: str, name: str) -> str:
    nm = (name or "").strip()
    if not nm:
        return ""

    with get_conn() as conn:
        row = conn.execute(
            "SELECT node_id FROM nodes WHERE record_id=? AND lower(name)=lower(?)",
            (record_id, nm),
        ).fetchone()

        if row:
            return row["node_id"]

    return create_node(record_id, nm)


def update_txn_node_ids(txn_id: str, record_id: str, input_node_id: str | None, reporting_node_id: str | None, output_node_id: str | None):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE txns
            SET input_node_id=?, reporting_node_id=?, output_node_id=?, updated_at=?
            WHERE txn_id=? AND record_id=?
            """,
            (input_node_id, reporting_node_id, output_node_id, now_iso(), txn_id, record_id),
        )
        touch_record_activity(record_id, conn)


def resolve_nodes_for_record(record_id: str):
    txns = list_txns(record_id)

    for t in txns:
        in_name = (t["input_node_name"] or "").strip()
        reporting_name = (t["reporting_node_name"] or "").strip()
        out_name = (t["output_node_name"] or "").strip()

        in_id = upsert_node_by_name(record_id, in_name) if in_name else None
        reporting_id = upsert_node_by_name(record_id, reporting_name) if reporting_name else None
        out_id = upsert_node_by_name(record_id, out_name) if out_name else None

        update_txn_node_ids(
            txn_id=t["txn_id"],
            record_id=record_id,
            input_node_id=in_id,
            reporting_node_id=reporting_id,
            output_node_id=out_id,
        )

def list_geos(record_id: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM geos WHERE record_id=? ORDER BY created_at ASC",
            (record_id,),
        ).fetchall()


def insert_geo(record_id: str, anchor_type: str, original_name: str, content_bytes: bytes) -> str:
    geo_id = str(uuid.uuid4())
    now = now_iso()

    safe_name = original_name.replace("/", "_").replace("\\", "_")
    out_dir = FILES_ROOT / record_id / "geo"
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / f"{geo_id}__{safe_name}"
    file_path.write_bytes(content_bytes)

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO geos(geo_id, record_id, anchor_type, file_name, file_path, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (geo_id, record_id, anchor_type, safe_name, str(file_path), now, now),
        )
        touch_record_activity(record_id, conn)

    return geo_id

def list_evidences(record_id: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM evidences WHERE record_id=? ORDER BY uploaded_at DESC",
            (record_id,),
        ).fetchall()


def insert_evidence(
    record_id: str,
    evidence_type: str,
    original_name: str,
    content_bytes: bytes,
    link_type: str,
    link_id: str | None,
):
    evidence_id = str(uuid.uuid4())
    uploaded_at = now_iso()
    file_hash = sha256_bytes(content_bytes)

    safe_name = original_name.replace("/", "_").replace("\\", "_")
    out_dir = FILES_ROOT / record_id / "evidence"
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / f"{evidence_id}__{safe_name}"
    file_path.write_bytes(content_bytes)

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO evidences VALUES (?,?,?,?,?,?,?,?,?)",
            (
                evidence_id,
                record_id,
                evidence_type,
                safe_name,
                str(file_path),
                uploaded_at,
                file_hash,
                link_type,
                link_id,
            ),
        )
        touch_record_activity(record_id, conn)


def update_evidence_link(
    evidence_id: str,
    record_id: str,
    evidence_type: str,
    link_type: str,
    link_id: str | None,
):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE evidences
            SET evidence_type=?, link_type=?, link_id=?
            WHERE evidence_id=? AND record_id=?
            """,
            (evidence_type, link_type, link_id, evidence_id, record_id),
        )
        touch_record_activity(record_id, conn)




def submit_record(record_id: str, org_id: str, manifest_hash: str):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE records
            SET status='submitted', submitted_at=?, manifest_hash=?, last_activity_at=?
            WHERE record_id=? AND owner_org_id=? AND integrity_mode='narrative'
            """,
            (now_iso(), manifest_hash, now_iso(), record_id, org_id),
        )


def seal_record(record_id: str, org_id: str, manifest_hash: str):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE records
            SET status='sealed', sealed_at=?, manifest_hash=?, last_activity_at=?
            WHERE record_id=? AND owner_org_id=? AND integrity_mode='source_fact'
            """,
            (now_iso(), manifest_hash, now_iso(), record_id, org_id),
        )


def downgrade_record(record_id: str, org_id: str, actor: str, reason: str):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE records
            SET
                integrity_mode='narrative',
                downgraded_at=?,
                downgraded_by=?,
                downgrade_reason=?,
                submitted_at=NULL,
                sealed_at=NULL,
                manifest_hash=NULL,
                status='draft',
                last_activity_at=?
            WHERE record_id=?
              AND owner_org_id=?
              AND integrity_mode='source_fact'
              AND status='draft'
            """,
            (now_iso(), actor, reason.strip(), now_iso(), record_id, org_id),
        )
