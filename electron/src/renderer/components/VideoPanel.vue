<template>
  <div class="video-panel">
    <div class="video-header">
      <h3>手机镜像</h3>
      <div class="video-controls">
        <div class="mirror-mode-toggle">
          <button
            class="mode-btn"
            :class="{ active: mirrorMode === 'video' }"
            @click="switchMirrorMode('video')"
          >
            视频
          </button>
          <button
            class="mode-btn"
            :class="{ active: mirrorMode === 'image' }"
            @click="switchMirrorMode('image')"
          >
            图片
          </button>
        </div>
       
        <span v-if="connectionStatus" class="status-indicator" :class="connectionStatus">
          {{ connectionStatusText }}
        </span>
        <!-- 设备状态按钮 -->
        <button 
          class="device-status-btn" 
          @click="showDeviceInfo = !showDeviceInfo"
          :title="deviceInfo ? `${deviceInfo.brand} ${deviceInfo.model}` : '设备信息'"
        >
          <span class="device-icon">📱</span>
          <span class="device-name">{{ deviceInfo ? deviceInfo.model : '未连接' }}</span>
        </button>
      </div>
    </div>
    
    <!-- 设备信息悬浮卡片 -->
    <div v-if="showDeviceInfo && deviceInfo" class="device-info-card">
      <div class="device-info-header">
        <span>设备信息</span>
        <button class="close-info-btn" @click="showDeviceInfo = false">✕</button>
      </div>
      <div class="device-info-content">
        <div class="info-row">
          <span class="label">型号:</span>
          <span class="value">{{ deviceInfo.model }}</span>
        </div>
        <div class="info-row">
          <span class="label">品牌:</span>
          <span class="value">{{ deviceInfo.brand }}</span>
        </div>
        <div class="info-row">
          <span class="label">Android:</span>
          <span class="value">{{ deviceInfo.android_version }}</span>
        </div>
        <div class="info-row">
          <span class="label">连接方式:</span>
          <span class="value">{{ deviceInfo.connection_type === 'usb' ? 'USB' : 'Wi-Fi' }}</span>
        </div>
        <div class="info-row">
          <span class="label">屏幕:</span>
          <span class="value">{{ deviceInfo.screen_width }}×{{ deviceInfo.screen_height }}</span>
        </div>
      </div>
    </div>

    <div class="video-container" ref="videoContainer">
      <!-- 手机边框容器 -->
      <div class="phone-frame">
        <!-- 手机顶部听筒/摄像头区域 -->
        <div class="phone-notch"></div>
        
        <!-- 手机屏幕区域 -->
        <div class="phone-screen">
          <canvas ref="videoCanvas" class="video-canvas"></canvas>
          <div v-if="!isConnected" class="no-device">
            <p>未连接设备</p>
            <p class="hint">请先连接 Android 设备</p>
          </div>
          <div v-else-if="!isStreaming && mirrorMode === 'video'" class="no-stream">
            <p>视频流未启动</p>
            <p class="hint">正在连接视频流...</p>
          </div>
          <!-- AI 操作可视化层 -->
          <div v-if="aiOverlay" class="ai-overlay">
            <div
              v-for="(overlay, index) in aiOverlays"
              :key="index"
              class="overlay-item"
              :style="overlay.style"
            >
              <span class="overlay-label">{{ overlay.label }}</span>
            </div>
          </div>
        </div>
        
        <!-- 手机底部导航栏 -->
        <div class="phone-navbar">
          <button class="nav-btn" @click="handleBack" title="返回">
            <span class="nav-icon back-icon">◀</span>
          </button>
          <button class="nav-btn" @click="handleHome" title="主页">
            <span class="nav-icon home-icon">○</span>
          </button>
          <button class="nav-btn" @click="handleRecent" title="多任务">
            <span class="nav-icon recent-icon">□</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import {
  getApiBaseUrl,
  setApiBaseUrl,
  createVideoStreamWebSocket,
  manualTap,
  manualBack,
  manualHome,
  manualRecent,
  getDeviceInfo,
  listDevices,
  connectDevice,
  type DeviceInfo,
  type DeviceDetailInfo,
} from '../utils/api'

