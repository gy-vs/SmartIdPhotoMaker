"""
智能证件照制作系统 - A4 批量排版导出服务
基于策略模式实现多种版式，支持 A4 PDF（300 DPI）和 A4 JPG（300 DPI）输出
"""

import io
import os
import logging
import math
import uuid
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional

import cv2
import numpy as np
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from config import get_config
from models import get_session, update_session_print_flag

logger = logging.getLogger("printing")
cfg = get_config()

A4_WIDTH_MM = 210
A4_HEIGHT_MM = 297
DPI = 300
MM_TO_PT = 72.0 / 25.4
MM_TO_PX = DPI / 25.4

BLEED_MM = 2.0
GAP_MM = 3.0
CROP_LINE_COLOR = (200, 200, 200)
SAFE_GRID_COLOR = (230, 230, 230)
PLACEHOLDER_COLOR = (235, 235, 235)


class LayoutStrategy(ABC):
    """排版策略抽象基类，所有版式策略必须实现 layout 方法"""

    name: str = ""

    @abstractmethod
    def layout(self, photos: List[np.ndarray]) -> List[dict]:
        """
        根据输入照片列表，生成排版布局。

        Args:
            photos: 已加载的证件照 numpy 数组列表（已按尺寸裁剪）

        Returns:
            布局信息列表，每项为 dict: {
                "photo": np.ndarray,  # 要绘制的照片（或 None 代表占位）
                "row": int,
                "col": int,
                "x_mm": float,
                "y_mm": float,
                "w_mm": float,
                "h_mm": float,
                "bleed_mm": float,
            }
        """

    @abstractmethod
    def photo_size_mm(self) -> Tuple[float, float]:
        """
        返回单张照片的宽高（毫米）。

        Returns:
            (width_mm, height_mm)
        """

    @abstractmethod
    def description(self) -> str:
        """返回版式描述字符串"""


