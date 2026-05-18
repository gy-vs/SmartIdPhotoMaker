"""
智能证件照制作系统 - 数据持久化与历史记录测试
"""

import io
import os
import pytest
import numpy as np
import cv2

from app import app
from models import (
    init_db, DB_PATH, get_db,
    create_session, get_session, get_user_sessions, update_session_time, delete_session,
    add_history, get_session_history, get_user_history, get_user_stats,
    create_user, get_user_by_username,
)


@pytest.fixture(autouse=True)
def clean_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def token(client):
    client.post("/api/register", json={"username": "testuser", "password": "test123456"})
    res = client.post("/api/login", json={"username": "testuser", "password": "test123456"})
    return res.get_json()["token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def make_test_image_bytes(w=400, h=600):
    img = np.full((h, w, 3), (200, 180, 160), dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


def upload_and_get_sid(client, token):
    img_bytes = make_test_image_bytes()
    data = {"file": (io.BytesIO(img_bytes), "test.jpg")}
    res = client.post("/api/upload", data=data, content_type="multipart/form-data",
                      headers=auth_header(token))
    assert res.status_code == 200
    return res.get_json()["session_id"]


# ============ models.py 单元测试 ============

class TestSessionModel:
    def test_create_session(self):
        """创建会话应成功"""
        from auth import hash_password
        create_user("testuser", hash_password("test123456"))
        result = create_session("abc12345", "testuser", "photo.jpg", "/tmp/photo.jpg",
                                has_face=True, confidence=0.95, has_glasses=False)
        assert result is True

    def test_create_duplicate_session(self):
        """重复 sid 应返回 False"""
        from auth import hash_password
        create_user("testuser", hash_password("test123456"))
        create_session("abc12345", "testuser")
        result = create_session("abc12345", "testuser")
        assert result is False

    def test_get_session(self):
        """查询会话应返回正确数据"""
        from auth import hash_password
        create_user("testuser", hash_password("test123456"))
        create_session("abc12345", "testuser", "photo.jpg", has_face=True, confidence=0.95)
        session = get_session("abc12345")
        assert session is not None
        assert session["sid"] == "abc12345"
        assert session["username"] == "testuser"
        assert session["filename"] == "photo.jpg"
        assert session["has_face"] == 1
        assert session["confidence"] == 0.95

    def test_get_nonexistent_session(self):
        """查询不存在的会话应返回 None"""
        assert get_session("nonexistent") is None

    def test_get_user_sessions(self):
        """获取用户会话列表"""
        from auth import hash_password
        create_user("testuser", hash_password("test123456"))
        create_session("sid001", "testuser", "a.jpg")
        create_session("sid002", "testuser", "b.jpg")
        create_session("sid003", "testuser", "c.jpg")
        sessions = get_user_sessions("testuser")
        assert len(sessions) == 3

    def test_get_user_sessions_limit(self):
        """获取用户会话列表应支持分页"""
        from auth import hash_password
        create_user("testuser", hash_password("test123456"))
        for i in range(5):
            create_session(f"sid{i:03d}", "testuser", f"photo{i}.jpg")
        sessions = get_user_sessions("testuser", limit=2)
        assert len(sessions) == 2

    def test_update_session_time(self):
        """更新会话时间应成功"""
        from auth import hash_password
        create_user("testuser", hash_password("test123456"))
        create_session("abc12345", "testuser")
        s1 = get_session("abc12345")
        update_session_time("abc12345")
        s2 = get_session("abc12345")
        assert s2["updated_at"] >= s1["updated_at"]

    def test_delete_session(self):
        """删除会话应同时删除历史记录"""
        from auth import hash_password
        create_user("testuser", hash_password("test123456"))
        create_session("abc12345", "testuser")
        add_history("abc12345", "testuser", "upload")
        add_history("abc12345", "testuser", "enhance")
        delete_session("abc12345")
        assert get_session("abc12345") is None
        assert len(get_session_history("abc12345")) == 0


class TestHistoryModel:
    def test_add_history(self):
        """添加历史记录应成功"""
        from auth import hash_password
        create_user("testuser", hash_password("test123456"))
        create_session("abc12345", "testuser")
        add_history("abc12345", "testuser", "upload", "photo.jpg")
        history = get_session_history("abc12345")
        assert len(history) == 1
        assert history[0]["action"] == "upload"
        assert history[0]["params"] == "photo.jpg"
        assert history[0]["status"] == "success"

    def test_add_multiple_history(self):
        """多条历史记录应按时间排序"""
        from auth import hash_password
        create_user("testuser", hash_password("test123456"))
        create_session("abc12345", "testuser")
        add_history("abc12345", "testuser", "upload")
        add_history("abc12345", "testuser", "enhance")
        add_history("abc12345", "testuser", "replace_background", "蓝底")
        add_history("abc12345", "testuser", "export", "jpg")
        history = get_session_history("abc12345")
        assert len(history) == 4
        assert history[0]["action"] == "upload"
        assert history[3]["action"] == "export"

    def test_add_error_history(self):
        """错误状态历史记录"""
        from auth import hash_password
        create_user("testuser", hash_password("test123456"))
        create_session("abc12345", "testuser")
        add_history("abc12345", "testuser", "enhance", status="error")
        history = get_session_history("abc12345")
        assert history[0]["status"] == "error"

    def test_get_user_history(self):
        """获取用户历史应包含文件名"""
        from auth import hash_password
        create_user("testuser", hash_password("test123456"))
        create_session("abc12345", "testuser", "photo.jpg")
        add_history("abc12345", "testuser", "upload", "photo.jpg")
        add_history("abc12345", "testuser", "enhance")
        history = get_user_history("testuser")
        assert len(history) == 2
        assert history[0]["filename"] == "photo.jpg"

    def test_get_user_history_limit(self):
        """用户历史应支持分页"""
        from auth import hash_password
        create_user("testuser", hash_password("test123456"))
        create_session("abc12345", "testuser")
        for i in range(10):
            add_history("abc12345", "testuser", "enhance")
        history = get_user_history("testuser", limit=3)
        assert len(history) == 3

    def test_get_user_stats(self):
        """用户统计信息应正确"""
        from auth import hash_password
        create_user("testuser", hash_password("test123456"))
        create_session("sid001", "testuser")
        create_session("sid002", "testuser")
        add_history("sid001", "testuser", "upload")
        add_history("sid001", "testuser", "enhance")
        add_history("sid001", "testuser", "export", "jpg")
        add_history("sid002", "testuser", "upload")
        add_history("sid002", "testuser", "export", "png")
        stats = get_user_stats("testuser")
        assert stats["session_count"] == 2
        assert stats["history_count"] == 5
        assert stats["export_count"] == 2


# ============ API 集成测试 ============

class TestHistoryAPI:
    def test_upload_creates_session_and_history(self, client, token):
        """上传应创建会话和历史记录"""
        sid = upload_and_get_sid(client, token)
        session = get_session(sid)
        assert session is not None
        assert session["username"] == "testuser"
        assert session["filename"] == "test.jpg"
        history = get_session_history(sid)
        assert len(history) == 1
        assert history[0]["action"] == "upload"

    def test_process_creates_history(self, client, token):
        """处理操作应创建历史记录"""
        sid = upload_and_get_sid(client, token)
        client.post("/api/process", json={
            "session_id": sid, "action": "replace_background", "bg_color": "蓝底"
        }, headers=auth_header(token))
        client.post("/api/process", json={
            "session_id": sid, "action": "enhance"
        }, headers=auth_header(token))
        history = get_session_history(sid)
        assert len(history) == 3  # upload + replace_background + enhance
        assert history[1]["action"] == "replace_background"
        assert history[1]["params"] == "蓝底"
        assert history[2]["action"] == "enhance"

    def test_export_creates_history(self, client, token):
        """导出应创建历史记录"""
        sid = upload_and_get_sid(client, token)
        client.post("/api/export", json={"session_id": sid, "format": "jpg"},
                     headers=auth_header(token))
        history = get_session_history(sid)
        actions = [h["action"] for h in history]
        assert "export" in actions

    def test_get_history_all(self, client, token):
        """获取全部历史记录"""
        sid = upload_and_get_sid(client, token)
        client.post("/api/process", json={"session_id": sid, "action": "enhance"},
                     headers=auth_header(token))
        res = client.get("/api/history?type=all", headers=auth_header(token))
        assert res.status_code == 200
        data = res.get_json()
        assert "history" in data
        assert len(data["history"]) >= 2

    def test_get_history_sessions(self, client, token):
        """获取会话列表"""
        upload_and_get_sid(client, token)
        upload_and_get_sid(client, token)
        res = client.get("/api/history?type=sessions", headers=auth_header(token))
        assert res.status_code == 200
        data = res.get_json()
        assert "sessions" in data
        assert len(data["sessions"]) == 2

    def test_get_history_stats(self, client, token):
        """获取统计信息"""
        sid = upload_and_get_sid(client, token)
        client.post("/api/process", json={"session_id": sid, "action": "enhance"},
                     headers=auth_header(token))
        client.post("/api/export", json={"session_id": sid, "format": "jpg"},
                     headers=auth_header(token))
        res = client.get("/api/history?type=stats", headers=auth_header(token))
        assert res.status_code == 200
        data = res.get_json()
        assert "stats" in data
        assert data["stats"]["session_count"] == 1
        assert data["stats"]["history_count"] >= 3
        assert data["stats"]["export_count"] == 1

    def test_get_session_detail(self, client, token):
        """获取指定会话的操作历史"""
        sid = upload_and_get_sid(client, token)
        client.post("/api/process", json={"session_id": sid, "action": "enhance"},
                     headers=auth_header(token))
        res = client.get(f"/api/history/{sid}", headers=auth_header(token))
        assert res.status_code == 200
        data = res.get_json()
        assert data["sid"] == sid
        assert len(data["history"]) == 2

    def test_history_requires_auth(self, client):
        """历史记录 API 需要认证"""
        res = client.get("/api/history")
        assert res.status_code == 401

    def test_history_limit(self, client, token):
        """历史记录应支持 limit 参数"""
        sid = upload_and_get_sid(client, token)
        for _ in range(5):
            client.post("/api/process", json={"session_id": sid, "action": "enhance"},
                         headers=auth_header(token))
        res = client.get("/api/history?type=all&limit=3", headers=auth_header(token))
        assert res.status_code == 200
        assert len(res.get_json()["history"]) == 3

    def test_history_isolated_between_users(self, client):
        """不同用户的历史记录应隔离"""
        # user1
        client.post("/api/register", json={"username": "user1", "password": "pass123456"})
        res1 = client.post("/api/login", json={"username": "user1", "password": "pass123456"})
        token1 = res1.get_json()["token"]
        upload_and_get_sid(client, token1)

        # user2
        client.post("/api/register", json={"username": "user2", "password": "pass123456"})
        res2 = client.post("/api/login", json={"username": "user2", "password": "pass123456"})
        token2 = res2.get_json()["token"]

        # user2 应看不到 user1 的记录
        res = client.get("/api/history?type=all", headers=auth_header(token2))
        assert res.status_code == 200
        assert len(res.get_json()["history"]) == 0
