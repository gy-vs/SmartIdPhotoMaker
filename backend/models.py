"""
智能证件照制作系统 - 数据模型
基于 SQLite 的轻量级存储：用户、会话、操作历史
"""

import os
import sqlite3
import logging
from datetime import datetime
from typing import List

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


def _column_exists(table_name: str, column_name: str) -> bool:
    """检查列是否存在"""
    conn = get_db()
    try:
        cursor = conn.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        return column_name in columns
    finally:
        conn.close()


def init_db():
    """初始化数据库表并执行迁移"""
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
                used_for_printing INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS print_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT UNIQUE NOT NULL,
                username TEXT NOT NULL,
                layout_type TEXT NOT NULL,
                session_ids TEXT NOT NULL,
                pdf_path TEXT,
                jpg_path TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
        """)

        if not _column_exists("sessions", "used_for_printing"):
            try:
                conn.execute(
                    "ALTER TABLE sessions ADD COLUMN used_for_printing INTEGER DEFAULT 0"
                )
                logger.info("数据库迁移：已添加 sessions.used_for_printing 列")
            except sqlite3.OperationalError as e:
                logger.warning("添加列失败（可能已存在）：%s", e)

        conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_sessions_username ON sessions(username);
            CREATE INDEX IF NOT EXISTS idx_sessions_sid ON sessions(sid);
            CREATE INDEX IF NOT EXISTS idx_history_username ON history(username);
            CREATE INDEX IF NOT EXISTS idx_history_sid ON history(sid);
        """)
        conn.commit()
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
            """SELECT sid, filename, has_face, confidence, has_glasses, used_for_printing,
                      created_at, updated_at
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
        print_count = conn.execute(
            "SELECT COUNT(*) FROM print_tasks WHERE username = ?", (username,)
        ).fetchone()[0]
        return {
            "session_count": session_count,
            "history_count": history_count,
            "export_count": export_count,
            "print_count": print_count,
        }
    finally:
        conn.close()


def mark_sessions_for_printing(sids: List[str]) -> None:
    """
    标记会话已用于排版导出

    Args:
        sids: 会话 ID 列表
    """
    if not sids:
        return
    conn = get_db()
    try:
        for sid in sids:
            conn.execute(
                "UPDATE sessions SET used_for_printing = 1, updated_at = ? WHERE sid = ?",
                (datetime.now().isoformat(), sid),
            )
        conn.commit()
        logger.debug("已标记 %d 个会话用于排版", len(sids))
    finally:
        conn.close()


def create_print_task(task_id: str, username: str, layout_type: str,
                      session_ids: List[str], pdf_path: str = None,
                      jpg_path: str = None, status: str = "completed") -> bool:
    """
    创建打印任务记录

    Args:
        task_id: 任务 ID
        username: 用户名
        layout_type: 版式类型
        session_ids: 会话 ID 列表
        pdf_path: PDF 文件路径
        jpg_path: JPG 文件路径
        status: 任务状态

    Returns:
        是否创建成功
    """
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO print_tasks
               (task_id, username, layout_type, session_ids, pdf_path, jpg_path, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                task_id,
                username,
                layout_type,
                ",".join(session_ids),
                pdf_path,
                jpg_path,
                status,
            ),
        )
        conn.commit()
        logger.debug("打印任务已创建: task_id=%s, user=%s", task_id, username)
        return True
    except sqlite3.IntegrityError:
        logger.warning("打印任务已存在: task_id=%s", task_id)
        return False
    finally:
        conn.close()


def get_print_task(task_id: str) -> dict | None:
    """
    根据任务 ID 查询打印任务

    Args:
        task_id: 任务 ID

    Returns:
        任务信息字典，不存在返回 None
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM print_tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_print_tasks(username: str, limit: int = 20, offset: int = 0) -> List[dict]:
    """
    获取用户的打印任务列表

    Args:
        username: 用户名
        limit: 最大返回数量
        offset: 偏移量

    Returns:
        任务列表
    """
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT task_id, layout_type, session_ids, status, created_at
               FROM print_tasks WHERE username = ?
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (username, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
