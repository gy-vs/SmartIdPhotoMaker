"""
智能证件照制作系统 - Flask API 接口单元测试
"""

import io
import os
import json
import pytest
import numpy as np
import cv2

from app import app
from models import init_db, DB_PATH


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
    """创建 Flask 测试客户端"""
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def token(client):
    """注册并登录，返回有效 token"""
    client.post("/api/register", json={"username": "testuser", "password": "test123456"})
    res = client.post("/api/login", json={"username": "testuser", "password": "test123456"})
    return res.get_json()["token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def make_test_image_bytes(w=400, h=600, fmt=".jpg"):
    """生成测试图片的字节流"""
    img = np.full((h, w, 3), (200, 180, 160), dtype=np.uint8)
    # 画一个椭圆模拟人脸
    cv2.ellipse(img, (w // 2, h // 3), (80, 110), 0, 0, 360, (180, 150, 130), -1)
    _, buf = cv2.imencode(fmt, img)
    return buf.tobytes()


def upload_photo(client, token, img_bytes=None, filename="test.jpg"):
    """辅助函数：上传照片并返回响应"""
    if img_bytes is None:
        img_bytes = make_test_image_bytes()
    data = {"file": (io.BytesIO(img_bytes), filename)}
    return client.post("/api/upload", data=data, content_type="multipart/form-data",
                       headers=auth_header(token))


# ============ /api/health ============

class TestHealth:
    def test_health_ok(self, client):
        """健康检查应返回 200"""
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.get_json()
        assert data["status"] == "ok"


# ============ /api/upload ============

class TestUpload:
    def test_upload_no_file(self, client, token):
        """无文件应返回 400"""
        res = client.post("/api/upload", headers=auth_header(token))
        assert res.status_code == 400
        assert "未上传文件" in res.get_json()["error"]

    def test_upload_empty_filename(self, client, token):
        """空文件名应返回 400"""
        data = {"file": (io.BytesIO(b""), "")}
        res = client.post("/api/upload", data=data, content_type="multipart/form-data",
                          headers=auth_header(token))
        assert res.status_code == 400
        assert "文件名为空" in res.get_json()["error"]

    def test_upload_invalid_extension(self, client, token):
        """不支持的扩展名应返回 400"""
        data = {"file": (io.BytesIO(b"fake"), "test.gif")}
        res = client.post("/api/upload", data=data, content_type="multipart/form-data",
                          headers=auth_header(token))
        assert res.status_code == 400
        assert "不支持的文件格式" in res.get_json()["error"]

    def test_upload_invalid_content(self, client, token):
        """非图片内容应返回 400"""
        data = {"file": (io.BytesIO(b"this is not an image"), "test.jpg")}
        res = client.post("/api/upload", data=data, content_type="multipart/form-data",
                          headers=auth_header(token))
        assert res.status_code == 400
        assert "不是有效的图片" in res.get_json()["error"]

    def test_upload_too_small_image(self, client, token):
        """过小图片应返回 400"""
        img_bytes = make_test_image_bytes(w=50, h=50)
        res = upload_photo(client, token, img_bytes, "small.jpg")
        assert res.status_code == 400
        assert "尺寸过小" in res.get_json()["error"]

    def test_upload_valid_image(self, client, token):
        """有效图片应返回 200 和 session_id"""
        res = upload_photo(client, token)
        assert res.status_code == 200
        data = res.get_json()
        assert "session_id" in data
        assert "original" in data
        assert "preview" in data
        assert isinstance(data["has_face"], bool)

    def test_upload_png(self, client, token):
        """PNG 格式应正常上传"""
        img_bytes = make_test_image_bytes(fmt=".png")
        res = upload_photo(client, token, img_bytes, "test.png")
        assert res.status_code == 200
        assert "session_id" in res.get_json()


# ============ /api/process ============

class TestProcess:
    def _get_session(self, client, token):
        """上传照片获取 session_id"""
        res = upload_photo(client, token)
        return res.get_json()["session_id"]

    def test_process_no_session(self, client, token):
        """缺少 session_id 应返回 400"""
        res = client.post("/api/process", json={}, headers=auth_header(token))
        assert res.status_code == 400
        assert "session_id" in res.get_json()["error"]

    def test_process_invalid_session(self, client, token):
        """无效 session_id 应返回 400"""
        res = client.post("/api/process", json={"session_id": "invalid", "action": "enhance"},
                          headers=auth_header(token))
        assert res.status_code == 400
        assert "无效的会话标识" in res.get_json()["error"]

    def test_process_unknown_action(self, client, token):
        """未知操作应返回 400 并列出可用操作"""
        sid = self._get_session(client, token)
        res = client.post("/api/process", json={"session_id": sid, "action": "unknown"},
                          headers=auth_header(token))
        assert res.status_code == 400
        error = res.get_json()["error"]
        assert "未知操作" in error
        assert "replace_background" in error

    def test_process_invalid_bg_color(self, client, token):
        """无效背景颜色应返回 400"""
        sid = self._get_session(client, token)
        res = client.post("/api/process", json={
            "session_id": sid, "action": "replace_background", "bg_color": "紫底"
        }, headers=auth_header(token))
        assert res.status_code == 400
        assert "不支持的背景颜色" in res.get_json()["error"]

    def test_process_invalid_size(self, client, token):
        """无效证件照尺寸应返回 400"""
        sid = self._get_session(client, token)
        res = client.post("/api/process", json={
            "session_id": sid, "action": "crop", "size": "三寸"
        }, headers=auth_header(token))
        assert res.status_code == 400
        assert "不支持的证件照尺寸" in res.get_json()["error"]

    def test_process_replace_background(self, client, token):
        """替换背景应返回 200"""
        sid = self._get_session(client, token)
        res = client.post("/api/process", json={
            "session_id": sid, "action": "replace_background", "bg_color": "蓝底"
        }, headers=auth_header(token))
        assert res.status_code == 200
        data = res.get_json()
        assert "preview" in data

    def test_process_enhance(self, client, token):
        """画质增强应返回 200"""
        sid = self._get_session(client, token)
        res = client.post("/api/process", json={"session_id": sid, "action": "enhance"},
                          headers=auth_header(token))
        assert res.status_code == 200
        assert "preview" in res.get_json()

    def test_process_remove_glasses(self, client, token):
        """消除眼镜应返回 200"""
        sid = self._get_session(client, token)
        res = client.post("/api/process", json={"session_id": sid, "action": "remove_glasses"},
                          headers=auth_header(token))
        assert res.status_code == 200

    def test_process_reset(self, client, token):
        """重置应返回 200"""
        sid = self._get_session(client, token)
        res = client.post("/api/process", json={"session_id": sid, "action": "reset"},
                          headers=auth_header(token))
        assert res.status_code == 200

    def test_process_auto_invalid_params(self, client, token):
        """一键处理无效参数应返回 400"""
        sid = self._get_session(client, token)
        res = client.post("/api/process", json={
            "session_id": sid, "action": "auto", "bg_color": "绿底", "size": "一寸"
        }, headers=auth_header(token))
        assert res.status_code == 400
        assert "不支持的背景颜色" in res.get_json()["error"]


# ============ /api/export ============

class TestExport:
    def _get_session(self, client, token):
        res = upload_photo(client, token)
        return res.get_json()["session_id"]

    def test_export_no_session(self, client, token):
        """缺少 session_id 应返回 400"""
        res = client.post("/api/export", json={}, headers=auth_header(token))
        assert res.status_code == 400

    def test_export_invalid_session(self, client, token):
        """无效 session_id 应返回 400"""
        res = client.post("/api/export", json={"session_id": "invalid"},
                          headers=auth_header(token))
        assert res.status_code == 400
        assert "无效的会话标识" in res.get_json()["error"]

    def test_export_invalid_format(self, client, token):
        """无效导出格式应返回 400"""
        sid = self._get_session(client, token)
        res = client.post("/api/export", json={"session_id": sid, "format": "gif"},
                          headers=auth_header(token))
        assert res.status_code == 400
        assert "不支持的导出格式" in res.get_json()["error"]

    def test_export_valid(self, client, token):
        """有效导出应返回文件"""
        sid = self._get_session(client, token)
        res = client.post("/api/export", json={"session_id": sid, "format": "jpg"},
                          headers=auth_header(token))
        assert res.status_code == 200
        assert res.content_type in ("image/jpeg", "application/octet-stream")

    def test_export_png(self, client, token):
        """PNG 导出应返回文件"""
        sid = self._get_session(client, token)
        res = client.post("/api/export", json={"session_id": sid, "format": "png"},
                          headers=auth_header(token))
        assert res.status_code == 200


# ============ /api/detect ============

class TestDetect:
    def _get_session(self, client, token):
        res = upload_photo(client, token)
        return res.get_json()["session_id"]

    def test_detect_no_session(self, client, token):
        """缺少 session_id 应返回 400"""
        res = client.post("/api/detect", json={}, headers=auth_header(token))
        assert res.status_code == 400

    def test_detect_invalid_session(self, client, token):
        """无效 session_id 应返回 400"""
        res = client.post("/api/detect", json={"session_id": "invalid"},
                          headers=auth_header(token))
        assert res.status_code == 400
        assert "无效的会话标识" in res.get_json()["error"]

    def test_detect_valid_session(self, client, token):
        """有效 session 应返回 200 或 400（取决于是否检测到人脸）"""
        sid = self._get_session(client, token)
        res = client.post("/api/detect", json={"session_id": sid},
                          headers=auth_header(token))
        # 模拟图片不一定能检测到人脸
        assert res.status_code in (200, 400)
