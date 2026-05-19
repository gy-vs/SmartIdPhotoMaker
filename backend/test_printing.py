"""
测试排版导出功能
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(__file__))

from printing import (
    get_strategy, OneInchStrategy, TwoInchStrategy, MixedStrategy,
    LayoutComposer, generate_print_layout, STRATEGY_MAP
)


class TestStrategies:
    """测试排版策略"""

    def test_one_inch_strategy(self):
        """测试一寸版式策略"""
        strategy = OneInchStrategy()
        assert strategy.get_layout_name() == "一寸（8张）"
        assert strategy.get_max_photos() == 8
        slots = strategy.get_slots()
        assert len(slots) == 8
        for slot in slots:
            assert slot.width_mm == 25
            assert slot.height_mm == 35

    def test_two_inch_strategy(self):
        """测试二寸版式策略"""
        strategy = TwoInchStrategy()
        assert strategy.get_layout_name() == "二寸（4张）"
        assert strategy.get_max_photos() == 4
        slots = strategy.get_slots()
        assert len(slots) == 4
        for slot in slots:
            assert slot.width_mm == 35
            assert slot.height_mm == 49

    def test_mixed_strategy(self):
        """测试混排版式策略"""
        strategy = MixedStrategy()
        assert strategy.get_layout_name() == "一寸+二寸混排"
        assert strategy.get_max_photos() == 6
        slots = strategy.get_slots()
        assert len(slots) == 6

    def test_get_strategy(self):
        """测试获取策略"""
        for key in STRATEGY_MAP:
            strategy = get_strategy(key)
            assert strategy is not None
            assert strategy.get_max_photos() > 0

        with pytest.raises(ValueError):
            get_strategy("invalid")


def create_test_image():
    """创建测试图片"""
    import numpy as np

    img = np.zeros((413, 295, 3), dtype=np.uint8)
    img[:] = (200, 200, 200)
    return img


class TestLayoutComposer:
    """测试排版合成器"""

    def test_compose_image(self, tmp_path):
        """测试合成 JPG 图像"""
        import cv2

        strategy = OneInchStrategy()
        composer = LayoutComposer(strategy)

        test_img = create_test_image()
        photo_paths = []
        for i in range(3):
            path = str(tmp_path / f"test_{i}.jpg")
            cv2.imwrite(path, cv2.cvtColor(test_img, cv2.COLOR_RGB2BGR))
            photo_paths.append(path)

        img = composer.compose_image(photo_paths)
        assert img is not None
        assert img.size == (2480, 3508)

    def test_compose_pdf(self, tmp_path):
        """测试合成 PDF"""
        import cv2

        strategy = OneInchStrategy()
        composer = LayoutComposer(strategy)

        test_img = create_test_image()
        photo_paths = []
        for i in range(3):
            path = str(tmp_path / f"test_{i}.jpg")
            cv2.imwrite(path, cv2.cvtColor(test_img, cv2.COLOR_RGB2BGR))
            photo_paths.append(path)

        pdf_path = str(tmp_path / "test.pdf")
        composer.compose_pdf(photo_paths, pdf_path)
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 0


class TestGeneratePrintLayout:
    """测试生成排版输出"""

    def test_generate_both(self, tmp_path):
        """测试同时生成 PDF 和 JPG"""
        import cv2

        test_img = create_test_image()
        photo_paths = []
        for i in range(3):
            path = str(tmp_path / f"test_{i}.jpg")
            cv2.imwrite(path, cv2.cvtColor(test_img, cv2.COLOR_RGB2BGR))
            photo_paths.append(path)

        pdf_path, jpg_path = generate_print_layout(
            photo_paths=photo_paths,
            layout_type="one_inch",
            output_dir=str(tmp_path),
            output_format="both",
        )

        assert pdf_path is not None
        assert jpg_path is not None
        assert os.path.exists(pdf_path)
        assert os.path.exists(jpg_path)

    def test_generate_pdf_only(self, tmp_path):
        """测试只生成 PDF"""
        import cv2

        test_img = create_test_image()
        photo_paths = []
        for i in range(2):
            path = str(tmp_path / f"test_{i}.jpg")
            cv2.imwrite(path, cv2.cvtColor(test_img, cv2.COLOR_RGB2BGR))
            photo_paths.append(path)

        pdf_path, jpg_path = generate_print_layout(
            photo_paths=photo_paths,
            layout_type="two_inch",
            output_dir=str(tmp_path),
            output_format="pdf",
        )

        assert pdf_path is not None
        assert jpg_path is None
        assert os.path.exists(pdf_path)

    def test_invalid_format(self, tmp_path):
        """测试无效的输出格式"""
        with pytest.raises(ValueError):
            generate_print_layout(
                photo_paths=["test.jpg"],
                layout_type="one_inch",
                output_dir=str(tmp_path),
                output_format="invalid",
            )

    def test_empty_photos(self, tmp_path):
        """测试空照片列表"""
        with pytest.raises(ValueError):
            generate_print_layout(
                photo_paths=[],
                layout_type="one_inch",
                output_dir=str(tmp_path),
            )

    def test_too_many_photos(self, tmp_path):
        """测试照片数量超过限制"""
        import cv2

        test_img = create_test_image()
        photo_paths = []
        for i in range(10):
            path = str(tmp_path / f"test_{i}.jpg")
            cv2.imwrite(path, cv2.cvtColor(test_img, cv2.COLOR_RGB2BGR))
            photo_paths.append(path)

        with pytest.raises(ValueError):
            generate_print_layout(
                photo_paths=photo_paths,
                layout_type="one_inch",
                output_dir=str(tmp_path),
            )
