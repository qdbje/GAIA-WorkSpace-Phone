<template>
  <div class="chat-panel">
    <div class="chat-header">
      <h3>Phone Agent</h3>
    </div>
    <div class="chat-messages" ref="messagesContainer">
      <div
        v-for="(message, index) in messages"
        :key="index"
        :class="['message', message.type, message.isFinished ? 'finished' : '']"
      >
        <div class="message-content">
          <div v-if="message.type === 'user'" class="user-message">
            <div v-html="renderMarkdown(message.content || '')"></div>
          </div>
          <div v-else-if="message.type === 'assistant'" class="assistant-message">
            <!-- 步骤卡片样式 -->
            <template v-if="message.stepCount">
              <div class="step-header">
                <span class="step-icon">☁️</span>
                <span class="step-title">步骤 {{ message.stepCount }} - 思考过程</span>
              </div>
              <div class="step-thinking">
                <div v-html="renderMarkdown(message.thinking || '')"></div>
              </div>
              <div class="step-toggle" @click="toggleAction(index)">
                <span class="toggle-icon">{{ message.showActionDetails ? '▼' : '▶' }}</span>
                <span class="toggle-text">查看动作</span>
              </div>
              <div v-if="message.showActionDetails && message.action" class="step-action">
                {{ formatAction(message.action) }}
              </div>
            </template>
            <!-- 其他助手消息（保留兼容） -->
            <template v-else>
              <div v-if="message.thinking" class="thinking">
                <strong>思考:</strong> {{ message.thinking }}
              </div>
              <div v-if="message.action" class="action">
                <strong>操作:</strong> {{ formatAction(message.action) }}
              </div>
              <div v-if="message.content" class="content">
                <div v-html="renderMarkdown(message.content)"></div>
              </div>
            </template>
          </div>
          <div v-else-if="message.type === 'system'" class="system-message">
            <span v-if="message.isFinished" class="finished-icon">✓</span>
            <div v-html="renderMarkdown(message.content || '')"></div>
          </div>
        </div>
      </div>
    </div>
    <div class="chat-input">
      <input
        v-model="inputText"
        @keyup.enter="sendMessage"
        placeholder="输入任务指令..."
        :disabled="isExecuting"
      />
      <button @click="sendMessage" :disabled="isExecuting || !inputText.trim()">
        发送
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { marked } from 'marked'
import {
  setApiBaseUrl,
  getWebSocketUrl,
  createAITaskStreamWebSocket,
  getAIStatus,
  initAI,
  type AIConfig,
} from '../utils/api'

interface Message {
  type: 'user' | 'assistant' | 'system'
  content?: string
  thinking?: string
  action?: any
  stepCount?: number
  showActionDetails?: boolean
  isFinished?: boolean
}

const messages = ref<Message[]>([])
const inputText = ref('')
const isExecuting = ref(false)
const messagesContainer = ref<HTMLElement | null>(null)

// 获取 Python 服务端口
onMounted(async () => {
  if (window.electronAPI) {
    const port = await window.electronAPI.getPythonPort()
    if (port) {
      setApiBaseUrl(`http://127.0.0.1:${port}`)
    }
  }
})

const formatAction = (action: any): string => {
  if (!action) return ''
  if (typeof action === 'string') return action
  return JSON.stringify(action, null, 2)
}

