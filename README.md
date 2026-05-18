# 智能证件照制作系统

## How to Run

```bash
# 克隆项目
git clone <repo-url>
cd label-00255

# 一键启动（需要 Docker 和 Docker Compose）
docker-compose up --build -d

# 访问前端界面
# 浏览器打开 http://localhost:8081
```

停止服务：

```bash
docker-compose down
```

## Services

| 服务 | 说明 | 端口 |
|------|------|------|
| frontend-admin | Nginx 静态前端 | 8081 (对外) |
| backend | Flask + AI 引擎 API | 5000 (内部) |

## 测试账号

首次使用需注册账号，在登录页面点击"立即注册"创建新用户。

注册要求：
- 用户名：2~20 个字符，支持字母、数字、下划线、中文
- 密码：6~50 个字符

---

## 项目介绍

基于 OpenCV + MediaPipe 的智能证件照制作系统，提供完整的 Web 界面操作流程。

### 核心功能

- **人脸检测**：基于 MediaPipe Face Mesh，提取 468 个人脸关键点，自动定位人脸区域
- **背景替换**：基于 MediaPipe Selfie Segmentation 人像分割，支持蓝底/白底/红底，Alpha 混合羽化过渡
- **眼镜消除**：通过关键点定位眼镜区域，分析边缘密度+反光特征检测眼镜，使用 OpenCV Navier-Stokes + Telea 双算法 Inpainting 修复
- **画质增强**：Non-Local Means 降噪 + CLAHE 自适应均衡 + 双边滤波美肤 + Unsharp Mask 锐化
- **智能裁剪**：根据人脸位置自动裁剪为标准证件照尺寸（一寸/二寸/小二寸）
- **一键处理**：自动完成 眼镜消除 → 画质增强 → 背景替换 → 裁剪 全流程
- **用户认证**：JWT Token 认证 + bcrypt 密码哈希，支持注册/登录
- **数据持久化**：SQLite 存储用户数据、会话记录、操作历史
- **历史记录**：记录每次操作，支持查看会话列表、操作详情、使用统计

### 技术栈

- **后端**：Python 3.11 + Flask + OpenCV + MediaPipe + Gunicorn
- **前端**：HTML5 + CSS3 + JavaScript（原生，无框架依赖）
- **部署**：Docker + Docker Compose + Nginx 反向代理

### 项目结构

```
label-00255/
├── docker-compose.yml          # Docker 编排配置
├── README.md                   # 项目说明
├── .github/workflows/ci.yml    # CI 持续集成配置
├── backend/                    # 后端服务
│   ├── Dockerfile              # 后端容器构建
│   ├── requirements.txt        # Python 依赖
│   ├── config.py               # 配置管理模块
│   ├── .env.example            # 环境变量示例
│   ├── auth.py                 # 用户认证模块（JWT + bcrypt）
│   ├── models.py               # 用户数据模型（SQLite）
│   ├── app.py                  # Flask Web API
│   ├── ai_engine.py            # 核心 AI 算法模块
│   ├── test_ai_engine.py       # AI 算法模块单元测试
│   ├── test_app.py             # Flask API 接口单元测试
│   ├── test_auth.py            # 用户认证模块测试
│   ├── test_persistence.py     # 数据持久化与历史记录测试
│   ├── test_integration.py     # 集成测试
│   ├── uploads/                # 上传文件目录
│   └── output/                 # 导出文件目录
└── frontend-admin/             # 前端服务
    ├── Dockerfile              # 前端容器构建
    ├── nginx.conf              # Nginx 配置（含反向代理）
    ├── index.html              # Web 界面
    └── img/                    # 测试图片目录
        ├── person.jpeg         # 测试图片1
        └── person1.webp        # 测试图片2
```

### 测试

#### 运行测试

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 运行全部测试
pytest -v

# 仅运行单元测试
pytest test_ai_engine.py test_app.py -v

# 仅运行集成测试
pytest test_integration.py -v

# 运行测试并生成覆盖率报告
pytest --cov=. --cov-report=term-missing --cov-report=html -v
```

#### 测试文件说明

| 文件 | 类型 | 用例数 | 说明 |
|------|------|--------|------|
| test_ai_engine.py | 单元测试 | 38 | 覆盖 FaceDetector、BackgroundReplacer、GlassesRemover、ImageEnhancer、IDPhotoProcessor |
| test_app.py | 单元测试 | 27 | 覆盖所有 API 接口的参数校验、正常/异常响应 |
| test_auth.py | 单元测试 | 25 | 覆盖注册/登录/认证中间件/完整认证流程 |
| test_persistence.py | 单元+集成 | 28 | 覆盖数据模型CRUD/会话持久化/历史记录API/用户隔离 |
| test_integration.py | 集成测试 | 28 | 覆盖完整业务流程、多会话隔离、参数化测试、Docker 部署验证 |

#### 覆盖率要求

- 核心算法模块 (`ai_engine.py`)：≥ 70%
- API 接口 (`app.py`)：≥ 80%
- 整体项目：≥ 60%

#### 持续集成

项目配置了 GitHub Actions CI，每次 push 和 PR 自动运行：
1. 安装 Python 3.11 和系统依赖
2. 执行全部测试用例
3. 生成覆盖率报告并检查是否达标（整体 ≥ 60%）

### 配置管理

项目通过 `config.py` 统一管理配置，支持通过环境变量覆盖默认值。

#### 环境切换

通过 `APP_ENV` 环境变量切换运行环境：

```bash
# 开发环境（DEBUG 模式，日志级别 DEBUG）
APP_ENV=development python app.py

