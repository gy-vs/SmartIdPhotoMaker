"""
智能证件照制作系统 - 数据模型
基于 SQLite 的轻量级存储：用户、会话、操作历史
"""

import os
import sqlite3
import logging
from datetime import datetime

from config import get_config

logger = logging.getLogger("models")
cfg = get_config()

DB_PATH = os.path.join(cfg.BASE_DIR, "users.db")


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_login TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sid TEXT UNIQUE NOT NULL,
                username TEXT NOT NULL,
                filename TEXT,
                file_path TEXT,
                has_face INTEGER DEFAULT 0,
                confidence REAL,
                has_glasses INTEGER DEFAULT 0,
                layout_exported INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sid TEXT NOT NULL,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                params TEXT,
                status TEXT NOT NULL DEFAULT 'success',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_username ON sessions(username);
            CREATE INDEX IF NOT EXISTS idx_sessions_sid ON sessions(sid);
            CREATE INDEX IF NOT EXISTS idx_history_username ON history(username);
            CREATE INDEX IF NOT EXISTS idx_history_sid ON history(sid);
        """)
        conn.commit()

        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN layout_exported INTEGER DEFAULT 0")
            conn.commit()
        except Exception:
            pass

        logger.info("数据库初始化完成: %s", DB_PATH)
    except Exception as e:
        logger.error("数据库初始化失败: %s", e)
        raise
    finally:
        conn.close()


# ============ 用户操作 ============

def create_user(username: str, password_hash: str) -> bool:
    """创建用户，成功返回 True，用户名重复返回 False"""
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        conn.commit()
        logger.info("用户注册成功: %s", username)
        return True
    except sqlite3.IntegrityError:
        logger.warning("用户名已存在: %s", username)
        return False
    finally:
        conn.close()


def get_user_by_username(username: str) -> dict | None:
    """根据用户名查询用户"""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def update_last_login(username: str):
    """更新最后登录时间"""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE users SET last_login = ? WHERE username = ?",
            (datetime.now().isoformat(), username),
        )
        conn.commit()
    finally:
        conn.close()


# ============ 会话操作 ============

def create_session(sid: str, username: str, filename: str = None,
                   file_path: str = None, has_face: bool = False,
                   confidence: float = None, has_glasses: bool = False) -> bool:
    """创建会话记录"""
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO sessions (sid, username, filename, file_path, has_face, confidence, has_glasses)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (sid, username, filename, file_path, int(has_face), confidence, int(has_glasses)),
        )
        conn.commit()
        logger.debug("会话已创建: sid=%s, user=%s", sid, username)
        return True
    except sqlite3.IntegrityError:
        logger.warning("会话已存在: sid=%s", sid)
        return False
    finally:
        conn.close()


def get_session(sid: str) -> dict | None:
    """根据 sid 查询会话"""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM sessions WHERE sid = ?", (sid,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_sessions(username: str, limit: int = 20, offset: int = 0) -> list:
    """获取用户的会话列表（按时间倒序）"""
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT sid, filename, has_face, confidence, has_glasses, layout_exported, created_at, updated_at
               FROM sessions WHERE username = ?
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (username, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_session_time(sid: str):
    """更新会话的最后活跃时间"""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE sid = ?",
            (datetime.now().isoformat(), sid),
        )
        conn.commit()
    finally:
        conn.close()


def delete_session(sid: str):
    """删除会话及其历史记录"""
    conn = get_db()
    try:
        conn.execute("DELETE FROM history WHERE sid = ?", (sid,))
        conn.execute("DELETE FROM sessions WHERE sid = ?", (sid,))
        conn.commit()
        logger.debug("会话已删除: sid=%s", sid)
    finally:
        conn.close()


# ============ 历史记录操作 ============

def add_history(sid: str, username: str, action: str,
                params: str = None, status: str = "success"):
    """添加操作历史记录"""
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO history (sid, username, action, params, status)
               VALUES (?, ?, ?, ?, ?)""",
            (sid, username, action, params, status),
        )
        conn.commit()
    finally:
        conn.close()


def get_session_history(sid: str) -> list:
    """获取指定会话的操作历史"""
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT action, params, status, created_at
               FROM history WHERE sid = ?
               ORDER BY created_at ASC""",
            (sid,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_user_history(username: str, limit: int = 50, offset: int = 0) -> list:
    """获取用户的操作历史（按时间倒序）"""
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT h.sid, h.action, h.params, h.status, h.created_at,
                      s.filename
               FROM history h
               LEFT JOIN sessions s ON h.sid = s.sid
               WHERE h.username = ?
               ORDER BY h.created_at DESC LIMIT ? OFFSET ?""",
            (username, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_user_stats(username: str) -> dict:
    """获取用户统计信息"""
    conn = get_db()
    try:
        session_count = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE username = ?", (username,)
        ).fetchone()[0]
        history_count = conn.execute(
            "SELECT COUNT(*) FROM history WHERE username = ?", (username,)
        ).fetchone()[0]
        export_count = conn.execute(
            "SELECT COUNT(*) FROM history WHERE username = ? AND action = 'export'",
            (username,),
        ).fetchone()[0]
        return {
            "session_count": session_count,
            "history_count": history_count,
            "export_count": export_count,
        }
    finally:
        conn.close()


def mark_sessions_exported(sid_list: list):
    """标记会话为已用于排版导出。

    Args:
        sid_list (list[str]): 需要标记的会话 ID 列表。

    Returns:
        int: 成功更新的行数。
    """
    if not sid_list:
        return 0
    conn = get_db()
    try:
        placeholders = ",".join("?" for _ in sid_list)
        cursor = conn.execute(
            f"UPDATE sessions SET layout_exported = 1 WHERE sid IN ({placeholders})",
            sid_list,
        )
        conn.commit()
        logger.info("已标记 %d 个会话为排版导出: %s", cursor.rowcount, sid_list)
        return cursor.rowcount
    finally:
        conn.close()


def get_sessions_by_ids(sid_list: list, username: str) -> list:
    """根据 sid 列表查询会话，并校验用户归属。

    Args:
        sid_list (list[str]): 会话 ID 列表。
        username (str): 当前用户名。

    Returns:
        list[dict]: 属于当前用户的会话列表。
    """
    if not sid_list:
        return []
    conn = get_db()
    try:
        placeholders = ",".join("?" for _ in sid_list)
        rows = conn.execute(
            f"""SELECT sid, username, filename, file_path, has_face, layout_exported
                FROM sessions WHERE sid IN ({placeholders}) AND username = ?""",
            sid_list + [username],
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
