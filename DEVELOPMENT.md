# GAIA-WorkSpace-Phone 开发指南

## 项目结构

```
GAIA-WorkSpace-Phone/
├── phone_agent/          # 核心自动化引擎（来自 Open-AutoGLM）
│   ├── agent.py         # PhoneAgent 主类
│   ├── model/           # 模型客户端
│   ├── actions/         # 操作处理器
│   ├── adb/             # ADB 底层操作
│   └── config/          # 系统提示词配置
├── python-service/      # Python 后端服务
│   ├── main.py          # FastAPI 主服务器
│   ├── adb_manager.py   # ADB 连接管理
│   ├── video_stream.py  # Scrcpy 视频流处理
│   └── ai_core.py       # AI 核心模块
├── electron/            # Electron 前端应用
│   ├── src/
│   │   ├── main/        # 主进程
│   │   ├── renderer/     # 渲染进程 (Vue.js)
│   │   │   ├── components/
│   │   │   │   ├── ChatPanel.vue      # 聊天面板
│   │   │   │   ├── VideoPanel.vue     # 视频流面板
│   │   │   │   └── WorkspacePanel.vue # 工作区面板
│   │   │   └── utils/
│   │   │       └── api.ts             # API 客户端
│   │   └── preload/     # Preload 脚本
│   └── package.json
├── resources/           # 资源文件
│   ├── scrcpy-server.jar  # Scrcpy 服务器（需要手动添加）
│   └── adb              # ADB 二进制（可选，使用系统 ADB）
└── requirements.txt     # Python 依赖
```

## 开发环境设置

### 1. Python 后端

```bash
# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 运行后端服务（开发模式）
cd python-service
python main.py 0  # 0 表示随机端口
```

### 2. Electron 前端

```bash
cd electron

# 安装依赖
npm install

# 开发模式
npm run dev

# 构建
npm run build

# 打包
npm run dist
```

## 核心功能模块

### 1. ADB 连接管理 (`python-service/adb_manager.py`)

- **USB 连接**：自动检测设备，处理授权
- **Wi-Fi 连接**：支持 TCP/IP 和 Android 11+ 无线调试
- **设备监控**：自动检测设备插拔和状态变化
- **多设备支持**：管理多个设备连接

### 2. 视频流处理 (`python-service/video_stream.py`)

- **Scrcpy 集成**：启动 scrcpy-server，接收 H.264 视频流
- **WebSocket 转发**：将视频流通过 WebSocket 发送给前端
- **多客户端支持**：支持多个前端客户端同时连接

### 3. AI 核心模块 (`python-service/ai_core.py`)

- **PhoneAgent 集成**：封装 Open-AutoGLM 的 PhoneAgent
- **任务执行**：支持同步和流式执行
- **状态管理**：管理 AI 执行状态和上下文

### 4. 前端组件

#### ChatPanel.vue
- 聊天界面：发送任务给 AI
- 流式反馈：实时显示 AI 思考过程和操作
- 消息历史：保存对话记录

#### VideoPanel.vue
- 视频流显示：使用 WebCodecs API 解码 H.264 视频流
- 备选方案：如果 WebCodecs 不可用，使用截图模式
- 手动控制：点击画布直接操作设备
- AI 可视化：显示 AI 操作的可视化反馈

#### WorkspacePanel.vue
- 设备状态：显示设备信息（型号、Android 版本等）
- AI 配置：配置模型服务地址、API Key 等
- 任务历史：记录和查看历史任务

## API 接口

### ADB 连接管理

- `GET /api/devices` - 获取设备列表
- `POST /api/connect` - 连接设备
- `POST /api/disconnect` - 断开设备连接
- `GET /api/device/info` - 获取设备信息

### 视频流

- `WebSocket /api/video/stream` - 视频流 WebSocket 连接

### AI 任务执行

- `POST /api/ai/init` - 初始化 AI 核心模块
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

## 使用流程

### 1. 启动服务

```bash
# 终端 1：启动 Python 后端
cd python-service
python main.py 0

# 终端 2：启动 Electron 前端
cd electron
npm run dev
```

