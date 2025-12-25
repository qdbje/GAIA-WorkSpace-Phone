# Python 后端服务

GAIA-WorkSpace-Phone 的 Python 后端服务，基于 FastAPI 构建。

## 功能模块

### 1. ADB 连接管理 (`adb_manager.py`)

- USB 和 Wi-Fi 连接支持
- 设备状态监控
- 自动重连机制
- 多设备支持

### 2. 视频流处理 (`video_stream.py`)

- Scrcpy Server 生命周期管理
- H.264 视频流转发
- WebSocket 多客户端支持

### 3. AI 核心模块 (`ai_core.py`)

- PhoneAgent 集成
- 任务执行（同步和流式）
- 状态管理

## API 端点

### 设备管理

- `GET /api/devices` - 获取设备列表
- `POST /api/connect` - 连接设备
- `POST /api/disconnect` - 断开设备
- `GET /api/device/info` - 获取设备信息

### 视频流

- `WebSocket /api/video/stream` - 视频流 WebSocket

### AI 任务

- `POST /api/ai/init` - 初始化 AI
- `POST /api/ai/chat` - 执行任务（同步）
- `WebSocket /api/ai/chat/stream` - 执行任务（流式）
- `POST /api/ai/reset` - 重置 AI 状态
- `GET /api/ai/status` - 获取 AI 状态

### 手动控制

- `POST /api/control/tap` - 点击操作
- `POST /api/control/swipe` - 滑动操作
- `POST /api/control/back` - 返回操作
- `POST /api/control/home` - 主页操作
- `GET /api/screenshot` - 获取截图

## 运行

```bash
# 安装依赖
pip install -r ../requirements.txt

# 运行服务（端口 0 表示自动分配）
python main.py 0

# 或指定端口
python main.py 18080
```

## 端口管理

服务启动时会绑定到指定端口（或随机端口）。如果端口为 0，系统会自动分配一个可用端口，并将端口号打印到 stdout，格式为：`PORT=18080`

Electron 主进程会读取这个端口号，并传递给渲染进程。

