import sqlite3

from flask import g

import config


def get_db():
    if "db" not in g:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(config.DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    for category in config.DOCUMENT_CATEGORIES:
        (config.DOCUMENTS_DIR / category).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    try:
        with open(config.SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
    finally:
        conn.close()


def init_app(app):
    app.teardown_appcontext(close_db)