const videoCanvas = ref<HTMLCanvasElement | null>(null)
const videoContainer = ref<HTMLElement | null>(null)
const isConnected = ref(false)
const isStreaming = ref(false)
const connectionStatus = ref<'connected' | 'disconnected' | 'connecting' | null>(null)
const connectionStatusText = ref('')
const isAIExecuting = ref(false)
const aiOverlay = ref(false)
const aiOverlays = ref<Array<{ style: any; label: string }>>([])
const showDeviceInfo = ref(false)
const deviceInfo = ref<DeviceDetailInfo | null>(null)
const mirrorMode = ref<'video' | 'image'>('video')

let videoWebSocket: WebSocket | null = null
let decoder: VideoDecoder | null = null
let canvasContext: CanvasRenderingContext2D | null = null
let scaleX = 1
let scaleY = 1

// 实际视频分辨率（初始给一个常见竖屏值，后续用首帧更新）
let videoWidth = 1080
let videoHeight = 1920

// H.264 相关状态
let hasKeyFrame = false
let configNalUnits: Uint8Array[] = []
let spsNal: Uint8Array | null = null
let ppsNal: Uint8Array | null = null
let decoderConfigured = false

// 统一重置解码器状态
const resetDecoderState = () => {
  try {
    if (decoder && decoder.state !== 'closed') {
      decoder.close()
    }
  } catch (e) {
    // 忽略关闭时的错误
  }
  decoder = null
  hasKeyFrame = false
  configNalUnits = []
  spsNal = null
  ppsNal = null
  decoderConfigured = false
}

// 重连视频流（解码错误恢复时使用）
const reconnectVideoStream = () => {
  console.log('解码错误，重新连接视频流...')
  
  // 关闭现有 WebSocket
  if (videoWebSocket) {
    try {
      videoWebSocket.close()
    } catch (e) {
      // ignore
    }
    videoWebSocket = null
  }
  
  // 重置解码器状态
  resetDecoderState()
  
  // 重新初始化解码器
  initVideoDecoder()
  
  // 延迟重连 WebSocket，让 scrcpy 重新发送完整的流
  setTimeout(() => {
    if (isConnected.value) {
      startVideoStream()
    }
  }, 500)
}

// 初始化 API 基础 URL
onMounted(async () => {
  if (window.electronAPI) {
    const port = await window.electronAPI.getPythonPort()
    if (port) {
      setApiBaseUrl(`http://127.0.0.1:${port}`)
    }
  }

  // 检查设备连接状态
  checkDeviceConnection()

  // 初始化视频解码器
  initVideoDecoder()

  // 监听窗口大小变化
  window.addEventListener('resize', resizeCanvas)
  resizeCanvas()
})

onUnmounted(() => {
  cleanup()
  window.removeEventListener('resize', resizeCanvas)
})

// 检查设备连接状态并自动连接
const checkDeviceConnection = async () => {
  try {
    // 先检查是否已连接
    const info = await getDeviceInfo()
    if (info) {
      // 已连接，直接启动视频流
      deviceInfo.value = info
      isConnected.value = true
      connectionStatus.value = 'connected'
      connectionStatusText.value = '已连接'
      startVideoStream()
      return
    }

    // 未连接，获取设备列表
    connectionStatus.value = 'connecting'
    connectionStatusText.value = '正在查找设备...'
    
    const devices = await listDevices()
    
    // 筛选出可用设备（状态为 "device"）
    const availableDevices = devices.filter(
      (device: DeviceInfo) => device.status === 'device'
    )

    if (availableDevices.length === 0) {
      // 没有可用设备
      isConnected.value = false
      connectionStatus.value = 'disconnected'
      connectionStatusText.value = '未找到可用设备'
      console.log('未找到可用设备，请确保设备已连接并启用 USB 调试')
      return
    }

    // 有可用设备，自动连接第一个设备
    // 如果只有一个设备，直接连接；如果有多个设备，也连接第一个（后续可以扩展为让用户选择）
    const targetDevice = availableDevices[0]
    connectionStatusText.value = `正在连接 ${targetDevice.model || targetDevice.serial}...`
    
    const result = await connectDevice(
      targetDevice.serial,
      targetDevice.connection_type
    )

    if (result.success && result.device) {
      deviceInfo.value = result.device as DeviceDetailInfo
      isConnected.value = true
      connectionStatus.value = 'connected'
      connectionStatusText.value = `已连接: ${result.device.model || result.device.serial}`
      startVideoStream()
    } else {
      isConnected.value = false
      connectionStatus.value = 'disconnected'
      connectionStatusText.value = result.error || '连接失败'
      console.error('连接设备失败:', result.error)
    }
  } catch (error) {
    console.error('检查设备连接失败:', error)
    isConnected.value = false
    connectionStatus.value = 'disconnected'
    connectionStatusText.value = '连接失败'
  }
}

