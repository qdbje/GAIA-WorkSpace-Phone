<template>
  <div class="app-wrapper">
    <!-- 自定义标题栏 -->
    <div class="title-bar">
      <div class="title-bar-drag-region">
        <div class="app-title">
          <span class="app-icon">📱</span>
          <span class="app-name">GAIA WorkSpace-Phone Agent</span>
        </div>
      </div>
      <div class="title-bar-actions">
        <button class="action-btn settings-btn" @click="showSettings = true" title="设置">
          <span>⚙️</span>
        </button>
      </div>
      <div class="window-controls">
        <button class="control-btn minimize-btn" @click="minimizeWindow" title="最小化">
          <span>─</span>
        </button>
        <button class="control-btn maximize-btn" @click="maximizeWindow" title="最大化">
          <span>□</span>
        </button>
        <button class="control-btn close-btn" @click="closeWindow" title="关闭">
          <span>✕</span>
        </button>
      </div>
    </div>

    <!-- 主内容区 -->
    <div class="app-container">
      <!-- 左侧栏：手机镜像区 -->
      <div class="sidebar-left">
        <VideoPanel ref="videoPanelRef" />
        
      </div>

      <!-- 中间栏：智能交互区 -->
      <div class="main-content">
        <ChatPanel />
      </div>
    </div>

    <!-- 设置弹窗 -->
    <SettingsDialog 
      :visible="showSettings" 
      @close="showSettings = false"
      @device-changed="onDeviceChanged"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import ChatPanel from './components/ChatPanel.vue'
import VideoPanel from './components/VideoPanel.vue'
import SettingsDialog from './components/SettingsDialog.vue'

const showSettings = ref(false)
const videoPanelRef = ref<InstanceType<typeof VideoPanel> | null>(null)

onMounted(async () => {
  // 获取 Python 服务端口
  if (window.electronAPI) {
    const port = await window.electronAPI.getPythonPort()
    console.log('Python 服务端口:', port)
  }
})

// 窗口控制函数
const minimizeWindow = () => {
  if (window.electronAPI) {
    window.electronAPI.windowMinimize()
  }
}

const maximizeWindow = () => {
  if (window.electronAPI) {
    window.electronAPI.windowMaximize()
  }
}

const closeWindow = () => {
  if (window.electronAPI) {
    window.electronAPI.windowClose()
  }
}

const onDeviceChanged = () => {
  // 通知 VideoPanel 刷新设备连接
  if (videoPanelRef.value) {
    videoPanelRef.value.checkDeviceConnection()
  }
}
</script>

<style scoped>
.app-wrapper {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #1a1a1a;
  overflow: hidden;
}

/* 自定义标题栏 */
.title-bar {
  height: 40px;
  background-color: #0f0f0f;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #2a2a2a;
  user-select: none;
}

.title-bar-drag-region {
  flex: 1;
  height: 100%;
  display: flex;
  align-items: center;
  -webkit-app-region: drag;
  padding-left: 16px;
}

.app-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #e0e0e0;
  font-size: 14px;
  font-weight: 500;
}

.app-icon {
  font-size: 18px;
}

.app-name {
  letter-spacing: 0.5px;
}

/* 窗口控制按钮 */
.window-controls {
  display: flex;
  height: 100%;
  -webkit-app-region: no-drag;
}

.control-btn {
  width: 50px;
  height: 100%;
  border: none;
  background-color: transparent;
  color: #b0b0b0;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s, color 0.2s;
}

.control-btn:hover {
  background-color: #2a2a2a;
  color: #ffffff;
}

.close-btn:hover {
  background-color: #e81123;
  color: #ffffff;
}

.minimize-btn span {
  margin-top: -8px;
  font-size: 18px;
}

.maximize-btn span {
  font-size: 14px;
}

.close-btn span {
  font-size: 16px;
}

/* 主内容区 */
.app-container {
  display: flex;
  flex: 1;
  width: 100%;
  height: calc(100vh - 40px);
  background-color: #1a1a1a;
}

.sidebar-left {
  width: 450px;
  min-width: 400px;
  border-right: 1px solid #2a2a2a;
  display: flex;
  flex-direction: column;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 标题栏操作按钮区域 */
.title-bar-actions {
  display: flex;
  align-items: center;
  height: 100%;
  -webkit-app-region: no-drag;
  padding-right: 8px;
}

.action-btn {
  width: 36px;
  height: 28px;
  border: none;
  background-color: transparent;
  color: #b0b0b0;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: background-color 0.2s, color 0.2s;
}

.action-btn:hover {
  background-color: #2a2a2a;
  color: #ffffff;
}

.settings-btn span {
  font-size: 18px;
}
</style>