# 测试环境（会话 1 分钟过期，最多 10 个会话）
APP_ENV=testing pytest -v

# 生产环境（默认）
APP_ENV=production gunicorn app:app
```

#### 环境变量说明

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| APP_ENV | production | 运行环境: development / testing / production |
| HOST | 0.0.0.0 | 服务监听地址 |
| PORT | 5000 | 服务监听端口 |
| LOG_LEVEL | INFO | 日志级别: DEBUG / INFO / WARNING / ERROR |
| MAX_FILE_SIZE | 10485760 | 最大上传文件大小（字节），默认 10MB |
| MIN_IMAGE_SIZE | 100 | 最小图片尺寸（像素） |
| MAX_IMAGE_SIZE | 8000 | 最大图片尺寸（像素） |
| MAX_SESSIONS | 100 | 最大同时会话数 |
| SESSION_EXPIRE_SECONDS | 1800 | 会话过期时间（秒），默认 30 分钟 |
| FACE_DETECTION_CONFIDENCE | 0.5 | 人脸检测置信度阈值 |
| JWT_SECRET | (内置默认值) | JWT 签名密钥，生产环境务必修改 |
| JWT_EXPIRE_SECONDS | 86400 | Token 过期时间（秒），默认 24 小时 |
| ENHANCE_DENOISE_STRENGTH | 3 | 降噪强度 |
| ENHANCE_BRIGHTNESS | 3 | 亮度调整值 |
| ENHANCE_CONTRAST | 1.02 | 对比度调整系数 |
| EXPORT_JPEG_QUALITY | 95 | JPEG 导出质量 |

#### Docker 部署配置

在 `docker-compose.yml` 中通过 `environment` 字段配置，或创建 `.env` 文件（参考 `backend/.env.example`）：

```bash
# 复制示例配置
cp backend/.env.example .env

