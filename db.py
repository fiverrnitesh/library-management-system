import pymysql
from flask import g

from config import Config


def get_db():
    if "db" not in g:
        g.db = pymysql.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_all(sql, params=None):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


def query_one(sql, params=None):
    rows = query_all(sql, params)
    return rows[0] if rows else None


def execute(sql, params=None):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(sql, params or ())
        last_id = cur.lastrowid
    db.commit()
    return last_id
