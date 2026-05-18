"""
智能证件照制作系统 - 核心AI算法模块
基于 OpenCV + MediaPipe 实现人脸检测、背景替换、眼镜消除、画质增强
"""

import logging
import os
import cv2
import numpy as np
import mediapipe as mp

from config import get_config

logger = logging.getLogger("ai_engine")
cfg = get_config()


# ============ 人脸检测器 ============

class FaceDetector:
    """基于 MediaPipe Face Mesh 的人脸检测"""

    PHOTO_SIZES = {
        "一寸": (295, 413),
        "二寸": (413, 579),
        "小二寸": (413, 531),
    }

    def __init__(self):
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=cfg.FACE_DETECTION_CONFIDENCE,
        )

    def detect_face(self, image):
        """
        检测人脸，返回 dict(bbox, landmarks, confidence) 或 None
        """
        try:
            if image is None:
                return None
            if not isinstance(image, np.ndarray) or image.size == 0:
                return None
            if image.ndim < 2:
                return None

            h, w = image.shape[:2]
            if h <= 0 or w <= 0:
                return None

            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = self.face_mesh.process(rgb)

            if not results.multi_face_landmarks:
                logger.info("未检测到人脸")
                return None

            # 多人脸时选置信度最高的（FaceMesh 默认 max=1，但做防御）
            face_landmarks = results.multi_face_landmarks[0]
            if len(results.multi_face_landmarks) > 1:
                logger.info("检测到 %d 张人脸，选择第一张", len(results.multi_face_landmarks))

            landmarks = []
            for lm in face_landmarks.landmark:
                landmarks.append((int(lm.x * w), int(lm.y * h)))

            xs = [p[0] for p in landmarks]
            ys = [p[1] for p in landmarks]
            bx, by = min(xs), min(ys)
            bw, bh = max(xs) - bx, max(ys) - by

            if bw <= 0 or bh <= 0:
                logger.warning("人脸边界框无效: bw=%d, bh=%d", bw, bh)
                return None

            # 用 landmark 分布估算置信度
            confidence = min(1.0, bw * bh / (w * h) * 10)

            logger.info("人脸检测成功: bbox=(%d,%d,%d,%d), confidence=%.2f", bx, by, bw, bh, confidence)
            return {
                "bbox": (bx, by, bw, bh),
                "landmarks": landmarks,
                "confidence": confidence,
            }
        except Exception as e:
            logger.error("人脸检测异常: %s", e, exc_info=True)
            return None

    def get_glasses_region(self, landmarks, image_shape):
        """
        根据 landmarks 生成眼镜区域掩码
        返回 uint8 掩码或 None
        """
        try:
            if not landmarks or len(landmarks) < 468:
                logger.debug("landmarks 为空或长度不足: %d", len(landmarks) if landmarks else 0)
                return None
            if not image_shape or len(image_shape) < 2:
                return None
            h, w = image_shape[:2]
            if h <= 0 or w <= 0:
                return None

            mask = np.zeros((h, w), dtype=np.uint8)

            # 左眼区域关键点
            left_eye_pts = [33, 7, 163, 144, 145, 153, 154, 155, 133,
                            173, 157, 158, 159, 160, 161, 246]
            # 右眼区域关键点
            right_eye_pts = [362, 382, 381, 380, 374, 373, 390, 249,
                             263, 466, 388, 387, 386, 385, 384, 398]
            # 眉毛上方
            left_brow = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46]
            right_brow = [300, 293, 334, 296, 336, 285, 295, 282, 283, 276]
            # 眼下方颧骨
            left_cheek = [111, 117, 118, 119, 120, 121, 128, 245]
            right_cheek = [340, 346, 347, 348, 349, 350, 357, 465]

            # 左眼区域凸包
            left_pts = np.array(
                [landmarks[i] for i in left_eye_pts + left_brow + left_cheek
                 if i < len(landmarks)], dtype=np.int32
            )
            if len(left_pts) > 2:
                cv2.fillConvexPoly(mask, left_pts, 255)

            # 右眼区域凸包
            right_pts = np.array(
                [landmarks[i] for i in right_eye_pts + right_brow + right_cheek
                 if i < len(landmarks)], dtype=np.int32
            )
            if len(right_pts) > 2:
                cv2.fillConvexPoly(mask, right_pts, 255)

            # 鼻梁连接
            nose_pts = [6, 168, 197, 195, 5]
            for idx in nose_pts:
                if idx < len(landmarks):
                    cv2.circle(mask, landmarks[idx], int(w * 0.03), 255, -1)

            # 镜腿连接处（太阳穴）
            temple_pts = [234, 454]
            for idx in temple_pts:
                if idx < len(landmarks):
                    cv2.circle(mask, landmarks[idx], int(w * 0.04), 255, -1)

            # 膨胀扩大覆盖
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
            mask = cv2.dilate(mask, kernel, iterations=2)

            return mask
        except Exception as e:
            logger.error("生成眼镜区域掩码异常: %s", e, exc_info=True)
            return None

    def crop_id_photo(self, image, face_info, size_name="一寸"):
        """
        根据人脸信息裁剪证件照
        """
        try:
            tw, th = self.PHOTO_SIZES.get(size_name, self.PHOTO_SIZES["一寸"])
            h, w = image.shape[:2]
            bx, by, bw, bh = face_info["bbox"]

            # 人脸中心
            cx = bx + bw // 2
            cy = by + bh // 2

            # 证件照中人脸应占 60-70% 高度
            target_face_ratio = 0.65
            scale = (th * target_face_ratio) / bh if bh > 0 else 1.0

            # 计算裁剪区域（以人脸为中心）
            crop_w = int(tw / scale)
            crop_h = int(th / scale)

            # 人脸在证件照中偏上（约 40% 位置）
            face_y_ratio = 0.40
            x1 = cx - crop_w // 2
            y1 = cy - int(crop_h * face_y_ratio)
            x2 = x1 + crop_w
            y2 = y1 + crop_h

            # 边界修正
            if x1 < 0:
                x2 -= x1
                x1 = 0
            if y1 < 0:
                y2 -= y1
                y1 = 0
            if x2 > w:
                x1 -= (x2 - w)
                x2 = w
            if y2 > h:
                y1 -= (y2 - h)
                y2 = h
            x1 = max(0, x1)
            y1 = max(0, y1)

            cropped = image[y1:y2, x1:x2]
            result = cv2.resize(cropped, (tw, th), interpolation=cv2.INTER_LANCZOS4)
            logger.info("裁剪完成: size=%s, target=(%d,%d)", size_name, tw, th)
            return result
        except Exception as e:
            logger.error("裁剪证件照异常: %s", e, exc_info=True)
            return cv2.resize(image, (tw, th), interpolation=cv2.INTER_LANCZOS4)


