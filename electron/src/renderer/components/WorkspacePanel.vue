<template>
  <div class="workspace-panel">
    <!-- 设备状态 -->
    <div class="panel-section">
      <div class="section-header">
        <h3>设备状态</h3>
        <button @click="refreshDeviceInfo" class="refresh-button" :disabled="isRefreshing">
          {{ isRefreshing ? '刷新中...' : '刷新' }}
        </button>
      </div>
      <div v-if="deviceInfo" class="device-info">
        <div class="info-item">
          <span class="label">型号:</span>
          <span class="value">{{ deviceInfo.model }}</span>
        </div>
        <div class="info-item">
          <span class="label">品牌:</span>
          <span class="value">{{ deviceInfo.brand }}</span>
        </div>
        <div class="info-item">
          <span class="label">Android:</span>
          <span class="value">{{ deviceInfo.android_version }}</span>
        </div>
        <div class="info-item">
          <span class="label">连接方式:</span>
          <span class="value">{{ deviceInfo.connection_type === 'usb' ? 'USB' : 'Wi-Fi' }}</span>
        </div>
        <div class="info-item">
          <span class="label">屏幕:</span>
          <span class="value">{{ deviceInfo.screen_width }}x{{ deviceInfo.screen_height }}</span>
        </div>
        <div class="info-item">
          <span class="label">状态:</span>
          <span class="value status" :class="deviceInfo.status">{{ deviceInfo.status }}</span>
        </div>
      </div>
      <div v-else class="no-device">
        <p>未连接设备</p>
      </div>
    </div>

    <!-- WiFi 设备管理 -->
    <div class="panel-section">
      <div class="section-header">
        <h3>WiFi 设备管理</h3>
      </div>
      <div class="wifi-device-form">
        <div class="form-item">
          <label>IP 地址:</label>
          <input
            v-model="wifiForm.ip"
            type="text"
            placeholder="192.168.1.100"
            :disabled="isWifiConnecting || isWifiDisconnecting"
          />
        </div>
        <div class="form-item">
          <label>端口:</label>
          <input
            v-model.number="wifiForm.port"
            type="number"
            min="1"
            max="65535"
            placeholder="5555"
            :disabled="isWifiConnecting || isWifiDisconnecting"
          />
        </div>
        <div class="form-actions">
          <button
            @click="connectWifiDevice"
            class="connect-button"
            :disabled="isWifiConnecting || isWifiDisconnecting || !wifiForm.ip"
          >
            {{ isWifiConnecting ? '连接中...' : '连接设备' }}
          </button>
          <button
            @click="disconnectWifiDevice"
            class="disconnect-button"
            :disabled="isWifiConnecting || isWifiDisconnecting || !wifiForm.ip"
          >
            {{ isWifiDisconnecting ? '断开中...' : '断开设备' }}
          </button>
        </div>
      </div>
    </div>

    <!-- AI 配置 -->
    <div class="panel-section">
      <div class="section-header">
        <h3>AI 配置</h3>
      </div>
      <div class="config-form">
        <div class="form-item">
          <label>模型服务地址:</label>
          <input v-model="aiConfig.base_url" type="text" placeholder="https://api.example.com/v1" />
        </div>
        <div class="form-item">
          <label>API Key:</label>
          <input v-model="aiConfig.api_key" type="password" placeholder="输入 API Key" />
        </div>
        <div class="form-item">
          <label>模型名称:</label>
          <input v-model="aiConfig.model_name" type="text" placeholder="autoglm-phone-9b" />
        </div>
        <div class="form-item">
          <label>语言:</label>
          <select v-model="aiConfig.lang">
            <option value="cn">中文</option>
            <option value="en">English</option>
          </select>
        </div>
        <div class="form-item">
          <label>最大步数:</label>
          <input v-model.number="aiConfig.max_steps" type="number" min="1" max="200" />
        </div>
        <button @click="saveAIConfig" class="save-button" :disabled="isSaving">
          {{ isSaving ? '保存中...' : '保存配置' }}
        </button>
      </div>
    </div>

    <!-- 任务历史 -->
    <div class="panel-section">
      <div class="section-header">
        <h3>任务历史</h3>
        <button @click="clearHistory" class="clear-button">清空</button>
      </div>
      <div class="task-history">
        <div
          v-for="(task, index) in taskHistory"
          :key="index"
          class="task-item"
          @click="selectTask(task)"
        >
          <div class="task-time">{{ formatTime(task.timestamp) }}</div>
          <div class="task-content">{{ task.content }}</div>
          <div class="task-status" :class="task.status">{{ getStatusText(task.status) }}</div>
        </div>
        <div v-if="taskHistory.length === 0" class="no-history">
          <p>暂无任务历史</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  getDeviceInfo,
  setApiBaseUrl,
  initAI,
  getAIStatus,
  connectWifiDevice as apiConnectWifiDevice,
  disconnectWifiDevice as apiDisconnectWifiDevice,
  type DeviceDetailInfo,
  type AIConfig,
} from '../utils/api'

