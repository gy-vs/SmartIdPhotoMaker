"""
智能证件照制作系统 - Flask Web API
提供 RESTful 接口供前端调用
"""

import os
import io
import uuid
import base64
import logging
import time
import threading
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import cv2
import numpy as np

from ai_engine import IDPhotoProcessor
from config import get_config
from models import (
    init_db, create_session, update_session_time, add_history,
    get_user_sessions, get_session_history, get_user_history, get_user_stats,
    get_session, mark_sessions_for_printing, create_print_task,
    get_print_task, get_user_print_tasks,
)
from printing import generate_print_layout, get_strategy
from auth import login_required, register_user, login_user

# 加载配置
cfg = get_config()

# 配置日志
logging.basicConfig(
    level=getattr(logging, cfg.LOG_LEVEL, logging.INFO),
    format=cfg.LOG_FORMAT,
    datefmt=cfg.LOG_DATE_FORMAT,
)
logger = logging.getLogger("app")

app = Flask(__name__)
CORS(app)

os.makedirs(cfg.UPLOAD_DIR, exist_ok=True)
os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)

# 初始化用户数据库
init_db()

# Flask 全局限制
app.config["MAX_CONTENT_LENGTH"] = cfg.MAX_FILE_SIZE

# 会话管理
processors: dict[str, IDPhotoProcessor] = {}
session_timestamps: dict[str, float] = {}
_cleanup_lock = threading.Lock()


def get_processor(sid: str) -> IDPhotoProcessor:
    if sid not in processors:
        processors[sid] = IDPhotoProcessor()
    session_timestamps[sid] = time.time()
    return processors[sid]


def cleanup_expired_sessions():
    """清理过期会话及其关联的磁盘文件"""
    with _cleanup_lock:
        now = time.time()
        expired = [
            sid for sid, ts in session_timestamps.items()
            if now - ts > cfg.SESSION_EXPIRE_SECONDS
        ]
        for sid in expired:
            processors.pop(sid, None)
            session_timestamps.pop(sid, None)
            _cleanup_session_files(sid)

        if expired:
            logger.info("已清理 %d 个过期会话: %s", len(expired), expired)


def _cleanup_session_files(sid: str):
    """清理指定会话的上传和导出文件"""
    for directory in [cfg.UPLOAD_DIR, cfg.OUTPUT_DIR]:
        try:
            for fname in os.listdir(directory):
                if fname.startswith(sid):
                    fpath = os.path.join(directory, fname)
                    os.remove(fpath)
                    logger.debug("已删除文件: %s", fpath)
        except OSError as e:
            logger.warning("清理文件失败: dir=%s, sid=%s, %s", directory, sid, e)


def _start_cleanup_timer():
    """启动定期清理定时器"""
    cleanup_expired_sessions()
    timer = threading.Timer(cfg.SESSION_CLEANUP_INTERVAL, _start_cleanup_timer)
    timer.daemon = True
    timer.start()


_start_cleanup_timer()


def image_to_base64(image: np.ndarray) -> str:
    """将 OpenCV 图像编码为 base64 字符串"""
    try:
        success, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not success:
            raise ValueError("cv2.imencode 编码失败")
        return base64.b64encode(buf).decode("utf-8")
    except Exception as e:
        logger.error("图像编码为 base64 失败: %s", e)
        raise RuntimeError(f"图像编码为 base64 失败: {e}")


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "智能证件照制作系统"})


@app.route("/api/register", methods=["POST"])
def register():
    """用户注册"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "请提供用户名和密码"}), 400
    username = data.get("username", "")
    password = data.get("password", "")
    result, status = register_user(username, password)
    if status == 201:
        logger.info("新用户注册: %s", username)
    return jsonify(result), status


@app.route("/api/login", methods=["POST"])
def login():
    """用户登录"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "请提供用户名和密码"}), 400
    username = data.get("username", "")
    password = data.get("password", "")
    result, status = login_user(username, password)
    return jsonify(result), status


