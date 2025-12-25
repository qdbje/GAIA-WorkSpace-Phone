# 资源文件说明

## scrcpy-server.jar

`scrcpy-server.jar` 是 Scrcpy 项目的服务器端组件，用于在 Android 设备上运行，提供视频流和控制功能。

### 获取方式

#### 方式一：从 Scrcpy 官方发布页面下载

1. 访问 Scrcpy GitHub 发布页面：https://github.com/Genymobile/scrcpy/releases
2. 下载最新版本的 `scrcpy-server-vX.X.X` 文件
3. 将文件重命名为 `scrcpy-server.jar`
4. 放置到 `resources/` 目录

#### 方式二：从已安装的 scrcpy 提取

如果你已经安装了 scrcpy（通过 Homebrew 或其他方式），可以找到 jar 文件：

**macOS (Homebrew):**
```bash
# 查找 scrcpy-server.jar
find /opt/homebrew -name "scrcpy-server*.jar" 2>/dev/null
# 或
find /usr/local -name "scrcpy-server*.jar" 2>/dev/null

# 复制到项目目录
cp /path/to/scrcpy-server.jar resources/
```

**Linux:**
```bash
# 通常在 /usr/share/scrcpy/ 目录
cp /usr/share/scrcpy/scrcpy-server.jar resources/
```

**Windows:**
```bash
# 通常在 scrcpy 安装目录
copy "C:\path\to\scrcpy\scrcpy-server.jar" resources\
```

#### 方式三：从源码构建

如果你有 Scrcpy 源码，可以构建：

```bash
git clone https://github.com/Genymobile/scrcpy.git
cd scrcpy
./install_release.sh  # 或按照官方构建说明
# 然后从构建输出中找到 scrcpy-server.jar
```

### 验证

放置文件后，验证文件是否存在：

```bash
ls -lh resources/scrcpy-server.jar
```

应该看到类似输出：
```
-rw-r--r--  1 user  staff   2.5M Dec 16 16:00 resources/scrcpy-server.jar
```

### 注意事项

1. **文件大小**：scrcpy-server.jar 通常约 2-3 MB
2. **版本兼容性**：建议使用较新版本（1.20+），以确保功能完整
3. **打包部署**：如果使用 PyInstaller 打包，确保将 `resources/` 目录包含在打包配置中

### 视频流功能

有了 `scrcpy-server.jar` 后，视频流功能才能正常工作。如果没有此文件：

- 服务仍可正常启动
- ADB 连接和设备控制功能正常
- AI 任务执行功能正常
- **但视频流功能不可用**

### 临时解决方案

如果暂时没有 `scrcpy-server.jar`，可以：

1. 使用截图功能替代视频流（通过 `/api/screenshot` 端点）
2. 手动操作设备，使用 AI 任务执行功能
3. 后续添加 `scrcpy-server.jar` 后，视频流功能会自动启用

