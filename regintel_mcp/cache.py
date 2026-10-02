"""SQLite cache. Raw API JSON is stored verbatim; derived fields sit beside it."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS api_cache (
    cache_key   TEXT PRIMARY KEY,      -- endpoint + canonical params (never the key)
    json        TEXT NOT NULL,
    fetched_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dockets (
    docket_id   TEXT PRIMARY KEY,
    json        TEXT NOT NULL,
    comment_total INTEGER,
    fetched_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    docket_id   TEXT NOT NULL,
    list_json   TEXT,
    detail_json TEXT,
    fetched_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS comments (
    comment_id  TEXT PRIMARY KEY,
    docket_id   TEXT NOT NULL,
    list_json   TEXT,
    detail_json TEXT,
    detail_fetched_at TEXT,
    listed_at   TEXT
);
CREATE INDEX IF NOT EXISTS comments_docket ON comments(docket_id);
CREATE TABLE IF NOT EXISTS attachments (
    attachment_key   TEXT PRIMARY KEY,  -- parentId#docOrder
    parent_id        TEXT NOT NULL,     -- comment or document id
    docket_id        TEXT NOT NULL,
    attachment_id    TEXT,
    doc_order        INTEGER,
    title            TEXT,
    url              TEXT,
    format           TEXT,
    other_formats    TEXT,              -- JSON list of formats not downloaded
    local_path       TEXT,
    bytes            INTEGER,
    sniffed_type     TEXT,
    page_count       INTEGER,
    extracted_text   TEXT,
    extraction_method TEXT,
    extraction_ok    INTEGER,
    needs_ocr        INTEGER,
    error            TEXT,
    fetched_at       TEXT
);
CREATE INDEX IF NOT EXISTS attachments_parent ON attachments(parent_id);
CREATE TABLE IF NOT EXISTS guidance_text (
    ref              TEXT PRIMARY KEY,  -- document id or URL as given
    source_url       TEXT,
    local_path       TEXT,
    page_count       INTEGER,
    extraction_method TEXT,
    text             TEXT,
    sections_json    TEXT,
    parser_version   TEXT,
    fetched_at       TEXT
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    config.DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.CACHE_DB, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def api_key_for(path: str, params: dict) -> str:
    return path + "?" + json.dumps(params, sort_keys=True)


def get_api(con, key: str):
    r = con.execute("SELECT json FROM api_cache WHERE cache_key=?", (key,)).fetchone()
    return json.loads(r["json"]) if r else None


def put_api(con, key: str, obj) -> None:
    con.execute("INSERT OR REPLACE INTO api_cache VALUES (?,?,?)", (key, json.dumps(obj), now()))
    con.commit()