@app.route("/api/upload", methods=["POST"])
@login_required
def upload_photo():
    """上传照片并自动检测人脸"""
    if "file" not in request.files:
        logger.warning("上传请求中未包含文件")
        return jsonify({"error": "未上传文件，请选择一张照片后重试"}), 400

    file = request.files["file"]
    if file.filename == "":
        logger.warning("上传的文件名为空")
        return jsonify({"error": "文件名为空，请重新选择有效的图片文件"}), 400

    # 校验文件扩展名
    ext = os.path.splitext(file.filename)[1].lower() or ".jpg"
    if ext not in cfg.ALLOWED_EXTENSIONS:
        logger.warning("不支持的文件扩展名: %s", ext)
        return jsonify({"error": f"不支持的文件格式 ({ext})，请上传 JPG/PNG/BMP 格式的图片"}), 400

    # 校验文件大小
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > cfg.MAX_FILE_SIZE:
        size_mb = round(file_size / (1024 * 1024), 1)
        logger.warning("文件过大: %.1fMB (上限 %dMB)", size_mb, cfg.MAX_FILE_SIZE // (1024 * 1024))
        return jsonify({"error": f"文件大小 ({size_mb}MB) 超过限制，请上传不超过 {cfg.MAX_FILE_SIZE // (1024 * 1024)}MB 的图片"}), 400

    # 校验文件内容（magic bytes）
    header = file.read(8)
    file.seek(0)
    is_valid_image = any(header.startswith(sig) for sig in cfg.IMAGE_SIGNATURES)
    if not is_valid_image:
        logger.warning("文件内容不是有效的图片格式: filename=%s", file.filename)
        return jsonify({"error": "文件内容不是有效的图片，请确认上传的是真实的 JPG/PNG/BMP 图片文件"}), 400

    # 检查会话数量限制
    if len(processors) >= cfg.MAX_SESSIONS:
        cleanup_expired_sessions()
        if len(processors) >= cfg.MAX_SESSIONS:
            logger.warning("会话数量已达上限: %d", cfg.MAX_SESSIONS)
            return jsonify({"error": "服务器繁忙，请稍后再试"}), 503

    # 生成 session id
    sid = str(uuid.uuid4())[:8]
    save_path = os.path.join(cfg.UPLOAD_DIR, f"{sid}{ext}")
    file.save(save_path)
    logger.info("照片已保存: sid=%s, path=%s, size=%.1fKB", sid, save_path, file_size / 1024)

    # 校验图片尺寸
    img_check = cv2.imread(save_path)
    if img_check is None:
        logger.warning("cv2.imread 无法读取已保存的文件: %s", save_path)
        os.remove(save_path)
        return jsonify({"error": "无法解析图片内容，请确认文件未损坏后重试"}), 400

    img_h, img_w = img_check.shape[:2]
    if img_w < cfg.MIN_IMAGE_SIZE or img_h < cfg.MIN_IMAGE_SIZE:
        logger.warning("图片尺寸过小: %dx%d (最小 %dpx)", img_w, img_h, cfg.MIN_IMAGE_SIZE)
        os.remove(save_path)
        return jsonify({"error": f"图片尺寸过小 ({img_w}×{img_h})，请上传宽高不小于 {cfg.MIN_IMAGE_SIZE}px 的图片"}), 400
    if img_w > cfg.MAX_IMAGE_SIZE or img_h > cfg.MAX_IMAGE_SIZE:
        logger.warning("图片尺寸过大: %dx%d (最大 %dpx)", img_w, img_h, cfg.MAX_IMAGE_SIZE)
        os.remove(save_path)
        return jsonify({"error": f"图片尺寸过大 ({img_w}×{img_h})，请上传宽高不超过 {cfg.MAX_IMAGE_SIZE}px 的图片"}), 400

    # 加载并检测
    try:
        proc = get_processor(sid)
        success = proc.load_image(save_path)
        if not success:
            logger.warning("无法加载图片: sid=%s, path=%s", sid, save_path)
            return jsonify({"error": "无法加载图片，请确认文件为 JPG/PNG/BMP 格式后重试"}), 400

        result = {
            "session_id": sid,
            "has_face": proc.has_face(),
            "original": image_to_base64(proc.original_image),
            "preview": image_to_base64(proc.current_image),
            "log": proc.get_log(),
        }

        if proc.has_face():
            result["confidence"] = round(float(proc.face_info["confidence"]), 2)
            result["has_glasses"] = proc.check_glasses()
            logger.info("上传成功: sid=%s, 检测到人脸(置信度=%.2f, 眼镜=%s)",
                        sid, result["confidence"], result["has_glasses"])
        else:
            logger.info("上传成功: sid=%s, 未检测到人脸", sid)

        # 持久化会话记录
        username = getattr(request, "current_user", "anonymous")
        create_session(
            sid=sid, username=username, filename=file.filename,
            file_path=save_path, has_face=proc.has_face(),
            confidence=result.get("confidence"),
            has_glasses=result.get("has_glasses", False),
        )
        add_history(sid, username, "upload", file.filename)

        return jsonify(result)
    except Exception as e:
        logger.error("处理上传照片时出错: sid=%s, %s", sid, e, exc_info=True)
        return jsonify({"error": f"处理上传照片时出错: {e}"}), 500


@app.route("/api/process", methods=["POST"])
@login_required
def process_photo():
    """执行单步处理操作"""
    data = request.get_json()
    if not data or "session_id" not in data:
        logger.warning("处理请求缺少 session_id")
        return jsonify({"error": "缺少 session_id，请先上传照片获取会话标识"}), 400

    sid = data["session_id"]
    action = data.get("action", "")

    if sid not in processors:
        logger.warning("无效的 session_id: %s", sid)
        return jsonify({"error": "无效的会话标识，请重新上传照片"}), 400

    proc = get_processor(sid)

    if proc.current_image is None:
        logger.warning("会话中无照片: sid=%s, action=%s", sid, action)
        return jsonify({"error": "当前会话中没有照片，请先上传一张照片"}), 400

    logger.info("开始处理: sid=%s, action=%s", sid, action)
    try:
        if action == "replace_background":
            bg_color = data.get("bg_color", "蓝底")
            if bg_color not in cfg.ALLOWED_BG_COLORS:
                logger.warning("无效的背景颜色: %s", bg_color)
                return jsonify({"error": f"不支持的背景颜色: {bg_color}，可选值: {', '.join(cfg.ALLOWED_BG_COLORS)}"}), 400
            proc.process_replace_background(bg_color)
        elif action == "remove_glasses":
            proc.process_remove_glasses()
        elif action == "enhance":
            proc.process_enhance()
        elif action == "crop":
            size_name = data.get("size", "一寸")
            if size_name not in cfg.ALLOWED_PHOTO_SIZES:
                logger.warning("无效的证件照尺寸: %s", size_name)
                return jsonify({"error": f"不支持的证件照尺寸: {size_name}，可选值: {', '.join(cfg.ALLOWED_PHOTO_SIZES)}"}), 400
            proc.process_crop(size_name)
        elif action == "auto":
            bg_color = data.get("bg_color", "蓝底")
            size_name = data.get("size", "一寸")
            if bg_color not in cfg.ALLOWED_BG_COLORS:
                logger.warning("无效的背景颜色: %s", bg_color)
                return jsonify({"error": f"不支持的背景颜色: {bg_color}，可选值: {', '.join(cfg.ALLOWED_BG_COLORS)}"}), 400
            if size_name not in cfg.ALLOWED_PHOTO_SIZES:
                logger.warning("无效的证件照尺寸: %s", size_name)
                return jsonify({"error": f"不支持的证件照尺寸: {size_name}，可选值: {', '.join(cfg.ALLOWED_PHOTO_SIZES)}"}), 400
            proc.process_full_pipeline(
                bg_color=bg_color, size_name=size_name,
                remove_glasses=True, enhance=True
            )
        elif action == "reset":
            proc.reset()
        else:
            logger.warning("未知操作: sid=%s, action=%s", sid, action)
            return jsonify({
                "error": f"未知操作: {action}，支持的操作有: replace_background(替换背景)、remove_glasses(消除眼镜)、enhance(画质增强)、crop(裁剪证件照)、auto(一键处理)、reset(重置)"
            }), 400

        logger.info("处理完成: sid=%s, action=%s", sid, action)

        # 记录操作历史
        username = getattr(request, "current_user", "anonymous")
        params_str = ""
        if action == "replace_background":
            params_str = data.get("bg_color", "蓝底")
        elif action == "crop":
            params_str = data.get("size", "一寸")
        elif action == "auto":
            params_str = f"{data.get('bg_color', '蓝底')},{data.get('size', '一寸')}"
        add_history(sid, username, action, params_str)
        update_session_time(sid)

        return jsonify({
            "session_id": sid,
            "preview": image_to_base64(proc.current_image),
            "log": proc.get_log(),
        })
    except Exception as e:
        logger.error("执行操作时出错: sid=%s, action=%s, %s", sid, action, e, exc_info=True)
        username = getattr(request, "current_user", "anonymous")
        add_history(sid, username, action, status="error")
        return jsonify({"error": f"执行操作 '{action}' 时出错: {e}"}), 500


@app.route("/api/export", methods=["POST"])
@login_required
def export_photo():
    """导出证件照"""
    data = request.get_json()
    if not data or "session_id" not in data:
        logger.warning("导出请求缺少 session_id")
        return jsonify({"error": "缺少 session_id，请先上传照片获取会话标识"}), 400

    sid = data["session_id"]
    fmt = data.get("format", "jpg")

    if sid not in processors:
        logger.warning("导出时无效的 session_id: %s", sid)
        return jsonify({"error": "无效的会话标识，请重新上传照片"}), 400

    if fmt not in cfg.ALLOWED_EXPORT_FORMATS:
        logger.warning("无效的导出格式: %s", fmt)
        return jsonify({"error": f"不支持的导出格式: {fmt}，可选值: {', '.join(cfg.ALLOWED_EXPORT_FORMATS)}"}), 400

    proc = get_processor(sid)

    if proc.current_image is None:
        logger.warning("导出时无照片: sid=%s", sid)
        return jsonify({"error": "没有可导出的照片，请先上传并处理照片"}), 400

    try:
        ext = ".png" if fmt == "png" else ".jpg"
        out_path = os.path.join(cfg.OUTPUT_DIR, f"{sid}_result{ext}")
        if not proc.save_result(out_path):
            logger.error("保存照片失败: sid=%s, path=%s", sid, out_path)
            return jsonify({"error": "保存照片失败，请稍后重试或尝试更换导出格式"}), 500

        logger.info("导出成功: sid=%s, format=%s, path=%s", sid, fmt, out_path)
        username = getattr(request, "current_user", "anonymous")
        add_history(sid, username, "export", fmt)
        return send_file(out_path, as_attachment=True,
                         download_name=f"证件照{ext}")
    except Exception as e:
        logger.error("导出照片时出错: sid=%s, %s", sid, e, exc_info=True)
        return jsonify({"error": f"导出照片时出错: {e}"}), 500


@app.route("/api/detect", methods=["POST"])
@login_required
def detect_face():
    """获取人脸检测可视化结果"""
    data = request.get_json()
    if not data or "session_id" not in data:
        logger.warning("人脸检测请求缺少 session_id")
        return jsonify({"error": "缺少 session_id，请先上传照片获取会话标识"}), 400

    sid = data["session_id"]

    if sid not in processors:
        logger.warning("人脸检测时无效的 session_id: %s", sid)
        return jsonify({"error": "无效的会话标识，请重新上传照片"}), 400

    proc = get_processor(sid)

    if proc.current_image is None:
        logger.warning("人脸检测时无照片: sid=%s", sid)
        return jsonify({"error": "当前会话中没有照片，请先上传一张照片"}), 400

    if not proc.has_face():
        logger.info("未检测到人脸: sid=%s", sid)
        return jsonify({"error": "未检测到人脸，请上传包含清晰正面人脸的照片后重试"}), 400

    try:
        info = proc.face_info
        display_img = proc.current_image.copy()
        x, y, w, h = info["bbox"]
        cv2.rectangle(display_img, (x, y), (x + w, y + h), (0, 255, 0), 2)

        if info.get("landmarks"):
            for i, (lx, ly) in enumerate(info["landmarks"]):
                if i % 10 == 0:
                    cv2.circle(display_img, (lx, ly), 1, (0, 200, 255), -1)

        logger.info("人脸检测可视化完成: sid=%s, confidence=%.2f", sid, info["confidence"])
        username = getattr(request, "current_user", "anonymous")
        add_history(sid, username, "detect")
        return jsonify({
            "session_id": sid,
            "preview": image_to_base64(display_img),
            "confidence": round(float(info["confidence"]), 2),
            "has_glasses": proc.check_glasses(),
            "log": proc.get_log(),
        })
    except Exception as e:
        logger.error("人脸检测可视化时出错: sid=%s, %s", sid, e, exc_info=True)
        return jsonify({"error": f"人脸检测可视化时出错: {e}"}), 500


@app.route("/api/history", methods=["GET"])
@login_required
def get_history():
    """获取当前用户的操作历史"""
    username = request.current_user
    history_type = request.args.get("type", "all")
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))

    try:
        if history_type == "sessions":
            data = get_user_sessions(username, limit, offset)
            return jsonify({"sessions": data})
        elif history_type == "stats":
            data = get_user_stats(username)
            return jsonify({"stats": data})
        else:
            data = get_user_history(username, limit, offset)
            return jsonify({"history": data})
    except Exception as e:
        logger.error("获取历史记录失败: user=%s, %s", username, e, exc_info=True)
        return jsonify({"error": "获取历史记录失败，请稍后重试"}), 500


