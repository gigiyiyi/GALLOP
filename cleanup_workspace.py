from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from db import DB_PATH, FILES_ROOT, get_conn


RETENTION_DAYS = 30


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def list_expired_records(retention_days: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    expired = []
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT record_id, case_title, status, created_at, last_activity_at
            FROM records
            """
        ).fetchall()

    for row in rows:
        last_seen = parse_iso(row["last_activity_at"]) or parse_iso(row["created_at"])
        if last_seen and last_seen <= cutoff:
            expired.append(dict(row))
    return expired


def delete_record(record_id: str):
    record_dir = FILES_ROOT / record_id
    with get_conn() as conn:
        conn.execute("DELETE FROM evidences WHERE record_id=?", (record_id,))
        conn.execute("DELETE FROM geos WHERE record_id=?", (record_id,))
        conn.execute("DELETE FROM nodes WHERE record_id=?", (record_id,))
        conn.execute("DELETE FROM txns WHERE record_id=?", (record_id,))
        conn.execute("DELETE FROM records WHERE record_id=?", (record_id,))

    if record_dir.exists():
        shutil.rmtree(record_dir)


def main():
    parser = argparse.ArgumentParser(description="Purge GALLOP MVP workspace data that has been inactive beyond the retention window.")
    parser.add_argument("--retention-days", type=int, default=RETENTION_DAYS)
    parser.add_argument("--apply", action="store_true", help="Delete expired records instead of only listing them.")
    args = parser.parse_args()

    expired = list_expired_records(args.retention_days)
    if not expired:
        print("No expired records found.")
        return

    print(f"Found {len(expired)} expired record(s) in {DB_PATH} based on last_activity_at and a {args.retention_days}-day retention window.")
    for row in expired:
        print(f"- {row['record_id']} | {row['status']} | {row['case_title']} | last_activity_at={row['last_activity_at']}")

    if not args.apply:
        print("Dry run only. Re-run with --apply to delete expired records and files.")
        return

    for row in expired:
        delete_record(row["record_id"])
    print("Expired records deleted.")


if __name__ == "__main__":
    main()
