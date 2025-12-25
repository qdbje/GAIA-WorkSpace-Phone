import { app, shell, BrowserWindow, ipcMain } from 'electron'
import { join } from 'path'
import { spawn, ChildProcess } from 'child_process'
import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'fs'

// 开发环境检测
const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged

let mainWindow: BrowserWindow | null = null
let pythonService: ChildProcess | null = null
let pythonServicePort: number | null = null
let isQuitting = false // 标记是否正在退出

/**
 * 启动 Python 后端服务
 */
function startPythonService(): Promise<number> {
  return new Promise((resolve, reject) => {
    // 获取 Python 服务路径
    let pythonScript: string
    let pythonExecutable: string

    if (isDev) {
      // 开发环境：使用系统 Python
      console.log("开发环境：使用系统 Python")
      pythonExecutable = 'python3'
      console.log(__dirname)
      pythonScript = join(__dirname, '../../../python-service/main.py')
    } else {
      // 生产环境：使用打包的 Python 可执行文件
      console.log("生产环境：使用打包的 Python 可执行文件")
      pythonExecutable = join(process.resourcesPath, 'python-service', 'python-service')
      pythonScript = ''
    }

    console.log(`启动 Python 服务: ${pythonExecutable} ${pythonScript}`)

    // 启动 Python 进程
    const args = pythonScript ? [pythonScript, '0'] : ['0'] // 0 表示随机端口
    pythonService = spawn(pythonExecutable, args, {
      cwd: isDev ? join(__dirname, '../..') : process.resourcesPath,
      stdio: ['ignore', 'pipe', 'pipe'],
    })

    let output = ''
    let errorOutput = ''

    // 监听 stdout，解析端口号
    pythonService.stdout?.on('data', (data: Buffer) => {
      const text = data.toString()
      output += text
      console.log(`[Python] ${text}`)

      // 解析端口号：PORT=18080
      const portMatch = text.match(/PORT=(\d+)/)
      if (portMatch) {
        pythonServicePort = parseInt(portMatch[1], 10)
        console.log(`Python 服务已启动，端口: ${pythonServicePort}`)
        resolve(pythonServicePort)
      }
    })

    // 监听 stderr
    pythonService.stderr?.on('data', (data: Buffer) => {
      const text = data.toString()
      errorOutput += text
      console.error(`[Python Error] ${text}`)
    })

    // 监听进程退出
    pythonService.on('exit', (code) => {
      console.log(`Python 服务已退出，代码: ${code}`)
      pythonService = null
      pythonServicePort = null

      // 如果不是正常退出且不是正在关闭应用，尝试重启
      if (code !== 0 && code !== null && !isQuitting) {
        console.log('Python 服务异常退出，尝试重启...')
        setTimeout(() => {
          if (!isQuitting) {
            startPythonService().catch((err) => {
              console.error('重启 Python 服务失败:', err)
            })
          }
        }, 3000)
      }
    })

    // 超时处理
    setTimeout(() => {
      if (pythonServicePort === null) {
        reject(new Error('Python 服务启动超时'))
      }
    }, 30000) // 30 秒超时
  })
}

/**
 * 创建主窗口
 */
function createWindow() {
  // 根据环境确定 preload 脚本路径
  // preload 应该构建为 CommonJS 格式（.cjs 或 .js），而不是 ESM（.mjs）
  let preloadPath: string

  const cjsPath = join(__dirname, '../preload/index.cjs')
  const jsPath = join(__dirname, '../preload/index.js')
  const mjsPath = join(__dirname, '../preload/index.mjs')
  
  // 优先使用 .cjs（CommonJS），然后 .js，最后 .mjs（向后兼容）
  if (existsSync(cjsPath)) {
    preloadPath = cjsPath
  } else if (existsSync(jsPath)) {
    preloadPath = jsPath
  } else if (existsSync(mjsPath)) {
    preloadPath = mjsPath
    console.warn('使用 .mjs 文件，建议重新构建为 CommonJS 格式')
  } else {
    preloadPath = cjsPath
    console.error(`Preload 文件不存在: ${cjsPath}, ${jsPath} 或 ${mjsPath}`)
  }

  console.log(`使用 preload 路径: ${preloadPath}`)

  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 1000,
    minHeight: 600,
    frame: false,  // 无边框窗口
    backgroundColor: '#1a1a1a',
    webPreferences: {
      preload: preloadPath,
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  // 在加载页面之前设置 CSP 策略，允许连接到 localhost
  // 这需要在加载任何内容之前设置
  const cspHeader = [
    "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob:; " +
    "connect-src 'self' http://localhost:* http://127.0.0.1:* ws://localhost:* ws://127.0.0.1:*; " +
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; " +
    "style-src 'self' 'unsafe-inline';"
  ]

  mainWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': cspHeader,
      },
    })
  })

  // 加载页面
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }

  // 打开外部链接
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