# ============ 背景替换器 ============

class BackgroundReplacer:
    """基于 MediaPipe Selfie Segmentation 的背景替换"""

    BG_COLORS = {
        "蓝底": (219, 142, 67),    # BGR
        "白底": (255, 255, 255),
        "红底": (76, 76, 237),
    }

    def __init__(self):
        self.segmentor = mp.solutions.selfie_segmentation.SelfieSegmentation(
            model_selection=cfg.SELFIE_SEG_MODEL,
        )

    def segment_person(self, image):
        """人像分割，返回 uint8 掩码 (255=人像, 0=背景)"""
        try:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = self.segmentor.process(rgb)
            mask = (results.segmentation_mask > 0.5).astype(np.uint8) * 255
            return mask
        except Exception as e:
            logger.error("人像分割异常: %s", e, exc_info=True)
            return np.ones(image.shape[:2], dtype=np.uint8) * 255

    def get_mask(self, image):
        """segment_person 的别名"""
        return self.segment_person(image)

    def replace_background(self, image, bg_color_name="蓝底"):
        """替换背景颜色"""
        try:
            bg_color = self.BG_COLORS.get(bg_color_name, self.BG_COLORS["蓝底"])
            mask = self.segment_person(image)

            # 高斯模糊掩码边缘
            mask_blur = cv2.GaussianBlur(mask, (7, 7), 3)
            alpha = mask_blur.astype(np.float32) / 255.0

            # 创建纯色背景
            bg = np.full_like(image, bg_color, dtype=np.uint8)

            # Alpha 混合
            alpha_3ch = np.stack([alpha] * 3, axis=-1)
            result = (image.astype(np.float32) * alpha_3ch +
                      bg.astype(np.float32) * (1 - alpha_3ch))
            return result.astype(np.uint8)
        except Exception as e:
            logger.error("背景替换异常: %s", e, exc_info=True)
            return image.copy()


# ============ 眼镜消除器 ============

