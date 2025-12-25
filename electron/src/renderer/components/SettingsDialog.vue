<template>
  <div v-if="visible" class="dialog-overlay" @click.self="close">
    <div class="dialog-container">
      <div class="dialog-header">
        <h2>设置</h2>
        <button class="close-btn" @click="close">✕</button>
      </div>
      
      <div class="dialog-content">
        <!-- 选项卡 -->
        <div class="tabs">
          <button 
            :class="['tab', { active: activeTab === 'wifi' }]" 
            @click="activeTab = 'wifi'"
          >
            WiFi 设备管理
          </button>
          <button 
            :class="['tab', { active: activeTab === 'ai' }]" 
            @click="activeTab = 'ai'"
          >
            AI 配置
          </button>
        </div>

        <!-- WiFi 设备管理 -->
        <div v-show="activeTab === 'wifi'" class="tab-content">
          <div class="form-section">
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
                class="primary-button"
                :disabled="isWifiConnecting || isWifiDisconnecting || !wifiForm.ip"
              >
                {{ isWifiConnecting ? '连接中...' : '连接设备' }}
              </button>
              <button
                @click="disconnectWifiDevice"
                class="danger-button"
                :disabled="isWifiConnecting || isWifiDisconnecting || !wifiForm.ip"
              >
                {{ isWifiDisconnecting ? '断开中...' : '断开设备' }}
              </button>
            </div>
          </div>
        </div>

        <!-- AI 配置 -->
        <div v-show="activeTab === 'ai'" class="tab-content">
          <div class="form-section">
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
            <div class="form-actions">
              <button @click="saveAIConfig" class="primary-button" :disabled="isSaving">
                {{ isSaving ? '保存中...' : '保存配置' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import {
  setApiBaseUrl,
  initAI,
  connectWifiDevice as apiConnectWifiDevice,
  disconnectWifiDevice as apiDisconnectWifiDevice,
  type AIConfig,
} from '../utils/api'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'device-changed'): void
}>()

const activeTab = ref<'wifi' | 'ai'>('wifi')
const isSaving = ref(false)

// WiFi 设备管理
const wifiForm = ref({
  ip: '',
  port: 5555,
})
const isWifiConnecting = ref(false)
const isWifiDisconnecting = ref(false)

// AI 配置
const aiConfig = ref<AIConfig>({
  base_url: '',
  api_key: '',
  model_name: 'autoglm-phone-9b',
  lang: 'cn',
  max_steps: 100,
})

// 初始化
onMounted(async () => {
  if (window.electronAPI) {
    const port = await window.electronAPI.getPythonPort()
    if (port) {
      setApiBaseUrl(`http://127.0.0.1:${port}`)
    }
  }
  await loadAIConfig()
  await loadWifiConfig()
})

// 加载 AI 配置
const loadAIConfig = async () => {
  try {
    // 优先使用 Electron API 读取配置
    if (window.electronAPI) {
      const saved = await window.electronAPI.getConfig('aiConfig')
      if (saved) {
        aiConfig.value = { ...aiConfig.value, ...saved }
        return
      }
    }
    // 回退到 localStorage（兼容旧数据）
    const localSaved = localStorage.getItem('aiConfig')
    if (localSaved) {
      aiConfig.value = { ...aiConfig.value, ...JSON.parse(localSaved) }
      // 迁移到 Electron 配置
      if (window.electronAPI) {
        await window.electronAPI.setConfig('aiConfig', aiConfig.value)
        localStorage.removeItem('aiConfig')
      }
    }
  } catch (error) {
    console.error('加载 AI 配置失败:', error)
  }
}