// 应用启动
app.whenReady().then(async () => {
  // 启动 Python 服务
  try {
    const port = await startPythonService()
    console.log(`Python 服务已启动，端口: ${port}`)
    
    // 通知前端端口已就绪
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('python-port-ready', port)
    }
  } catch (error) {
    console.error('启动 Python 服务失败:', error)
  }

  // 创建窗口
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

// 应用退出
app.on('window-all-closed', () => {
  isQuitting = true
  
  // 停止 Python 服务
  if (pythonService) {
    console.log('正在终止 Python 服务...')
    pythonService.kill('SIGTERM') // 使用 SIGTERM 优雅终止
    pythonService = null
    pythonServicePort = null
  }

  // macOS 上也直接退出（不保留在 Dock）
  app.quit()
})

app.on('before-quit', () => {
  isQuitting = true
  
  // 停止 Python 服务
  if (pythonService) {
    console.log('应用退出前终止 Python 服务...')
    pythonService.kill('SIGTERM')
    pythonService = null
    pythonServicePort = null
  }
})

// IPC 处理：获取 Python 服务端口
ipcMain.handle('get-python-port', () => {
  return pythonServicePort || 0
})

// IPC 处理：重启 Python 服务
ipcMain.handle('restart-python-service', async () => {
  if (pythonService) {
    pythonService.kill()
    pythonService = null
    pythonServicePort = null
  }
  try {
    const port = await startPythonService()
    return { success: true, port }
  } catch (error) {
    return { success: false, error: String(error) }
  }
})

// IPC 处理：窗口控制
ipcMain.handle('window-minimize', () => {
  if (mainWindow) mainWindow.minimize()
})

ipcMain.handle('window-maximize', () => {
  if (mainWindow) {
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize()
    } else {
      mainWindow.maximize()
    }
  }
})

ipcMain.handle('window-close', () => {
  if (mainWindow) {
    isQuitting = true
    
    // 先停止 Python 服务
    if (pythonService) {
      console.log('窗口关闭，终止 Python 服务...')
      pythonService.kill('SIGTERM')
      pythonService = null
      pythonServicePort = null
    }
    
    // 关闭窗口
    mainWindow.close()
    
    // 确保应用退出
    setTimeout(() => {
      app.quit()
    }, 500)
  }
})

// ==================== 配置持久化 ====================

/**
 * 获取配置文件路径
 */
function getConfigPath(): string {
  const userDataPath = app.getPath('userData')
  return join(userDataPath, 'config.json')
}

/**
 * 读取配置
 */
function loadConfig(): Record<string, any> {
  try {
    const configPath = getConfigPath()
    if (existsSync(configPath)) {
      const content = readFileSync(configPath, 'utf-8')
      return JSON.parse(content)
    }
  } catch (error) {
    console.error('读取配置文件失败:', error)
  }
  return {}
}

/**
 * 保存配置
 */
function saveConfig(config: Record<string, any>): boolean {
  try {
    const configPath = getConfigPath()
    const userDataPath = app.getPath('userData')
    
    // 确保目录存在
    if (!existsSync(userDataPath)) {
      mkdirSync(userDataPath, { recursive: true })
    }
    
    writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf-8')
    console.log('配置已保存到:', configPath)
    return true
  } catch (error) {
    console.error('保存配置文件失败:', error)
    return false
  }
}

// IPC 处理：获取配置
ipcMain.handle('get-config', (_event, key: string) => {
  const config = loadConfig()
  return key ? config[key] : config
})

// IPC 处理：保存配置
ipcMain.handle('set-config', (_event, key: string, value: any) => {
  const config = loadConfig()
  config[key] = value
  return saveConfig(config)
})

// IPC 处理：删除配置
ipcMain.handle('delete-config', (_event, key: string) => {
  const config = loadConfig()
  delete config[key]
  return saveConfig(config)
})