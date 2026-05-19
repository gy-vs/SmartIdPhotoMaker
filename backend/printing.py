"""
智能证件照制作系统 - A4 批量排版导出服务层
采用策略模式实现多种版式的 PDF/JPG 拼版输出
"""

import os
import io
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple, Optional

import numpy as np
import cv2
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from config import get_config

logger = logging.getLogger("printing")
cfg = get_config()

DPI = 300
MM_TO_PX = DPI / 25.4

A4_WIDTH_MM = 210
A4_HEIGHT_MM = 297
A4_WIDTH_PX = int(A4_WIDTH_MM * MM_TO_PX)
A4_HEIGHT_PX = int(A4_HEIGHT_MM * MM_TO_PX)

BLEED_MM = 2
SAFE_GAP_MM = 3
BLEED_PX = int(BLEED_MM * MM_TO_PX)
SAFE_GAP_PX = int(SAFE_GAP_MM * MM_TO_PX)

PAGE_MARGIN_MM = 5
PAGE_MARGIN_PX = int(PAGE_MARGIN_MM * MM_TO_PX)

ONE_INCH_WIDTH_MM = 25
ONE_INCH_HEIGHT_MM = 35
ONE_INCH_WIDTH_PX = int(ONE_INCH_WIDTH_MM * MM_TO_PX)
ONE_INCH_HEIGHT_PX = int(ONE_INCH_HEIGHT_MM * MM_TO_PX)

TWO_INCH_WIDTH_MM = 35
TWO_INCH_HEIGHT_MM = 49
TWO_INCH_WIDTH_PX = int(TWO_INCH_WIDTH_MM * MM_TO_PX)
TWO_INCH_HEIGHT_PX = int(TWO_INCH_HEIGHT_MM * MM_TO_PX)

CUT_LINE_COLOR = (200, 200, 200)
PLACEHOLDER_COLOR = (240, 240, 240)
PLACEHOLDER_BORDER_COLOR = (200, 200, 200)
GRID_COLOR = (230, 230, 230)


@dataclass
class PhotoSlot:
    """照片槽位数据类"""
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    is_placeholder: bool = False


class BaseLayoutStrategy(ABC):
    """排版策略基类"""

    @abstractmethod
    def get_layout_name(self) -> str:
        """获取版式名称"""
        pass

    @abstractmethod
    def get_slots(self) -> List[PhotoSlot]:
        """获取所有槽位列表"""
        pass

    @abstractmethod
    def get_max_photos(self) -> int:
        """获取最大照片数量"""
        pass

    def calculate_positions(
        self,
        photo_width_mm: float,
        photo_height_mm: float,
        cols: int,
        rows: int,
    ) -> List[PhotoSlot]:
        """
        计算网格布局的槽位位置

        Args:
            photo_width_mm: 照片宽度（mm）
            photo_height_mm: 照片高度（mm）
            cols: 列数
            rows: 行数

        Returns:
            槽位列表
        """
        slots = []
        total_width = cols * (photo_width_mm + 2 * BLEED_MM) + (cols - 1) * SAFE_GAP_MM
        total_height = rows * (photo_height_mm + 2 * BLEED_MM) + (rows - 1) * SAFE_GAP_MM

        start_x = (A4_WIDTH_MM - total_width) / 2
        start_y = (A4_HEIGHT_MM - total_height) / 2

        for row in range(rows):
            for col in range(cols):
                x = start_x + col * (photo_width_mm + 2 * BLEED_MM + SAFE_GAP_MM)
                y = start_y + row * (photo_height_mm + 2 * BLEED_MM + SAFE_GAP_MM)
                slots.append(PhotoSlot(
                    x_mm=x,
                    y_mm=y,
                    width_mm=photo_width_mm,
                    height_mm=photo_height_mm,
                ))
        return slots