# 修改后启动
docker-compose up --build -d
```

### AI 算法说明

| 模块 | 算法 | 说明 |
|------|------|------|
| FaceDetector | MediaPipe Face Mesh + Face Detection | 468 关键点 + 人脸边界框 |
| BackgroundReplacer | MediaPipe Selfie Segmentation | 人像分割 + Alpha 混合 |
| GlassesRemover | OpenCV Inpainting (NS + Telea) | Canny 边缘 + 反光检测 + 双算法融合修复 |
| ImageEnhancer | NLM 降噪 + CLAHE + 双边滤波 + USM 锐化 | 多级画质增强流水线 |

### API 接口文档

所有接口基础路径: `/api`，错误响应统一格式: `{"error": "错误描述信息"}`

#### GET /api/health

健康检查（无需认证）。

响应示例:
```json
{"status": "ok", "service": "智能证件照制作系统"}
```

#### POST /api/register

用户注册（无需认证）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名，2~20 字符，支持字母/数字/下划线/中文 |
| password | string | 是 | 密码，6~50 字符 |

成功响应 (201):
```json
{"message": "注册成功"}
```

错误码: 400（参数不合规）、409（用户名已存在）

#### POST /api/login

用户登录（无需认证）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |

成功响应 (200):
```json
{
  "message": "登录成功",
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "username": "testuser"
}
```

错误码: 400（参数为空）、401（用户名或密码错误）

> 以下接口均需要在请求头中携带 `Authorization: Bearer <token>`

#### POST /api/upload

上传照片并自动检测人脸。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | 是 | 图片文件，支持 JPG/PNG/BMP，最大 10MB，尺寸 100~8000px |

请求格式: `multipart/form-data`

成功响应:
```json
{
  "session_id": "a1b2c3d4",
  "has_face": true,
  "original": "base64...",
  "preview": "base64...",
  "log": "已加载图片\n检测到人脸 (置信度: 0.95)",
  "confidence": 0.95,
  "has_glasses": false
}
```

错误码: 400（文件格式/大小/内容/尺寸不合规）、500（处理异常）、503（服务器繁忙）

#### POST /api/process

执行单步处理操作。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session_id | string | 是 | 上传时返回的会话标识 |
| action | string | 是 | 操作类型（见下表） |
| bg_color | string | 否 | 背景颜色，默认"蓝底"，可选: 蓝底/白底/红底 |
| size | string | 否 | 证件照尺寸，默认"一寸"，可选: 一寸/二寸/小二寸 |

支持的 action:

| action | 说明 | 额外参数 |
|--------|------|----------|
| replace_background | 替换背景 | bg_color |
| remove_glasses | 消除眼镜 | - |
| enhance | 画质增强 | - |
| crop | 裁剪证件照 | size |
| auto | 一键处理（眼镜消除→增强→背景→裁剪） | bg_color, size |
| reset | 重置为原图 | - |

成功响应:
```json
{
  "session_id": "a1b2c3d4",
  "preview": "base64...",
  "log": "已替换背景为蓝底"
}
```

#### POST /api/export

导出证件照文件。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session_id | string | 是 | 会话标识 |
| format | string | 否 | 导出格式，默认"jpg"，可选: jpg/png |

成功响应: 文件流（`Content-Disposition: attachment`）

#### POST /api/detect

获取人脸检测可视化结果（标注人脸框和关键点）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| session_id | string | 是 | 会话标识 |

成功响应:
```json
{
  "session_id": "a1b2c3d4",
  "preview": "base64...",
  "confidence": 0.95,
  "has_glasses": false,
  "log": "处理日志"
}
```

#### GET /api/history

获取当前用户的操作历史（需认证）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 否 | 查询类型: all(全部操作)/sessions(会话列表)/stats(统计信息)，默认 all |
| limit | int | 否 | 返回条数，默认 50，最大 200 |
| offset | int | 否 | 偏移量，默认 0 |

成功响应 (type=all):
```json
{
  "history": [
    {"sid": "a1b2c3d4", "action": "upload", "params": "photo.jpg", "status": "success", "created_at": "2025-01-01 12:00:00", "filename": "photo.jpg"},
    {"sid": "a1b2c3d4", "action": "replace_background", "params": "蓝底", "status": "success", "created_at": "2025-01-01 12:01:00", "filename": "photo.jpg"}
  ]
}
```

成功响应 (type=sessions):
```json
{
  "sessions": [
    {"sid": "a1b2c3d4", "filename": "photo.jpg", "has_face": 1, "confidence": 0.95, "has_glasses": 0, "created_at": "...", "updated_at": "..."}
  ]
}
```

成功响应 (type=stats):
```json
{
  "stats": {"session_count": 5, "history_count": 23, "export_count": 3}
}
```

#### GET /api/history/:sid

获取指定会话的操作历史（需认证）。

成功响应:
```json
{
  "sid": "a1b2c3d4",
  "history": [
    {"action": "upload", "params": "photo.jpg", "status": "success", "created_at": "..."},
    {"action": "enhance", "params": null, "status": "success", "created_at": "..."}
  ]
}
```

### 眼镜消除效果说明

本系统的眼镜消除功能严格依赖 OpenCV 算法库实现，采用以下技术方案：

1. **镜框检测**：在 MediaPipe 关键点定位的眼镜区域内，通过亮度阈值（深色像素检测）、Canny 边缘检测、局部对比度分析三种特征组合，精准定位镜框线条像素
2. **分轮修复**：使用 OpenCV Inpainting（Telea 算法）对镜框像素进行多轮迭代修复——核心像素 → 边缘过渡 → 残留清理
3. **融合过渡**：高斯模糊渐变掩码实现修复区域与原图的自然过渡

**效果局限性：**

OpenCV 的 Inpainting 算法（`cv2.inpaint`）本质上是基于偏微分方程（PDE）的图像修复方法，其原理是从缺损区域边界向内扩散周围像素的颜色和纹理信息。该算法适用于修复小面积划痕、水印等简单缺损，但对于眼镜消除这类场景存在以下固有限制：

- **无法重建被遮挡内容**：镜框下方的皮肤纹理、眉毛走向、眼部细节等信息在原图中已被完全遮挡，PDE 扩散只能用周围像素"填充"，无法凭空生成合理的面部结构
- **粗框眼镜效果有限**：镜框越粗，需要修复的面积越大，扩散距离越远，修复结果越不自然，容易出现模糊、色块不均匀等问题
- **镜片反光和阴影难以处理**：眼镜镜片产生的反光、阴影会改变眼部区域的光照分布，简单的像素扩散无法还原正确的光照

如需达到商业级的眼镜消除效果，通常需要基于深度学习的生成式模型（如 GAN、Diffusion Model），这些模型能够"理解"人脸结构并生成被遮挡区域的合理内容，但已超出 OpenCV 传统算法库的能力范围。