@app.route("/api/history/<sid>", methods=["GET"])
@login_required
def get_session_detail(sid):
    """获取指定会话的操作历史"""
    try:
        history = get_session_history(sid)
        return jsonify({"sid": sid, "history": history})
    except Exception as e:
        logger.error("获取会话历史失败: sid=%s, %s", sid, e, exc_info=True)
        return jsonify({"error": "获取会话历史失败，请稍后重试"}), 500


@app.route("/api/print/layouts", methods=["GET"])
@login_required
def get_available_layouts():
    """获取支持的排版版式列表"""
    try:
        layouts = []
        for key in ["one_inch", "two_inch", "mixed"]:
            strategy = get_strategy(key)
            layouts.append({
                "type": key,
                "name": strategy.get_layout_name(),
                "max_photos": strategy.get_max_photos(),
            })
        return jsonify({"layouts": layouts})
    except Exception as e:
        logger.error("获取版式列表失败: %s", e, exc_info=True)
        return jsonify({"error": "获取版式列表失败"}), 500


@app.route("/api/print/preview", methods=["POST"])
@login_required
def preview_print_layout():
    """预览排版效果（返回合成后的 JPG base64）"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "缺少请求参数"}), 400

    session_ids = data.get("session_ids", [])
    layout_type = data.get("layout_type", "one_inch")

    if not session_ids:
        return jsonify({"error": "请选择至少一张照片"}), 400

    if not isinstance(session_ids, list):
        return jsonify({"error": "session_ids 必须是数组"}), 400

    username = request.current_user

    try:
        strategy = get_strategy(layout_type)
        max_photos = strategy.get_max_photos()
        if len(session_ids) > max_photos:
            return jsonify({
                "error": f"照片数量超过限制（最大 {max_photos} 张）"
            }), 400

        photo_paths = []
        for sid in session_ids:
            session = get_session(sid)
            if not session:
                return jsonify({"error": f"会话不存在: {sid}"}), 404
            if session["username"] != username:
                return jsonify({"error": "无权访问其他用户的会话"}), 403

            output_path = os.path.join(cfg.OUTPUT_DIR, f"{sid}_result.jpg")
            if not os.path.exists(output_path):
                output_path = os.path.join(cfg.OUTPUT_DIR, f"{sid}_result.png")
            if not os.path.exists(output_path):
                output_path = session["file_path"]
                if not os.path.exists(output_path):
                    return jsonify({
                        "error": f"会话 {sid} 没有可用的照片文件"
                    }), 404
            photo_paths.append(output_path)

        from printing import LayoutComposer
        composer = LayoutComposer(strategy)
        img = composer.compose_image(photo_paths)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        import base64 as b64
        img_base64 = b64.b64encode(buf.getvalue()).decode("utf-8")

        return jsonify({
            "preview": img_base64,
            "layout_type": layout_type,
            "layout_name": strategy.get_layout_name(),
            "photo_count": len(photo_paths),
            "max_photos": max_photos,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error("预览排版失败: %s", e, exc_info=True)
        return jsonify({"error": f"预览排版失败: {e}"}), 500


@app.route("/api/print/generate", methods=["POST"])
@login_required
def generate_print_files():
    """生成排版文件（PDF + JPG）"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "缺少请求参数"}), 400

    session_ids = data.get("session_ids", [])
    layout_type = data.get("layout_type", "one_inch")
    output_format = data.get("format", "both")

    if not session_ids:
        return jsonify({"error": "请选择至少一张照片"}), 400

    if not isinstance(session_ids, list):
        return jsonify({"error": "session_ids 必须是数组"}), 400

    username = request.current_user

    try:
        strategy = get_strategy(layout_type)
        max_photos = strategy.get_max_photos()
        if len(session_ids) > max_photos:
            return jsonify({
                "error": f"照片数量超过限制（最大 {max_photos} 张）"
            }), 400

        photo_paths = []
        for sid in session_ids:
            session = get_session(sid)
            if not session:
                return jsonify({"error": f"会话不存在: {sid}"}), 404
            if session["username"] != username:
                return jsonify({"error": "无权访问其他用户的会话"}), 403

            output_path = os.path.join(cfg.OUTPUT_DIR, f"{sid}_result.jpg")
            if not os.path.exists(output_path):
                output_path = os.path.join(cfg.OUTPUT_DIR, f"{sid}_result.png")
            if not os.path.exists(output_path):
                output_path = session["file_path"]
                if not os.path.exists(output_path):
                    return jsonify({
                        "error": f"会话 {sid} 没有可用的照片文件"
                    }), 404
            photo_paths.append(output_path)

        print_dir = os.path.join(cfg.OUTPUT_DIR, "print")
        os.makedirs(print_dir, exist_ok=True)

        pdf_path, jpg_path = generate_print_layout(
            photo_paths=photo_paths,
            layout_type=layout_type,
            output_dir=print_dir,
            output_format=output_format,
        )

        task_id = str(uuid.uuid4())[:12]
        create_print_task(
            task_id=task_id,
            username=username,
            layout_type=layout_type,
            session_ids=session_ids,
            pdf_path=pdf_path,
            jpg_path=jpg_path,
            status="completed",
        )

        mark_sessions_for_printing(session_ids)

        for sid in session_ids:
            add_history(sid, username, "print", layout_type)

        result = {
            "task_id": task_id,
            "layout_type": layout_type,
            "layout_name": strategy.get_layout_name(),
            "photo_count": len(photo_paths),
        }

        if pdf_path:
            result["pdf_url"] = f"/api/print/download/{task_id}/pdf"
        if jpg_path:
            result["jpg_url"] = f"/api/print/download/{task_id}/jpg"

        logger.info("排版生成成功: task_id=%s, layout=%s, photos=%d",
                    task_id, layout_type, len(photo_paths))
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error("生成排版文件失败: %s", e, exc_info=True)
        return jsonify({"error": f"生成排版文件失败: {e}"}), 500