class OneInchStrategy(BaseLayoutStrategy):
    """纯一寸版式：8 张/A4（2行×4列）"""

    def get_layout_name(self) -> str:
        """获取版式名称"""
        return "一寸（8张）"

    def get_max_photos(self) -> int:
        """获取最大照片数量"""
        return 8

    def get_slots(self) -> List[PhotoSlot]:
        """获取一寸照片的槽位布局"""
        return self.calculate_positions(
            photo_width_mm=ONE_INCH_WIDTH_MM,
            photo_height_mm=ONE_INCH_HEIGHT_MM,
            cols=4,
            rows=2,
        )


class TwoInchStrategy(BaseLayoutStrategy):
    """纯二寸版式：4 张/A4（2行×2列）"""

    def get_layout_name(self) -> str:
        """获取版式名称"""
        return "二寸（4张）"

    def get_max_photos(self) -> int:
        """获取最大照片数量"""
        return 4

    def get_slots(self) -> List[PhotoSlot]:
        """获取二寸照片的槽位布局"""
        return self.calculate_positions(
            photo_width_mm=TWO_INCH_WIDTH_MM,
            photo_height_mm=TWO_INCH_HEIGHT_MM,
            cols=2,
            rows=2,
        )


class MixedStrategy(BaseLayoutStrategy):
    """一寸+二寸混排版式：一寸4张 + 二寸2张"""

    def get_layout_name(self) -> str:
        """获取版式名称"""
        return "一寸+二寸混排"

    def get_max_photos(self) -> int:
        """获取最大照片数量"""
        return 6

    def get_slots(self) -> List[PhotoSlot]:
        """获取混排的槽位布局"""
        slots = []

        two_inch_width = TWO_INCH_WIDTH_MM + 2 * BLEED_MM
        two_inch_height = TWO_INCH_HEIGHT_MM + 2 * BLEED_MM
        one_inch_width = ONE_INCH_WIDTH_MM + 2 * BLEED_MM
        one_inch_height = ONE_INCH_HEIGHT_MM + 2 * BLEED_MM

        total_width = max(
            2 * two_inch_width + SAFE_GAP_MM,
            4 * one_inch_width + 3 * SAFE_GAP_MM,
        )

        two_start_x = (A4_WIDTH_MM - (2 * two_inch_width + SAFE_GAP_MM)) / 2
        one_start_x = (A4_WIDTH_MM - (4 * one_inch_width + 3 * SAFE_GAP_MM)) / 2

        total_height = two_inch_height + SAFE_GAP_MM + one_inch_height
        start_y = (A4_HEIGHT_MM - total_height) / 2

        for i in range(2):
            slots.append(PhotoSlot(
                x_mm=two_start_x + i * (two_inch_width + SAFE_GAP_MM),
                y_mm=start_y,
                width_mm=TWO_INCH_WIDTH_MM,
                height_mm=TWO_INCH_HEIGHT_MM,
            ))

        for i in range(4):
            slots.append(PhotoSlot(
                x_mm=one_start_x + i * (one_inch_width + SAFE_GAP_MM),
                y_mm=start_y + two_inch_height + SAFE_GAP_MM,
                width_mm=ONE_INCH_WIDTH_MM,
                height_mm=ONE_INCH_HEIGHT_MM,
            ))

        return slots


STRATEGY_MAP = {
    "one_inch": OneInchStrategy,
    "two_inch": TwoInchStrategy,
    "mixed": MixedStrategy,
}


