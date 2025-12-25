# AutoGLM-GUI 项目总结

## 项目概述

AutoGLM-GUI 是一个基于 Web 的图形界面，为 AutoGLM Phone Agent 提供现代化的用户交互体验。项目将 Open-AutoGLM 的核心自动化引擎封装为 Web 服务，通过浏览器界面实现 AI 驱动的 Android 设备自动化操作。

## 项目架构

### 技术栈

- **后端**: FastAPI (Python 3.10+)
- **前端**: React 19 + TanStack Router + Tailwind CSS 4
- **设备控制**: ADB (Android Debug Bridge)
- **视频流**: scrcpy (H.264 实时视频流)
- **模型服务**: OpenAI 兼容 API (调用 AutoGLM 模型)

### 目录结构

```
AutoGLM-GUI-main/
├── AutoGLM_GUI/          # Web GUI 后端服务
│   ├── server.py          # FastAPI 主服务器
│   ├── scrcpy_stream.py   # scrcpy 视频流处理
│   └── adb_plus/          # 扩展的 ADB 工具
├── phone_agent/           # ⭐ 来自 Open-AutoGLM 的核心模块
│   ├── agent.py           # PhoneAgent 主类
│   ├── model/             # 模型客户端
│   ├── actions/           # 操作处理器
│   ├── adb/               # ADB 底层操作
│   └── config/            # 系统提示词配置
├── frontend/              # React 前端应用
└── main.py                # 入口文件
```

## ⭐ 直接使用 Open-AutoGLM 服务的部分

### 1. `phone_agent/` 目录（核心自动化引擎）

这是**直接从 Open-AutoGLM 项目使用的核心模块**，包含以下关键组件：

#### 1.1 `phone_agent/agent.py` - PhoneAgent 类

**功能**: 主要的自动化编排器，负责整个任务执行流程

**关键方法**:
- `run(task: str) -> str`: 执行自然语言任务
- `step(task: str | None) -> StepResult`: 执行单步操作
- `_execute_step()`: 核心执行循环
  - 截图 → 调用模型 → 解析操作 → 执行操作 → 更新上下文

**使用位置**: 
```python
# AutoGLM_GUI/server.py
from phone_agent import PhoneAgent
agent = PhoneAgent(model_config=model_config, agent_config=agent_config)
result = agent.run(request.message)
```

#### 1.2 `phone_agent/model/client.py` - ModelClient 类

**功能**: 通过 OpenAI 兼容 API 调用 AutoGLM 模型服务

**关键组件**:
- `ModelConfig`: 模型配置（base_url, api_key, model_name 等）
- `ModelClient`: OpenAI 客户端封装
  - `request(messages)`: 发送请求到模型服务
  - `_parse_response()`: 解析模型返回的 thinking 和 action

**与 Open-AutoGLM 的关系**:
- **直接调用**: AutoGLM 模型服务（通过 OpenAI 兼容 API）
- **服务地址**: 可以是智谱 BigModel、ModelScope 或自建的 vLLM/SGLang 服务
- **模型名称**: `autoglm-phone-9b` 或 `ZhipuAI/AutoGLM-Phone-9B`

**使用位置**:
```python
# phone_agent/agent.py
self.model_client = ModelClient(self.model_config)
response = self.model_client.request(self._context)
```

#### 1.3 `phone_agent/actions/handler.py` - ActionHandler 类

**功能**: 执行模型输出的操作指令

**支持的操作**:
- `Launch`: 启动应用
- `Tap`: 点击操作
- `Type`/`Type_Name`: 文本输入
- `Swipe`: 滑动手势
- `Back`/`Home`: 导航操作
- `Long Press`/`Double Tap`: 高级手势
- `Wait`: 等待操作
- `Take_over`: 人工接管请求
- `finish`: 任务完成

**操作格式解析**:
- 解析模型返回的 `do(action=...)` 或 `finish(message=...)` 格式
- 将相对坐标（0-1000）转换为绝对像素坐标

**使用位置**:
```python
# phone_agent/agent.py
self.action_handler = ActionHandler(device_id=self.agent_config.device_id)
result = self.action_handler.execute(action, screenshot.width, screenshot.height)
```

#### 1.4 `phone_agent/adb/` - ADB 底层操作

**功能**: 提供 Android 设备的底层控制接口

