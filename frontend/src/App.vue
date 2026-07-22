<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElNotification } from 'element-plus'
import { Bell, HomeFilled, List, Setting, WarningFilled } from '@element-plus/icons-vue'
import api from './api'
import { useAlertStore } from './stores/alert'
import { useSettingsStore } from './stores/settings'
import { createPoller } from './utils/poller'

const router = useRouter()
const route = useRoute()
const alertStore = useAlertStore()
const settingsStore = useSettingsStore()
const lastAlertId = ref(0)
const initialized = ref(false)
const alertPoller = createPoller(checkAlerts)
const navigation = [
  { path: '/', label: '仪表盘', icon: HomeFilled },
  { path: '/holdings', label: '持仓', desktopLabel: '持仓管理', icon: List },
  { path: '/alerts', label: '告警', desktopLabel: '告警历史', icon: WarningFilled },
  { path: '/settings', label: '设置', icon: Setting },
]

function isActive(path) {
  return path === '/' ? route.path === '/' : route.path.startsWith(path)
}

async function checkAlerts() {
  try {
    const res = await api.get('/alerts?unread=true&size=1')
    const alerts = res.data.items || []
    if (!initialized.value) {
      lastAlertId.value = alerts[0]?.id || 0
      initialized.value = true
    } else if (alerts.length > 0 && alerts[0].id !== lastAlertId.value) {
      lastAlertId.value = alerts[0].id
      const a = alerts[0]
      ElNotification({
        title: '止损触发',
        message: `${a.holding_name}(${a.holding_code}) 当前价 ${a.current_price} 触及止损价 ${a.trigger_price}`,
        type: 'warning',
        duration: 0,
      })
    }
  } catch {
    // ignore
  }
  alertStore.fetchUnreadCount()
}

function startAlertPolling() {
  alertPoller.start(settingsStore.pollInterval)
}

onMounted(async () => {
  await settingsStore.fetchSettings()
  alertStore.fetchUnreadCount()
  await checkAlerts()
  startAlertPolling()
})

watch(() => settingsStore.pollInterval, startAlertPolling)

onUnmounted(() => {
  alertPoller.stop()
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
