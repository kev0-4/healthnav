import json
import logging
from datetime import datetime, timedelta

from src.utils.db_connect import get_connection

log = logging.getLogger(__name__)
_TTL_DAYS = 90
_INIT_DONE = False


def _ensure_table() -> None:
    global _INIT_DONE
    if _INIT_DONE:
        return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='review_cache'
        )
        CREATE TABLE dbo.review_cache (
            cache_key  NVARCHAR(200)  NOT NULL PRIMARY KEY,
            data_json  NVARCHAR(MAX)  NOT NULL,
            fetched_at DATETIME2      NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    _INIT_DONE = True


def cache_get(key: str) -> dict | None:
    _ensure_table()
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT data_json, fetched_at FROM dbo.review_cache WHERE cache_key=?", (key,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        if datetime.utcnow() - row[1] > timedelta(days=_TTL_DAYS):
            return None
        return json.loads(row[0])
    except Exception as e:
        log.warning("review_cache get failed: %s", e)
        return None


def cache_set(key: str, data: dict) -> None:
    _ensure_table()
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            MERGE dbo.review_cache AS t
            USING (VALUES (?, ?, ?)) AS s (cache_key, data_json, fetched_at)
               ON t.cache_key = s.cache_key
            WHEN MATCHED     THEN UPDATE SET data_json=s.data_json, fetched_at=s.fetched_at
            WHEN NOT MATCHED THEN INSERT (cache_key, data_json, fetched_at)
                                  VALUES (s.cache_key, s.data_json, s.fetched_at);
        """, (key, json.dumps(data, default=str), datetime.utcnow()))
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning("review_cache set failed: %s", e)