def _build_grid_layout(
    photos: List[Optional[np.ndarray]],
    w_mm: float,
    h_mm: float,
    bleed_mm: float,
    gap_mm: float,
) -> List[dict]:
    """
    通用网格布局生成器。
    在 A4 页面内根据照片尺寸 + 出血 + 间距计算可容纳的行列，
    剩余位置使用占位框补齐。
    """
    cols = int((A4_WIDTH_MM - 2 * bleed_mm + gap_mm) // (w_mm + gap_mm))
    rows = int((A4_HEIGHT_MM - 2 * bleed_mm + gap_mm) // (h_mm + gap_mm))

    content_width = cols * w_mm + (cols - 1) * gap_mm
    content_height = rows * h_mm + (rows - 1) * gap_mm
    offset_x = (A4_WIDTH_MM - content_width) / 2
    offset_y = (A4_HEIGHT_MM - content_height) / 2

    total = rows * cols
    filled: List[Optional[np.ndarray]] = []
    for i in range(total):
        if i < len(photos):
            filled.append(photos[i])
        else:
            filled.append(None)

    layout = []
    for idx in range(total):
        r = idx // cols
        c = idx % cols
        x_mm = offset_x + c * (w_mm + gap_mm)
        y_mm = offset_y + r * (h_mm + gap_mm)
        layout.append({
            "photo": filled[idx],
            "row": r,
            "col": c,
            "x_mm": x_mm,
            "y_mm": y_mm,
            "w_mm": w_mm,
            "h_mm": h_mm,
            "bleed_mm": bleed_mm,
        })
    return layout


class OneInchStrategy(LayoutStrategy):
    """纯一寸版式：每页 8 张一寸照片"""

    name = "one_inch"

    def photo_size_mm(self) -> Tuple[float, float]:
        return 25.0, 35.0

    def description(self) -> str:
        return "一寸 (25×35mm)"

    def layout(self, photos: List[np.ndarray]) -> List[dict]:
        w, h = self.photo_size_mm()
        return _build_grid_layout(photos, w, h, BLEED_MM, GAP_MM)


class TwoInchStrategy(LayoutStrategy):
    """纯二寸版式：每页 4 张二寸照片"""

    name = "two_inch"

    def photo_size_mm(self) -> Tuple[float, float]:
        return 35.0, 49.0

    def description(self) -> str:
        return "二寸 (35×49mm)"

    def layout(self, photos: List[np.ndarray]) -> List[dict]:
        w, h = self.photo_size_mm()
        return _build_grid_layout(photos, w, h, BLEED_MM, GAP_MM)


class MixedStrategy(LayoutStrategy):
    """一寸+二寸混排版式：同页混合 2 张二寸 + 4 张一寸"""

    name = "mixed"

    def photo_size_mm(self) -> Tuple[float, float]:
        return 35.0, 49.0

    def description(self) -> str:
        return "一寸 + 二寸混排"

    def layout(self, photos: List[np.ndarray]) -> List[dict]:
        one_w, one_h = 25.0, 35.0
        two_w, two_h = 35.0, 49.0

        if len(photos) >= 4:
            group_one = photos[:4]
            group_two = photos[4:6]
            rest = photos[6:]
        else:
            group_one = photos[:len(photos)]
            group_two = []
            rest = []

        layout: List[dict] = []
        row_idx = 0

        def _emit(items: List[Optional[np.ndarray]], w: float, h: float):
            nonlocal row_idx
            cols = int((A4_WIDTH_MM - 2 * BLEED_MM + GAP_MM) // (w + GAP_MM))
            content_width = cols * w + (cols - 1) * GAP_MM
            offset_x = (A4_WIDTH_MM - content_width) / 2
            for i in range(cols):
                x_mm = offset_x + i * (w + GAP_MM)
                y_mm = BLEED_MM + row_idx * (h + GAP_MM)
                photo = items[i] if i < len(items) else None
                layout.append({
                    "photo": photo,
                    "row": row_idx,
                    "col": i,
                    "x_mm": x_mm,
                    "y_mm": y_mm,
                    "w_mm": w,
                    "h_mm": h,
                    "bleed_mm": BLEED_MM,
                })
            row_idx += 1

        _emit(group_two, two_w, two_h)
        _emit(group_two[2:], two_w, two_h)
        _emit(group_one, one_w, one_h)

        total_rows = row_idx
        if len(rest) > 0:
            per_row = len(rest) // total_rows if total_rows > 0 else len(rest)
            chunks = []
            start = 0
            for i in range(total_rows):
                end = start + per_row + (1 if i < len(rest) % max(total_rows, 1) else 0)
                chunks.append(rest[start:end])
                start = end
            while len(chunks) < total_rows:
                chunks.append([])
            for chunk in chunks:
                _emit(chunk, one_w, one_h)
        else:
            _emit([], one_w, one_h)
            _emit([], one_w, one_h)

        return layout


STRATEGY_MAP = {
    "one_inch": OneInchStrategy,
    "two_inch": TwoInchStrategy,
    "mixed": MixedStrategy,
}


def get_strategy(key: str) -> LayoutStrategy:
    """
    根据 key 获取对应的排版策略实例。

    Args:
        key: 版式标识（one_inch / two_inch / mixed）

    Returns:
        实例化的 LayoutStrategy

    Raises:
        ValueError: key 不在支持列表中
    """
    if key not in STRATEGY_MAP:
        raise ValueError(f"不支持的版式: {key}，可选值: {', '.join(STRATEGY_MAP.keys())}")
    return STRATEGY_MAP[key]()


def _load_photo_for_layout(session_data: dict, strategy: LayoutStrategy) -> Optional[np.ndarray]:
    """
    根据会话数据加载照片，并按策略尺寸裁剪。

    Args:
        session_data: get_session 返回的会话字典
        strategy: 当前版式策略

    Returns:
        裁剪后的 BGR ndarray，失败返回 None
    """
    path = session_data.get("file_path")
    if not path or not os.path.exists(path):
        logger.warning("会话文件不存在: sid=%s path=%s", session_data.get("sid"), path)
        return None

    raw = cv2.imread(path, cv2.IMREAD_COLOR)
    if raw is None:
        logger.warning("cv2.imread 失败: %s", path)
        return None

    w_mm, h_mm = strategy.photo_size_mm()
    px_w = int(w_mm * MM_TO_PX)
    px_h = int(h_mm * MM_TO_PX)

    h_raw, w_raw = raw.shape[:2]
    if w_raw / h_raw > px_w / px_h:
        scale = px_h / h_raw
        resized = cv2.resize(raw, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        rx = (resized.shape[1] - px_w) // 2
        cropped = resized[:, rx:rx + px_w]
    else:
        scale = px_w / w_raw
        resized = cv2.resize(raw, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        ry = (resized.shape[0] - px_h) // 2
        cropped = resized[ry:ry + px_h, :]

    if cropped.shape[0] != px_h or cropped.shape[1] != px_w:
        cropped = cv2.copyMakeBorder(
            cropped,
            max(0, (px_h - cropped.shape[0]) // 2),
            max(0, px_h - cropped.shape[0] - max(0, (px_h - cropped.shape[0]) // 2)),
            max(0, (px_w - cropped.shape[1]) // 2),
            max(0, px_w - cropped.shape[1] - max(0, (px_w - cropped.shape[1]) // 2)),
            cv2.BORDER_CONSTANT,
            value=(255, 255, 255),
        )
        cropped = cropped[:px_h, :px_w]

    return cropped


def _draw_crop_guide(pil_img: Image.Image, layout: List[dict]) -> None:
    """在 PIL 图像上绘制裁切线和安全网格辅助线"""
    draw = ImageDraw.Draw(pil_img)
    px_per_mm = DPI / 25.4
    for item in layout:
        if item["photo"] is None:
            continue
        x0 = int(item["x_mm"] * px_per_mm)
        y0 = int(item["y_mm"] * px_per_mm)
        x1 = int((item["x_mm"] + item["w_mm"]) * px_per_mm)
        y1 = int((item["y_mm"] + item["h_mm"]) * px_per_mm)
        draw.rectangle([x0, y0, x1, y1], outline=CROP_LINE_COLOR, width=2)
        mid_x = (x0 + x1) // 2
        mid_y = (y0 + y1) // 2
        draw.line([x0, mid_y, x1, mid_y], fill=SAFE_GRID_COLOR, width=1)
        draw.line([mid_x, y0, mid_x, y1], fill=SAFE_GRID_COLOR, width=1)


def _render_a4_pil(layout: List[dict], strategy: LayoutStrategy) -> Image.Image:
    """
    将布局绘制到 A4 尺寸的 PIL 图像上。

    Args:
        layout: 由策略生成的布局列表
        strategy: 当前版式策略

    Returns:
        A4 尺寸的 PIL Image (RGB)
    """
    px_w = int(A4_WIDTH_MM * MM_TO_PX)
    px_h = int(A4_HEIGHT_MM * MM_TO_PX)
    canvas_img = Image.new("RGB", (px_w, px_h), (255, 255, 255))

    px_per_mm = DPI / 25.4
    for item in layout:
        x0 = int(item["x_mm"] * px_per_mm)
        y0 = int(item["y_mm"] * px_per_mm)
        w_px = int(item["w_mm"] * px_per_mm)
        h_px = int(item["h_mm"] * px_per_mm)

        if item["photo"] is None:
            placeholder = Image.new("RGB", (w_px, h_px), PLACEHOLDER_COLOR)
            draw = ImageDraw.Draw(placeholder)
            draw.rectangle([0, 0, w_px - 1, h_px - 1], outline=(180, 180, 180), width=1)
            text = "留白占位"
            tw = draw.textlength(text) if hasattr(draw, "textlength") else len(text) * 6
            draw.text(((w_px - tw) // 2, (h_px - 12) // 2), text, fill=(160, 160, 160))
            canvas_img.paste(placeholder, (x0, y0))
        else:
            photo_bgr = item["photo"]
            if photo_bgr.shape[0] != h_px or photo_bgr.shape[1] != w_px:
                photo_bgr = cv2.resize(photo_bgr, (w_px, h_px), interpolation=cv2.INTER_AREA)
            photo_rgb = cv2.cvtColor(photo_bgr, cv2.COLOR_BGR2RGB)
            canvas_img.paste(Image.fromarray(photo_rgb), (x0, y0))

    _draw_crop_guide(canvas_img, layout)
    return canvas_img


def generate_a4_pdf(layout: List[dict], strategy: LayoutStrategy, output_path: str) -> str:
    """
    根据布局生成 A4 PDF 文件。

    Args:
        layout: 由策略生成的布局列表
        strategy: 当前版式策略
        output_path: PDF 输出文件路径

    Returns:
        生成的 PDF 文件路径

    Raises:
        RuntimeError: PDF 写入失败
    """
    try:
        c = canvas.Canvas(output_path, pagesize=A4)
        a4_w_pt, a4_h_pt = A4

        px_per_mm_pt = 72.0 / 25.4
        px_per_mm = DPI / 25.4

        for item in layout:
            x_pt = item["x_mm"] * px_per_mm_pt
            y_pt = a4_h_pt - (item["y_mm"] + item["h_mm"]) * px_per_mm_pt
            w_pt = item["w_mm"] * px_per_mm_pt
            h_pt = item["h_mm"] * px_per_mm_pt

            if item["photo"] is None:
                c.setFillColorRGB(0.92, 0.92, 0.92)
                c.rect(x_pt, y_pt, w_pt, h_pt, fill=1, stroke=0)
                c.setStrokeColorRGB(0.7, 0.7, 0.7)
                c.setLineWidth(0.3)
                c.rect(x_pt, y_pt, w_pt, h_pt, fill=0, stroke=1)
                c.setFillColorRGB(0.6, 0.6, 0.6)
                c.setFont("Helvetica", 9)
                c.drawCentredString(x_pt + w_pt / 2, y_pt + h_pt / 2, "留白占位")
            else:
                buf = io.BytesIO()
                photo_bgr = item["photo"]
                photo_rgb = cv2.cvtColor(photo_bgr, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(photo_rgb)
                pil_img.save(buf, format="JPEG", quality=95)
                buf.seek(0)
                reader = ImageReader(buf)
                c.drawImage(reader, x_pt, y_pt, width=w_pt, height=h_pt)

        c.setStrokeColorRGB(0.78, 0.78, 0.78)
        c.setLineWidth(0.4)
        for item in layout:
            x_pt = item["x_mm"] * px_per_mm_pt
            y_pt = a4_h_pt - (item["y_mm"] + item["h_mm"]) * px_per_mm_pt
            w_pt = item["w_mm"] * px_per_mm_pt
            h_pt = item["h_mm"] * px_per_mm_pt
            c.rect(x_pt, y_pt, w_pt, h_pt, fill=0, stroke=1)
            mid_y_pt = y_pt + h_pt / 2
            c.line(x_pt, mid_y_pt, x_pt + w_pt, mid_y_pt)
            mid_x_pt = x_pt + w_pt / 2
            c.line(mid_x_pt, y_pt, mid_x_pt, y_pt + h_pt)

        c.showPage()
        c.save()
        logger.info("A4 PDF 已生成: %s", output_path)
        return output_path
    except Exception as e:
        logger.error("生成 PDF 失败: %s", e, exc_info=True)
        raise RuntimeError(f"生成 PDF 失败: {e}") from e


def generate_a4_jpg(layout: List[dict], strategy: LayoutStrategy, output_path: str) -> str:
    """
    根据布局生成 A4 JPG 文件（300 DPI 高清）。

    Args:
        layout: 由策略生成的布局列表
        strategy: 当前版式策略
        output_path: JPG 输出文件路径

    Returns:
        生成的 JPG 文件路径

    Raises:
        RuntimeError: JPG 写入失败
    """
    try:
        img = _render_a4_pil(layout, strategy)
        img.save(output_path, "JPEG", quality=95)
        logger.info("A4 JPG 已生成: %s", output_path)
        return output_path
    except Exception as e:
        logger.error("生成 JPG 失败: %s", e, exc_info=True)
        raise RuntimeError(f"生成 JPG 失败: {e}") from e


def build_printing_task(
    session_ids: List[str],
    layout_key: str,
    username: str,
) -> Tuple[str, str]:
    """
    构建批量排版任务：加载照片、执行策略、输出 PDF + JPG。

    Args:
        session_ids: 选中的会话 ID 列表
        layout_key: 版式标识（one_inch / two_inch / mixed）
        username: 当前登录用户名

    Returns:
        (pdf_path, jpg_path) 生成的两个文件的绝对路径

    Raises:
        ValueError: 参数不合法
        RuntimeError: 排版失败
    """
    if not session_ids:
        raise ValueError("session_ids 不能为空")
    strategy = get_strategy(layout_key)

    photos: List[np.ndarray] = []
    valid_sids: List[str] = []
    for sid in session_ids:
        session_data = get_session(sid)
        if session_data is None:
            logger.warning("跳过不存在的会话: %s", sid)
            continue
        if session_data.get("username") != username:
            logger.warning("会话不属于当前用户: sid=%s user=%s", sid, username)
            continue
        photo = _load_photo_for_layout(session_data, strategy)
        if photo is not None:
            photos.append(photo)
            valid_sids.append(sid)

    if not photos:
        raise ValueError("没有可用的照片参与排版，请确认会话文件存在")

    layout = strategy.layout(photos)

    task_id = uuid.uuid4().hex[:12]
    pdf_path = os.path.join(cfg.OUTPUT_DIR, f"printing_{task_id}_{layout_key}.pdf")
    jpg_path = os.path.join(cfg.OUTPUT_DIR, f"printing_{task_id}_{layout_key}.jpg")

    generate_a4_pdf(layout, strategy, pdf_path)
    generate_a4_jpg(layout, strategy, jpg_path)

    for sid in valid_sids:
        try:
            update_session_print_flag(sid, True)
        except Exception as e:
            logger.warning("更新 used_for_printing 标志失败: sid=%s %s", sid, e)

    logger.info("排版任务完成: task_id=%s strategy=%s count=%d", task_id, layout_key, len(photos))
    return pdf_path, jpg_path