### 2. 连接设备

1. 确保 Android 设备已开启 USB 调试
2. 通过 USB 连接设备到电脑
3. 在应用中，右侧面板会显示设备信息
4. 如果设备未授权，手机会弹出授权提示，点击"允许"

### 3. 配置 AI 模型

1. 在右侧面板的"AI 配置"区域
2. 填写模型服务地址（如：`https://open.bigmodel.cn/api/paas/v4`）
3. 填写 API Key
4. 选择模型名称（如：`autoglm-phone-9b`）
5. 点击"保存配置"

### 4. 执行任务

1. 在左侧面板输入自然语言任务，例如：
   - "打开微信"
   - "发送消息给张三"
   - "截图并保存"
2. 点击"发送"按钮
3. AI 将自动执行任务，实时显示执行进度

### 5. 手动控制

1. 在中间面板的视频画面上直接点击
2. 点击位置会转换为设备坐标并执行点击操作
3. 显示点击反馈动画

## 视频流解码

### WebCodecs API（首选）

项目使用 WebCodecs API 进行 H.264 视频流解码，这是性能最优的方案。

**支持情况**：
- Chrome 94+
- Edge 94+
- Electron（基于 Chromium，通常支持）

### 截图模式（备选）

如果浏览器不支持 WebCodecs API，会自动切换到截图模式：
- 每 500ms 获取一次设备截图
- 在画布上显示截图
- 功能正常，但流畅度较低

## 资源文件

### scrcpy-server.jar

视频流功能需要 `scrcpy-server.jar` 文件，请参考 `resources/README.md` 获取文件。

**获取方式**：
1. 从 Scrcpy 官方发布页面下载
2. 从已安装的 scrcpy 提取
3. 从源码构建

### ADB 二进制

项目默认使用系统的 ADB（通过 `adbutils` 库）。如果需要使用内置 ADB：

1. 下载对应平台的 ADB 二进制
2. 放置到 `resources/` 目录
3. 修改 `python-service/adb_manager.py` 指定 ADB 路径

## 常见问题

### 1. 设备未检测到

- 检查 USB 调试是否开启
- 检查 USB 驱动是否安装（Windows）
- 尝试重新插拔 USB 线
- 运行 `adb devices` 查看设备状态

### 2. 视频流无法显示

- 检查 `scrcpy-server.jar` 是否存在
- 检查设备是否已连接
- 查看浏览器控制台错误信息
- 如果 WebCodecs 不支持，会自动切换到截图模式

### 3. AI 任务执行失败

- 检查 AI 配置是否正确（服务地址、API Key）
- 检查设备是否已连接
- 查看后端日志错误信息
- 确认模型服务是否可访问

### 4. Python 服务启动失败

- 检查 Python 版本（需要 3.10+）
- 检查依赖是否安装完整
- 检查端口是否被占用
- 查看错误日志

## 开发建议

### 1. 调试 Python 后端

```bash
# 直接运行，查看详细日志
cd python-service
python main.py 0
```

### 2. 调试 Electron 前端

```bash
# 开发模式会自动打开 DevTools
cd electron
npm run dev
```

### 3. 测试 API

可以使用 curl 或 Postman 测试 API：

```bash
# 获取设备列表
curl http://127.0.0.1:18080/api/devices

# 获取健康状态
curl http://127.0.0.1:18080/api/health
```

## 下一步开发

参考 `技术架构.md` 中的开发路线图：

- [ ] Phase 1: 基础架构搭建 ✅
- [ ] Phase 2: 核心功能实现 🔄
- [ ] Phase 3: 稳定性优化
- [ ] Phase 4: 高级功能

## 参考资源

- [Open-AutoGLM](https://github.com/THUDM/Open-AutoGLM) - 核心自动化引擎
- [Scrcpy](https://github.com/Genymobile/scrcpy) - 视频流技术
- [FastAPI](https://fastapi.tiangolo.com/) - Python Web 框架
- [Electron](https://www.electronjs.org/) - 桌面应用框架
- [WebCodecs API](https://www.w3.org/TR/webcodecs/) - 视频解码 API


