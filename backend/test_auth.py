"""
智能证件照制作系统 - 用户认证模块测试
"""

import io
import os
import pytest
import numpy as np
import cv2

from app import app
from models import init_db, DB_PATH


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前清理数据库"""
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


def register(client, username="testuser", password="test123456"):
    return client.post("/api/register", json={"username": username, "password": password})


def login(client, username="testuser", password="test123456"):
    return client.post("/api/login", json={"username": username, "password": password})


def get_token(client, username="testuser", password="test123456"):
    """注册并登录，返回 token"""
    register(client, username, password)
    res = login(client, username, password)
    return res.get_json()["token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def make_test_image_bytes(w=400, h=600):
    img = np.full((h, w, 3), (200, 180, 160), dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


# ============ 注册测试 ============

class TestRegister:
    def test_register_success(self, client):
        """正常注册应返回 201"""
        res = register(client)
        assert res.status_code == 201
        assert res.get_json()["message"] == "注册成功"

    def test_register_duplicate(self, client):
        """重复注册应返回 409"""
        register(client)
        res = register(client)
        assert res.status_code == 409
        assert "已被注册" in res.get_json()["error"]

    def test_register_empty_username(self, client):
        """空用户名应返回 400"""
        res = register(client, username="", password="test123456")
        assert res.status_code == 400

    def test_register_short_username(self, client):
        """过短用户名应返回 400"""
        res = register(client, username="a", password="test123456")
        assert res.status_code == 400
        assert "2~20" in res.get_json()["error"]

    def test_register_empty_password(self, client):
        """空密码应返回 400"""
        res = register(client, username="testuser", password="")
        assert res.status_code == 400

    def test_register_short_password(self, client):
        """过短密码应返回 400"""
        res = register(client, username="testuser", password="123")
        assert res.status_code == 400
        assert "6~50" in res.get_json()["error"]

    def test_register_no_body(self, client):
        """无请求体应返回 400"""
        res = client.post("/api/register")
        assert res.status_code == 400

    def test_register_chinese_username(self, client):
        """中文用户名应可以注册"""
        res = register(client, username="测试用户", password="test123456")
        assert res.status_code == 201

    def test_register_special_chars(self, client):
        """特殊字符用户名应返回 400"""
        res = register(client, username="test@user!", password="test123456")
        assert res.status_code == 400
        assert "只能包含" in res.get_json()["error"]


# ============ 登录测试 ============

class TestLogin:
    def test_login_success(self, client):
        """正常登录应返回 200 和 token"""
        register(client)
        res = login(client)
        assert res.status_code == 200
        data = res.get_json()
        assert "token" in data
        assert data["username"] == "testuser"
        assert data["message"] == "登录成功"

    def test_login_wrong_password(self, client):
        """错误密码应返回 401"""
        register(client)
        res = login(client, password="wrongpassword")
        assert res.status_code == 401
        assert "用户名或密码错误" in res.get_json()["error"]

    def test_login_nonexistent_user(self, client):
        """不存在的用户应返回 401"""
        res = login(client, username="nouser", password="test123456")
        assert res.status_code == 401

    def test_login_empty_fields(self, client):
        """空字段应返回 400"""
        res = login(client, username="", password="")
        assert res.status_code == 400

    def test_login_no_body(self, client):
        """无请求体应返回 400"""
        res = client.post("/api/login")
        assert res.status_code == 400


# ============ 认证中间件测试 ============

class TestAuthMiddleware:
    def test_upload_without_token(self, client):
        """无 token 上传应返回 401"""
        img_bytes = make_test_image_bytes()
        data = {"file": (io.BytesIO(img_bytes), "test.jpg")}
        res = client.post("/api/upload", data=data, content_type="multipart/form-data")
        assert res.status_code == 401
        assert "认证令牌" in res.get_json()["error"]

    def test_upload_with_invalid_token(self, client):
        """无效 token 应返回 401"""
        img_bytes = make_test_image_bytes()
        data = {"file": (io.BytesIO(img_bytes), "test.jpg")}
        res = client.post("/api/upload", data=data, content_type="multipart/form-data",
                          headers={"Authorization": "Bearer invalid.token.here"})
        assert res.status_code == 401
        assert "无效或已过期" in res.get_json()["error"]

    def test_upload_with_valid_token(self, client):
        """有效 token 上传应正常"""
        token = get_token(client)
        img_bytes = make_test_image_bytes()
        data = {"file": (io.BytesIO(img_bytes), "test.jpg")}
        res = client.post("/api/upload", data=data, content_type="multipart/form-data",
                          headers=auth_header(token))
        assert res.status_code == 200
        assert "session_id" in res.get_json()

    def test_process_without_token(self, client):
        """无 token 处理应返回 401"""
        res = client.post("/api/process", json={"session_id": "test", "action": "enhance"})
        assert res.status_code == 401

    def test_export_without_token(self, client):
        """无 token 导出应返回 401"""
        res = client.post("/api/export", json={"session_id": "test", "format": "jpg"})
        assert res.status_code == 401

    def test_detect_without_token(self, client):
        """无 token 检测应返回 401"""
        res = client.post("/api/detect", json={"session_id": "test"})
        assert res.status_code == 401

    def test_health_no_token_needed(self, client):
        """健康检查不需要 token"""
        res = client.get("/api/health")
        assert res.status_code == 200

    def test_register_no_token_needed(self, client):
        """注册不需要 token"""
        res = register(client, username="newuser", password="test123456")
        assert res.status_code == 201

    def test_login_no_token_needed(self, client):
        """登录不需要 token"""
        register(client)
        res = login(client)
        assert res.status_code == 200


# ============ 完整认证流程测试 ============

class TestAuthWorkflow:
    def test_register_login_upload_process_export(self, client):
        """完整流程: 注册 -> 登录 -> 上传 -> 处理 -> 导出"""
        # 注册
        res = register(client)
        assert res.status_code == 201

        # 登录
        res = login(client)
        assert res.status_code == 200
        token = res.get_json()["token"]

        # 上传
        img_bytes = make_test_image_bytes()
        data = {"file": (io.BytesIO(img_bytes), "test.jpg")}
        res = client.post("/api/upload", data=data, content_type="multipart/form-data",
                          headers=auth_header(token))
        assert res.status_code == 200
        sid = res.get_json()["session_id"]

        # 处理
        res = client.post("/api/process", json={"session_id": sid, "action": "enhance"},
                          headers={**auth_header(token), "Content-Type": "application/json"})
        assert res.status_code == 200

        # 导出
        res = client.post("/api/export", json={"session_id": sid, "format": "jpg"},
                          headers={**auth_header(token), "Content-Type": "application/json"})
        assert res.status_code == 200

    def test_multiple_users_isolated(self, client):
        """不同用户的会话应互不影响"""
        token1 = get_token(client, "user1", "pass123456")
        token2 = get_token(client, "user2", "pass123456")

        # user1 上传
        img_bytes = make_test_image_bytes()
        data = {"file": (io.BytesIO(img_bytes), "test.jpg")}
        res = client.post("/api/upload", data=data, content_type="multipart/form-data",
                          headers=auth_header(token1))
        assert res.status_code == 200
        sid1 = res.get_json()["session_id"]

        # user2 上传
        data = {"file": (io.BytesIO(img_bytes), "test.jpg")}
        res = client.post("/api/upload", data=data, content_type="multipart/form-data",
                          headers=auth_header(token2))
        assert res.status_code == 200
        sid2 = res.get_json()["session_id"]

        assert sid1 != sid2
