# GAIA-WorkSpace-Phone macOS 一体化打包流程

目标：  
生成一个 **macOS 安装包（.dmg）**，应用内置：

- Python 后端（PyInstaller 打包为单文件）
- scrcpy-server.jar
- adb 可执行文件

�� 户安装后 **无需再单独安装 Python / adb / scrcpy**。

---

## 目录

- [开发者打包流程](#开发者打包流程)
  - [1. 前置环境](#1-前置环境)
  - [2. 资源文件准备](#2-资源文件准备只需做一次)
  - [3. Python 后端服务打包](#3-python-后端服务打包pyinstaller)
  - [4. Electron 集成](#4-将-python-可执行集成进-electron)
  - [5. 打包 dmg](#5-electron-前端打包-dmg)
  - [6. 打包后验证](#6-打包后验证)
  - [7. 快速重新打包](#7-每次重新打包时的最小步骤速查版)
  - [8. 常见问题排查](#常见问题排查)
- [用户安装指南](#用户安装指南)
  - [安装步骤](#安装步骤)
  - [解决"已损坏"提示](#解决已损坏无法打开的提示)
  - [使用要求](#使用要求)

---

# 开发者打包流程

---

## 1. 前置环境

在开发机（mac）上需要：

- Python 3.8 / 3.9（兼容项目依赖和 scrcpy）
- Node.js（建议 18+）
- adb / Android 平台工具（用于准备内置 adb）
- 已安装 Python 依赖：

```bash
cd /Users/ls/dev/gui-agent/GAIA-WorkSpace-Phone
pip install -r requirements.txt
pip install pyinstaller
```

---

## 2. 资源文件准备（只需做一次）

### 2.1 scrcpy-server.jar 位置

将 `scrcpy-server.jar` 放到项目根的 `resources/` 下：

```bash
cd /Users/ls/dev/gui-agent/GAIA-WorkSpace-Phone

mkdir -p resources
cp /你的路径/scrcpy-server.jar resources/scrcpy-server.jar
```

目录结构示例：

```text
GAIA-WorkSpace-Phone/
  resources/
    scrcpy-server.jar
  python-service/
  electron/
  ...
```

### 2.2 内置 adb 位置

1. 找到当前系统 adb 的路径：

```bash
which adb
# 假设输出：/opt/homebrew/bin/adb
```

2. 复制到项目资源目录：

```bash
cd /Users/ls/dev/gui-agent/GAIA-WorkSpace-Phone

mkdir -p resources/adb/mac
cp /opt/homebrew/bin/adb resources/adb/mac/adb
chmod +x resources/adb/mac/adb
```

目录结构示例：

```text
GAIA-WorkSpace-Phone/
  resources/
    scrcpy-server.jar
    adb/
      mac/
        adb
```

---

## 3. Python 后端服务打包（PyInstaller）

### 3.1 清理旧产物

```bash
cd /Users/ls/dev/gui-agent/GAIA-WorkSpace-Phone/python-service

rm -rf build dist python-service.spec
```

### 3.2 打包命令

```bash
cd /Users/ls/dev/gui-agent/GAIA-WorkSpace-Phone/python-service

pyinstaller \
  --name python-service \
  --onefile \
  --paths . \
  --paths .. \
  --hidden-import adb_manager \
  --hidden-import ai_core \
  --hidden-import video_stream \
  --add-data "../resources/scrcpy-server.jar:resources" \
  --add-data "../resources/adb/mac/adb:resources/adb/mac" \
  main.py
```

打包完成后会生成：

```text
python-service/dist/python-service
```

### 3.3 本地验证 Python 可执行

```bash
cd /Users/ls/dev/gui-agent/GAIA-WorkSpace-Phone/python-service
./dist/python-service
```

观察日志，确认：

- 启动时输出 `PORT=xxxxx`（FastAPI 启动成功）
- 连接设备 / 开启视频流时不报「未找到 scrcpy-server.jar」或「adb: command not found」

若此处不正常，先修完再进行后续步骤。

---

## 4. 将 Python 可执行集成进 Electron

### 4.1 拷贝可执行文件到 Electron 工程

```bash
cd /Users/ls/dev/gui-agent/GAIA-WorkSpace-Phone

mkdir -p electron/python-service
cp python-service/dist/python-service electron/python-service/python-service
```

### 4.2 Electron 打包配置要点（已修改好的逻辑）

**electron/package.json 关键部分：**

```json
{
  "main": "out/main/index.js",
  "scripts": {
    "dev": "electron-vite dev",
    "build": "electron-vite build",
    "preview": "electron-vite preview",
    "dist": "electron-vite build && electron-builder"
  },
  "build": {
    "appId": "com.gaia.workspace.phone",
    "productName": "GAIA-WorkSpace-Phone",
    "directories": {
      "output": "release"
    },
    "files": ["out/**/*", "resources/**/*"],
    "extraResources": [
      {
        "from": "python-service",
        "to": "python-service"
      }
    ],
    "mac": {
      "category": "public.app-category.utilities",
      "target": "dmg"
    }
  }
}
```

含义：

- `files`：把 Electron 构建后的 `out/**/*` 打进 app
- `extraResources`：
  - 将 `electron/python-service` 目录复制到打包后的 `Contents/Resources/python-service/`
  - 里面包含 `python-service` 可执行

### 4.3 Electron 主进程启动 Python 的逻辑（关键片段）

**electron/src/main/index.ts：**

```typescript
// 开发环境检测
const isDev = process.env.NODE_ENV === "development" || !app.isPackaged;

function startPythonService(): Promise<number> {
  return new Promise((resolve, reject) => {
    let pythonScript: string;
    let pythonExecutable: string;

    if (isDev) {
      console.log("开发环境：使用系统 Python");
      pythonExecutable = "python3";
      pythonScript = join(__dirname, "../../../python-service/main.py");
    } else {
      console.log("生产环境：使用打包的 Python 可执行文件");
      pythonExecutable = join(
        process.resourcesPath,
        "python-service",
        "python-service"
      );
      pythonScript = "";
    }

    console.log(`启动 Python 服务: ${pythonExecutable} ${pythonScript}`);

    const args = pythonScript ? [pythonScript, "0"] : ["0"]; // 0 表示随机端口
    pythonService = spawn(pythonExecutable, args, {
      cwd: isDev ? join(__dirname, "../..") : process.resourcesPath,
      stdio: ["ignore", "pipe", "pipe"],
    });

    // 监听 stdout 解析 PORT=xxxx，省略其余代码...
  });
}
```

---

## 5. Electron 前端打包 dmg

### 5.1 安装依赖（首次或依赖变化时）

```bash
cd /Users/ls/dev/gui-agent/GAIA-WorkSpace-Phone/electron

npm install
```

### 5.2 构建并打包

```bash
cd /Users/ls/dev/gui-agent/GAIA-WorkSpace-Phone/electron

npm run dist
```

完成后，在：

```bash
electron/release/
```

可以看到：

- `GAIA-WorkSpace-Phone-1.0.0.dmg`
- `mac-arm64/GAIA-WorkSpace-Phone.app/`

---

## 6. 打包后验证

### 6.1 用终端启动 .app 看完整日志（推荐）

```bash
/Applications/GAIA-WorkSpace-Phone.app/Contents/MacOS/GAIA-WorkSpace-Phone
```

确认日志中：

- 出现 `生产环境：使用打包的 Python 可执行文件`
- Python 输出 `PORT=xxxxx`
- `ADBManager` 日志中有「使用 ADB 路径: ...」之类的提示
- 连接设备 / 视频流 / AI 调用正常

### 6.2 用户正常使用

- 正常安装 `.dmg`
- 双击 `GAIA-WorkSpace-Phone` 启动即可，无需额外安装 Python / adb / scrcpy

---

## 7. 每次重新打包时的最小步骤（速查版）

以后如果只是代码更新，要重新出一个新的 mac 安装包，按下面最小路径即可：

### 步骤 1：更新 Python 服务并重新打包

```bash
cd /Users/ls/dev/gui-agent/GAIA-WorkSpace-Phone/python-service

rm -rf build dist python-service.spec

pyinstaller \
  --name python-service \
  --onefile \
  --paths . \
  --paths .. \
  --hidden-import adb_manager \
  --hidden-import ai_core \
  --hidden-import video_stream \
  --add-data "../resources/scrcpy-server.jar:resources" \
  --add-data "../resources/adb/mac/adb:resources/adb/mac" \
  main.py
```

### 步骤 2：覆盖 Electron 内部的 python-service

```bash
cd /Users/ls/dev/gui-agent/GAIA-WorkSpace-Phone

cp python-service/dist/python-service electron/python-service/python-service
```

### 步骤 3：打包 Electron

```bash
cd electron

npm run dist
```

### 步骤 4：验证和发布

在 `electron/release/` 里找到新的 `.dmg`，发给用户或自己安装测试即可。

---

## 常见问题排查

### Q1：打包后双击启动失败，但终端启动正常

**原因：** macOS GUI 应用环境变量与终端不同，可能是 PATH 问题。

**解决方案：**

- 确保 adb 已通过 `--add-data` 打包进 Python 可执行
- 检查 `adb_manager.py` 中的 `_detect_adb_path` 逻辑是否正确

### Q2：Python 服务启动失败，提示找不到 scrcpy-server.jar

**原因：** PyInstaller 打包时资源文件未正确包含。

**解决方案：**

- 确认 `resources/scrcpy-server.jar` 存在
- 检查 PyInstaller 命令中的 `--add-data` 参数是否正确
- 验证 `video_stream.py` 中的 `_get_resource_path` 逻辑

### Q3：adb 命令执行失败

**原因：** adb 可执行文件权限不足或路径错误。

**解决方案：**

```bash
chmod +x resources/adb/mac/adb
```

确保 `adb_manager.py` 中的 PATH 更新逻辑正确执行。

---

## 附录：关键文件路径

- Python 服务入口：`python-service/main.py`
- ADB 管理器：`python-service/adb_manager.py`
- 视频流管理：`python-service/video_stream.py`
- Electron 主进程：`electron/src/main/index.ts`
- 打包配置：`electron/package.json`
- 资源目录：`resources/`

---

# 用户安装指南

> 此部分适用于接收到 `.dmg` 安装包的用户。

---

## 安装步骤

### 1. 下载安装包

获取 `GAIA-WorkSpace-Phone-x.x.x.dmg` 文件。

### 2. 打开 DMG 文件

双击 `.dmg` 文件，会自动挂载并打开一个窗口。

### 3. 安装应用

将 `GAIA-WorkSpace-Phone.app` 拖拽到 `Applications` 文件夹。

### 4. 启动应用

从「启动台」或「应用程序」文件夹中找到 `GAIA-WorkSpace-Phone`，双击启动。

---

## 解决“已损坏，无法打开”的提示

如果您在启动应用时看到下面的错误提示：

> **“GAIA-WorkSpace-Phone” 已损坏，无法打开。您应该将它移到废纸篓。**

**请放心，文件并没有损坏！** 这是 macOS 的安全机制（Gatekeeper）对未签名应用的保护措施。

请按以下任一方法解决：

### 方法 1：右键打开（推荐）

1. 在「应用程序」文件夹中找到 `GAIA-WorkSpace-Phone`
2. **按住 `Control` 键**，然后点击应用图标
3. 在弹出菜单中选择「**打开**」
4. 在新的对话框中点击「**打开**」按钮

✅ **第一次这样操作后，系统会记住您的选择，以后就能正常双击打开了。**

### 方法 2：移除隔离属性（如果方法 1 不生效）

1. 打开「终端」应用（在「启动台」或「应用程序 > 实用工具」中）

2. 执行以下命令：

```bash
# 进入应用程序目录
cd /Applications

# 移除隔离属性
sudo xattr -cr GAIA-WorkSpace-Phone.app
```

3. 输入您的 macOS 管理员密码（输入时不会显示，输入完按回车）

4. 再次尝试打开应用

### 方法 3：系统设置中允许（备用）

如果以上方法都不生效：

1. 打开「**系统偏好设置**」 > 「**隐私与安全性**」 > 「**通用**」
2. 找到被阻止的应用名称
3. 点击「**仍要打开**」或「**打开**」

---

## 使用要求

### 系统要求

- **操作系统**：macOS 10.15 或更高版本
- **架构**：Apple Silicon (M1/M2/M3) 或 Intel

### 设备要求

- Android 手机或平板（开启 USB 调试）
- USB 数据线（用于 USB 连接）
- 或与 Mac 处于同一 Wi-Fi 网络（用于无线连接）

### 首次启动准备

1. **开启 Android 设备的 USB 调试**

   - 进入「设置」 > 「关于手机」
   - 连续点击「版本号」7 次，启用开发者模式
   - 返回「设置」> 「开发者选项」
   - 开启「USB 调试」

2. **连接设备**

   - USB 连接：直接用数据线连接 Mac 和 Android 设备
   - Wi-Fi 连接：在应用设置中输入设备 IP 和端口

3. **首次连接时**
   - Android 设备会弹出“允许 USB 调试”的提示
   - 勾选“始终允许来自这台计算机的调试”
   - 点击“允许”

---

## 常见问题

### Q：应用无法识别设备

**解决方案：**

1. 检查 USB 调试是否开启
2. 重新插拔 USB 线
3. 在设备上重新授权 USB 调试
4. 尝试重启应用

### Q：视频流无法显示

**解决方案：**

1. 确认设备已正常连接
2. 检查设备屏幕是否处于亮屏状态
3. 尝试断开重连设备

### Q：应用启动后闪退

**解决方法：**

1. 用终端启动应用查看详细错误：

```bash
/Applications/GAIA-WorkSpace-Phone.app/Contents/MacOS/GAIA-WorkSpace-Phone
```

2. 将错误信息反馈给开发者

---

## 技术支持

如遇到其他问题，请联系开发者或查看项目文档。
