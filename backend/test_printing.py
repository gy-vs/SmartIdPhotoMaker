"""
智能证件照制作系统 - 批量排版导出服务单元测试
仅测试 printing 模块本身，不依赖 Flask 应用启动
"""

import io
import os
import shutil
import numpy as np
import cv2
import pytest

from printing import (
    OneInchStrategy, TwoInchStrategy, MixedStrategy,
    get_strategy, STRATEGY_MAP,
    _build_grid_layout, _render_a4_pil,
    generate_a4_pdf, generate_a4_jpg, build_printing_task,
    A4_WIDTH_MM, A4_HEIGHT_MM,
)
from models import init_db, DB_PATH, get_session, create_session


@pytest.fixture(autouse=True)
def clean_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)


@pytest.fixture
def tmp_output_dir(tmp_path):
    return str(tmp_path)


def _make_photo(size=(400, 500)):
    img = np.full((size[1], size[0], 3), (180, 200, 220), dtype=np.uint8)
    cv2.ellipse(img, (size[0] // 2, size[1] // 3), (size[0] // 4, size[1] // 4), 0, 0, 360, (160, 140, 120), -1)
    return img


class TestStrategyRegistry:
    def test_strategy_keys(self):
        assert "one_inch" in STRATEGY_MAP
        assert "two_inch" in STRATEGY_MAP
        assert "mixed" in STRATEGY_MAP

    def test_get_strategy_ok(self):
        s = get_strategy("one_inch")
        assert isinstance(s, OneInchStrategy)

    def test_get_strategy_invalid(self):
        with pytest.raises(ValueError):
            get_strategy("unknown")


class TestPhotoSize:
    def test_one_inch_size(self):
        s = OneInchStrategy()
        w, h = s.photo_size_mm()
        assert abs(w - 25.0) < 0.01
        assert abs(h - 35.0) < 0.01

    def test_two_inch_size(self):
        s = TwoInchStrategy()
        w, h = s.photo_size_mm()
        assert abs(w - 35.0) < 0.01
        assert abs(h - 49.0) < 0.01


class TestGridLayout:
    def test_one_inch_layout_four_photos(self):
        photos = [_make_photo() for _ in range(4)]
        s = OneInchStrategy()
        layout = s.layout(photos)
        non_placeholder = [item for item in layout if item["photo"] is not None]
        placeholder = [item for item in layout if item["photo"] is None]
        assert len(non_placeholder) == 4
        assert len(placeholder) > 0
        for item in layout:
            assert 0 <= item["x_mm"] < A4_WIDTH_MM
            assert 0 <= item["y_mm"] < A4_HEIGHT_MM
            assert item["x_mm"] + item["w_mm"] <= A4_WIDTH_MM + 0.1
            assert item["y_mm"] + item["h_mm"] <= A4_HEIGHT_MM + 0.1

    def test_two_inch_layout_two_photos(self):
        photos = [_make_photo() for _ in range(2)]
        s = TwoInchStrategy()
        layout = s.layout(photos)
        non_placeholder = [item for item in layout if item["photo"] is not None]
        assert len(non_placeholder) == 2


class TestRender:
    def test_render_pil_size(self, tmp_output_dir):
        photos = [_make_photo() for _ in range(3)]
        s = OneInchStrategy()
        layout = s.layout(photos)
        img = _render_a4_pil(layout, s)
        assert img.size[0] > 0
        assert img.size[1] > 0

    def test_pdf_generation(self, tmp_output_dir):
        photos = [_make_photo() for _ in range(3)]
        s = OneInchStrategy()
        layout = s.layout(photos)
        out_path = os.path.join(tmp_output_dir, "test.pdf")
        generate_a4_pdf(layout, s, out_path)
        assert os.path.exists(out_path)
        assert os.path.getsize(out_path) > 0

    def test_jpg_generation(self, tmp_output_dir):
        photos = [_make_photo() for _ in range(3)]
        s = OneInchStrategy()
        layout = s.layout(photos)
        out_path = os.path.join(tmp_output_dir, "test.jpg")
        generate_a4_jpg(layout, s, out_path)
        assert os.path.exists(out_path)
        assert os.path.getsize(out_path) > 0


class TestBuildPrintingTask:
    def test_empty_session_ids(self):
        with pytest.raises(ValueError):
            build_printing_task([], "one_inch", "user1")

    def test_invalid_layout(self):
        with pytest.raises(ValueError):
            build_printing_task(["sid1"], "unknown", "user1")

    def test_no_matching_session(self):
        with pytest.raises(ValueError):
            build_printing_task(["nonexistent"], "one_inch", "user1")

    def test_valid_task(self, tmp_path, monkeypatch):
        test_dir = str(tmp_path)
        monkeypatch.setattr("printing.cfg.OUTPUT_DIR", test_dir)

        sid = "test1"
        fname = os.path.join(test_dir, f"{sid}.jpg")
        cv2.imwrite(fname, _make_photo())
        create_session(
            sid=sid, username="user1",
            filename="test.jpg", file_path=fname,
            has_face=True, confidence=0.9, has_glasses=False,
        )

        pdf_path, jpg_path = build_printing_task([sid], "one_inch", "user1")
        assert os.path.exists(pdf_path)
        assert os.path.exists(jpg_path)
        session_data = get_session(sid)
        assert session_data.get("used_for_printing") == 1
