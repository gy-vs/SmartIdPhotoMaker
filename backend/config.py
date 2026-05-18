"""
智能证件照制作系统 - 配置管理模块
支持通过环境变量覆盖默认配置，适配开发/测试/生产环境
"""

import os


class BaseConfig:
    """基础配置（所有环境共享）"""

    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "idphoto-default-secret-key")

    # 文件存储
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(BASE_DIR, "uploads"))
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", os.path.join(BASE_DIR, "output"))

    # 上传限制
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 10 * 1024 * 1024))  # 10MB
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    IMAGE_SIGNATURES = {
        b"\xff\xd8\xff": "jpeg",
        b"\x89PNG": "png",
        b"BM": "bmp",
        b"RIFF": "webp",
    }
    MIN_IMAGE_SIZE = int(os.getenv("MIN_IMAGE_SIZE", 100))
    MAX_IMAGE_SIZE = int(os.getenv("MAX_IMAGE_SIZE", 8000))

    # API 参数允许值
    ALLOWED_BG_COLORS = {"蓝底", "白底", "红底"}
    ALLOWED_PHOTO_SIZES = {"一寸", "二寸", "小二寸"}
    ALLOWED_EXPORT_FORMATS = {"jpg", "png"}

    # 会话管理
    SESSION_EXPIRE_SECONDS = int(os.getenv("SESSION_EXPIRE_SECONDS", 30 * 60))
    SESSION_CLEANUP_INTERVAL = int(os.getenv("SESSION_CLEANUP_INTERVAL", 5 * 60))
    MAX_SESSIONS = int(os.getenv("MAX_SESSIONS", 100))

    # 服务器
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 5000))

    # 日志
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    # AI 引擎参数
    FACE_DETECTION_CONFIDENCE = float(os.getenv("FACE_DETECTION_CONFIDENCE", 0.5))
    SELFIE_SEG_MODEL = int(os.getenv("SELFIE_SEG_MODEL", 1))
    ENHANCE_DENOISE_STRENGTH = int(os.getenv("ENHANCE_DENOISE_STRENGTH", 3))
    ENHANCE_BRIGHTNESS = int(os.getenv("ENHANCE_BRIGHTNESS", 3))
    ENHANCE_CONTRAST = float(os.getenv("ENHANCE_CONTRAST", 1.02))
    ENHANCE_SKIN_STRENGTH = float(os.getenv("ENHANCE_SKIN_STRENGTH", 0.2))
    ENHANCE_SHARPEN_STRENGTH = float(os.getenv("ENHANCE_SHARPEN_STRENGTH", 0.3))
    EXPORT_JPEG_QUALITY = int(os.getenv("EXPORT_JPEG_QUALITY", 95))

    # 用户认证
    JWT_SECRET = os.getenv("JWT_SECRET", "idphoto-jwt-secret-change-in-production")
    JWT_EXPIRE_SECONDS = int(os.getenv("JWT_EXPIRE_SECONDS", 24 * 3600))  # 24 小时
    USERNAME_MIN_LEN = 2
    USERNAME_MAX_LEN = 20
    PASSWORD_MIN_LEN = 6
    PASSWORD_MAX_LEN = 50


class DevelopmentConfig(BaseConfig):
    """开发环境配置"""
    DEBUG = True
    LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")


class TestingConfig(BaseConfig):
    """测试环境配置"""
    TESTING = True
    LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING")
    SESSION_EXPIRE_SECONDS = 60  # 测试时 1 分钟过期
    MAX_SESSIONS = 10


class ProductionConfig(BaseConfig):
    """生产环境配置"""
    DEBUG = False
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 10 * 1024 * 1024))
    MAX_SESSIONS = int(os.getenv("MAX_SESSIONS", 200))


# 环境名 -> 配置类映射
config_map = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config():
    """根据 APP_ENV 环境变量获取对应配置"""
    env = os.getenv("APP_ENV", "production").lower()
    return config_map.get(env, ProductionConfig)()