**主要模块**:
- `connection.py`: 设备连接管理（USB/WiFi/远程）
- `device.py`: 设备信息获取（屏幕尺寸、当前应用）
- `input.py`: 触摸和键盘输入
- `screenshot.py`: 截图捕获

**使用位置**: 被 `ActionHandler` 和 `PhoneAgent` 内部调用

#### 1.5 `phone_agent/config/` - 系统提示词配置

**功能**: 定义 AI 模型的系统提示词和行为规则

**关键文件**:
- `prompts_zh.py`: 中文系统提示词（包含 18 条详细规则）
- `prompts_en.py`: 英文系统提示词
- `prompts.py`: 提示词加载逻辑

**提示词内容**: 定义了模型需要遵循的操作指令格式和执行规则

## 项目自己的部分（GUI 封装层）

### 2. `AutoGLM_GUI/server.py` - FastAPI 服务器

**功能**: 将 PhoneAgent 封装为 Web API

**主要 API 端点**:
- `POST /api/init`: 初始化 PhoneAgent（配置模型和代理参数）
- `POST /api/chat`: 发送任务并执行（同步）
- `POST /api/chat/stream`: 发送任务并实时推送执行进度（SSE）
- `GET /api/status`: 获取 Agent 状态
- `POST /api/reset`: 重置 Agent 状态
- `POST /api/screenshot`: 获取设备截图
- `POST /api/control/tap`: 手动点击操作
- `WebSocket /api/video/stream`: scrcpy 视频流

**关键集成点**:
```python
# 初始化 PhoneAgent
agent = PhoneAgent(
    model_config=ModelConfig(base_url=base_url, api_key=api_key, model_name=model_name),
    agent_config=AgentConfig(device_id=device_id, lang=lang)
)

# 执行任务
result = agent.run(request.message)
```

### 3. `AutoGLM_GUI/scrcpy_stream.py` - 视频流处理

**功能**: 管理 scrcpy 服务器生命周期和 H.264 视频流

**特点**:
- 启动 scrcpy-server 进程
- 处理 TCP socket 视频数据
- 缓存 SPS/PPS/IDR 帧用于新客户端连接
- 通过 WebSocket 传输 H.264 数据

### 4. `frontend/` - React 前端应用

**功能**: 提供用户交互界面

**主要功能**:
- 聊天界面：发送任务给 Agent
- 实时视频流：显示设备屏幕（基于 scrcpy）
- 手动控制：在视频画面上直接点击操作
- 配置管理：设置模型服务参数

**API 调用**: 通过 `frontend/src/api.ts` 调用后端 API

## 数据流和调用链

### 任务执行流程

```
用户输入任务
    ↓
前端 (React) → POST /api/chat/stream
    ↓
后端 (FastAPI) → PhoneAgent.run(task)
    ↓
PhoneAgent._execute_step():
    1. 截图 (phone_agent/adb/screenshot.py)
    2. 构建消息 (包含截图 base64)
    3. 调用模型 (phone_agent/model/client.py)
       ↓
       ModelClient.request() → OpenAI API → AutoGLM 模型服务
       ↓
       返回 thinking + action
    4. 解析操作 (phone_agent/actions/handler.py)
    5. 执行操作 (phone_agent/adb/input.py)
    6. 更新上下文
    ↓
SSE 推送执行进度 → 前端实时显示
    ↓
任务完成 → finish(message)
```

### 模型服务调用

```
ModelClient.request(messages)
    ↓
OpenAI Client (base_url, api_key, model_name)
    ↓
HTTP POST → AutoGLM 模型服务
    ↓
返回响应 (包含 <think> 和 <answer>)
    ↓
解析为 thinking 和 action
```

## 关键配置参数

### 模型服务配置

- **base_url**: AutoGLM 模型服务的 API 地址
  - 智谱 BigModel: `https://open.bigmodel.cn/api/paas/v4`
  - ModelScope: `https://api-inference.modelscope.cn/v1`
  - 自建服务: `http://localhost:8000/v1` (vLLM/SGLang)
  
- **model_name**: 模型名称
  - `autoglm-phone` (智谱)
  - `ZhipuAI/AutoGLM-Phone-9B` (ModelScope)
  - `autoglm-phone-9b` (自建服务)

- **api_key**: API 密钥（如果服务需要）

### Agent 配置

