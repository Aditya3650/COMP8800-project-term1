# src/shared/storage.py
from pathlib import Path
import sqlite3
import json
from typing import Iterable, Dict, Any, Optional

DB_PATH = Path(__file__).resolve().parents[2] / "events.db"  # repo_root/events.db

def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    p = Path(db_path) if db_path else DB_PATH
    conn = sqlite3.connect(p)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY,
  log_type TEXT NOT NULL,           -- System | Security | Application
  event_id INTEGER NOT NULL,
  source TEXT,
  time TEXT NOT NULL,               -- ISO string
  category INTEGER,
  record INTEGER NOT NULL,          -- RecordNumber
  event_type INTEGER,
  message_json TEXT                 -- JSON-encoded array
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_events_log_record ON events(log_type, record);
CREATE INDEX IF NOT EXISTS ix_events_time ON events(time);
CREATE INDEX IF NOT EXISTS ix_events_event_id ON events(event_id);

CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY,
  rule TEXT NOT NULL,
  severity TEXT NOT NULL,           -- info | warn | critical
  time TEXT NOT NULL,               -- ISO string
  context_json TEXT                 -- JSON payload
);
"""

def init_db(conn: Optional[sqlite3.Connection] = None):
    own = False
    if conn is None:
        conn, own = connect(), True
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        if own:
            conn.close()

def insert_events(log_type: str, events: Iterable[Dict[str, Any]], db_path: Optional[Path] = None) -> int:
    conn = connect(db_path)
    try:
        cur = conn.cursor()
        rows = [
            (
                log_type,
                e.get("EventID"),
                e.get("Source"),
                e.get("Time"),
                e.get("Category"),
                e.get("Record"),
                e.get("EventType"),
                json.dumps(e.get("Message") or [])
            )
            for e in events
        ]
        cur.executemany(
            """
            INSERT OR IGNORE INTO events
            (log_type, event_id, source, time, category, record, event_type, message_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows
        )
        conn.commit()
        return cur.rowcount  # inserted (ignored rows don't count)
    finally:
        conn.close()

def fetch_latest(limit: int = 50, log_types: Optional[list[str]] = None, event_id: Optional[int] = None):
    conn = connect()
    try:
        q = "SELECT log_type, time, event_id, source, message_json FROM events"
        conds, params = [], []
        if log_types:
            conds.append(f"log_type IN ({','.join('?'*len(log_types))})")
            params.extend(log_types)
        if event_id is not None:
            conds.append("event_id = ?")
            params.append(event_id)
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY datetime(time) DESC LIMIT ?"
        params.append(limit)
        cur = conn.execute(q, params)
        rows = [
            {
                "log_type": lt, "time": t, "event_id": eid, "source": s,
                "message": json.loads(msg) if msg else []
            }
            for (lt, t, eid, s, msg) in cur.fetchall()
        ]
        return rows
    finally:
        conn.close()

def fetch_stats():
    conn = connect()
    try:
        # counts + timeframe per log_type
        cur = conn.execute("""
          SELECT log_type,
                 COUNT(*) as cnt,
                 MIN(time) as oldest,
                 MAX(time) as newest
          FROM events
          GROUP BY log_type
        """)
        stats = []
        total = 0
        for lt, cnt, oldest, newest in cur.fetchall():
            stats.append({"log_type": lt, "count": cnt, "range": f"{oldest or 'N/A'} → {newest or 'N/A'}"})
            total += cnt
        return stats, total
    finally:
        conn.close()