@app.route("/api/print/download/<task_id>/<file_type>", methods=["GET"])
@login_required
def download_print_file(task_id: str, file_type: str):
    """下载排版生成的文件"""
    if file_type not in {"pdf", "jpg"}:
        return jsonify({"error": "不支持的文件类型"}), 400

    task = get_print_task(task_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404

    if task["username"] != request.current_user:
        return jsonify({"error": "无权下载"}), 403

    file_path = task.get(f"{file_type}_path")
    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": "文件不存在或已过期"}), 404

    try:
        download_name = f"证件照排版_{task['layout_type']}_{task_id}.{file_type}"
        return send_file(file_path, as_attachment=True,
                        download_name=download_name)
    except Exception as e:
        logger.error("下载文件失败: task_id=%s, %s", task_id, e, exc_info=True)
        return jsonify({"error": "下载失败"}), 500


@app.route("/api/print/tasks", methods=["GET"])
@login_required
def get_print_tasks():
    """获取当前用户的排版任务列表"""
    username = request.current_user
    limit = min(int(request.args.get("limit", 20)), 100)
    offset = int(request.args.get("offset", 0))

    try:
        tasks = get_user_print_tasks(username, limit, offset)
        return jsonify({"tasks": tasks})
    except Exception as e:
        logger.error("获取排版任务列表失败: %s", e, exc_info=True)
        return jsonify({"error": "获取排版任务列表失败"}), 500


if __name__ == "__main__":
    logger.info("智能证件照制作系统启动，监听 %s:%d", cfg.HOST, cfg.PORT)
    app.run(host=cfg.HOST, port=cfg.PORT, debug=getattr(cfg, "DEBUG", False))
