# 数据访问层: SQLite 为主, 文件 (profile.json / briefings / outbox) 作为镜像与 LLM 工具读写对象。
# 数据库文件 db/news.db, schema 见 db.sql (首次连接自动建表)。

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

import profile_store

BASE = Path(__file__).resolve().parent
DB_DIR = BASE / "db"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "news.db"

_lock = threading.Lock()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    schema = (BASE / "db.sql").read_text(encoding="utf-8")
    conn.executescript(schema)
    conn.commit()


def init_db() -> None:
    with _lock:
        conn = connect()
        try:
            _init_schema(conn)
            # 迁移: 若 profile.json 有内容但表是空的, 灌一条
            row = conn.execute("SELECT COUNT(*) AS c FROM subscriptions").fetchone()
            if row["c"] == 0:
                profile = profile_store.load()
                sub = profile.get("subscription", {})
                ident = profile.get("identity", {})
                conn.execute(
                    """
                    INSERT INTO subscriptions (user_name, user_role, timezone, topics, keywords, excluded,
                                                language, max_items, channel, push_time)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        ident.get("name", ""),
                        ident.get("role", ""),
                        ident.get("timezone", "Asia/Shanghai"),
                        json.dumps(sub.get("topics", [])),
                        json.dumps(sub.get("keywords", [])),
                        json.dumps(sub.get("excluded", [])),
                        sub.get("language", "zh"),
                        sub.get("max_items_per_briefing", 12),
                        "outbox",
                        profile.get("delivery", {}).get("time", "08:00"),
                    ),
                )
                conn.commit()
        finally:
            conn.close()


# ------------------------------------------------- subscriptions
def upsert_subscription(profile: dict) -> int:
    """把 profile dict 写进 subscriptions 表 (单用户示例: 取第一行, 没有则插入)。"""
    ident = profile.get("identity", {})
    sub = profile.get("subscription", {})
    with _lock:
        conn = connect()
        try:
            row = conn.execute(
                "SELECT id FROM subscriptions ORDER BY id LIMIT 1"
            ).fetchone()
            values = (
                ident.get("name", ""),
                ident.get("role", ""),
                ident.get("timezone", "Asia/Shanghai"),
                json.dumps(sub.get("topics", [])),
                json.dumps(sub.get("keywords", [])),
                json.dumps(sub.get("excluded", [])),
                sub.get("language", "zh"),
                sub.get("max_items_per_briefing", 12),
                "outbox",
                profile.get("delivery", {}).get("time", "08:00"),
            )
            if row is None:
                cur = conn.execute(
                    """INSERT INTO subscriptions
                       (user_name,user_role,timezone,topics,keywords,excluded,
                        language,max_items,channel,push_time)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    values,
                )
                sid = cur.lastrowid
            else:
                conn.execute(
                    """UPDATE subscriptions SET user_name=?,user_role=?,timezone=?,topics=?,
                       keywords=?,excluded=?,language=?,max_items=?,channel=?,push_time=?,
                       updated_at=datetime('now') WHERE id=?""",
                    (*values, row["id"]),
                )
                sid = row["id"]
            conn.commit()
            return sid
        finally:
            conn.close()


def list_subscriptions() -> list[dict]:
    with _lock:
        conn = connect()
        try:
            rows = conn.execute("SELECT * FROM subscriptions").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


# ------------------------------------------------- briefings
def record_briefing(briefing: dict) -> None:
    """一次 run_daily 的结果落表 (upsert by date)。"""
    with _lock:
        conn = connect()
        try:
            conn.execute(
                """INSERT INTO briefings
                   (date, file_path, push_path, trace_path, rounds, tool_calls, ai_items)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(date) DO UPDATE SET
                     rounds=excluded.rounds, tool_calls=excluded.tool_calls,
                     ai_items=excluded.ai_items, created_at=datetime('now')""",
                (
                    briefing["date"],
                    briefing["briefing_path"],
                    briefing["push_path"],
                    briefing["trace_path"],
                    briefing.get("llm", {}).get("rounds", 0),
                    briefing.get("llm", {}).get("tool_calls", 0),
                    briefing.get("fetch", {}).get("ai_items", 0),
                ),
            )
            conn.commit()
        finally:
            conn.close()


def list_briefings() -> list[dict]:
    with _lock:
        conn = connect()
        try:
            rows = conn.execute(
                "SELECT * FROM briefings ORDER BY date DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def stats() -> dict:
    with _lock:
        conn = connect()
        try:
            sub = conn.execute("SELECT COUNT(*) AS c FROM subscriptions").fetchone()["c"]
            br = conn.execute("SELECT COUNT(*) AS c FROM briefings").fetchone()["c"]
            return {"db": str(DB_PATH), "subscriptions": sub, "briefings": br}
        finally:
            conn.close()


# 模块加载时确保表存在 (幂等)
init_db()