// 加载 WiFi 配置
const loadWifiConfig = async () => {
  try {
    // 优先使用 Electron API 读取配置
    if (window.electronAPI) {
      const saved = await window.electronAPI.getConfig('wifiConfig')
      if (saved) {
        wifiForm.value = { ...wifiForm.value, ...saved }
        return
      }
    }
    // 回退到 localStorage（兼容旧数据）
    const localSaved = localStorage.getItem('wifiConfig')
    if (localSaved) {
      wifiForm.value = { ...wifiForm.value, ...JSON.parse(localSaved) }
      // 迁移到 Electron 配置
      if (window.electronAPI) {
        await window.electronAPI.setConfig('wifiConfig', wifiForm.value)
        localStorage.removeItem('wifiConfig')
      }
    }
  } catch (error) {
    console.error('加载 WiFi 配置失败:', error)
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
      // 将响应式对象转换为纯对象
      const plainConfig = JSON.parse(JSON.stringify(aiConfig.value))
      
      // 使用 Electron API 保存配置
      if (window.electronAPI) {
        const saved = await window.electronAPI.setConfig('aiConfig', plainConfig)
        if (saved) {
          alert('配置保存成功')
        } else {
          alert('配置初始化成功，但保存到本地失败')
        }
      } else {
        // 回退到 localStorage
        localStorage.setItem('aiConfig', JSON.stringify(plainConfig))
        alert('配置保存成功')
      }
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

// 连接 WiFi 设备
const connectWifiDevice = async () => {
  if (!wifiForm.value.ip) {
    alert('请输入 IP 地址')
    return
  }

  isWifiConnecting.value = true
  try {
    // 将响应式对象转换为纯对象
    const plainConfig = JSON.parse(JSON.stringify(wifiForm.value))
    
    // 保存 WiFi 配置
    if (window.electronAPI) {
      await window.electronAPI.setConfig('wifiConfig', plainConfig)
    } else {
      localStorage.setItem('wifiConfig', JSON.stringify(plainConfig))
    }
    
    const result = await apiConnectWifiDevice(wifiForm.value.ip, wifiForm.value.port)
    if (result.success) {
      alert(result.message || '连接成功')
      emit('device-changed')
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
      emit('device-changed')
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

const close = () => {
  emit('close')
}
</script>

<style scoped>
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog-container {
  background-color: #1e1e1e;
  border-radius: 12px;
  width: 480px;
  max-height: 80vh;
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  border: 1px solid #333;
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #333;
}

.dialog-header h2 {
  font-size: 18px;
  font-weight: 600;
  color: #e0e0e0;
  margin: 0;
}

.dialog-header .close-btn {
  background: none;
  border: none;
  color: #888;
  font-size: 18px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
}

.dialog-header .close-btn:hover {
  background-color: #333;
  color: #fff;
}

.dialog-content {
  padding: 0;
}

.tabs {
  display: flex;
  border-bottom: 1px solid #333;
}

.tab {
  flex: 1;
  padding: 12px 16px;
  background: none;
  border: none;
  color: #888;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  border-bottom: 2px solid transparent;
}

.tab:hover {
  color: #e0e0e0;
  background-color: #252525;
}

.tab.active {
  color: #4a9eff;
  border-bottom-color: #4a9eff;
}

.tab-content {
  padding: 20px;
  max-height: 400px;
  overflow-y: auto;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-item label {
  font-size: 13px;
  color: #888;
}

.form-item input,
.form-item select {
  padding: 10px 12px;
  background-color: #2a2a2a;
  border: 1px solid #3a3a3a;
  border-radius: 6px;
  color: #e0e0e0;
  font-size: 14px;
}

.form-item input:focus,
.form-item select:focus {
  outline: none;
  border-color: #4a9eff;
}

.form-actions {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}

.primary-button {
  flex: 1;
  padding: 12px;
  background-color: #4a9eff;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background-color 0.2s;
}

.primary-button:hover:not(:disabled) {
  background-color: #5aaeff;
}

.primary-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.danger-button {
  flex: 1;
  padding: 12px;
  background-color: #d32f2f;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background-color 0.2s;
}

.danger-button:hover:not(:disabled) {
  background-color: #c62828;
}

.danger-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
