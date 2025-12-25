import { contextBridge, ipcRenderer } from 'electron'

/**
 * 暴露安全的 API 给渲染进程
 */
contextBridge.exposeInMainWorld('electronAPI', {
  /**
   * 获取 Python 服务端口
   */
  getPythonPort: () => ipcRenderer.invoke('get-python-port'),

  /**
   * 重启 Python 服务
   */
  restartPythonService: () => ipcRenderer.invoke('restart-python-service'),

  /**
   * 窗口控制
   */
  windowMinimize: () => ipcRenderer.invoke('window-minimize'),
  windowMaximize: () => ipcRenderer.invoke('window-maximize'),
  windowClose: () => ipcRenderer.invoke('window-close'),

  /**
   * 配置持久化
   */
  getConfig: (key: string) => ipcRenderer.invoke('get-config', key),
  setConfig: (key: string, value: any) => ipcRenderer.invoke('set-config', key, value),
  deleteConfig: (key: string) => ipcRenderer.invoke('delete-config', key),
})

// 类型声明
declare global {
  interface Window {
    electronAPI: {
      getPythonPort: () => Promise<number>
      restartPythonService: () => Promise<{ success: boolean; port?: number; error?: string }>
      windowMinimize: () => Promise<void>
      windowMaximize: () => Promise<void>
      windowClose: () => Promise<void>
      getConfig: (key: string) => Promise<any>
      setConfig: (key: string, value: any) => Promise<boolean>
      deleteConfig: (key: string) => Promise<boolean>
    }
  }
}

