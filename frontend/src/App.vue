<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElNotification } from 'element-plus'
import { Bell, HomeFilled, List, Setting, TrendCharts, WarningFilled } from '@element-plus/icons-vue'
import api from './api'
import { useAlertStore } from './stores/alert'
import { useSettingsStore } from './stores/settings'
import { useRuntimeCapabilitiesStore } from './stores/runtimeCapabilities'
import { createPoller } from './utils/poller'
import {
  createTriggerNotifier,
  getNotificationPreferences,
  playTriggerChime,
  sendTriggerNotification,
} from './utils/notifications'

const router = useRouter()
const route = useRoute()
const alertStore = useAlertStore()
const settingsStore = useSettingsStore()
const runtimeCapabilities = useRuntimeCapabilitiesStore()
const alertPoller = createPoller(checkAlerts)
const defaultTitle = document.title || '止损不止盈'
const navigationItems = [
  { path: '/', label: '仪表盘', icon: HomeFilled },
  { path: '/holdings', label: '持仓', desktopLabel: '持仓管理', icon: List },
  { path: '/planner', label: '试算', desktopLabel: '风险试算', icon: TrendCharts, capability: 'risk_plan_previews' },
  { path: '/alerts', label: '告警', desktopLabel: '告警历史', icon: WarningFilled },
  { path: '/settings', label: '设置', icon: Setting },
]
const navigation = computed(() => navigationItems.filter(
  item => !item.capability || runtimeCapabilities.isAvailable(item.capability)
))

function isActive(path) {
  return path === '/' ? route.path === '/' : route.path.startsWith(path)
}

function presentTrigger(alert) {
  ElNotification({
    title: '止损触发',
    message: `${alert.holding_name}(${alert.holding_code}) 当前价 ${alert.current_price} 触及止损价 ${alert.trigger_price}`,
    type: 'warning',
    duration: 0,
  })
  const preferences = getNotificationPreferences()
  if (preferences.notificationsEnabled) sendTriggerNotification(alert)
  if (preferences.soundEnabled) playTriggerChime()
}

// 基线 = 首次成功轮询响应中的最新未读 id；同一条告警只通知一次（见 utils/notifications.js）
const onAlertSnapshot = createTriggerNotifier(presentTrigger)

async function checkAlerts() {
  try {
    const res = await api.get('/alerts?unread=true&size=1')
    onAlertSnapshot(res.data.items || [])
  } catch {
    // ignore
  }
  alertStore.fetchUnreadCount()
}

function startAlertPolling() {
  alertPoller.start(settingsStore.pollInterval)
}

// 未读徽标：与铃铛角标共享同一未读事实来源；未读为零时恢复原标题
watch(() => alertStore.unreadCount, (count) => {
  document.title = count > 0 ? `(${count}) ${defaultTitle}` : defaultTitle
}, { immediate: true })

// 从隐藏恢复可见：立即刷新告警（轮询器在可见瞬间已立即回调，这里兜底页面数据依赖的计数）
function handleVisibilityChange() {
  if (document.visibilityState === 'visible') {
    checkAlerts()
  }
}

onMounted(async () => {
  await runtimeCapabilities.fetchCapabilities()
  await settingsStore.fetchSettings()
  alertStore.fetchUnreadCount()
  await checkAlerts()
  startAlertPolling()
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

watch(() => settingsStore.pollInterval, startAlertPolling)

onUnmounted(() => {
  alertPoller.stop()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="app-header__inner">
        <button class="brand" type="button" aria-label="返回仪表盘" @click="router.push('/')">
          <span class="brand__mark" aria-hidden="true">止</span>
          <span class="brand__text">止损不止盈</span>
        </button>
        <nav class="desktop-nav" aria-label="主导航">
          <router-link
            v-for="item in navigation"
            :key="item.path"
            :to="item.path"
            class="desktop-nav__link"
            :class="{ 'is-active': isActive(item.path) }"
            :aria-current="isActive(item.path) ? 'page' : undefined"
          >
            {{ item.desktopLabel || item.label }}
          </router-link>
        </nav>
        <button class="alert-button" type="button" aria-label="查看告警历史" @click="router.push('/alerts')">
          <el-badge :value="alertStore.unreadCount" :hidden="alertStore.unreadCount === 0">
            <el-icon :size="20"><Bell /></el-icon>
          </el-badge>
        </button>
      </div>
    </header>

    <main class="app-main">
      <div class="page-container">
        <router-view />
      </div>
    </main>

    <nav class="mobile-nav" aria-label="移动端主导航">
      <router-link
        v-for="item in navigation"
        :key="item.path"
        :to="item.path"
        class="mobile-nav__link"
        :class="{ 'is-active': isActive(item.path) }"
        :aria-current="isActive(item.path) ? 'page' : undefined"
      >
        <el-icon :size="20"><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
        <span v-if="item.path === '/alerts' && alertStore.unreadCount" class="mobile-nav__badge">
          {{ alertStore.unreadCount > 99 ? '99+' : alertStore.unreadCount }}
        </span>
      </router-link>
    </nav>
  </div>
</template>