const deviceInfo = ref<DeviceDetailInfo | null>(null)
const isRefreshing = ref(false)
const isSaving = ref(false)

// WiFi 设备管理
const wifiForm = ref({
  ip: '',
  port: 5555,
})
const isWifiConnecting = ref(false)
const isWifiDisconnecting = ref(false)

const aiConfig = ref<AIConfig>({
  base_url: '',
  api_key: '',
  model_name: 'autoglm-phone-9b',
  lang: 'cn',
  max_steps: 100,
})

interface TaskHistoryItem {
  timestamp: number
  content: string
  status: 'success' | 'failed' | 'running'
}

const taskHistory = ref<TaskHistoryItem[]>([])

// 初始化
onMounted(async () => {
  // 获取 Python 服务端口
  if (window.electronAPI) {
    const port = await window.electronAPI.getPythonPort()
    if (port) {
      setApiBaseUrl(`http://127.0.0.1:${port}`)
    }
  }

  // 加载设备信息
  await refreshDeviceInfo()

  // 加载 AI 配置（从 localStorage）
  loadAIConfig()

  // 加载任务历史（从 localStorage）
  loadTaskHistory()
})

// 刷新设备信息
const refreshDeviceInfo = async () => {
  isRefreshing.value = true
  try {
    deviceInfo.value = await getDeviceInfo()
  } catch (error) {
    console.error('获取设备信息失败:', error)
  } finally {
    isRefreshing.value = false
  }
}

// 保存 AI 配置
const saveAIConfig = async () => {
  if (!aiConfig.value.base_url || !aiConfig.value.api_key) {
    alert('请填写模型服务地址和 API Key')
    return
  }

  isSaving.value = true
  try {
    const result = await initAI(aiConfig.value)
    if (result.success) {
      // 保存到 localStorage
      localStorage.setItem('aiConfig', JSON.stringify(aiConfig.value))
      alert('配置保存成功')
    } else {
      alert(`配置保存失败: ${result.error}`)
    }
  } catch (error) {
    console.error('保存 AI 配置失败:', error)
    alert('配置保存失败')
  } finally {
    isSaving.value = false
  }
}

// 加载 AI 配置
const loadAIConfig = () => {
  const saved = localStorage.getItem('aiConfig')
  if (saved) {
    try {
      aiConfig.value = { ...aiConfig.value, ...JSON.parse(saved) }
    } catch (error) {
      console.error('加载 AI 配置失败:', error)
    }
  }
}

// 加载任务历史
const loadTaskHistory = () => {
  const saved = localStorage.getItem('taskHistory')
  if (saved) {
    try {
      taskHistory.value = JSON.parse(saved)
    } catch (error) {
      console.error('加载任务历史失败:', error)
    }
  }
}

// 保存任务历史
const saveTaskHistory = () => {
  localStorage.setItem('taskHistory', JSON.stringify(taskHistory.value))
}

// 添加任务历史
function addTaskHistory(content: string, status: 'success' | 'failed' | 'running') {
  taskHistory.value.unshift({
    timestamp: Date.now(),
    content,
    status,
  })
  // 只保留最近 50 条
  if (taskHistory.value.length > 50) {
    taskHistory.value = taskHistory.value.slice(0, 50)
  }
  saveTaskHistory()
}

// 清空历史
const clearHistory = () => {
  if (confirm('确定要清空任务历史吗？')) {
    taskHistory.value = []
    saveTaskHistory()
  }
}

// 选择任务
const selectTask = (task: TaskHistoryItem) => {
  // TODO: 实现任务回放或重新执行
  console.log('选择任务:', task)
}

