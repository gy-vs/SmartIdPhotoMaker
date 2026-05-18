"""
智能证件照制作系统 - A4 批量排版导出服务层

基于策略模式实现三种版式排版，输出 A4 PDF（300 DPI）和 A4 JPG（300 DPI）。
拼版算法封装在本模块，app.py 只负责路由、参数校验和调用。
"""

import abc
import logging
import os
import uuid

from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

logger = logging.getLogger("printing")

A4_W_MM = 210.0
A4_H_MM = 297.0
DPI = 300
A4_W_PX = int(A4_W_MM / 25.4 * DPI)
A4_H_PX = int(A4_H_MM / 25.4 * DPI)

BLEED_MM = 2.0
GAP_MM = 3.0

GRID_COLOR = (200, 200, 200)
PLACEHOLDER_FILL = (230, 230, 230)
PLACEHOLDER_BORDER = (180, 180, 180)

PHOTO_SPECS = {
    "一寸": {"mm_w": 25, "mm_h": 35, "px_w": 295, "px_h": 413},
    "二寸": {"mm_w": 35, "mm_h": 49, "px_w": 413, "px_h": 579},
}

ALLOWED_LAYOUTS = {"one_inch", "two_inch", "mixed"}


class LayoutStrategy(abc.ABC):
    """排版策略抽象基类。

    所有具体版式策略必须实现 ``layout`` 方法，返回照片在 A4 页面中的
    放置位置列表以及该版式总共能容纳的照片数量。
    """

    @abc.abstractmethod
    def layout(self):
        """计算排版布局。

        Returns:
            list[dict]: 每个元素包含 ``x_mm``, ``y_mm``, ``photo_w_mm``,
                ``photo_h_mm``, ``size_name`` 字段，表示一张照片在 A4
                页面上的左下角坐标与尺寸。
        """

    @abc.abstractmethod
    def capacity(self):
        """返回当前版式下 A4 页面可容纳的照片总数。

        Returns:
            int
        """

    def _calc_fixed_grid(self, photo_w_mm, photo_h_mm, cols, rows):
        """根据指定行列数和出血/间距约束，计算居中布局坐标。

        Args:
            photo_w_mm (float): 单张照片宽度（mm），不含出血。
            photo_h_mm (float): 单张照片高度（mm），不含出血。
            cols (int): 列数。
            rows (int): 行数。

        Returns:
            list[dict]: 布局坐标列表，每项含 ``x_mm`` 和 ``y_mm``。
        """
        cell_w = photo_w_mm + 2 * BLEED_MM + GAP_MM
        cell_h = photo_h_mm + 2 * BLEED_MM + GAP_MM
        total_w = cols * cell_w - GAP_MM
        total_h = rows * cell_h - GAP_MM
        offset_x = (A4_W_MM - total_w) / 2
        offset_y = (A4_H_MM - total_h) / 2
        positions = []
        for r in range(rows):
            for c in range(cols):
                x = offset_x + c * cell_w
                y = offset_y + (rows - 1 - r) * cell_h
                positions.append({"x_mm": x, "y_mm": y})
        return positions


class OneInchStrategy(LayoutStrategy):
    """纯一寸版式策略：A4 页面排列 8 张一寸照片（4 列 × 2 行）。"""

    def __init__(self):
        self._spec = PHOTO_SPECS["一寸"]
        self._positions = self._calc_fixed_grid(
            self._spec["mm_w"], self._spec["mm_h"], cols=4, rows=2
        )

    def layout(self):
        """计算纯一寸排版布局。

        Returns:
            list[dict]: 每个元素含 ``x_mm``, ``y_mm``, ``photo_w_mm``,
                ``photo_h_mm``, ``size_name``。
        """
        result = []
        for pos in self._positions:
            result.append({
                "x_mm": pos["x_mm"],
                "y_mm": pos["y_mm"],
                "photo_w_mm": self._spec["mm_w"],
                "photo_h_mm": self._spec["mm_h"],
                "size_name": "一寸",
            })
        return result

    def capacity(self):
        """纯一寸版式 A4 容量。

        Returns:
            int
        """
        return len(self._positions)


class TwoInchStrategy(LayoutStrategy):
    """纯二寸版式策略：A4 页面排列 4 张二寸照片（2 列 × 2 行）。"""

    def __init__(self):
        self._spec = PHOTO_SPECS["二寸"]
        self._positions = self._calc_fixed_grid(
            self._spec["mm_w"], self._spec["mm_h"], cols=2, rows=2
        )

    def layout(self):
        """计算纯二寸排版布局。

        Returns:
            list[dict]
        """
        result = []
        for pos in self._positions:
            result.append({
                "x_mm": pos["x_mm"],
                "y_mm": pos["y_mm"],
                "photo_w_mm": self._spec["mm_w"],
                "photo_h_mm": self._spec["mm_h"],
                "size_name": "二寸",
            })
        return result

    def capacity(self):
        """纯二寸版式 A4 容量。

        Returns:
            int
        """
        return len(self._positions)


