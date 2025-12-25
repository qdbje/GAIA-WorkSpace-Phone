/**
 * API 客户端工具类
 * 统一管理后端 API 调用
 */

let apiBaseUrl = 'http://127.0.0.1:18080'

/**
 * 设置 API 基础 URL
 */
export function setApiBaseUrl(url: string) {
  apiBaseUrl = url
}

/**
 * 获取 API 基础 URL
 */
export function getApiBaseUrl(): string {
  return apiBaseUrl
}

/**
 * 获取 WebSocket URL
 */
export function getWebSocketUrl(path: string): string {
  const url = new URL(apiBaseUrl)
  return `ws://${url.hostname}:${url.port}${path}`
}

/**
 * 通用 API 请求
 */
async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${apiBaseUrl}${endpoint}`
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: response.statusText }))
    throw new Error(error.error || `HTTP ${response.status}`)
  }

  return response.json()
}

// ==================== ADB 连接管理 API ====================

export interface DeviceInfo {
  serial: string
  model: string
  connection_type: string
  status: string
  ip_address?: string
}

export interface DeviceDetailInfo extends DeviceInfo {
  brand: string
  android_version: string
  sdk_version: string
  screen_width: number
  screen_height: number
}

/**
 * 获取设备列表
 */
export async function listDevices(): Promise<DeviceInfo[]> {
  const response = await request<{ devices: DeviceInfo[] }>('/api/devices')
  return response.devices
}

/**
 * 连接设备
 */
export async function connectDevice(
  deviceId?: string,
  connectionType: string = 'usb'
): Promise<{ success: boolean; device?: DeviceDetailInfo; error?: string }> {
  const params = new URLSearchParams()
  if (deviceId) params.append('device_id', deviceId)
  params.append('connection_type', connectionType)

  try {
    const response = await request<{ success: boolean; device?: DeviceDetailInfo }>(
      `/api/connect?${params.toString()}`,
      { method: 'POST' }
    )
    return response
  } catch (error) {
    return { success: false, error: String(error) }
  }
}

/**
 * 断开设备连接
 */
export async function disconnectDevice(): Promise<{ success: boolean }> {
  return request('/api/disconnect', { method: 'POST' })
}

/**
 * 通过 Wi-Fi 连接设备
 */
export async function connectWifiDevice(
  ip: string,
  port: number = 5555
): Promise<{ success: boolean; message?: string; error?: string }> {
  try {
    const params = new URLSearchParams()
    params.append('ip', ip)
    params.append('port', String(port))
    return await request(`/api/wifi/connect?${params.toString()}`, { method: 'POST' })
  } catch (error) {
    return { success: false, error: String(error) }
  }
}

/**
 * 断开 Wi-Fi 设备连接
 */
export async function disconnectWifiDevice(
  ip: string,
  port: number = 5555
): Promise<{ success: boolean; message?: string; error?: string }> {
  try {
    const params = new URLSearchParams()
    params.append('ip', ip)
    params.append('port', String(port))
    return await request(`/api/wifi/disconnect?${params.toString()}`, { method: 'POST' })
  } catch (error) {
    return { success: false, error: String(error) }
  }
}

/**
 * 获取当前设备信息
 */
export async function getDeviceInfo(): Promise<DeviceDetailInfo | null> {
  try {
    const response = await request<{ device: DeviceDetailInfo }>('/api/device/info')
    return response.device
  } catch {
    return null
  }
}

/**
 * 获取健康状态
 */
export async function healthCheck(): Promise<{
  status: string
  adb_connected: boolean
}> {
  return request('/api/health')
}

// ==================== 视频流 API ====================

/**
 * 创建视频流 WebSocket 连接
 */
export function createVideoStreamWebSocket(): WebSocket {
  return new WebSocket(getWebSocketUrl('/api/video/stream'))
}

// ==================== AI 任务执行 API ====================

export interface AIConfig {
  base_url: string
  api_key: string
  model_name?: string
  device_id?: string
  lang?: string
  max_steps?: number
}

/**
 * 初始化 AI 核心模块
 */
export async function initAI(config: AIConfig): Promise<{ success: boolean; error?: string }> {
  const params = new URLSearchParams()
  params.append('base_url', config.base_url)
  params.append('api_key', config.api_key)
  params.append('model_name', config.model_name || 'autoglm-phone-9b')
  if (config.device_id) params.append('device_id', config.device_id)
  params.append('lang', config.lang || 'cn')
  if (config.max_steps) params.append('max_steps', String(config.max_steps))

  try {
    return await request(`/api/ai/init?${params.toString()}`, { method: 'POST' })
  } catch (error) {
    return { success: false, error: String(error) }
  }
}

/**
 * 执行 AI 任务（同步）
 */
export async function chatTask(task: string): Promise<{ success: boolean; result?: string; error?: string }> {
  try {
    const params = new URLSearchParams()
    params.append('task', task)
    return await request(`/api/ai/chat?${params.toString()}`, { method: 'POST' })
  } catch (error) {
    return { success: false, error: String(error) }
  }
}

/**
 * 创建 AI 任务流式 WebSocket 连接
 */
export function createAITaskStreamWebSocket(): WebSocket {
  return new WebSocket(getWebSocketUrl('/api/ai/chat/stream'))
}

/**
 * 重置 AI 状态
 */
export async function resetAI(): Promise<{ success: boolean }> {
  return request('/api/ai/reset', { method: 'POST' })
}

/**
 * 获取 AI 状态
 */
export async function getAIStatus(): Promise<{
  initialized: boolean
  step_count: number
  max_steps: number
  device_id?: string
  lang?: string
}> {
  return request('/api/ai/status')
}

// ==================== 手动控制 API ====================

/**
 * 手动点击操作
 */
export async function manualTap(x: number, y: number): Promise<{ success: boolean; error?: string }> {
  try {
    const params = new URLSearchParams()
    params.append('x', String(x))
    params.append('y', String(y))
    return await request(`/api/control/tap?${params.toString()}`, { method: 'POST' })
  } catch (error) {
    return { success: false, error: String(error) }
  }
}

/**
 * 手动滑动操作
 */
export async function manualSwipe(
  startX: number,
  startY: number,
  endX: number,
  endY: number,
  durationMs: number = 300
): Promise<{ success: boolean; error?: string }> {
  try {
    const params = new URLSearchParams()
    params.append('start_x', String(startX))
    params.append('start_y', String(startY))
    params.append('end_x', String(endX))
    params.append('end_y', String(endY))
    params.append('duration_ms', String(durationMs))
    return await request(`/api/control/swipe?${params.toString()}`, { method: 'POST' })
  } catch (error) {
    return { success: false, error: String(error) }
  }
}

/**
 * 手动返回操作
 */
export async function manualBack(): Promise<{ success: boolean; error?: string }> {
  try {
    return await request('/api/control/back', { method: 'POST' })
  } catch (error) {
    return { success: false, error: String(error) }
  }
}

/**
 * 手动主页操作
 */
export async function manualHome(): Promise<{ success: boolean; error?: string }> {
  try {
    return await request('/api/control/home', { method: 'POST' })
  } catch (error) {
    return { success: false, error: String(error) }
  }
}

/**
 * 手动多任务操作
 */
export async function manualRecent(): Promise<{ success: boolean; error?: string }> {
  try {
    return await request('/api/control/recent', { method: 'POST' })
  } catch (error) {
    return { success: false, error: String(error) }
  }
}

/**
 * 获取设备截图
 */
export async function getScreenshot(): Promise<{
  base64: string
  width: number
  height: number
} | null> {
  try {
    const response = await request<{
      base64: string
      width: number
      height: number
    }>('/api/screenshot')
    return response
  } catch {
    return null
  }
}


