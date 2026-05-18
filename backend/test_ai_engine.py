"""
智能证件照制作系统 - 核心AI算法模块单元测试
"""

import pytest
import numpy as np
import cv2

from ai_engine import (
    FaceDetector,
    BackgroundReplacer,
    GlassesRemover,
    ImageEnhancer,
    IDPhotoProcessor,
)


# ============ 测试辅助 ============

def make_dummy_image(w=400, h=600, color=(200, 180, 160)):
    """生成纯色测试图片"""
    return np.full((h, w, 3), color, dtype=np.uint8)


def make_face_image(w=400, h=600):
    """生成带简单人脸特征的测试图片（椭圆模拟）"""
    img = np.full((h, w, 3), (220, 210, 200), dtype=np.uint8)
    # 脸部椭圆
    cv2.ellipse(img, (w // 2, h // 3), (80, 110), 0, 0, 360, (180, 150, 130), -1)
    # 眼睛
    cv2.circle(img, (w // 2 - 30, h // 3 - 15), 8, (60, 40, 30), -1)
    cv2.circle(img, (w // 2 + 30, h // 3 - 15), 8, (60, 40, 30), -1)
    # 嘴巴
    cv2.ellipse(img, (w // 2, h // 3 + 40), (20, 8), 0, 0, 360, (100, 60, 60), -1)
    return img


# ============ FaceDetector 测试 ============

class TestFaceDetector:
    def setup_method(self):
        self.detector = FaceDetector()

    def test_detect_face_with_none_image(self):
        """空图像应返回 None"""
        result = self.detector.detect_face(None)
        assert result is None

    def test_detect_face_with_empty_image(self):
        """空数组应返回 None"""
        empty = np.array([], dtype=np.uint8)
        result = self.detector.detect_face(empty)
        assert result is None

    def test_detect_face_with_dummy_image(self):
        """纯色图片应检测不到人脸"""
        img = make_dummy_image()
        result = self.detector.detect_face(img)
        assert result is None

    def test_detect_face_return_structure(self):
        """检测结果应包含 bbox, landmarks, confidence 字段"""
        img = make_face_image()
        result = self.detector.detect_face(img)
        # 模拟人脸不一定能被 MediaPipe 识别，跳过无检测结果的情况
        if result is not None:
            assert "bbox" in result
            assert "landmarks" in result
            assert "confidence" in result
            assert len(result["bbox"]) == 4
            assert isinstance(result["confidence"], float)

    def test_photo_sizes_constant(self):
        """证件照尺寸常量应包含标准尺寸"""
        assert "一寸" in FaceDetector.PHOTO_SIZES
        assert "二寸" in FaceDetector.PHOTO_SIZES
        assert "小二寸" in FaceDetector.PHOTO_SIZES
        for name, (w, h) in FaceDetector.PHOTO_SIZES.items():
            assert w > 0 and h > 0

    def test_get_glasses_region_empty_landmarks(self):
        """空 landmarks 应返回 None"""
        result = self.detector.get_glasses_region([], (600, 400, 3))
        assert result is None

    def test_get_glasses_region_short_landmarks(self):
        """landmarks 长度不足 468 应返回 None"""
        landmarks = [(0, 0)] * 100
        result = self.detector.get_glasses_region(landmarks, (600, 400, 3))
        assert result is None

    def test_get_glasses_region_none_landmarks(self):
        """None landmarks 应返回 None"""
        result = self.detector.get_glasses_region(None, (600, 400, 3))
        assert result is None

    def test_get_glasses_region_invalid_shape(self):
        """无效 image_shape 应返回 None"""
        landmarks = [(100, 100)] * 468
        result = self.detector.get_glasses_region(landmarks, ())
        assert result is None

    def test_get_glasses_region_valid(self):
        """有效 landmarks 应返回掩码"""
        landmarks = [(200 + i % 50, 150 + i % 40) for i in range(478)]
        result = self.detector.get_glasses_region(landmarks, (600, 400, 3))
        assert result is not None
        assert result.shape == (600, 400)
        assert result.dtype == np.uint8

    def test_crop_id_photo_output_size(self):
        """裁剪输出尺寸应与目标一致"""
        img = make_dummy_image(800, 1200)
        face_info = {"bbox": (300, 200, 200, 250), "landmarks": [], "confidence": 0.9}
        for size_name, (tw, th) in FaceDetector.PHOTO_SIZES.items():
            cropped = self.detector.crop_id_photo(img, face_info, size_name)
            assert cropped.shape[1] == tw
            assert cropped.shape[0] == th


# ============ BackgroundReplacer 测试 ============

class TestBackgroundReplacer:
    def setup_method(self):
        self.replacer = BackgroundReplacer()

    def test_bg_colors_constant(self):
        """背景颜色常量应包含标准颜色"""
        assert "蓝底" in BackgroundReplacer.BG_COLORS
        assert "白底" in BackgroundReplacer.BG_COLORS
        assert "红底" in BackgroundReplacer.BG_COLORS

    def test_segment_person_returns_mask(self):
        """人像分割应返回与输入同尺寸的掩码"""
        img = make_dummy_image(200, 300)
        mask = self.replacer.segment_person(img)
        assert mask.shape == (300, 200)
        assert mask.dtype == np.uint8

    def test_replace_background_returns_image(self):
        """背景替换应返回与输入同尺寸的图片"""
        img = make_dummy_image(200, 300)
        result = self.replacer.replace_background(img, "蓝底")
        assert result.shape == img.shape
        assert result.dtype == np.uint8

    def test_replace_background_invalid_color_fallback(self):
        """无效颜色名应回退到蓝底"""
        img = make_dummy_image(200, 300)
        result = self.replacer.replace_background(img, "紫底")
        assert result.shape == img.shape

    def test_get_mask_same_as_segment(self):
        """get_mask 应与 segment_person 返回相同结果"""
        img = make_dummy_image(200, 300)
        mask1 = self.replacer.segment_person(img)
        mask2 = self.replacer.get_mask(img)
        np.testing.assert_array_equal(mask1, mask2)


# ============ GlassesRemover 测试 ============

class TestGlassesRemover:
    def setup_method(self):
        self.remover = GlassesRemover()

    def test_detect_glasses_empty_landmarks(self):
        """空 landmarks 应返回 (False, None)"""
        img = make_dummy_image()
        has, mask = self.remover.detect_glasses(img, [])
        assert has is False
        assert mask is None

    def test_detect_glasses_short_landmarks(self):
        """landmarks 不足应返回 (False, None)"""
        img = make_dummy_image()
        has, mask = self.remover.detect_glasses(img, [(0, 0)] * 100)
        assert has is False
        assert mask is None

    def test_remove_glasses_no_glasses(self):
        """无眼镜时应返回原图"""
        img = make_dummy_image()
        result = self.remover.remove_glasses(img, [])
        np.testing.assert_array_equal(result, img)

    def test_remove_glasses_returns_same_shape(self):
        """消除眼镜后图片尺寸应不变"""
        img = make_dummy_image()
        landmarks = [(200 + i % 50, 150 + i % 40) for i in range(478)]
        result = self.remover.remove_glasses(img, landmarks)
        assert result.shape == img.shape


# ============ ImageEnhancer 测试 ============

class TestImageEnhancer:
    def setup_method(self):
        self.enhancer = ImageEnhancer()

    def test_denoise_returns_same_shape(self):
        """降噪后图片尺寸应不变"""
        img = make_dummy_image()
        result = self.enhancer.denoise(img, strength=5)
        assert result.shape == img.shape

    def test_sharpen_returns_same_shape(self):
        """锐化后图片尺寸应不变"""
        img = make_dummy_image()
        result = self.enhancer.sharpen(img, strength=1.0)
        assert result.shape == img.shape
        assert result.dtype == np.uint8

    def test_adjust_brightness_contrast_returns_same_shape(self):
        """亮度对比度调整后图片尺寸应不变"""
        img = make_dummy_image()
        result = self.enhancer.adjust_brightness_contrast(img)
        assert result.shape == img.shape

    def test_smooth_skin_without_mask(self):
        """无掩码美肤后图片尺寸应不变"""
        img = make_dummy_image()
        result = self.enhancer.smooth_skin(img, face_mask=None)
        assert result.shape == img.shape

    def test_smooth_skin_with_mask(self):
        """有掩码美肤后图片尺寸应不变"""
        img = make_dummy_image(200, 300)
        mask = np.full((300, 200), 255, dtype=np.uint8)
        result = self.enhancer.smooth_skin(img, face_mask=mask)
        assert result.shape == img.shape

    def test_super_resolve_doubles_size(self):
        """2x 超分辨率应将尺寸翻倍"""
        img = make_dummy_image(100, 150)
        result = self.enhancer.super_resolve(img, scale=2)
        assert result.shape[0] == 300
        assert result.shape[1] == 200

    def test_enhance_returns_same_shape(self):
        """一键增强后图片尺寸应不变"""
        img = make_dummy_image()
        result = self.enhancer.enhance(img)
        assert result.shape == img.shape


# ============ IDPhotoProcessor 测试 ============

class TestIDPhotoProcessor:
    def setup_method(self):
        self.proc = IDPhotoProcessor()

    def test_initial_state(self):
        """初始状态应为空"""
        assert self.proc.original_image is None
        assert self.proc.current_image is None
        assert self.proc.face_info is None
        assert self.proc.has_face() is False

    def test_load_image_invalid_path(self):
        """加载不存在的文件应返回 False"""
        result = self.proc.load_image("/nonexistent/path.jpg")
        assert result is False

    def test_load_image_from_array_none(self):
        """加载 None 应返回 False"""
        result = self.proc.load_image_from_array(None)
        assert result is False

    def test_load_image_from_array_empty(self):
        """加载空数组应返回 False"""
        result = self.proc.load_image_from_array(np.array([], dtype=np.uint8))
        assert result is False

    def test_load_image_from_array_valid(self):
        """加载有效图片应返回 True"""
        img = make_dummy_image()
        result = self.proc.load_image_from_array(img)
        assert result is True
        assert self.proc.original_image is not None
        assert self.proc.current_image is not None

    def test_check_glasses_no_face(self):
        """无人脸时检测眼镜应返回 False"""
        assert self.proc.check_glasses() is False

    def test_process_remove_glasses_no_face(self):
        """无人脸时消除眼镜应返回当前图片"""
        img = make_dummy_image()
        self.proc.load_image_from_array(img)
        result = self.proc.process_remove_glasses()
        assert result is not None

    def test_process_replace_background(self):
        """背景替换应返回同尺寸图片"""
        img = make_dummy_image()
        self.proc.load_image_from_array(img)
        result = self.proc.process_replace_background("蓝底")
        assert result.shape == img.shape

    def test_process_enhance(self):
        """画质增强应返回同尺寸图片"""
        img = make_dummy_image()
        self.proc.load_image_from_array(img)
        result = self.proc.process_enhance()
        assert result.shape == img.shape

    def test_process_crop_no_face(self):
        """无人脸时裁剪应返回当前图片不变"""
        img = make_dummy_image()
        self.proc.load_image_from_array(img)
        result = self.proc.process_crop("一寸")
        assert result.shape == img.shape

    def test_process_full_pipeline_no_image(self):
        """无图片时完整流水线应返回 None"""
        result = self.proc.process_full_pipeline()
        assert result is None

    def test_process_full_pipeline_no_face(self):
        """无人脸时完整流水线应返回 None"""
        img = make_dummy_image()
        self.proc.load_image_from_array(img)
        result = self.proc.process_full_pipeline()
        assert result is None

    def test_save_result_no_image(self):
        """无图片时保存应返回 False"""
        result = self.proc.save_result("/tmp/test_output.jpg")
        assert result is False

    def test_save_result_valid(self, tmp_path):
        """有图片时保存应成功"""
        img = make_dummy_image()
        self.proc.load_image_from_array(img)
        out = str(tmp_path / "result.jpg")
        result = self.proc.save_result(out)
        assert result is True

    def test_reset(self):
        """重置后应恢复为原图"""
        img = make_dummy_image()
        self.proc.load_image_from_array(img)
        self.proc.process_replace_background("红底")
        self.proc.reset()
        np.testing.assert_array_equal(self.proc.current_image, self.proc.original_image)

    def test_get_log(self):
        """日志应为字符串"""
        img = make_dummy_image()
        self.proc.load_image_from_array(img)
        log = self.proc.get_log()
        assert isinstance(log, str)
        assert len(log) > 0