class GlassesRemover:
    """基于 OpenCV Inpainting 的眼镜消除"""

    def __init__(self):
        self.face_detector = FaceDetector()

    def detect_glasses(self, image, landmarks):
        """
        检测是否佩戴眼镜
        返回 (has_glasses: bool, glasses_mask: ndarray | None)
        """
        try:
            if not landmarks or len(landmarks) < 468:
                return False, None

            h, w = image.shape[:2]
            region_mask = self.face_detector.get_glasses_region(landmarks, image.shape)
            if region_mask is None:
                return False, None

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            roi = cv2.bitwise_and(gray, gray, mask=region_mask)

            # 边缘密度检测
            edges = cv2.Canny(roi, 40, 120)
            edge_pixels = cv2.countNonZero(edges)
            region_pixels = cv2.countNonZero(region_mask)
            edge_density = edge_pixels / max(region_pixels, 1)

            # 反光检测
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            _, _, v = cv2.split(hsv)
            bright_mask = cv2.bitwise_and(v, v, mask=region_mask)
            bright_pixels = cv2.countNonZero(cv2.threshold(bright_mask, 220, 255, cv2.THRESH_BINARY)[1])
            bright_ratio = bright_pixels / max(region_pixels, 1)

            # 组合判断（提高阈值避免误判）
            has_glasses = (
                (edge_density > 0.15 and bright_ratio > 0.03) or
                edge_density > 0.25 or
                bright_ratio > 0.15
            )

            logger.debug("眼镜检测: edge_density=%.3f, bright_ratio=%.3f, has_glasses=%s",
                         edge_density, bright_ratio, has_glasses)
            return has_glasses, region_mask if has_glasses else None
        except Exception as e:
            logger.error("眼镜检测异常: %s", e, exc_info=True)
            return False, None

    def remove_glasses(self, image, landmarks):
        """
        消除眼镜（精准修复镜框线条）
        """
        try:
            if not landmarks or len(landmarks) < 468:
                return image.copy()

            h, w = image.shape[:2]
            region_mask = self.face_detector.get_glasses_region(landmarks, image.shape)
            if region_mask is None:
                return image.copy()

            # 构建眼睛保护区域
            eye_protect = np.zeros((h, w), dtype=np.uint8)

            # 左眼轮廓
            left_eye_idx = [33, 7, 163, 144, 145, 153, 154, 155, 133,
                            173, 157, 158, 159, 160, 161, 246]
            left_eye_pts = np.array([landmarks[i] for i in left_eye_idx if i < len(landmarks)], dtype=np.int32)
            if len(left_eye_pts) > 2:
                cv2.fillPoly(eye_protect, [left_eye_pts], 255)

            # 右眼轮廓
            right_eye_idx = [362, 382, 381, 380, 374, 373, 390, 249,
                             263, 466, 388, 387, 386, 385, 384, 398]
            right_eye_pts = np.array([landmarks[i] for i in right_eye_idx if i < len(landmarks)], dtype=np.int32)
            if len(right_eye_pts) > 2:
                cv2.fillPoly(eye_protect, [right_eye_pts], 255)

            # 瞳孔保护（iris landmarks 468-477）
            for iris_start in [468, 473]:
                iris_pts = [landmarks[i] for i in range(iris_start, min(iris_start + 5, len(landmarks)))]
                if iris_pts:
                    cx = int(np.mean([p[0] for p in iris_pts]))
                    cy = int(np.mean([p[1] for p in iris_pts]))
                    radius = int(np.linalg.norm(np.array(iris_pts[0]) - np.array(iris_pts[-1])) * 2.5)
                    cv2.circle(eye_protect, (cx, cy), max(radius, 5), 255, -1)

            # 眉毛保护
            left_brow = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46]
            right_brow = [300, 293, 334, 296, 336, 285, 295, 282, 283, 276]
            for brow_idx in [left_brow, right_brow]:
                pts = np.array([landmarks[i] for i in brow_idx if i < len(landmarks)], dtype=np.int32)
                if len(pts) > 2:
                    cv2.polylines(eye_protect, [pts], False, 255, 3)

            # 膨胀保护区
            eye_protect = cv2.dilate(eye_protect, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), iterations=1)

            # 工作区域 = 眼镜区域 - 眼睛保护
            work_region = cv2.subtract(region_mask, eye_protect)

            result = image.copy()
            gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)

            # 用鼻梁中心分左右
            nose_x = landmarks[6][0] if 6 < len(landmarks) else w // 2
            left_mask = np.zeros((h, w), dtype=np.uint8)
            right_mask = np.zeros((h, w), dtype=np.uint8)
            left_mask[:, :nose_x] = 255
            right_mask[:, nose_x:] = 255

            left_work = cv2.bitwise_and(work_region, left_mask)
            right_work = cv2.bitwise_and(work_region, right_mask)

            def detect_frame_in_region(img_gray, work_mask, is_weak=False):
                """检测镜框线条"""
                low_t, high_t = (30, 90) if is_weak else (40, 120)
                roi = cv2.bitwise_and(img_gray, img_gray, mask=work_mask)
                edges = cv2.Canny(roi, low_t, high_t)
                edges = cv2.bitwise_and(edges, work_mask)

                # 高光检测
                hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV)
                _, _, v = cv2.split(hsv)
                v_roi = cv2.bitwise_and(v, v, mask=work_mask)
                highlights = cv2.threshold(v_roi, 230, 255, cv2.THRESH_BINARY)[1]
                # 只保留边缘附近的高光
                edge_dilated = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=1)
                highlights = cv2.bitwise_and(highlights, edge_dilated)

                combined = cv2.bitwise_or(edges, highlights)

                if is_weak:
                    # 增加暗像素检测
                    dark_thresh = np.percentile(img_gray[work_mask > 0], 25) if cv2.countNonZero(work_mask) > 0 else 60
                    dark_mask = cv2.threshold(roi, int(dark_thresh), 255, cv2.THRESH_BINARY_INV)[1]
                    dark_mask = cv2.bitwise_and(dark_mask, work_mask)
                    combined = cv2.bitwise_or(combined, dark_mask)

                # 膨胀连接
                k_size = 5 if is_weak else 3
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_size, k_size))
                combined = cv2.dilate(combined, kernel, iterations=2)
                combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE,
                                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
                combined = cv2.bitwise_and(combined, work_mask)
                return combined

            # 分别检测左右
            left_frame = detect_frame_in_region(gray, left_work)
            right_frame = detect_frame_in_region(gray, right_work)

            left_count = cv2.countNonZero(left_frame)
            right_count = cv2.countNonZero(right_frame)

            # 弱侧增强
            if left_count > 0 and right_count > 0:
                ratio = min(left_count, right_count) / max(left_count, right_count)
                if ratio < 0.6:
                    if left_count < right_count:
                        left_frame = detect_frame_in_region(gray, left_work, is_weak=True)
                    else:
                        right_frame = detect_frame_in_region(gray, right_work, is_weak=True)

            frame_mask = cv2.bitwise_or(left_frame, right_frame)

            if cv2.countNonZero(frame_mask) == 0:
                logger.info("未检测到镜框线条，跳过修复")
                return image.copy()

            # 多轮修复
            num_rounds = 3
            for i in range(num_rounds):
                if cv2.countNonZero(frame_mask) == 0:
                    break
                radius = 4 if i < 2 else 3
                result = cv2.inpaint(result, frame_mask, radius, cv2.INPAINT_TELEA)

                # 重新检测残留
                gray_new = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
                edges_new = cv2.Canny(cv2.bitwise_and(gray_new, gray_new, mask=work_region), 40, 120)
                frame_mask = cv2.bitwise_and(edges_new, work_region)
                frame_mask = cv2.dilate(frame_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), iterations=1)

            # 最终精修
            if cv2.countNonZero(frame_mask) > 0:
                result = cv2.inpaint(result, frame_mask, 3, cv2.INPAINT_NS)

            # 平滑融合
            blend_mask = cv2.GaussianBlur(work_region, (5, 5), 2)
            alpha = blend_mask.astype(np.float32) / 255.0
            alpha_3ch = np.stack([alpha] * 3, axis=-1)
            result = (result.astype(np.float32) * alpha_3ch +
                      image.astype(np.float32) * (1 - alpha_3ch)).astype(np.uint8)

            logger.info("眼镜消除完成")
            return result
        except Exception as e:
            logger.error("眼镜消除异常: %s", e, exc_info=True)
            return image.copy()