// 初始化视频解码器（使用 WebCodecs API）
const initVideoDecoder = async () => {
  if (!videoCanvas.value) return

  canvasContext = videoCanvas.value.getContext('2d')
  if (!canvasContext) {
    console.error('无法获取 Canvas 上下文')
    return
  }

  // 检查 WebCodecs 支持
  if (!('VideoDecoder' in window)) {
    console.warn('浏览器不支持 WebCodecs API，将使用备选方案（截图模式）')
    // 备选方案：定期获取截图（仅在完全不支持 WebCodecs 时使用）
    startScreenshotMode()
    return
  }

  try {
    // 创建 VideoDecoder
    decoder = new VideoDecoder({
      output: (frame) => {
        if (canvasContext && videoCanvas.value) {
          const f: any = frame
          const codedW = f.codedWidth || f.displayWidth
          const codedH = f.codedHeight || f.displayHeight
          if (codedW && codedH) {
            // 首帧或分辨率变化时更新视频宽高并调整画布
            if (codedW !== videoWidth || codedH !== videoHeight) {
              videoWidth = codedW
              videoHeight = codedH
              resizeCanvas()
            }
          }

          const canvas = videoCanvas.value
          canvasContext.clearRect(0, 0, canvas.width, canvas.height)
          canvasContext.drawImage(frame, 0, 0, canvas.width, canvas.height)
          frame.close()
        } else {
          frame.close()
        }
      },
      error: (error) => {
        console.error('视频解码错误:', error)
        // 发生错误后，直接置空解码器（此时 decoder 已处于错误状态，无需调用 close）
        decoder = null
        decoderConfigured = false
        hasKeyFrame = false
        spsNal = null
        ppsNal = null

        // 异步重连视频流，让 scrcpy 重新发送 SPS/PPS + IDR
        setTimeout(() => {
          if (videoCanvas.value && canvasContext && isConnected.value) {
            reconnectVideoStream()
          }
        }, 100)
      },
    })

    // 每次初始化 / 重新初始化时重置关键帧状态
    hasKeyFrame = false
    configNalUnits = []
    spsNal = null
    ppsNal = null
    decoderConfigured = false

    // 不在这里 configure，等拿到 SPS / PPS 后再配置
  } catch (error) {
    console.error('初始化视频解码器失败:', error)
    // 仅重置状态，不自动降级到截图模式
    resetDecoderState()
  }
}

// 截图模式（备选方案）
let screenshotInterval: number | null = null
const startScreenshotMode = () => {
  if (screenshotInterval) return

  screenshotInterval = window.setInterval(async () => {
    if (mirrorMode.value !== 'image' || !isConnected.value || !canvasContext || !videoCanvas.value) return

    try {
      const { getScreenshot } = await import('../utils/api')
      const screenshot = await getScreenshot()
      if (screenshot) {
        if (screenshot.width && screenshot.height) {
          if (screenshot.width !== videoWidth || screenshot.height !== videoHeight) {
            videoWidth = screenshot.width
            videoHeight = screenshot.height
            resizeCanvas()
          }
        }
        const img = new Image()
        img.onload = () => {
          if (canvasContext && videoCanvas.value) {
            canvasContext.clearRect(0, 0, videoCanvas.value.width, videoCanvas.value.height)
            canvasContext.drawImage(img, 0, 0, videoCanvas.value.width, videoCanvas.value.height)
          }
        }
        img.src = `data:image/png;base64,${screenshot.base64}`
      }
    } catch (error) {
      console.error('获取截图失败:', error)
    }
  }, 500) // 每 500ms 更新一次
}

const stopScreenshotMode = () => {
  if (screenshotInterval) {
    clearInterval(screenshotInterval)
    screenshotInterval = null
  }
}

