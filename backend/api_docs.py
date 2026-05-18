"""
智能证件照制作系统 - API 接口文档

所有接口基础路径: /api
响应格式: JSON (除 /api/export 成功时返回文件流)
错误响应统一格式: {"error": "错误描述信息"}
"""

API_DOCS = {
    "health": {
        "path": "/api/health",
        "method": "GET",
        "description": "健康检查",
        "request": None,
        "response_200": {
            "status": "ok",
            "service": "智能证件照制作系统"
        },
    },
    "upload": {
        "path": "/api/upload",
        "method": "POST",
        "description": "上传照片并自动检测人脸",
        "content_type": "multipart/form-data",
        "request": {
            "file": "(必填) 图片文件，支持 JPG/PNG/BMP，最大 10MB，尺寸 100~8000px"
        },
        "response_200": {
            "session_id": "str - 会话标识，后续接口必传",
            "has_face": "bool - 是否检测到人脸",
            "original": "str - 原图 base64 编码",
            "preview": "str - 预览图 base64 编码",
            "log": "str - 处理日志",
            "confidence": "float - (仅检测到人脸时) 置信度 0~1",
            "has_glasses": "bool - (仅检测到人脸时) 是否佩戴眼镜",
        },
        "errors": {
            400: [
                "未上传文件",
                "文件名为空",
                "不支持的文件格式",
                "文件大小超过限制",
                "文件内容不是有效的图片",
                "无法解析图片内容",
                "图片尺寸过小",
                "图片尺寸过大",
                "无法加载图片",
            ],
            500: ["处理上传照片时出错"],
            503: ["服务器繁忙（会话数达上限）"],
        },
    },
    "process": {
        "path": "/api/process",
        "method": "POST",
        "description": "执行单步处理操作",
        "content_type": "application/json",
        "request": {
            "session_id": "(必填) str - 会话标识",
            "action": "(必填) str - 操作类型，见下方说明",
            "bg_color": "(可选) str - 背景颜色，默认'蓝底'，可选: 蓝底/白底/红底",
            "size": "(可选) str - 证件照尺寸，默认'一寸'，可选: 一寸/二寸/小二寸",
        },
        "actions": {
            "replace_background": "替换背景 (需要 bg_color 参数)",
            "remove_glasses": "消除眼镜",
            "enhance": "画质增强",
            "crop": "裁剪证件照 (需要 size 参数)",
            "auto": "一键处理 (需要 bg_color + size 参数)",
            "reset": "重置为原图",
        },
        "response_200": {
            "session_id": "str - 会话标识",
            "preview": "str - 处理后预览图 base64 编码",
            "log": "str - 处理日志",
        },
        "errors": {
            400: [
                "缺少 session_id",
                "无效的会话标识",
                "当前会话中没有照片",
                "不支持的背景颜色",
                "不支持的证件照尺寸",
                "未知操作",
            ],
            500: ["执行操作时出错"],
        },
    },
    "export": {
        "path": "/api/export",
        "method": "POST",
        "description": "导出证件照文件",
        "content_type": "application/json",
        "request": {
            "session_id": "(必填) str - 会话标识",
            "format": "(可选) str - 导出格式，默认'jpg'，可选: jpg/png",
        },
        "response_200": "文件流 (Content-Disposition: attachment, filename=证件照.jpg/.png)",
        "errors": {
            400: [
                "缺少 session_id",
                "无效的会话标识",
                "不支持的导出格式",
                "没有可导出的照片",
            ],
            500: ["保存照片失败", "导出照片时出错"],
        },
    },
    "detect": {
        "path": "/api/detect",
        "method": "POST",
        "description": "获取人脸检测可视化结果",
        "content_type": "application/json",
        "request": {
            "session_id": "(必填) str - 会话标识",
        },
        "response_200": {
            "session_id": "str - 会话标识",
            "preview": "str - 标注人脸框和关键点的预览图 base64 编码",
            "confidence": "float - 人脸检测置信度 0~1",
            "has_glasses": "bool - 是否佩戴眼镜",
            "log": "str - 处理日志",
        },
        "errors": {
            400: [
                "缺少 session_id",
                "无效的会话标识",
                "当前会话中没有照片",
                "未检测到人脸",
            ],
            500: ["人脸检测可视化时出错"],
        },
    },
}
