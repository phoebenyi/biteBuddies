<template>
  <div class="notif-wrapper">
    <div class="notif-icon" @click="toggle">
      🔔
      <span v-if="unreadCount > 0" class="notif-badge">{{ unreadCount }}</span>
    </div>

    <transition name="slide">
      <div v-if="isOpen" class="notif-dropdown">
        <div class="notif-header">
          <span>Notifications</span>
          <button @click="toggle" class="close-btn">✕</button>
        </div>

        <div
          v-for="(notif, index) in notifications"
          :key="index"
          class="notif-box"
        >
          <div class="notif-title">{{ notif.title }}</div>
          <div class="notif-message">{{ notif.message }}</div>
          <div class="notif-time">{{ notif.datetime }}</div>
        </div>

        <div v-if="notifications.length === 0" class="notif-empty">
          No notifications yet.
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { inject, ref, onMounted, watch } from 'vue'
import API_URLS from '../config.js'

const notifications = ref([])
const isOpen = ref(false)
const unreadCount = ref(0)
const userData = inject('userData')
const currentUserEmail = ref(userData?.email || '')

const toggle = () => {
  isOpen.value = !isOpen.value
  if (isOpen.value) unreadCount.value = 0
}

const fetchNotificationHistory = async () => {
  if (!currentUserEmail.value) return

  try {
    const res = await fetch(`${API_URLS.NOTIFICATION_SERVICE}/get_notification_history/${encodeURIComponent(currentUserEmail.value)}`)
    const data = await res.json()
    console.log("Fetched notifications:", data)

    if (Array.isArray(data.notifications)) {
      notifications.value = data.notifications
    } else {
      console.warn("No notifications array in response")
    }
  } catch (err) {
    console.error("Failed to fetch notification history:", err)
  }
}

onMounted(() => {
  // Watch for when email is available
  watch(() => userData.email, (newVal) => {
    currentUserEmail.value = newVal
    if (newVal) {
      fetchNotificationHistory()
    }
  }, { immediate: true })

  const socket = new WebSocket('ws://localhost:8005')

  socket.onmessage = (event) => {
    const data = JSON.parse(event.data)
    console.log("Received WS notification:", data)

    if (data.recipient_email === currentUserEmail.value) {
      notifications.value.unshift({
        title: data.title || 'Notification',
        message: data.message || JSON.stringify(data),
        datetime: data.datetime || null
      })

      if (!isOpen.value) unreadCount.value += 1
    }
  }

  socket.onclose = () => {
    console.warn('Notification WebSocket disconnected')
  }
})
</script>

<style>
.notif-wrapper {
  position: relative;
  display: inline-block;
}

.notif-icon {
  cursor: pointer;
  font-size: 1.5rem;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 5px;
}

.notif-badge {
  position: absolute;
  top: 0;
  right: 0;
  background-color: #ff4d4f;
  color: white;
  font-size: 0.7rem;
  padding: 1px 5px;
  border-radius: 10px;
  min-width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
}

.notif-dropdown {
  position: absolute;
  top: calc(100% + 5px);
  right: -10px;
  width: 320px;
  max-height: 400px;
  overflow-y: auto;
  background: white;
  border: 1px solid #ddd;
  border-radius: 6px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
  z-index: 1001;
}

.notif-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  background-color: #f5f5f5;
  border-bottom: 1px solid #eee;
  font-weight: bold;
}

.close-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: #666;
  font-size: 16px;
}

.notif-box {
  padding: 1rem;
  border-bottom: 1px solid #eee;
}

.notif-title {
  font-weight: bold;
  color: #2563eb;
  margin-bottom: 0.25rem;
}

.notif-message {
  color: #333;
  font-size: 14px;
}

.notif-time {
  font-size: 11px;
  color: #888;
  margin-top: 0.25rem;
}

.notif-empty {
  padding: 1rem;
  text-align: center;
  color: #888;
  font-style: italic;
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateY(-10px);
  opacity: 0;
}

.slide-enter-to,
.slide-leave-from {
  transform: translateY(0);
  opacity: 1;
}
</style>