class MixedStrategy(LayoutStrategy):
    """一寸 + 二寸混排策略：上半部分排列二寸，下半部分排列一寸。"""

    def __init__(self):
        self._spec1 = PHOTO_SPECS["一寸"]
        self._spec2 = PHOTO_SPECS["二寸"]
        self._two_positions = self._calc_half_grid(self._spec2, cols=2, rows=1, top=True)
        self._one_positions = self._calc_half_grid(self._spec1, cols=4, rows=1, top=False)

    def _calc_half_grid(self, spec, cols, rows, top=True):
        """计算半页排版坐标。

        Args:
            spec (dict): 照片尺寸规格。
            cols (int): 列数。
            rows (int): 行数。
            top (bool): True 使用上半页，False 使用下半页。

        Returns:
            list[dict]
        """
        cell_w = spec["mm_w"] + 2 * BLEED_MM + GAP_MM
        cell_h = spec["mm_h"] + 2 * BLEED_MM + GAP_MM
        total_w = cols * cell_w - GAP_MM
        total_h = rows * cell_h - GAP_MM
        half_h = A4_H_MM / 2
        offset_x = (A4_W_MM - total_w) / 2
        if top:
            offset_y = A4_H_MM - (half_h - (half_h - total_h) / 2)
        else:
            offset_y = (half_h - total_h) / 2
        positions = []
        for r in range(rows):
            for c in range(cols):
                x = offset_x + c * cell_w
                y = offset_y + (rows - 1 - r) * cell_h
                positions.append({
                    "x_mm": x,
                    "y_mm": y,
                    "photo_w_mm": spec["mm_w"],
                    "photo_h_mm": spec["mm_h"],
                    "size_name": "一寸" if spec == self._spec1 else "二寸",
                })
        return positions

    def layout(self):
        """计算混排布局：二寸在上半页，一寸在下半页。

        Returns:
            list[dict]
        """
        return self._two_positions + self._one_positions

    def capacity(self):
        """混排版式 A4 容量。

        Returns:
            int
        """
        return len(self._two_positions) + len(self._one_positions)


STRATEGY_MAP = {
    "one_inch": OneInchStrategy,
    "two_inch": TwoInchStrategy,
    "mixed": MixedStrategy,
}


def _mm_to_px(mm_val):
    """将毫米转换为 300 DPI 像素值。

    Args:
        mm_val (float): 毫米值。

    Returns:
        int: 像素值。
    """
    return int(mm_val / 25.4 * DPI)


def _load_photo(file_path):
    """从磁盘读取照片并返回 Pillow Image 对象。

    Args:
        file_path (str): 照片文件路径。

    Returns:
        PIL.Image.Image | None: 成功返回 Image 对象，失败返回 None。

    Raises:
        FileNotFoundError: 文件不存在时。
    """
    if not os.path.exists(file_path):
        logger.warning("照片文件不存在: %s", file_path)
        return None
    try:
        img = Image.open(file_path).convert("RGB")
        return img
    except Exception as e:
        logger.error("读取照片失败: %s, %s", file_path, e, exc_info=True)
        return None


def _resize_to_spec(img, size_name):
    """将照片缩放到证件照规格像素尺寸。

    Args:
        img (PIL.Image.Image): 原始图片。
        size_name (str): 证件照尺寸名称，如 ``"一寸"`` 或 ``"二寸"``。

    Returns:
        PIL.Image.Image: 缩放后的图片。
    """
    spec = PHOTO_SPECS.get(size_name, PHOTO_SPECS["一寸"])
    return img.resize((spec["px_w"], spec["px_h"]), Image.LANCZOS)