- **device_id**: ADB 设备 ID（可选，默认使用第一个设备）
- **max_steps**: 最大执行步数（默认 100）
- **lang**: 语言（"cn" 或 "en"）
- **system_prompt**: 自定义系统提示词（可选）

## 为桌面程序开发提供的参考

### 1. 核心依赖关系

**必须保留的 Open-AutoGLM 模块**:
- `phone_agent/agent.py` - PhoneAgent 类（核心编排器）
- `phone_agent/model/client.py` - ModelClient 类（模型调用）
- `phone_agent/actions/handler.py` - ActionHandler 类（操作执行）
- `phone_agent/adb/` - ADB 操作模块
- `phone_agent/config/` - 系统提示词配置

**可以替换的部分**:
- `AutoGLM_GUI/server.py` - FastAPI 服务器（可替换为桌面应用的业务逻辑层）
- `frontend/` - React 前端（可替换为桌面 UI 框架，如 Electron、Tauri、PyQt 等）

### 2. 最小化集成方案

如果开发桌面程序，最小化需要集成的代码：

```python
from phone_agent import PhoneAgent
from phone_agent.model import ModelConfig
from phone_agent.agent import AgentConfig

# 1. 配置模型服务（指向 AutoGLM）
model_config = ModelConfig(
    base_url="https://open.bigmodel.cn/api/paas/v4",
    api_key="your-api-key",
    model_name="autoglm-phone"
)

# 2. 配置 Agent
agent_config = AgentConfig(
    device_id=None,  # 使用第一个设备
    max_steps=100,
    lang="cn"
)

# 3. 创建 PhoneAgent 实例
agent = PhoneAgent(
    model_config=model_config,
    agent_config=agent_config
)

# 4. 执行任务
result = agent.run("打开微信，发送消息给张三")
print(result)
```

### 3. 流式执行（实时反馈）

如果需要实时显示执行进度：

```python
# 使用 step() 方法逐步执行
step_result = agent.step("打开微信")
while not step_result.finished:
    print(f"Step {agent.step_count}: {step_result.action}")
    print(f"Thinking: {step_result.thinking}")
    
    if agent.step_count >= agent.agent_config.max_steps:
        break
    
    step_result = agent.step()

print(f"完成: {step_result.message}")
agent.reset()  # 重置状态
```

### 4. 手动控制集成

如果需要手动控制设备（类似 GUI 中的点击功能）：

```python
from phone_agent.adb import tap, get_screenshot

# 获取截图
screenshot = get_screenshot(device_id=None)

# 手动点击
tap(x=500, y=1000, device_id=None)
```

### 5. 视频流集成

如果需要显示设备屏幕（类似 GUI 中的 scrcpy 功能）：

- 可以使用 `AutoGLM_GUI/scrcpy_stream.py` 中的 `ScrcpyStreamer` 类
- 或者直接使用 scrcpy 命令行工具
- 或者使用其他屏幕镜像方案

### 6. 关键注意事项

1. **模型服务依赖**: 必须确保可以访问 AutoGLM 模型服务（通过 OpenAI 兼容 API）
2. **ADB 要求**: 需要设备已开启 USB 调试，且 ADB 已安装并添加到 PATH
3. **系统提示词**: `phone_agent/config/prompts_zh.py` 中的提示词定义了模型的行为规则，如需自定义可修改
4. **操作格式**: 模型返回的操作格式为 `do(action=...)` 或 `finish(message=...)`，由 `ActionHandler` 解析执行
5. **坐标系统**: 模型使用相对坐标（0-1000），`ActionHandler` 会自动转换为设备实际像素坐标

## 总结

AutoGLM-GUI 项目将 Open-AutoGLM 的核心自动化引擎（`phone_agent/` 目录）封装为 Web 服务，通过 FastAPI 提供 REST API 和 WebSocket，前端通过 React 提供用户界面。

**核心价值**:
- `phone_agent/` 模块提供了完整的 Android 自动化能力
- 通过 OpenAI 兼容 API 调用 AutoGLM 模型服务
- 模型理解屏幕内容并生成操作指令
- ActionHandler 执行操作，PhoneAgent 管理整个任务流程

**桌面程序开发建议**:
- 保留 `phone_agent/` 模块作为核心引擎
- 替换 Web 服务层为桌面应用的业务逻辑层
- 替换 React 前端为桌面 UI 框架
- 保持与 PhoneAgent 的接口不变，确保兼容性

