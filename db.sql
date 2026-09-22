-- 数据库 schema (SQLite)
-- 用法: 首次运行时自动建表, 也可手动执行本文件。

CREATE TABLE IF NOT EXISTS subscriptions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_name   TEXT NOT NULL DEFAULT '',
    user_role   TEXT NOT NULL DEFAULT '',
    timezone    TEXT NOT NULL DEFAULT 'Asia/Shanghai',
    topics      TEXT NOT NULL DEFAULT '[]',   -- JSON array
    keywords    TEXT NOT NULL DEFAULT '[]',   -- JSON array
    excluded    TEXT NOT NULL DEFAULT '[]',   -- JSON array
    language    TEXT NOT NULL DEFAULT 'zh',
    max_items   INTEGER NOT NULL DEFAULT 12,
    channel     TEXT NOT NULL DEFAULT 'outbox',
    push_time   TEXT NOT NULL DEFAULT '08:00',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS briefings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,                -- YYYY-MM-DD
    file_path   TEXT NOT NULL,                -- briefings/YYYY-MM-DD.md
    push_path   TEXT NOT NULL,                -- outbox/YYYY-MM-DD.json
    trace_path  TEXT NOT NULL,                -- logs/trace-YYYY-MM-DD.json
    rounds      INTEGER NOT NULL DEFAULT 0,   -- LLM 循环轮数
    tool_calls  INTEGER NOT NULL DEFAULT 0,   -- 工具调用次数
    ai_items    INTEGER NOT NULL DEFAULT 0,   -- 抓取到的 AI 新闻条数
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(date)
);

CREATE INDEX IF NOT EXISTS idx_briefings_date ON briefings(date);