const configureDecoderIfNeeded = () => {
  if (!decoder || decoderConfigured || !spsNal || !ppsNal) {
    return
  }

  // 基本长度检查，避免异常/截断的 SPS 导致崩溃
  if (spsNal.length < 4) {
    console.warn('SPS NAL 长度异常，跳过本次配置', spsNal)
    spsNal = null
    return
  }

  try {
    // 从 SPS 里拿 profile/compat/level
    const profile = spsNal[1]
    const compat = spsNal[2]
    const level = spsNal[3]

    if (
      profile === undefined ||
      compat === undefined ||
      level === undefined
    ) {
      console.warn('SPS profile/compat/level 非法，跳过本次配置', spsNal)
      spsNal = null
      return
    }

    const toHex = (n: number) => n.toString(16).padStart(2, '0').toUpperCase()
    const codec = `avc1.${toHex(profile)}${toHex(compat)}${toHex(level)}`

    const spsLength = spsNal.length
    const ppsLength = ppsNal.length

    // 构造 AVCDecoderConfigurationRecord (avcC)
    const avcC = new Uint8Array(11 + spsLength + ppsLength)
    let offset = 0

    avcC[offset++] = 1 // configurationVersion
    avcC[offset++] = profile
    avcC[offset++] = compat
    avcC[offset++] = level
    avcC[offset++] = 0xff // 111111 + lengthSizeMinusOne(3 -> 4 字节长度)
    avcC[offset++] = 0xE1 // 111 + numOfSequenceParameterSets(1)

    // SPS
    avcC[offset++] = (spsLength >> 8) & 0xff
    avcC[offset++] = spsLength & 0xff
    avcC.set(spsNal, offset)
    offset += spsLength

    // PPS
    avcC[offset++] = 1 // numOfPictureParameterSets
    avcC[offset++] = (ppsLength >> 8) & 0xff
    avcC[offset++] = ppsLength & 0xff
    avcC.set(ppsNal, offset)

    decoder.configure({
      codec,
      description: avcC.buffer,
      optimizeForLatency: true,
    })
    decoderConfigured = true
    console.log('VideoDecoder 已根据 SPS/PPS 完成配置，codec =', codec)
  } catch (error) {
    console.error('配置 VideoDecoder 失败:', error)
  }
}

// 启动视频流
const startVideoStream = () => {
  if (videoWebSocket) {
    return // 已经连接
  }

  // 启动视频流前，确保截图模式已停止
  stopScreenshotMode()

  connectionStatus.value = 'connecting'
  connectionStatusText.value = '正在连接...'

  try {
    videoWebSocket = createVideoStreamWebSocket()

    videoWebSocket.onopen = () => {
      console.log('视频流 WebSocket 已连接')
      isStreaming.value = true
      connectionStatus.value = 'connected'
      connectionStatusText.value = '已连接'
    }

    videoWebSocket.onmessage = async (event) => {
      if (event.data instanceof Blob) {
        // 接收二进制 H.264 数据
        const buffer = await event.data.arrayBuffer()
        await processH264Data(buffer)
      } else if (event.data instanceof ArrayBuffer) {
        await processH264Data(event.data)
      }
    }

    videoWebSocket.onerror = (error) => {
      console.error('视频流 WebSocket 错误:', error)
      connectionStatus.value = 'disconnected'
      connectionStatusText.value = '连接错误'
      isStreaming.value = false
    }

    videoWebSocket.onclose = () => {
      console.log('视频流 WebSocket 已断开')
      videoWebSocket = null
      isStreaming.value = false

      if (mirrorMode.value === 'video') {
        connectionStatus.value = 'disconnected'
        connectionStatusText.value = '已断开'

        // 尝试重连
        if (isConnected.value) {
          setTimeout(() => {
            if (mirrorMode.value === 'video' && !videoWebSocket) {
              startVideoStream()
            }
          }, 3000)
        }
      }
    }
  } catch (error) {
    console.error('启动视频流失败:', error)
    connectionStatus.value = 'disconnected'
    connectionStatusText.value = '启动失败'
  }
}

const stopVideoStream = () => {
  if (videoWebSocket) {
    try {
      // 避免触发 onclose 中的自动重连逻辑
      videoWebSocket.onclose = null
      videoWebSocket.close()
    } catch (e) {
      // ignore
    }
    videoWebSocket = null
  }
  isStreaming.value = false
  resetDecoderState()
}

const switchMirrorMode = async (mode: 'video' | 'image') => {
  if (mirrorMode.value === mode) return

  mirrorMode.value = mode

  if (mode === 'video') {
    stopScreenshotMode()

    // 如果当前未连接设备，尝试重新检查并连接设备（内部会启动视频流）
    if (!isConnected.value) {
      await checkDeviceConnection()
      return
    }

    if (!decoder) {
      await initVideoDecoder()
    }
    startVideoStream()
  } else {
    stopVideoStream()
    connectionStatus.value = 'connected'
    connectionStatusText.value = '截图模式'
    if (isConnected.value) {
      startScreenshotMode()
    }
  }
}

