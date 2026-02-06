<template>
  <main style="max-width: 860px; margin: 40px auto; font-family: system-ui, -apple-system, Segoe UI, Roboto;">
    <header style="display: flex; align-items: baseline; justify-content: space-between; gap: 12px;">
      <h1 style="margin: 0;">AI Chat</h1>
      <small style="color: #6b7280;">Backend: <code>http://127.0.0.1:8000</code></small>
    </header>

    <section style="margin-top: 16px; border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden;">
      <div
        ref="scrollRef"
        style="height: 520px; padding: 16px; overflow: auto; background: #0b1020;"
      >
        <div v-if="messages.length === 0" style="color: #9ca3af;">输入一句话开始对话</div>

        <div
          v-for="m in messages"
          :key="m.id"
          style="display: flex; margin-bottom: 12px;"
          :style="{ justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start' }"
        >
          <div
            style="max-width: 80%; padding: 10px 12px; border-radius: 12px; line-height: 1.4; white-space: pre-wrap;"
            :style="{
              background: m.role === 'user' ? '#2563eb' : '#111827',
              color: '#e5e7eb',
              border: m.role === 'user' ? '1px solid #1d4ed8' : '1px solid #374151'
            }"
          >
            <div style="font-size: 12px; opacity: 0.8; margin-bottom: 6px;">
              {{ m.role === 'user' ? '你' : '模型' }}
            </div>
            <div>{{ m.content }}</div>
          </div>
        </div>

        <div v-if="loading" style="color: #9ca3af;">模型输入中...</div>
      </div>

      <form
        @submit.prevent="send"
        style="display: flex; gap: 8px; padding: 12px; background: white; border-top: 1px solid #e5e7eb;"
      >
        <input
          v-model="draft"
          :disabled="loading"
          placeholder="输入消息，回车发送"
          style="flex: 1; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 10px;"
        />
        <button
          type="submit"
          :disabled="loading || !draft.trim()"
          style="padding: 10px 14px; border-radius: 10px; border: 1px solid #1d4ed8; background: #2563eb; color: white;"
        >
          发送
        </button>
      </form>
    </section>
  </main>
</template>

<script setup>
import { nextTick, ref } from 'vue'

const messages = ref([])
const draft = ref('')
const loading = ref(false)
const scrollRef = ref(null)

function pushMessage(role, content) {
  messages.value.push({
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    role,
    content
  })
}

async function scrollToBottom() {
  await nextTick()
  if (!scrollRef.value) return
  scrollRef.value.scrollTop = scrollRef.value.scrollHeight
}

async function send() {
  const text = draft.value.trim()
  if (!text || loading.value) return

  draft.value = ''
  pushMessage('user', text)
  await scrollToBottom()

  loading.value = true
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    })

    if (!res.ok) {
      const errText = await res.text()
      throw new Error(errText || `HTTP ${res.status}`)
    }

    const data = await res.json()
    pushMessage('assistant', data.reply ?? '')
  } catch (e) {
    pushMessage('assistant', `请求失败：${String(e)}`)
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}
</script>
