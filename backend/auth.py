"""
智能证件照制作系统 - 用户认证模块
JWT Token 认证 + bcrypt 密码哈希
"""

import re
import logging
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
import bcrypt
from flask import request, jsonify

from config import get_config
from models import create_user, get_user_by_username, update_last_login

logger = logging.getLogger("auth")
cfg = get_config()


def hash_password(password: str) -> str:
    """密码哈希"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码"""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def generate_token(username: str) -> str:
    """生成 JWT Token"""
    payload = {
        "sub": username,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(seconds=cfg.JWT_EXPIRE_SECONDS),
    }
    return jwt.encode(payload, cfg.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    """解码 JWT Token，失败返回 None"""
    try:
        return jwt.decode(token, cfg.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        logger.debug("Token 已过期")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug("Token 无效: %s", e)
        return None


def validate_username(username: str) -> str | None:
    """校验用户名，返回错误信息或 None"""
    if not username or not isinstance(username, str):
        return "用户名不能为空"
    username = username.strip()
    if len(username) < 2 or len(username) > 20:
        return "用户名长度需在 2~20 个字符之间"
    if not re.match(r'^[\w\u4e00-\u9fff]+$', username):
        return "用户名只能包含字母、数字、下划线或中文"
    return None


def validate_password(password: str) -> str | None:
    """校验密码，返回错误信息或 None"""
    if not password or not isinstance(password, str):
        return "密码不能为空"
    if len(password) < 6 or len(password) > 50:
        return "密码长度需在 6~50 个字符之间"
    return None


def login_required(f):
    """认证装饰器：需要有效的 JWT Token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            token = request.args.get("token")

        if not token:
            return jsonify({"error": "未提供认证令牌，请先登录"}), 401

        payload = decode_token(token)
        if payload is None:
            return jsonify({"error": "认证令牌无效或已过期，请重新登录"}), 401

        request.current_user = payload["sub"]
        return f(*args, **kwargs)
    return decorated


def register_user(username: str, password: str) -> tuple:
    """
    注册用户
    返回 (response_dict, status_code)
    """
    # 校验用户名
    err = validate_username(username)
    if err:
        return {"error": err}, 400

    # 校验密码
    err = validate_password(password)
    if err:
        return {"error": err}, 400

    # 创建用户
    pw_hash = hash_password(password)
    if not create_user(username, pw_hash):
        return {"error": "用户名已被注册，请更换一个用户名"}, 409

    logger.info("用户注册成功: %s", username)
    return {"message": "注册成功"}, 201


def login_user(username: str, password: str) -> tuple:
    """
    用户登录
    返回 (response_dict, status_code)
    """
    if not username or not password:
        return {"error": "用户名和密码不能为空"}, 400

    user = get_user_by_username(username)
    if not user:
        return {"error": "用户名或密码错误"}, 401

    if not verify_password(password, user["password_hash"]):
        return {"error": "用户名或密码错误"}, 401

    # 更新最后登录时间
    update_last_login(username)

    # 生成 token
    token = generate_token(username)
    logger.info("用户登录成功: %s", username)

    return {
        "message": "登录成功",
        "token": token,
        "username": username,
    }, 200