// 处理 H.264 数据
const processH264Data = async (data: ArrayBuffer) => {
  if (!decoder) {
    // 解码器尚未就绪（刚刚出错重建中等），当前数据直接丢弃
    return
  }

  try {
    const bytes = new Uint8Array(data)

    // 解析 Annex-B 起始码
    let offset = 0
    if (bytes.length >= 4 && bytes[0] === 0 && bytes[1] === 0) {
      if (bytes[2] === 1) {
        offset = 3
      } else if (bytes[2] === 0 && bytes[3] === 1) {
        offset = 4
      }
    }

    if (offset >= bytes.length) {
      return
    }

    // H.264 NAL 类型: 后 5 bit
    const nalHeader = bytes[offset]
    const nalType = nalHeader & 0x1f

    // 去掉起始码后的 NAL（包含 NAL 头）
    const nalWithoutStartCode = bytes.subarray(offset)

    // SPS(7) / PPS(8)：只缓存并配置解码器，不解码
    if (nalType === 7) {
      spsNal = nalWithoutStartCode
      configureDecoderIfNeeded()
      return
    }

    if (nalType === 8) {
      ppsNal = nalWithoutStartCode
      configureDecoderIfNeeded()
      return
    }

    const isIdr = nalType === 5
    const isVcl = nalType === 1 || nalType === 5

    // 非 VCL（如 SEI=6、AUD=9 等）直接丢弃
    if (!isVcl) {
      return
    }

    // 还没 configure 成功之前，任何非 SPS/PPS 数据都丢掉
    if (!decoderConfigured) {
      return
    }

    // 还没拿到关键帧之前，非 IDR 帧直接丢弃
    if (!hasKeyFrame && !isIdr) {
      return
    }

    // 构造 AVCC 格式：多个 NAL，每个前面 4 字节长度
    let nalList: Uint8Array[] = []

    if (!hasKeyFrame && isIdr) {
      // 第一次关键帧：把 SPS + PPS + 当前 IDR 拼成一个 access unit
      if (spsNal) {
        nalList.push(spsNal)
      }
      if (ppsNal) {
        nalList.push(ppsNal)
      }
      nalList.push(nalWithoutStartCode)
      hasKeyFrame = true
    } else {
      // 后续帧：单个 VCL NAL
      nalList.push(nalWithoutStartCode)
    }

    // 计算总长度
    let totalPayload = 0
    for (const nal of nalList) {
      totalPayload += nal.length
    }

    const chunkData = new Uint8Array(nalList.length * 4 + totalPayload)
    let pos = 0
    for (const nal of nalList) {
      const len = nal.length
      // 写入 4 字节长度（大端）
      chunkData[pos++] = (len >>> 24) & 0xff
      chunkData[pos++] = (len >>> 16) & 0xff
      chunkData[pos++] = (len >>> 8) & 0xff
      chunkData[pos++] = len & 0xff
      // 写入 NAL 数据
      chunkData.set(nal, pos)
      pos += len
    }

    const chunk = new EncodedVideoChunk({
      type: isIdr ? 'key' : 'delta',
      timestamp: performance.now() * 1000, // 微秒
      data: chunkData,
    })

    decoder.decode(chunk)
  } catch (error) {
    console.error('处理 H.264 数据失败:', error)
  }
}

// 处理画布点击（手动控制）
const handleCanvasClick = async (event: MouseEvent) => {
  if (!videoCanvas.value || !isConnected.value) return

  const rect = videoCanvas.value.getBoundingClientRect()
  const x = Math.floor((event.clientX - rect.left) / scaleX)
  const y = Math.floor((event.clientY - rect.top) / scaleY)

  try {
    const result = await manualTap(x, y)
    if (result.success) {
      // 显示点击反馈
      showClickFeedback(x, y)
    }
  } catch (error) {
    console.error('点击操作失败:', error)
  }
}