class LayoutComposer:
    """排版合成器，负责将照片合成到 A4 版面"""

    def __init__(self, strategy: BaseLayoutStrategy):
        """
        初始化排版合成器

        Args:
            strategy: 排版策略实例
        """
        self.strategy = strategy
        self.slots = strategy.get_slots()

    def _load_image(self, image_path: str, target_width_px: int, target_height_px: int) -> np.ndarray:
        """
        加载并调整图片尺寸

        Args:
            image_path: 图片文件路径
            target_width_px: 目标宽度（像素）
            target_height_px: 目标高度（像素）

        Returns:
            调整后的 OpenCV 图像（BGR 格式）

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 图片无法读取
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        img = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"无法读取图片: {image_path}")

        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(img_rgb, (target_width_px, target_height_px),
                            interpolation=cv2.INTER_LANCZOS4)
        return resized

    def _create_bleed_photo(self, photo_rgb: np.ndarray, slot: PhotoSlot) -> np.ndarray:
        """
        创建带出血的照片（2mm 出血区域）

        Args:
            photo_rgb: 原始照片（RGB 格式）
            slot: 槽位信息

        Returns:
            带出血区域的照片
        """
        photo_width_px = int(slot.width_mm * MM_TO_PX)
        photo_height_px = int(slot.height_mm * MM_TO_PX)

        bleed_width_px = int((slot.width_mm + 2 * BLEED_MM) * MM_TO_PX)
        bleed_height_px = int((slot.height_mm + 2 * BLEED_MM) * MM_TO_PX)

        bleed_img = np.zeros((bleed_height_px, bleed_width_px, 3), dtype=np.uint8)

        edge_top = photo_rgb[0:1, :, :]
        edge_bottom = photo_rgb[-1:, :, :]
        edge_left = photo_rgb[:, 0:1, :]
        edge_right = photo_rgb[:, -1:, :]

        corner_tl = photo_rgb[0:1, 0:1, :]
        corner_tr = photo_rgb[0:1, -1:, :]
        corner_bl = photo_rgb[-1:, 0:1, :]
        corner_br = photo_rgb[-1:, -1:, :]

        bleed_img[BLEED_PX:BLEED_PX + photo_height_px,
                  BLEED_PX:BLEED_PX + photo_width_px] = photo_rgb

        bleed_img[0:BLEED_PX, BLEED_PX:BLEED_PX + photo_width_px] = np.repeat(
            edge_top, BLEED_PX, axis=0
        )
        bleed_img[BLEED_PX + photo_height_px:,
                  BLEED_PX:BLEED_PX + photo_width_px] = np.repeat(
            edge_bottom, BLEED_PX, axis=0
        )
        bleed_img[BLEED_PX:BLEED_PX + photo_height_px,
                  0:BLEED_PX] = np.repeat(edge_left, BLEED_PX, axis=1)
        bleed_img[BLEED_PX:BLEED_PX + photo_height_px,
                  BLEED_PX + photo_width_px:] = np.repeat(
            edge_right, BLEED_PX, axis=1
        )

        bleed_img[0:BLEED_PX, 0:BLEED_PX] = np.tile(corner_tl, (BLEED_PX, BLEED_PX, 1))
        bleed_img[0:BLEED_PX, BLEED_PX + photo_width_px:] = np.tile(
            corner_tr, (BLEED_PX, BLEED_PX, 1)
        )
        bleed_img[BLEED_PX + photo_height_px:, 0:BLEED_PX] = np.tile(
            corner_bl, (BLEED_PX, BLEED_PX, 1)
        )
        bleed_img[BLEED_PX + photo_height_px:,
                  BLEED_PX + photo_width_px:] = np.tile(
            corner_br, (BLEED_PX, BLEED_PX, 1)
        )

        return bleed_img

    def _create_placeholder(self, slot: PhotoSlot) -> np.ndarray:
        """
        创建留白占位框

        Args:
            slot: 槽位信息

        Returns:
            占位框图像
        """
        bleed_width_px = int((slot.width_mm + 2 * BLEED_MM) * MM_TO_PX)
        bleed_height_px = int((slot.height_mm + 2 * BLEED_MM) * MM_TO_PX)

        placeholder = np.full(
            (bleed_height_px, bleed_width_px, 3),
            PLACEHOLDER_COLOR,
            dtype=np.uint8,
        )

        photo_width_px = int(slot.width_mm * MM_TO_PX)
        photo_height_px = int(slot.height_mm * MM_TO_PX)

        cv2.rectangle(
            placeholder,
            (BLEED_PX, BLEED_PX),
            (BLEED_PX + photo_width_px - 1, BLEED_PX + photo_height_px - 1),
            PLACEHOLDER_BORDER_COLOR,
            2,
        )

        return placeholder

    def _draw_cut_lines(self, draw: ImageDraw.ImageDraw, slot: PhotoSlot) -> None:
        """
        绘制裁切线

        Args:
            draw: PIL ImageDraw 对象
            slot: 槽位信息
        """
        x_px = int(slot.x_mm * MM_TO_PX)
        y_px = int(slot.y_mm * MM_TO_PX)
        bleed_width_px = int((slot.width_mm + 2 * BLEED_MM) * MM_TO_PX)
        bleed_height_px = int((slot.height_mm + 2 * BLEED_MM) * MM_TO_PX)

        line_length = int(3 * MM_TO_PX)
        line_width = 1

        draw.line(
            [(x_px, y_px), (x_px + line_length, y_px)],
            fill=CUT_LINE_COLOR,
            width=line_width,
        )
        draw.line(
            [(x_px, y_px), (x_px, y_px + line_length)],
            fill=CUT_LINE_COLOR,
            width=line_width,
        )

        draw.line(
            [(x_px + bleed_width_px - line_length, y_px),
             (x_px + bleed_width_px, y_px)],
            fill=CUT_LINE_COLOR,
            width=line_width,
        )
        draw.line(
            [(x_px + bleed_width_px, y_px),
             (x_px + bleed_width_px, y_px + line_length)],
            fill=CUT_LINE_COLOR,
            width=line_width,
        )

        draw.line(
            [(x_px, y_px + bleed_height_px - line_length),
             (x_px, y_px + bleed_height_px)],
            fill=CUT_LINE_COLOR,
            width=line_width,
        )
        draw.line(
            [(x_px, y_px + bleed_height_px),
             (x_px + line_length, y_px + bleed_height_px)],
            fill=CUT_LINE_COLOR,
            width=line_width,
        )

        draw.line(
            [(x_px + bleed_width_px - line_length, y_px + bleed_height_px),
             (x_px + bleed_width_px, y_px + bleed_height_px)],
            fill=CUT_LINE_COLOR,
            width=line_width,
        )
        draw.line(
            [(x_px + bleed_width_px, y_px + bleed_height_px - line_length),
             (x_px + bleed_width_px, y_px + bleed_height_px)],
            fill=CUT_LINE_COLOR,
            width=line_width,
        )

    def _draw_grid(self, draw: ImageDraw.ImageDraw) -> None:
        """
        绘制浅灰色裁切辅助网格

        Args:
            draw: PIL ImageDraw 对象
        """
        grid_spacing_mm = 10
        grid_spacing_px = int(grid_spacing_mm * MM_TO_PX)

        for x in range(0, A4_WIDTH_PX, grid_spacing_px):
            draw.line([(x, 0), (x, A4_HEIGHT_PX)], fill=GRID_COLOR, width=1)

        for y in range(0, A4_HEIGHT_PX, grid_spacing_px):
            draw.line([(0, y), (A4_WIDTH_PX, y)], fill=GRID_COLOR, width=1)

    def compose_image(self, photo_paths: List[str]) -> Image.Image:
        """
        合成 A4 高清 JPG 图像

        Args:
            photo_paths: 照片文件路径列表

        Returns:
            合成后的 PIL Image 对象（RGB 模式）

        Raises:
            ValueError: 照片数量超过最大限制
            FileNotFoundError: 照片文件不存在
        """
        max_photos = self.strategy.get_max_photos()
        if len(photo_paths) > max_photos:
            raise ValueError(
                f"照片数量 ({len(photo_paths)}) 超过最大限制 ({max_photos})"
            )

        canvas_img = Image.new("RGB", (A4_WIDTH_PX, A4_HEIGHT_PX), "white")
        draw = ImageDraw.Draw(canvas_img)

        self._draw_grid(draw)

        for i, slot in enumerate(self.slots):
            x_px = int(slot.x_mm * MM_TO_PX)
            y_px = int(slot.y_mm * MM_TO_PX)
            bleed_width_px = int((slot.width_mm + 2 * BLEED_MM) * MM_TO_PX)
            bleed_height_px = int((slot.height_mm + 2 * BLEED_MM) * MM_TO_PX)

            if i < len(photo_paths):
                try:
                    photo_width_px = int(slot.width_mm * MM_TO_PX)
                    photo_height_px = int(slot.height_mm * MM_TO_PX)
                    photo = self._load_image(
                        photo_paths[i], photo_width_px, photo_height_px
                    )
                    bleed_photo = self._create_bleed_photo(photo, slot)
                    photo_pil = Image.fromarray(bleed_photo)
                    canvas_img.paste(photo_pil, (x_px, y_px))
                except Exception as e:
                    logger.warning("加载照片失败，使用占位框替代: %s", e)
                    placeholder = self._create_placeholder(slot)
                    placeholder_pil = Image.fromarray(placeholder)
                    canvas_img.paste(placeholder_pil, (x_px, y_px))
            else:
                placeholder = self._create_placeholder(slot)
                placeholder_pil = Image.fromarray(placeholder)
                canvas_img.paste(placeholder_pil, (x_px, y_px))

            self._draw_cut_lines(draw, slot)

        return canvas_img

    def compose_pdf(self, photo_paths: List[str], output_path: str) -> None:
        """
        合成 A4 PDF 文件

        Args:
            photo_paths: 照片文件路径列表
            output_path: 输出 PDF 文件路径

        Raises:
            ValueError: 照片数量超过最大限制
        """
        max_photos = self.strategy.get_max_photos()
        if len(photo_paths) > max_photos:
            raise ValueError(
                f"照片数量 ({len(photo_paths)}) 超过最大限制 ({max_photos})"
            )

        c = canvas.Canvas(output_path, pagesize=A4)
        c.setTitle(f"证件照排版 - {self.strategy.get_layout_name()}")

        page_width, page_height = A4

        for i, slot in enumerate(self.slots):
            x_mm = slot.x_mm
            y_mm = slot.y_mm
            photo_width_mm = slot.width_mm
            photo_height_mm = slot.height_mm
            bleed_width_mm = photo_width_mm + 2 * BLEED_MM
            bleed_height_mm = photo_height_mm + 2 * BLEED_MM

            x_pt = x_mm * mm
            y_pt = page_height - (y_mm + bleed_height_mm) * mm
            width_pt = bleed_width_mm * mm
            height_pt = bleed_height_mm * mm

            if i < len(photo_paths):
                try:
                    photo_width_px = int(photo_width_mm * MM_TO_PX)
                    photo_height_px = int(photo_height_mm * MM_TO_PX)
                    photo = self._load_image(
                        photo_paths[i], photo_width_px, photo_height_px
                    )
                    bleed_photo = self._create_bleed_photo(photo, slot)
                    img_reader = ImageReader(Image.fromarray(bleed_photo))
                    c.drawImage(
                        img_reader, x_pt, y_pt, width=width_pt, height=height_pt
                    )
                except Exception as e:
                    logger.warning("加载照片失败，使用占位框替代: %s", e)
                    c.setFillColorRGB(
                        PLACEHOLDER_COLOR[0] / 255,
                        PLACEHOLDER_COLOR[1] / 255,
                        PLACEHOLDER_COLOR[2] / 255,
                    )
                    c.rect(x_pt, y_pt, width_pt, height_pt, fill=1, stroke=0)
                    c.setStrokeColorRGB(
                        PLACEHOLDER_BORDER_COLOR[0] / 255,
                        PLACEHOLDER_BORDER_COLOR[1] / 255,
                        PLACEHOLDER_BORDER_COLOR[2] / 255,
                    )
                    c.setLineWidth(1)
                    inner_x = x_pt + BLEED_MM * mm
                    inner_y = y_pt + BLEED_MM * mm
                    inner_w = width_pt - 2 * BLEED_MM * mm
                    inner_h = height_pt - 2 * BLEED_MM * mm
                    c.rect(inner_x, inner_y, inner_w, inner_h, fill=0, stroke=1)
            else:
                c.setFillColorRGB(
                    PLACEHOLDER_COLOR[0] / 255,
                    PLACEHOLDER_COLOR[1] / 255,
                    PLACEHOLDER_COLOR[2] / 255,
                )
                c.rect(x_pt, y_pt, width_pt, height_pt, fill=1, stroke=0)
                c.setStrokeColorRGB(
                    PLACEHOLDER_BORDER_COLOR[0] / 255,
                    PLACEHOLDER_BORDER_COLOR[1] / 255,
                    PLACEHOLDER_BORDER_COLOR[2] / 255,
                )
                c.setLineWidth(1)
                inner_x = x_pt + BLEED_MM * mm
                inner_y = y_pt + BLEED_MM * mm
                inner_w = width_pt - 2 * BLEED_MM * mm
                inner_h = height_pt - 2 * BLEED_MM * mm
                c.rect(inner_x, inner_y, inner_w, inner_h, fill=0, stroke=1)

            self._draw_pdf_cut_lines(c, slot)

        self._draw_pdf_grid(c)

        c.showPage()
        c.save()
        logger.info("PDF 已生成: %s", output_path)

    def _draw_pdf_cut_lines(self, c: canvas.Canvas, slot: PhotoSlot) -> None:
        """
        在 PDF 上绘制裁切线

        Args:
            c: reportlab Canvas 对象
            slot: 槽位信息
        """
        page_width, page_height = A4

        x_mm = slot.x_mm
        y_mm = slot.y_mm
        bleed_width_mm = slot.width_mm + 2 * BLEED_MM
        bleed_height_mm = slot.height_mm + 2 * BLEED_MM

        line_len_mm = 3

        c.setStrokeColorRGB(
            CUT_LINE_COLOR[0] / 255, CUT_LINE_COLOR[1] / 255, CUT_LINE_COLOR[2] / 255
        )
        c.setLineWidth(0.5)

        c.line(
            x_mm * mm,
            page_height - y_mm * mm,
            (x_mm + line_len_mm) * mm,
            page_height - y_mm * mm,
        )
        c.line(
            x_mm * mm,
            page_height - y_mm * mm,
            x_mm * mm,
            page_height - (y_mm + line_len_mm) * mm,
        )

        c.line(
            (x_mm + bleed_width_mm - line_len_mm) * mm,
            page_height - y_mm * mm,
            (x_mm + bleed_width_mm) * mm,
            page_height - y_mm * mm,
        )
        c.line(
            (x_mm + bleed_width_mm) * mm,
            page_height - y_mm * mm,
            (x_mm + bleed_width_mm) * mm,
            page_height - (y_mm + line_len_mm) * mm,
        )

        c.line(
            x_mm * mm,
            page_height - (y_mm + bleed_height_mm - line_len_mm) * mm,
            x_mm * mm,
            page_height - (y_mm + bleed_height_mm) * mm,
        )
        c.line(
            x_mm * mm,
            page_height - (y_mm + bleed_height_mm) * mm,
            (x_mm + line_len_mm) * mm,
            page_height - (y_mm + bleed_height_mm) * mm,
        )

        c.line(
            (x_mm + bleed_width_mm - line_len_mm) * mm,
            page_height - (y_mm + bleed_height_mm) * mm,
            (x_mm + bleed_width_mm) * mm,
            page_height - (y_mm + bleed_height_mm) * mm,
        )
        c.line(
            (x_mm + bleed_width_mm) * mm,
            page_height - (y_mm + bleed_height_mm - line_len_mm) * mm,
            (x_mm + bleed_width_mm) * mm,
            page_height - (y_mm + bleed_height_mm) * mm,
        )

    def _draw_pdf_grid(self, c: canvas.Canvas) -> None:
        """
        在 PDF 上绘制裁切辅助网格

        Args:
            c: reportlab Canvas 对象
        """
        page_width, page_height = A4
        grid_spacing_mm = 10

        c.setStrokeColorRGB(
            GRID_COLOR[0] / 255, GRID_COLOR[1] / 255, GRID_COLOR[2] / 255
        )
        c.setLineWidth(0.2)

        for x_mm in range(0, int(A4_WIDTH_MM), grid_spacing_mm):
            c.line(x_mm * mm, 0, x_mm * mm, page_height)

        for y_mm in range(0, int(A4_HEIGHT_MM), grid_spacing_mm):
            c.line(0, y_mm * mm, page_width, y_mm * mm)


def get_strategy(layout_type: str) -> BaseLayoutStrategy:
    """
    根据版式类型获取对应的策略实例

    Args:
        layout_type: 版式类型（one_inch / two_inch / mixed）

    Returns:
        排版策略实例

    Raises:
        ValueError: 不支持的版式类型
    """
    if layout_type not in STRATEGY_MAP:
        raise ValueError(
            f"不支持的版式类型: {layout_type}，可选值: {list(STRATEGY_MAP.keys())}"
        )
    return STRATEGY_MAP[layout_type]()


def generate_print_layout(
    photo_paths: List[str],
    layout_type: str,
    output_dir: str,
    output_format: str = "both",
) -> Tuple[Optional[str], Optional[str]]:
    """
    生成排版输出文件（PDF/JPG）

    Args:
        photo_paths: 照片文件路径列表
        layout_type: 版式类型（one_inch / two_inch / mixed）
        output_dir: 输出目录
        output_format: 输出格式（pdf / jpg / both）

    Returns:
        (pdf_path, jpg_path) 元组，未生成的格式返回 None

    Raises:
        ValueError: 参数错误
        RuntimeError: 生成失败
    """
    if not photo_paths:
        raise ValueError("照片列表不能为空")

    if output_format not in {"pdf", "jpg", "both"}:
        raise ValueError(
            f"不支持的输出格式: {output_format}，可选值: pdf, jpg, both"
        )

    os.makedirs(output_dir, exist_ok=True)

    strategy = get_strategy(layout_type)
    composer = LayoutComposer(strategy)

    timestamp = int(__import__("time").time())
    base_name = f"layout_{layout_type}_{timestamp}"

    pdf_path = None
    jpg_path = None

    if output_format in {"pdf", "both"}:
        pdf_path = os.path.join(output_dir, f"{base_name}.pdf")
        try:
            composer.compose_pdf(photo_paths, pdf_path)
        except Exception as e:
            logger.error("生成 PDF 失败: %s", e, exc_info=True)
            raise RuntimeError(f"生成 PDF 失败: {e}") from e

    if output_format in {"jpg", "both"}:
        jpg_path = os.path.join(output_dir, f"{base_name}.jpg")
        try:
            img = composer.compose_image(photo_paths)
            img.save(jpg_path, "JPEG", quality=95, dpi=(DPI, DPI))
            logger.info("JPG 已生成: %s", jpg_path)
        except Exception as e:
            logger.error("生成 JPG 失败: %s", e, exc_info=True)
            if pdf_path and os.path.exists(pdf_path):
                os.remove(pdf_path)
            raise RuntimeError(f"生成 JPG 失败: {e}") from e

    return pdf_path, jpg_path
