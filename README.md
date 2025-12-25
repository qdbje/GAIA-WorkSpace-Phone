# GAIA-WorkSpace-Phone

AI 驱动的 Android 设备自动化桌面应用

## 项目概述

GAIA-WorkSpace-Phone 是一款运行在 PC/Mac 上的桌面软件，通过 ADB 连接安卓手机，利用多模态大模型作为"大脑"，通过视觉识别手机屏幕，自动规划任务路径，并模拟人类手指操作，实现"一句话操控手机"的智能体验。

## 技术架构

- **前端**: Electron + Vue.js 3
- **后端**: Python + FastAPI
- **核心引擎**: phone_agent (基于 Open-AutoGLM)
- **视频流**: Scrcpy
- **ADB 管理**: adbutils

## 项目结构

```
GAIA-WorkSpace-Phone/
├── phone_agent/          # 核心自动化引擎（来自 Open-AutoGLM）
├── python-service/       # Python 后端服务
│   ├── main.py          # FastAPI 主服务器
│   ├── adb_manager.py   # ADB 连接管理
│   ├── video_stream.py  # Scrcpy 视频流处理
│   └── ai_core.py       # AI 核心模块
├── electron/            # Electron 前端应用
│   ├── main/           # 主进程
│   ├── renderer/       # 渲染进程 (Vue.js)
│   └── preload/        # Preload 脚本
├── requirements.txt     # Python 依赖
└── README.md
```

## 开发环境设置

### 1. Python 后端

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 运行后端服务
cd python-service
python main.py
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

## 使用说明

### 连接设备

1. 确保 Android 设备已开启 USB 调试
2. 通过 USB 连接设备到电脑
3. 在应用中点击"连接设备"按钮

### 执行任务

1. 在左侧输入框输入自然语言任务，例如：

   - "打开微信"
   - "发送消息给张三"
   - "截图并保存"

2. 点击"发送"按钮，AI 将自动执行任务

### 配置 AI 模型

1. 点击右侧"配置 AI 模型"按钮
2. 输入模型服务地址、API Key 和模型名称
3. 保存配置

## 功能特性

- ✅ USB 和 Wi-Fi 连接支持
- ✅ 实时视频流显示
- ✅ AI 任务自动执行
- ✅ 流式执行进度反馈
- ✅ 手动控制支持
- ✅ 任务日志记录

## 开发路线图

- [ ] Phase 1: 基础架构搭建 ✅
- [ ] Phase 2: 核心功能实现 🔄
- [ ] Phase 3: 稳定性优化
- [ ] Phase 4: 高级功能

## 许可证

MIT

## 致谢

本项目在自动化决策与多模态理解能力上，使用并受益于清华大学 KEG 实验室与智谱 AI 开源的 Auto-GLM / Open-AutoGLM 项目，在此对其出色的研究与开源工作表示诚挚感谢。

## 参考资源

- [Open-AutoGLM](https://github.com/THUDM/Open-AutoGLM) - 核心自动化引擎参考
- [Scrcpy](https://github.com/Genymobile/scrcpy) - 视频流技术
- [FastAPI](https://fastapi.tiangolo.com/) - Python Web 框架
- [Electron](https://www.electronjs.org/) - 桌面应用框架