// 显示点击反馈
const showClickFeedback = (x: number, y: number) => {
  if (!videoCanvas.value) return

  const rect = videoCanvas.value.getBoundingClientRect()
  const displayX = x * scaleX
  const displayY = y * scaleY

  // 创建点击反馈元素
  const feedback = document.createElement('div')
  feedback.className = 'click-feedback'
  feedback.style.left = `${rect.left + displayX}px`
  feedback.style.top = `${rect.top + displayY}px`
  document.body.appendChild(feedback)

  // 动画后移除
  setTimeout(() => {
    feedback.remove()
  }, 500)
}

// 停止 AI
const stopAI = () => {
  isAIExecuting.value = false
  // TODO: 实现停止 AI 的逻辑
}

// 导航按钮处理函数
const handleBack = async () => {
  if (!isConnected.value) return
  try {
    await manualBack()
  } catch (error) {
    console.error('返回操作失败:', error)
  }
}

const handleHome = async () => {
  if (!isConnected.value) return
  try {
    await manualHome()
  } catch (error) {
    console.error('主页操作失败:', error)
  }
}

const handleRecent = async () => {
  if (!isConnected.value) return
  try {
    await manualRecent()
  } catch (error) {
    console.error('多任务操作失败:', error)
  }
}

// 清理资源
const cleanup = () => {
  stopVideoStream()
  stopScreenshotMode()
}

// 监听画布点击
watch(videoCanvas, (canvas) => {
  if (canvas) {
    canvas.addEventListener('click', handleCanvasClick)
  }
})

// 调整画布大小，保持手机屏幕长宽比
const resizeCanvas = () => {
  if (!videoCanvas.value || !videoContainer.value) return

  const container = videoContainer.value
  const containerWidth = container.clientWidth
  const containerHeight = container.clientHeight

  // 使用实际视频宽高计算比例
  const deviceAspect = videoWidth / videoHeight
  const containerAspect = containerWidth / containerHeight

  let displayWidth: number
  let displayHeight: number

  if (containerAspect > deviceAspect) {
    // 容器更宽，以高度为准
    displayHeight = containerHeight
    displayWidth = displayHeight * deviceAspect
  } else {
    // 容器更高，以宽度为准
    displayWidth = containerWidth
    displayHeight = displayWidth / deviceAspect
  }

  // Canvas 内部分辨率使用实际视频分辨率，保证清晰度
  videoCanvas.value.width = videoWidth
  videoCanvas.value.height = videoHeight

  // CSS 显示尺寸保持正确的长宽比
  videoCanvas.value.style.width = `${Math.floor(displayWidth)}px`
  videoCanvas.value.style.height = `${Math.floor(displayHeight)}px`

  // 根据显示尺寸和实际视频分辨率计算缩放比例（用于点击坐标映射）
  scaleX = displayWidth / videoWidth
  scaleY = displayHeight / videoHeight
}
// 暴露方法供外部调用
defineExpose({
  checkDeviceConnection,
})
</script>

<style scoped>
.video-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #1a1a1a;
  position: relative;
}

.video-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #2a2a2a;
}

.video-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: #e0e0e0;
}

.video-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.mirror-mode-toggle {
  display: inline-flex;
  border-radius: 999px;
  overflow: hidden;
  border: 1px solid #3a3a3a;
  margin-right: 8px;
}

.mode-btn {
  padding: 4px 10px;
  font-size: 12px;
  background-color: transparent;
  border: none;
  color: #b0b0b0;
  cursor: pointer;
}

.mode-btn.active {
  background-color: #4a9eff;
  color: #fff;
}

.mode-btn:not(.active):hover {
  background-color: #2a2a2a;
}

/* 设备状态按钮 */
.device-status-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background-color: #2a2a2a;
  border: 1px solid #3a3a3a;
  border-radius: 6px;
  color: #e0e0e0;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.device-status-btn:hover {
  background-color: #3a3a3a;
  border-color: #4a4a4a;
}

.device-icon {
  font-size: 14px;
}

.device-name {
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 设备信息悬浮卡片 */
.device-info-card {
  position: absolute;
  top: 50px;
  right: 16px;
  background-color: #252525;
  border: 1px solid #3a3a3a;
  border-radius: 8px;
  z-index: 100;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
  min-width: 200px;
}

.device-info-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid #3a3a3a;
  font-size: 13px;
  font-weight: 500;
  color: #e0e0e0;
}

.close-info-btn {
  background: none;
  border: none;
  color: #888;
  font-size: 14px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}

.close-info-btn:hover {
  background-color: #3a3a3a;
  color: #fff;
}

.device-info-content {
  padding: 12px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  padding: 4px 0;
}

