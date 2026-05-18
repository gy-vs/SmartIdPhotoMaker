"""
智能证件照制作系统 - A4 批量排版导出单元测试
"""

import os
import tempfile

import numpy as np
import pytest
from PIL import Image

from printing import (
    OneInchStrategy,
    TwoInchStrategy,
    MixedStrategy,
    generate_a4_layout,
    ALLOWED_LAYOUTS,
    A4_W_PX,
    A4_H_PX,
    PHOTO_SPECS,
)


def _make_test_photo(w=295, h=413, color=(200, 180, 160)):
    """生成测试用证件照文件。

    Args:
        w (int): 宽度像素。
        h (int): 高度像素。
        color (tuple): RGB 颜色。

    Returns:
        str: 临时文件路径。
    """
    img = Image.fromarray(np.full((h, w, 3), color, dtype=np.uint8))
    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    img.save(path, "JPEG")
    return path


class TestOneInchStrategy:
    def test_layout_returns_positions(self):
        strategy = OneInchStrategy()
        positions = strategy.layout()
        assert len(positions) > 0
        for pos in positions:
            assert "x_mm" in pos
            assert "y_mm" in pos
            assert "photo_w_mm" in pos
            assert "photo_h_mm" in pos
            assert pos["size_name"] == "一寸"

    def test_capacity_is_eight(self):
        strategy = OneInchStrategy()
        assert strategy.capacity() == 8

    def test_photo_dimensions(self):
        strategy = OneInchStrategy()
        positions = strategy.layout()
        spec = PHOTO_SPECS["一寸"]
        for pos in positions:
            assert pos["photo_w_mm"] == spec["mm_w"]
            assert pos["photo_h_mm"] == spec["mm_h"]


class TestTwoInchStrategy:
    def test_layout_returns_positions(self):
        strategy = TwoInchStrategy()
        positions = strategy.layout()
        assert len(positions) > 0
        for pos in positions:
            assert pos["size_name"] == "二寸"

    def test_capacity_is_four(self):
        strategy = TwoInchStrategy()
        assert strategy.capacity() == 4


class TestMixedStrategy:
    def test_layout_returns_positions(self):
        strategy = MixedStrategy()
        positions = strategy.layout()
        assert len(positions) > 0
        size_names = [p["size_name"] for p in positions]
        assert "一寸" in size_names
        assert "二寸" in size_names

    def test_capacity_at_least_six(self):
        strategy = MixedStrategy()
        assert strategy.capacity() >= 6


class TestGenerateA4Layout:
    def test_invalid_layout_type_raises(self):
        with pytest.raises(ValueError, match="不支持的版式类型"):
            generate_a4_layout(["/fake/path.jpg"], "invalid_type", "/tmp")

    def test_empty_paths_raises(self):
        with pytest.raises(ValueError, match="至少需要选择一张照片"):
            generate_a4_layout([], "one_inch", "/tmp")

    def test_generate_one_inch(self):
        paths = [_make_test_photo() for _ in range(3)]
        try:
            with tempfile.TemporaryDirectory() as out_dir:
                result = generate_a4_layout(paths, "one_inch", out_dir)
                assert "pdf_path" in result
                assert "jpg_path" in result
                assert os.path.exists(result["pdf_path"])
                assert os.path.exists(result["jpg_path"])
                assert result["pdf_path"].endswith(".pdf")
                assert result["jpg_path"].endswith(".jpg")
        finally:
            for p in paths:
                os.remove(p)

    def test_generate_two_inch(self):
        paths = [_make_test_photo(w=413, h=579) for _ in range(2)]
        try:
            with tempfile.TemporaryDirectory() as out_dir:
                result = generate_a4_layout(paths, "two_inch", out_dir)
                assert os.path.exists(result["pdf_path"])
                assert os.path.exists(result["jpg_path"])
        finally:
            for p in paths:
                os.remove(p)

    def test_generate_mixed(self):
        paths = [_make_test_photo() for _ in range(5)]
        try:
            with tempfile.TemporaryDirectory() as out_dir:
                result = generate_a4_layout(paths, "mixed", out_dir)
                assert os.path.exists(result["pdf_path"])
                assert os.path.exists(result["jpg_path"])
        finally:
            for p in paths:
                os.remove(p)

    def test_nonexistent_photo_skipped(self):
        good_path = _make_test_photo()
        try:
            with tempfile.TemporaryDirectory() as out_dir:
                result = generate_a4_layout(
                    [good_path, "/nonexistent/photo.jpg"], "one_inch", out_dir
                )
                assert os.path.exists(result["jpg_path"])
        finally:
            os.remove(good_path)

    def test_all_invalid_photos_raises(self):
        with tempfile.TemporaryDirectory() as out_dir:
            with pytest.raises(RuntimeError, match="所有照片加载失败"):
                generate_a4_layout(
                    ["/nonexistent1.jpg", "/nonexistent2.jpg"], "one_inch", out_dir
                )

    def test_jpg_image_size(self):
        paths = [_make_test_photo()]
        try:
            with tempfile.TemporaryDirectory() as out_dir:
                result = generate_a4_layout(paths, "one_inch", out_dir)
                img = Image.open(result["jpg_path"])
                assert img.size[0] == A4_W_PX
                assert img.size[1] == A4_H_PX
        finally:
            for p in paths:
                os.remove(p)

    def test_fewer_photos_than_capacity(self):
        paths = [_make_test_photo() for _ in range(1)]
        try:
            with tempfile.TemporaryDirectory() as out_dir:
                result = generate_a4_layout(paths, "one_inch", out_dir)
                assert os.path.exists(result["jpg_path"])
                img = Image.open(result["jpg_path"])
                assert img.size == (A4_W_PX, A4_H_PX)
        finally:
            for p in paths:
                os.remove(p)