// 格式化时间
const formatTime = (timestamp: number): string => {
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// 获取状态文本
const getStatusText = (status: string): string => {
  const statusMap: Record<string, string> = {
    success: '成功',
    failed: '失败',
    running: '运行中',
  }
  return statusMap[status] || status
}

// 连接 WiFi 设备
const connectWifiDevice = async () => {
  if (!wifiForm.value.ip) {
    alert('请输入 IP 地址')
    return
  }

  isWifiConnecting.value = true
  try {
    const result = await apiConnectWifiDevice(wifiForm.value.ip, wifiForm.value.port)
    if (result.success) {
      alert(result.message || '连接成功')
      // 刷新设备信息
      await refreshDeviceInfo()
    } else {
      alert(`连接失败: ${result.error || '未知错误'}`)
    }
  } catch (error) {
    console.error('连接 WiFi 设备失败:', error)
    alert(`连接失败: ${error}`)
  } finally {
    isWifiConnecting.value = false
  }
}

// 断开 WiFi 设备
const disconnectWifiDevice = async () => {
  if (!wifiForm.value.ip) {
    alert('请输入 IP 地址')
    return
  }

  isWifiDisconnecting.value = true
  try {
    const result = await apiDisconnectWifiDevice(wifiForm.value.ip, wifiForm.value.port)
    if (result.success) {
      alert(result.message || '断开成功')
      // 刷新设备信息
      await refreshDeviceInfo()
    } else {
      alert(`断开失败: ${result.error || '未知错误'}`)
    }
  } catch (error) {
    console.error('断开 WiFi 设备失败:', error)
    alert(`断开失败: ${error}`)
  } finally {
    isWifiDisconnecting.value = false
  }
}

// 暴露方法供外部调用
defineExpose({
  addTaskHistory,
  refreshDeviceInfo,
})
</script>

<style scoped>
.workspace-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #1a1a1a;
  overflow-y: auto;
}

.panel-section {
  padding: 16px;
  border-bottom: 1px solid #2a2a2a;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: #e0e0e0;
}

.refresh-button,
.clear-button {
  padding: 4px 8px;
  background-color: #2a2a2a;
  color: #e0e0e0;
  border: 1px solid #3a3a3a;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.refresh-button:hover:not(:disabled),
.clear-button:hover {
  background-color: #3a3a3a;
}

.refresh-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.device-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}

.info-item .label {
  color: #888;
}

.info-item .value {
  color: #e0e0e0;
  font-weight: 500;
}

.info-item .value.status {
  text-transform: uppercase;
}

.info-item .value.status.device {
  color: #4caf50;
}

.info-item .value.status.offline {
  color: #f44336;
}

.no-device,
.no-history {
  text-align: center;
  color: #888;
  font-size: 13px;
  padding: 20px 0;
}

.config-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-item label {
  font-size: 12px;
  color: #888;
}

.form-item input,
.form-item select {
  padding: 8px;
  background-color: #2a2a2a;
  border: 1px solid #3a3a3a;
  border-radius: 4px;
  color: #e0e0e0;
  font-size: 13px;
}

.form-item input:focus,
.form-item select:focus {
  outline: none;
  border-color: #4a9eff;
}

.save-button {
  padding: 10px;
  background-color: #4a9eff;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  margin-top: 8px;
}

.save-button:hover:not(:disabled) {
  background-color: #5aaeff;
}

.save-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.wifi-device-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.connect-button {
  flex: 1;
  padding: 10px;
  background-color: #4caf50;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
}

.connect-button:hover:not(:disabled) {
  background-color: #45a049;
}

.disconnect-button {
  flex: 1;
  padding: 10px;
  background-color: #f44336;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
}

.disconnect-button:hover:not(:disabled) {
  background-color: #da190b;
}

.connect-button:disabled,
.disconnect-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.task-history {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.task-item {
  padding: 10px;
  background-color: #2a2a2a;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.task-item:hover {
  background-color: #3a3a3a;
}

.task-time {
  font-size: 11px;
  color: #888;
  margin-bottom: 4px;
}

.task-content {
  font-size: 13px;
  color: #e0e0e0;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-status {
  font-size: 11px;
  font-weight: 500;
}

.task-status.success {
  color: #4caf50;
}

.task-status.failed {
  color: #f44336;
}

.task-status.running {
  color: #ff9800;
}
</style>