def _draw_a4_canvas(photo_data_list, strategy):
    """在 Pillow 上绘制 A4 排版画布（含出血线、网格和占位框）。

    Args:
        photo_data_list (list[PIL.Image.Image | None]): 照片列表，
            None 表示该位置用占位框补齐。
        strategy (LayoutStrategy): 排版策略实例。

    Returns:
        PIL.Image.Image: A4 画布图像（300 DPI）。
    """
    canvas_img = Image.new("RGB", (A4_W_PX, A4_H_PX), (255, 255, 255))
    draw = ImageDraw.Draw(canvas_img)
    positions = strategy.layout()

    for idx, pos in enumerate(positions):
        x_px = _mm_to_px(pos["x_mm"])
        y_px = A4_H_PX - _mm_to_px(pos["y_mm"]) - _mm_to_px(pos["photo_h_mm"])
        w_px = _mm_to_px(pos["photo_w_mm"])
        h_px = _mm_to_px(pos["photo_h_mm"])
        bleed_px = _mm_to_px(BLEED_MM)

        bleed_rect = [
            x_px - bleed_px,
            y_px - bleed_px,
            x_px + w_px + bleed_px,
            y_px + h_px + bleed_px,
        ]
        draw.rectangle(bleed_rect, outline=GRID_COLOR, width=1)

        inner_rect = [x_px, y_px, x_px + w_px, y_px + h_px]
        draw.rectangle(inner_rect, outline=GRID_COLOR, width=1)

        if idx < len(photo_data_list) and photo_data_list[idx] is not None:
            photo = _resize_to_spec(photo_data_list[idx], pos["size_name"])
            canvas_img.paste(photo, (x_px, y_px))
        else:
            draw.rectangle(inner_rect, fill=PLACEHOLDER_FILL, outline=PLACEHOLDER_BORDER, width=1)
            cx = x_px + w_px // 2
            cy = y_px + h_px // 2
            font_size = max(12, w_px // 8)
            try:
                from PIL import ImageFont
                font_paths = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
                ]
                font = None
                for fp in font_paths:
                    if os.path.exists(fp):
                        font = ImageFont.truetype(fp, font_size)
                        break
                if font is None:
                    font = ImageFont.load_default()
            except Exception:
                font = ImageFont.load_default()
            text = "留白"
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((cx - tw // 2, cy - th // 2), text, fill=PLACEHOLDER_BORDER, font=font)

    return canvas_img


def _save_pdf(canvas_img, pdf_path):
    """将 Pillow 画布保存为 A4 PDF（300 DPI）。

    Args:
        canvas_img (PIL.Image.Image): A4 画布图像。
        pdf_path (str): 输出 PDF 文件路径。

    Returns:
        str: PDF 文件路径。

    Raises:
        OSError: 写入文件失败时。
    """
    c = canvas.Canvas(pdf_path, pagesize=A4)
    temp_img_path = pdf_path.replace(".pdf", "_temp.jpg")
    canvas_img.save(temp_img_path, "JPEG", quality=95, dpi=(DPI, DPI))
    c.drawImage(temp_img_path, 0, 0, width=A4[0], height=A4[1])
    c.showPage()
    c.save()
    try:
        os.remove(temp_img_path)
    except OSError:
        pass
    logger.info("PDF 已生成: %s", pdf_path)
    return pdf_path


def generate_a4_layout(photo_paths, layout_type, output_dir):
    """生成 A4 排版 PDF 和 JPG 文件。

    Args:
        photo_paths (list[str]): 选中照片的文件路径列表。
        layout_type (str): 版式类型，可选 ``"one_inch"`` / ``"two_inch"``
            / ``"mixed"``。
        output_dir (str): 输出目录路径。

    Returns:
        dict: 包含 ``pdf_path`` 和 ``jpg_path`` 键，值为对应的文件路径。

    Raises:
        ValueError: 版式类型无效或照片路径列表为空时。
        RuntimeError: 所有照片均加载失败时。
    """
    if layout_type not in ALLOWED_LAYOUTS:
        raise ValueError(f"不支持的版式类型: {layout_type}，可选: {', '.join(ALLOWED_LAYOUTS)}")
    if not photo_paths:
        raise ValueError("至少需要选择一张照片")

    strategy_cls = STRATEGY_MAP[layout_type]
    strategy = strategy_cls()
    capacity = strategy.capacity()

    photos = []
    for p in photo_paths:
        photos.append(_load_photo(p))

    loaded_count = sum(1 for p in photos if p is not None)
    if loaded_count == 0:
        raise RuntimeError("所有照片加载失败，请检查文件是否存在")

    while len(photos) < capacity:
        photos.append(None)

    photos = photos[:capacity]

    canvas_img = _draw_a4_canvas(photos, strategy)

    task_id = str(uuid.uuid4())[:8]
    os.makedirs(output_dir, exist_ok=True)

    jpg_path = os.path.join(output_dir, f"a4_layout_{task_id}.jpg")
    canvas_img.save(jpg_path, "JPEG", quality=95, dpi=(DPI, DPI))
    logger.info("JPG 已生成: %s", jpg_path)

    pdf_path = os.path.join(output_dir, f"a4_layout_{task_id}.pdf")
    _save_pdf(canvas_img, pdf_path)

    return {"pdf_path": pdf_path, "jpg_path": jpg_path}