# ============ 画质增强器 ============

class ImageEnhancer:
    """基于 OpenCV 的画质增强"""

    def denoise(self, image, strength=None):
        """Non-Local Means 降噪"""
        try:
            s = strength if strength is not None else cfg.ENHANCE_DENOISE_STRENGTH
            return cv2.fastNlMeansDenoisingColored(image, None, s, s, 7, 21)
        except Exception as e:
            logger.error("降噪异常: %s", e, exc_info=True)
            return image.copy()

    def sharpen(self, image, strength=None):
        """Unsharp Mask 锐化"""
        try:
            s = strength if strength is not None else cfg.ENHANCE_SHARPEN_STRENGTH
            blurred = cv2.GaussianBlur(image, (0, 0), 3)
            result = cv2.addWeighted(image, 1.0 + s, blurred, -s, 0)
            return np.clip(result, 0, 255).astype(np.uint8)
        except Exception as e:
            logger.error("锐化异常: %s", e, exc_info=True)
            return image.copy()

    def adjust_brightness_contrast(self, image, brightness=None, contrast=None):
        """调整亮度和对比度"""
        try:
            b = brightness if brightness is not None else cfg.ENHANCE_BRIGHTNESS
            c = contrast if contrast is not None else cfg.ENHANCE_CONTRAST
            result = image.astype(np.float32)
            result = result * c + b
            return np.clip(result, 0, 255).astype(np.uint8)
        except Exception as e:
            logger.error("亮度对比度调整异常: %s", e, exc_info=True)
            return image.copy()

    def smooth_skin(self, image, face_mask=None, strength=None):
        """双边滤波美肤"""
        try:
            s = strength if strength is not None else cfg.ENHANCE_SKIN_STRENGTH
            smoothed = cv2.bilateralFilter(image, 9, 75, 75)
            if face_mask is not None:
                alpha = (face_mask.astype(np.float32) / 255.0 * s)
                alpha_3ch = np.stack([alpha] * 3, axis=-1)
                result = (smoothed.astype(np.float32) * alpha_3ch +
                          image.astype(np.float32) * (1 - alpha_3ch))
                return result.astype(np.uint8)
            else:
                return cv2.addWeighted(image, 1 - s, smoothed, s, 0)
        except Exception as e:
            logger.error("美肤异常: %s", e, exc_info=True)
            return image.copy()

    def super_resolve(self, image, scale=2):
        """简单超分辨率（双三次插值）"""
        try:
            h, w = image.shape[:2]
            return cv2.resize(image, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
        except Exception as e:
            logger.error("超分辨率异常: %s", e, exc_info=True)
            return image.copy()

    def enhance(self, image, face_mask=None):
        """一键增强流水线"""
        try:
            result = self.denoise(image)
            result = self.adjust_brightness_contrast(result)
            result = self.smooth_skin(result, face_mask)
            result = self.sharpen(result)
            logger.info("画质增强完成")
            return result
        except Exception as e:
            logger.error("一键增强异常: %s", e, exc_info=True)
            return image.copy()


# ============ 主处理流水线 ============

class IDPhotoProcessor:
    """整合所有 AI 模块的证件照处理器"""

    def __init__(self):
        self.face_detector = FaceDetector()
        self.bg_replacer = BackgroundReplacer()
        self.glasses_remover = GlassesRemover()
        self.enhancer = ImageEnhancer()

        self.original_image = None
        self.current_image = None
        self.face_info = None
        self.processing_log = []

    def _log(self, msg):
        self.processing_log.append(msg)
        logger.info(msg)

    def get_log(self):
        return "\n".join(self.processing_log)

    def has_face(self):
        return self.face_info is not None

    def check_glasses(self):
        """检测当前图片是否佩戴眼镜"""
        if not self.has_face() or self.current_image is None:
            return False
        has, _ = self.glasses_remover.detect_glasses(
            self.current_image, self.face_info.get("landmarks", [])
        )
        return has

    def load_image(self, path):
        """从文件路径加载图片"""
        try:
            if not path or not os.path.exists(path):
                logger.warning("图片路径无效: %s", path)
                return False
            img = cv2.imread(path)
            if img is None:
                logger.warning("cv2.imread 无法读取: %s", path)
                return False
            return self.load_image_from_array(img)
        except Exception as e:
            logger.error("加载图片异常: %s", e, exc_info=True)
            return False

    def load_image_from_array(self, image):
        """从 numpy 数组加载图片"""
        try:
            if image is None:
                return False
            if not isinstance(image, np.ndarray) or image.size == 0:
                return False

            self.original_image = image.copy()
            self.current_image = image.copy()
            self.processing_log = []
            self._log("图片已加载: %dx%d" % (image.shape[1], image.shape[0]))

            # 自动检测人脸
            self.face_info = self.face_detector.detect_face(image)
            if self.face_info:
                self._log("检测到人脸 (置信度: %.2f)" % self.face_info["confidence"])
            else:
                self._log("未检测到人脸")
            return True
        except Exception as e:
            logger.error("从数组加载图片异常: %s", e, exc_info=True)
            return False

    def process_remove_glasses(self):
        """消除眼镜"""
        try:
            if self.current_image is None:
                logger.warning("无图片，跳过眼镜消除")
                return None
            if not self.has_face():
                self._log("未检测到人脸，跳过眼镜消除")
                return self.current_image

            landmarks = self.face_info.get("landmarks", [])
            # 先检测是否有眼镜
            has_glasses = self.check_glasses()
            if not has_glasses:
                self._log("跳过眼镜消除：未检测到眼镜")
                logger.debug("跳过眼镜消除：未检测到眼镜")
                return self.current_image

            self.current_image = self.glasses_remover.remove_glasses(self.current_image, landmarks)
            self._log("已消除眼镜")
            return self.current_image
        except Exception as e:
            logger.error("眼镜消除处理异常: %s", e, exc_info=True)
            return self.current_image

    def process_replace_background(self, bg_color="蓝底"):
        """替换背景"""
        try:
            if self.current_image is None:
                logger.warning("无图片，跳过背景替换")
                return None
            logger.info("开始背景替换: color=%s", bg_color)
            self.current_image = self.bg_replacer.replace_background(self.current_image, bg_color)
            self._log("已替换背景: %s" % bg_color)
            return self.current_image
        except Exception as e:
            logger.error("背景替换处理异常: %s", e, exc_info=True)
            return self.current_image

    def process_enhance(self):
        """画质增强"""
        try:
            if self.current_image is None:
                logger.warning("无图片，跳过画质增强")
                return None
            logger.info("开始画质增强")
            self.current_image = self.enhancer.enhance(self.current_image)
            self._log("已增强画质")
            return self.current_image
        except Exception as e:
            logger.error("画质增强处理异常: %s", e, exc_info=True)
            return self.current_image

    def process_crop(self, size_name="一寸"):
        """裁剪证件照"""
        try:
            if self.current_image is None:
                logger.warning("无图片，跳过裁剪")
                return None
            if not self.has_face():
                self._log("未检测到人脸，无法裁剪")
                return self.current_image
            logger.info("开始裁剪: size=%s", size_name)
            self.current_image = self.face_detector.crop_id_photo(
                self.current_image, self.face_info, size_name
            )
            self._log("已裁剪为 %s" % size_name)
            return self.current_image
        except Exception as e:
            logger.error("裁剪处理异常: %s", e, exc_info=True)
            return self.current_image

    def process_full_pipeline(self, bg_color="蓝底", size_name="一寸",
                              remove_glasses=True, enhance=True):
        """完整处理流水线（从原图开始）"""
        try:
            if self.original_image is None:
                logger.warning("无原始图片，无法执行完整流水线")
                return None
            if not self.has_face():
                self._log("未检测到人脸，无法执行完整流水线")
                return None

            logger.info("开始完整流水线: bg=%s, size=%s, glasses=%s, enhance=%s",
                        bg_color, size_name, remove_glasses, enhance)

            # 从原图重新开始
            self.current_image = self.original_image.copy()

            if remove_glasses:
                self.process_remove_glasses()
            if enhance:
                self.process_enhance()
            self.process_replace_background(bg_color)
            self.process_crop(size_name)

            self._log("一键处理完成: %s %s" % (bg_color, size_name))
            return self.current_image
        except Exception as e:
            logger.error("完整流水线异常: %s", e, exc_info=True)
            return None

    def save_result(self, path):
        """保存当前结果"""
        try:
            if self.current_image is None:
                logger.warning("无图片可保存")
                return False
            os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
            ext = os.path.splitext(path)[1].lower()
            if ext == ".png":
                success = cv2.imwrite(path, self.current_image)
            else:
                success = cv2.imwrite(path, self.current_image,
                                      [cv2.IMWRITE_JPEG_QUALITY, cfg.EXPORT_JPEG_QUALITY])
            if success:
                logger.info("结果已保存: %s", path)
            else:
                logger.error("保存失败: %s", path)
            return success
        except Exception as e:
            logger.error("保存结果异常: %s", e, exc_info=True)
            return False

    def reset(self):
        """重置为原图"""
        try:
            if self.original_image is not None:
                self.current_image = self.original_image.copy()
                self._log("已重置为原图")
                logger.info("已重置为原图")
            else:
                logger.warning("无原始图片，无法重置")
        except Exception as e:
            logger.error("重置异常: %s", e, exc_info=True)