.info-row .label {
  color: #888;
}

.info-row .value {
  color: #e0e0e0;
  font-weight: 500;
}

.stop-button {
  padding: 6px 12px;
  background-color: #d32f2f;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
}

.stop-button:hover:not(:disabled) {
  background-color: #c62828;
}

.stop-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.status-indicator {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 4px;
}

.status-indicator.connected {
  background-color: #2e7d32;
  color: #fff;
}

.status-indicator.connecting {
  background-color: #f57c00;
  color: #fff;
}

.status-indicator.disconnected {
  background-color: #d32f2f;
  color: #fff;
}

.video-container {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  background-color: #0a0a0a;
  padding: 20px;
}

/* 手机边框样式 */
.phone-frame {
  display: flex;
  flex-direction: column;
  background: linear-gradient(145deg, #1a1a1a, #2a2a2a);
  border-radius: 36px;
  padding: 8px;
  box-shadow: 
    0 0 0 2px #333,
    0 0 0 4px #1a1a1a,
    0 20px 60px rgba(0, 0, 0, 0.5),
    inset 0 1px 1px rgba(255, 255, 255, 0.05);
  position: relative;
  max-height: 100%;
}

/* 手机顶部听筒区域 */
.phone-notch {
  width: 120px;
  height: 24px;
  background-color: #0a0a0a;
  border-radius: 0 0 16px 16px;
  margin: 0 auto 0 auto;
  position: relative;
  z-index: 10;
}

.phone-notch::before {
  content: '';
  position: absolute;
  top: 8px;
  left: 50%;
  transform: translateX(-50%);
  width: 60px;
  height: 6px;
  background-color: #1a1a1a;
  border-radius: 3px;
}

/* 手机屏幕区域 */
.phone-screen {
  flex: 1;
  background-color: #000;
  border-radius: 4px;
  overflow: hidden;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 手机底部导航栏 */
.phone-navbar {
  height: 48px;
  background-color: #0f0f0f;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 60px;
  border-radius: 0 0 28px 28px;
  margin-top: 4px;
}

.nav-btn {
  width: 40px;
  height: 40px;
  background: none;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.2s;
}

.nav-btn:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

.nav-btn:active {
  background-color: rgba(255, 255, 255, 0.2);
  transform: scale(0.95);
}

.nav-icon {
  font-size: 20px;
  color: #888;
  transition: color 0.2s;
}

.nav-btn:hover .nav-icon {
  color: #ccc;
}

.back-icon {
  font-size: 16px;
}

.home-icon {
  font-size: 24px;
  font-weight: 100;
}

.recent-icon {
  font-size: 18px;
}

.video-canvas {
  /* 不设置 max-width/max-height，由 JS 精确控制尺寸 */
  display: block;
}

.no-device,
.no-stream {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background-color: rgba(0, 0, 0, 0.6);
  z-index: 50;
  backdrop-filter: blur(2px);
}

.no-device > p:first-child,
.no-stream > p:first-child {
  font-size: 18px;
  font-weight: 500;
  color: #ff9800;
  text-shadow: 0 1px 4px rgba(255, 152, 0, 0.2);
  margin: 0;
  padding: 12px 24px;
  background-color: rgba(255, 152, 0, 0.08);
  border-radius: 8px;
  border: 1px solid rgba(255, 152, 0, 0.2);
}

.no-device .hint,
.no-stream .hint {
  font-size: 13px;
  color: #999;
  margin-top: 12px;
}

.ai-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.overlay-item {
  position: absolute;
  border: 2px solid #4a9eff;
  background-color: rgba(74, 158, 255, 0.1);
  pointer-events: none;
}

.overlay-label {
  position: absolute;
  top: -20px;
  left: 0;
  background-color: #4a9eff;
  color: #fff;
  padding: 2px 6px;
  font-size: 10px;
  border-radius: 2px;
}

/* 点击反馈动画 */
:global(.click-feedback) {
  position: fixed;
  width: 20px;
  height: 20px;
  border: 2px solid #4a9eff;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  animation: clickPulse 0.5s ease-out;
  pointer-events: none;
  z-index: 1000;
}

@keyframes clickPulse {
  0% {
    transform: translate(-50%, -50%) scale(0.5);
    opacity: 1;
  }
  100% {
    transform: translate(-50%, -50%) scale(2);
    opacity: 0;
  }
}
</style>