<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElNotification } from 'element-plus'
import { Bell } from '@element-plus/icons-vue'
import api from './api'
import { useAlertStore } from './stores/alert'
import { useSettingsStore } from './stores/settings'
import { createPoller } from './utils/poller'

const router = useRouter()
const alertStore = useAlertStore()
const settingsStore = useSettingsStore()
const lastAlertId = ref(0)
const initialized = ref(false)
const alertPoller = createPoller(checkAlerts)

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
  <el-container style="min-height: 100vh">
    <el-header style="background: #1d1e2c; padding: 0 24px; display: flex; align-items: center; justify-content: space-between">
      <div style="display: flex; align-items: center; gap: 32px">
        <span style="color: #fff; font-size: 18px; font-weight: 700; cursor: pointer" @click="router.push('/')">
          止损不止盈
        </span>
        <el-menu
          mode="horizontal"
          :default-active="router.currentRoute.value.path"
          @select="(index) => router.push(index)"
          background-color="transparent"
          text-color="#a0a0b8"
          active-text-color="#fff"
          style="border-bottom: none"
        >
          <el-menu-item index="/">仪表盘</el-menu-item>
          <el-menu-item index="/holdings">持仓管理</el-menu-item>
          <el-menu-item index="/alerts">告警历史</el-menu-item>
          <el-menu-item index="/settings">设置</el-menu-item>
        </el-menu>
      </div>
      <div style="display: flex; align-items: center; gap: 8px; cursor: pointer" @click="router.push('/alerts')">
        <el-badge :value="alertStore.unreadCount" :hidden="alertStore.unreadCount === 0">
          <el-icon :size="20" color="#a0a0b8"><Bell /></el-icon>
        </el-badge>
      </div>
    </el-header>
    <el-main style="background: #f5f6fa; padding: 24px">
      <router-view />
    </el-main>
  </el-container>
</template>