const renderMarkdown = (text: string): string => {
  if (!text) return ''
  
  // 预处理：去掉首尾空行，并删除纯空行
  const cleanedText = text
    .trim()
    .split('\n')
    .filter((line) => line.trim() !== '')
    .join('\n')
  
  // 配置 marked 选项
  const html = marked(cleanedText, { 
    breaks: true,  // 保留单个换行
    gfm: true      // GitHub Flavored Markdown
  }) as string
  
  // 后处理：移除空的 <p> 标签
  return html.replace(/<p>\s*<\/p>/g, '')
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

const toggleAction = (index: number) => {
  const msg = messages.value[index]
  if (msg && msg.type === 'assistant' && msg.stepCount) {
    msg.showActionDetails = !msg.showActionDetails
  }
}

// 尝试自动初始化 AI
const tryAutoInitAI = async (): Promise<boolean> => {
  try {
    // 优先使用 Electron API 读取配置
    let config: AIConfig | null = null
    
    if (window.electronAPI) {
      const saved = await window.electronAPI.getConfig('aiConfig')
      if (saved) {
        config = saved
      }
    }
    
    // 回退到 localStorage
    if (!config) {
      const localSaved = localStorage.getItem('aiConfig')
      if (localSaved) {
        try {
          config = JSON.parse(localSaved)
        } catch (error) {
          console.error('解析 AI 配置失败:', error)
          return false
        }
      }
    }

    if (!config) {
      return false
    }

    // 检查配置是否完整
    if (!config.base_url || !config.api_key) {
      return false
    }

    // 尝试初始化
    messages.value.push({
      type: 'system',
      content: '正在自动初始化 AI...',
    })
    scrollToBottom()

    const result = await initAI(config)
    if (result.success) {
      messages.value.push({
        type: 'system',
        content: 'AI 初始化成功',
      })
      scrollToBottom()
      return true
    } else {
      messages.value.push({
        type: 'system',
        content: `AI 自动初始化失败: ${result.error || '未知错误'}`,
      })
      scrollToBottom()
      return false
    }
  } catch (error) {
    console.error('自动初始化 AI 失败:', error)
    return false
  }
}

const sendMessage = async () => {
  if (!inputText.value.trim() || isExecuting.value) return

  const userMessage = inputText.value
  messages.value.push({ type: 'user', content: userMessage })
  inputText.value = ''
  isExecuting.value = true
  scrollToBottom()

  try {
    // 先检查 AI 是否已初始化
    let aiStatus = await getAIStatus()
    
    // 如果未初始化，尝试自动初始化
    if (!aiStatus.initialized) {
      const autoInitSuccess = await tryAutoInitAI()
      
      if (!autoInitSuccess) {
        messages.value.push({
          type: 'system',
          content: '错误: AI 未初始化。请先在"工作区"面板配置并保存 AI 设置。',
        })
        isExecuting.value = false
        scrollToBottom()
        return
      }
      
      // 重新检查状态
      aiStatus = await getAIStatus()
      if (!aiStatus.initialized) {
        messages.value.push({
          type: 'system',
          content: '错误: AI 初始化后状态异常，请重试。',
        })
        isExecuting.value = false
        scrollToBottom()
        return
      }
    }

    // 使用 WebSocket 流式执行
    const ws = createAITaskStreamWebSocket()

    ws.onopen = () => {
      console.log('WebSocket 连接已建立')
      ws.send(JSON.stringify({ task: userMessage }))
      console.log('已发送任务:', userMessage)
    }

    ws.onmessage = (event) => {
      console.log('收到 WebSocket 消息:', event.data)
      const data = JSON.parse(event.data)

      if (data.type === 'error') {
        // 处理错误消息，特别是 AI 未初始化的错误
        let errorMessage = data.message || '未知错误'
        if (errorMessage.includes('not initialized') || errorMessage.includes('未初始化')) {
          // 如果收到未初始化错误，尝试再次自动初始化
          tryAutoInitAI().then((success) => {
            if (success) {
              messages.value.push({
                type: 'system',
                content: '已自动重新初始化 AI，请重试发送消息。',
              })
            } else {
              messages.value.push({
                type: 'system',
                content: 'AI 未初始化。请先在"工作区"面板配置并保存 AI 设置。',
              })
            }
            scrollToBottom()
          })
        } else {
          messages.value.push({
            type: 'system',
            content: `错误: ${errorMessage}`,
          })
        }
        scrollToBottom()
        isExecuting.value = false
        return
      }

      if (data.type === 'started') {
        messages.value.push({
          type: 'system',
          content: '任务已开始执行...',
        })
      } else if (data.type === 'step') {
        // 每一步单独创建一条步骤消息
        messages.value.push({
          type: 'assistant',
          stepCount: data.step_count,
          thinking: data.thinking,
          action: data.action,
          showActionDetails: false,
        })
        scrollToBottom()
      } else if (data.type === 'finished') {
        messages.value.push({
          type: 'system',
          content: data.message || '任务完成',
          isFinished: true,
        })
        scrollToBottom()
        isExecuting.value = false
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket 错误:', error)
      messages.value.push({
        type: 'system',
        content: '连接错误，请检查 Python 服务是否运行',
      })
      isExecuting.value = false
    }

    ws.onclose = (event) => {
      // 如果连接关闭且没有正常完成，重置状态
      if (isExecuting.value) {
        isExecuting.value = false
      }
    }
  } catch (error) {
    console.error('发送消息失败:', error)
    messages.value.push({
      type: 'system',
      content: `错误: ${error}`,
    })
    isExecuting.value = false
  }
}
</script>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #1a1a1a;
}

.chat-header {
  padding: 16px;
  border-bottom: 1px solid #2a2a2a;
}

.chat-header h2 {
  font-size: 18px;
  font-weight: 600;
  color: #e0e0e0;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: linear-gradient(to bottom, rgba(26, 26, 26, 0.3), rgba(26, 26, 26, 0.1));
}

.message {
  margin-bottom: 12px;
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message-content {
  border-radius: 8px;
}

/* 用户消息样式 - 蓝色按钮样式 */
.user-message {
  background: linear-gradient(135deg, #4a9eff, #3b7dd6);
  color: #fff;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
  max-width: 90%;
  box-shadow: 0 2px 8px rgba(74, 158, 255, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

/* 助手消息容器 */
.assistant-message {
  background: linear-gradient(135deg, rgba(37, 37, 37, 0.6), rgba(45, 45, 45, 0.4));
  color: #e0e0e0;
  padding: 12px 14px;
  border-radius: 12px;
  max-width: 95%;
  border: 1px solid rgba(255, 255, 255, 0.05);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

/* 步骤头部 */
.step-header {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 12px;
  color: #4a9eff;
}

.step-icon {
  margin-right: 6px;
  font-size: 14px;
  filter: grayscale(0.3);
}

.step-title {
  font-weight: 500;
  letter-spacing: 0.3px;
}

/* 思考内容 */
.step-thinking {
  font-size: 13px;
  color: #d8d8d8;
  line-height: 1.6;
  margin-bottom: 8px;
  white-space: pre-wrap;
  word-break: break-word;
  background-color: rgba(0, 0, 0, 0.15);
  padding: 10px;
  border-radius: 8px;
  border-left: 3px solid #4a9eff;
}

/* 查看动作按钮 */
.step-toggle {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  color: #4a9eff;
  cursor: pointer;
  user-select: none;
  padding: 6px 12px;
  border-radius: 6px;
  background-color: rgba(74, 158, 255, 0.1);
  transition: all 0.2s;
  border: 1px solid rgba(74, 158, 255, 0.2);
}

.step-toggle:hover {
  background-color: rgba(74, 158, 255, 0.2);
  border-color: rgba(74, 158, 255, 0.4);
}

.toggle-icon {
  margin-right: 6px;
  font-size: 10px;
  transition: transform 0.2s;
}

.toggle-text {
  font-weight: 400;
}

/* 动作详情展开区域 */
.step-action {
  margin-top: 12px;
  padding: 12px;
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(26, 26, 26, 0.8), rgba(20, 20, 20, 0.6));
  font-size: 12px;
  font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
  color: #b8d4ff;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.6;
  border: 1px solid rgba(74, 158, 255, 0.15);
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.3);
}

/* 原有样式（兼容旧消息格式） */
.thinking {
  margin-bottom: 8px;
  font-size: 13px;
  color: #aaa;
}

.action {
  margin-bottom: 8px;
  font-size: 13px;
  color: #4a9eff;
  font-family: monospace;
  white-space: pre-wrap;
}

.content {
  font-size: 14px;
  color: #d0d0d0;
}

/* 系统消息样式 - 优化为低调提示 */
.system-message {
  background-color: rgba(42, 42, 42, 0.3);
  color: #888;
  text-align: center;
  font-size: 11px;
  padding: 8px 12px;
  margin: 12px auto;
  max-width: 70%;
  border-left: 2px solid #3a3a3a;
  border-radius: 4px;
  font-style: italic;
  backdrop-filter: blur(2px);
}

/* 任务完成消息样式 */
.message.finished .system-message {
  background: linear-gradient(135deg, rgba(76, 175, 80, 0.12), rgba(46, 125, 50, 0.08));
  color: #81c784;
  font-size: 13px;
  font-style: normal;
  font-weight: 500;
  padding: 12px 18px;
  border-left: 3px solid #4caf50;
  border-radius: 8px;
  max-width: 85%;
  box-shadow: 0 2px 8px rgba(76, 175, 80, 0.15);
  border: 1px solid rgba(76, 175, 80, 0.2);
  backdrop-filter: blur(4px);
}

.finished-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  margin-right: 8px;
  background: linear-gradient(135deg, #4caf50, #66bb6a);
  color: #fff;
  border-radius: 50%;
  font-size: 12px;
  font-weight: bold;
  vertical-align: middle;
  box-shadow: 0 2px 4px rgba(76, 175, 80, 0.3);
}

.chat-input {
  display: flex;
  padding: 16px;
  border-top: 1px solid #2a2a2a;
  gap: 8px;
}

.chat-input input {
  flex: 1;
  padding: 10px 12px;
  background-color: #2a2a2a;
  border: 1px solid #3a3a3a;
  border-radius: 6px;
  color: #e0e0e0;
  font-size: 14px;
}

.chat-input input:focus {
  outline: none;
  border-color: #4a9eff;
}

.chat-input input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-input button {
  padding: 10px 20px;
  background-color: #4a9eff;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
}

.chat-input button:hover:not(:disabled) {
  background-color: #5aaeff;
}

.chat-input button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Markdown 渲染样式 */
.message-content :deep(p) {
  margin: 0;
  line-height: 1.35;
}

.message-content :deep(p:last-child) {
  margin-bottom: 0;
}

.message-content :deep(ul),
.message-content :deep(ol) {
  margin: 2px 0;
  padding-left: 18px;
}

.message-content :deep(li) {
  margin: 0;
  line-height: 1.4;
  position: relative;
}

.message-content :deep(ul li)::marker {
  color: #4a9eff;
}

.message-content :deep(ol li)::marker {
  color: #4a9eff;
  font-weight: 600;
}

.message-content :deep(code) {
  background: linear-gradient(135deg, rgba(74, 158, 255, 0.15), rgba(74, 158, 255, 0.08));
  padding: 3px 8px;
  border-radius: 4px;
  font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
  font-size: 0.9em;
  border: 1px solid rgba(74, 158, 255, 0.2);
  color: #a0cfff;
}

.message-content :deep(pre) {
  background: linear-gradient(135deg, rgba(0, 0, 0, 0.4), rgba(0, 0, 0, 0.3));
  padding: 10px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 6px 0;
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.3);
}

.message-content :deep(pre code) {
  background-color: transparent;
  padding: 0;
}

.message-content :deep(strong) {
  font-weight: 600;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.message-content :deep(em) {
  font-style: italic;
  color: #d0d0d0;
}

.message-content :deep(h1),
.message-content :deep(h2),
.message-content :deep(h3),
.message-content :deep(h4) {
  margin: 6px 0 3px 0;
  font-weight: 600;
  line-height: 1.3;
}

.message-content :deep(h1) { font-size: 1.5em; }
.message-content :deep(h2) { font-size: 1.3em; }
.message-content :deep(h3) { font-size: 1.1em; }
.message-content :deep(h4) { font-size: 1em; }

.message-content :deep(blockquote) {
  border-left: 3px solid #4a9eff;
  padding-left: 12px;
  margin: 6px 0;
  color: #aaa;
  font-style: italic;
  background-color: rgba(74, 158, 255, 0.05);
  padding: 8px 12px;
  border-radius: 4px;
}

.message-content :deep(a) {
  color: #4a9eff;
  text-decoration: none;
}

.message-content :deep(a:hover) {
  text-decoration: underline;
}

.message-content :deep(hr) {
  border: none;
  border-top: 1px solid #3a3a3a;
  margin: 6px 0;
}

/* 完成消息中的 Markdown 样式微调 */
.message.finished .system-message :deep(strong) {
  color: #a5d6a7;
}

.message.finished .system-message :deep(code) {
  background-color: rgba(76, 175, 80, 0.15);
  color: #a5d6a7;
}
</style>

