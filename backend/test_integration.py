"""
智能证件照制作系统 - 集成测试
测试完整的 API 业务流程 + Docker 部署验证
"""

import io
import os
import pytest
import numpy as np
import cv2

from app import app
from models import init_db, DB_PATH


# ============ 测试辅助 ============

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
    """注册并登录，返回有效 token"""
    client.post("/api/register", json={"username": "testuser", "password": "test123456"})
    res = client.post("/api/login", json={"username": "testuser", "password": "test123456"})
    return res.get_json()["token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def make_test_image_bytes(w=400, h=600, fmt=".jpg"):
    img = np.full((h, w, 3), (220, 210, 200), dtype=np.uint8)
    cv2.ellipse(img, (w // 2, h // 3), (80, 110), 0, 0, 360, (180, 150, 130), -1)
    cv2.circle(img, (w // 2 - 30, h // 3 - 15), 8, (60, 40, 30), -1)
    cv2.circle(img, (w // 2 + 30, h // 3 - 15), 8, (60, 40, 30), -1)
    _, buf = cv2.imencode(fmt, img)
    return buf.tobytes()


def upload_and_get_sid(client, token):
    """上传照片并返回 session_id"""
    img_bytes = make_test_image_bytes()
    data = {"file": (io.BytesIO(img_bytes), "test.jpg")}
    res = client.post("/api/upload", data=data, content_type="multipart/form-data",
                      headers=auth_header(token))
    assert res.status_code == 200
    return res.get_json()["session_id"]


# ============ 完整业务流程集成测试 ============

class TestFullWorkflow:
    """测试完整的证件照制作流程：上传 -> 各步骤处理 -> 导出"""

    def test_upload_then_replace_background_then_export(self, client, token):
        """流程: 上传 -> 替换背景 -> 导出"""
        sid = upload_and_get_sid(client, token)

        res = client.post("/api/process", json={
            "session_id": sid, "action": "replace_background", "bg_color": "蓝底"
        }, headers=auth_header(token))
        assert res.status_code == 200
        data = res.get_json()
        assert "preview" in data
        assert "log" in data

        res = client.post("/api/export", json={"session_id": sid, "format": "jpg"},
                          headers=auth_header(token))
        assert res.status_code == 200
        assert len(res.data) > 0

    def test_upload_then_enhance_then_export_png(self, client, token):
        """流程: 上传 -> 画质增强 -> 导出 PNG"""
        sid = upload_and_get_sid(client, token)

        res = client.post("/api/process", json={"session_id": sid, "action": "enhance"},
                          headers=auth_header(token))
        assert res.status_code == 200

        res = client.post("/api/export", json={"session_id": sid, "format": "png"},
                          headers=auth_header(token))
        assert res.status_code == 200
        assert len(res.data) > 0

    def test_upload_then_multi_step_process(self, client, token):
        """流程: 上传 -> 消除眼镜 -> 画质增强 -> 替换背景 -> 导出"""
        sid = upload_and_get_sid(client, token)

        res = client.post("/api/process", json={"session_id": sid, "action": "remove_glasses"},
                          headers=auth_header(token))
        assert res.status_code == 200

        res = client.post("/api/process", json={"session_id": sid, "action": "enhance"},
                          headers=auth_header(token))
        assert res.status_code == 200

        res = client.post("/api/process", json={
            "session_id": sid, "action": "replace_background", "bg_color": "红底"
        }, headers=auth_header(token))
        assert res.status_code == 200

        res = client.post("/api/export", json={"session_id": sid, "format": "jpg"},
                          headers=auth_header(token))
        assert res.status_code == 200

    def test_upload_then_auto_process(self, client, token):
        """流程: 上传 -> 一键自动处理 -> 导出"""
        sid = upload_and_get_sid(client, token)

        res = client.post("/api/process", json={
            "session_id": sid, "action": "auto",
            "bg_color": "白底", "size": "二寸"
        }, headers=auth_header(token))
        assert res.status_code == 200
        data = res.get_json()
        assert "preview" in data
        assert "log" in data

        res = client.post("/api/export", json={"session_id": sid, "format": "jpg"},
                          headers=auth_header(token))
        assert res.status_code == 200

    def test_upload_then_detect_face(self, client, token):
        """流程: 上传 -> 人脸检测可视化"""
        sid = upload_and_get_sid(client, token)

        res = client.post("/api/detect", json={"session_id": sid},
                          headers=auth_header(token))
        assert res.status_code in (200, 400)
        if res.status_code == 200:
            data = res.get_json()
            assert "preview" in data
            assert "confidence" in data

    def test_upload_process_reset_reprocess(self, client, token):
        """流程: 上传 -> 替换背景 -> 重置 -> 重新替换背景"""
        sid = upload_and_get_sid(client, token)

        res = client.post("/api/process", json={
            "session_id": sid, "action": "replace_background", "bg_color": "蓝底"
        }, headers=auth_header(token))
        assert res.status_code == 200
        preview_blue = res.get_json()["preview"]

        res = client.post("/api/process", json={"session_id": sid, "action": "reset"},
                          headers=auth_header(token))
        assert res.status_code == 200

        res = client.post("/api/process", json={
            "session_id": sid, "action": "replace_background", "bg_color": "红底"
        }, headers=auth_header(token))
        assert res.status_code == 200
        preview_red = res.get_json()["preview"]

        assert preview_blue != preview_red


class TestMultiSession:
    """测试多会话隔离"""

    def test_two_sessions_independent(self, client, token):
        """两个 session 应互不影响"""
        sid1 = upload_and_get_sid(client, token)
        sid2 = upload_and_get_sid(client, token)
        assert sid1 != sid2

        res1 = client.post("/api/process", json={
            "session_id": sid1, "action": "replace_background", "bg_color": "蓝底"
        }, headers=auth_header(token))
        assert res1.status_code == 200

        res2 = client.post("/api/process", json={
            "session_id": sid2, "action": "replace_background", "bg_color": "红底"
        }, headers=auth_header(token))
        assert res2.status_code == 200

        assert res1.get_json()["preview"] != res2.get_json()["preview"]


class TestAllBackgroundColors:
    """测试所有背景颜色"""

    @pytest.mark.parametrize("color", ["蓝底", "白底", "红底"])
    def test_replace_background_color(self, client, token, color):
        sid = upload_and_get_sid(client, token)
        res = client.post("/api/process", json={
            "session_id": sid, "action": "replace_background", "bg_color": color
        }, headers=auth_header(token))
        assert res.status_code == 200
        assert "preview" in res.get_json()


class TestAllPhotoSizes:
    """测试所有证件照尺寸（通过 auto 流程）"""

    @pytest.mark.parametrize("size", ["一寸", "二寸", "小二寸"])
    def test_auto_with_size(self, client, token, size):
        sid = upload_and_get_sid(client, token)
        res = client.post("/api/process", json={
            "session_id": sid, "action": "auto",
            "bg_color": "蓝底", "size": size
        }, headers=auth_header(token))
        assert res.status_code == 200


class TestAllExportFormats:
    """测试所有导出格式"""

    @pytest.mark.parametrize("fmt", ["jpg", "png"])
    def test_export_format(self, client, token, fmt):
        sid = upload_and_get_sid(client, token)
        res = client.post("/api/export", json={"session_id": sid, "format": fmt},
                          headers=auth_header(token))
        assert res.status_code == 200
        assert len(res.data) > 0


class TestUploadFormats:
    """测试不同格式图片上传"""

    @pytest.mark.parametrize("fmt,filename", [
        (".jpg", "photo.jpg"),
        (".png", "photo.png"),
    ])
    def test_upload_format(self, client, token, fmt, filename):
        img_bytes = make_test_image_bytes(fmt=fmt)
        data = {"file": (io.BytesIO(img_bytes), filename)}
        res = client.post("/api/upload", data=data, content_type="multipart/form-data",
                          headers=auth_header(token))
        assert res.status_code == 200
        assert "session_id" in res.get_json()
        assert res.status_code == 200
        assert "session_id" in res.get_json()


# ============ Docker 部署验证测试 ============

class TestDockerDeployment:
    """验证 Docker 部署相关文件和配置的正确性"""

    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_backend_dockerfile_exists(self):
        """后端 Dockerfile 应存在"""
        path = os.path.join(self.PROJECT_ROOT, "backend", "Dockerfile")
        assert os.path.isfile(path)

    def test_frontend_dockerfile_exists(self):
        """前端 Dockerfile 应存在"""
        path = os.path.join(self.PROJECT_ROOT, "frontend-admin", "Dockerfile")
        assert os.path.isfile(path)

    def test_docker_compose_exists(self):
        """docker-compose.yml 应存在"""
        path = os.path.join(self.PROJECT_ROOT, "docker-compose.yml")
        assert os.path.isfile(path)

    def test_requirements_txt_exists(self):
        """requirements.txt 应存在"""
        path = os.path.join(self.PROJECT_ROOT, "backend", "requirements.txt")
        assert os.path.isfile(path)

    def test_requirements_has_key_deps(self):
        """requirements.txt 应包含关键依赖"""
        path = os.path.join(self.PROJECT_ROOT, "backend", "requirements.txt")
        with open(path) as f:
            content = f.read()
        for dep in ["flask", "opencv", "mediapipe", "numpy", "gunicorn"]:
            assert dep in content.lower(), f"缺少依赖: {dep}"

    def test_docker_compose_has_services(self):
        """docker-compose.yml 应包含 backend 和 frontend 服务"""
        path = os.path.join(self.PROJECT_ROOT, "docker-compose.yml")
        with open(path) as f:
            content = f.read()
        assert "backend" in content
        assert "frontend-admin" in content

    def test_docker_compose_network(self):
        """docker-compose.yml 应配置网络"""
        path = os.path.join(self.PROJECT_ROOT, "docker-compose.yml")
        with open(path) as f:
            content = f.read()
        assert "networks" in content

    def test_backend_dockerfile_exposes_port(self):
        """后端 Dockerfile 应暴露 5000 端口"""
        path = os.path.join(self.PROJECT_ROOT, "backend", "Dockerfile")
        with open(path) as f:
            content = f.read()
        assert "5000" in content

    def test_frontend_dockerfile_exposes_port(self):
        """前端 Dockerfile 应暴露 80 端口"""
        path = os.path.join(self.PROJECT_ROOT, "frontend-admin", "Dockerfile")
        with open(path) as f:
            content = f.read()
        assert "80" in content

    def test_upload_output_dirs_exist(self):
        """uploads 和 output 目录应可创建"""
        backend_dir = os.path.join(self.PROJECT_ROOT, "backend")
        for d in ["uploads", "output"]:
            dirpath = os.path.join(backend_dir, d)
            os.makedirs(dirpath, exist_ok=True)
            assert os.path.isdir(dirpath)

    def test_frontend_index_exists(self):
        """前端 index.html 应存在"""
        path = os.path.join(self.PROJECT_ROOT, "frontend-admin", "index.html")
        assert os.path.isfile(path)

    def test_frontend_nginx_conf_exists(self):
        """前端 nginx.conf 应存在"""
        path = os.path.join(self.PROJECT_ROOT, "frontend-admin", "nginx.conf")
        assert os.path.isfile(path)
