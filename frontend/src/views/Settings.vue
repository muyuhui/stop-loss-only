<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import { useSettingsStore } from '../stores/settings'
import { summarizeRefresh } from '../utils/refreshResult'

const settingsStore = useSettingsStore()
const pollInterval = ref(30)
const monitorInterval = ref(5)
const refreshing = ref(false)

onMounted(async () => {
  await settingsStore.fetchSettings()
  pollInterval.value = settingsStore.pollInterval
  monitorInterval.value = settingsStore.monitorInterval
})

async function save() {
  await settingsStore.saveSettings({
    poll_interval: pollInterval.value,
    monitor_interval: monitorInterval.value,
  })
  ElMessage.success('设置已保存')
}

async function refreshPrices() {
  refreshing.value = true
  try {
    const res = await api.post('/prices/refresh')
    const summary = summarizeRefresh(res.data)
    ElMessage[summary.type](summary.message)
  } finally {
    refreshing.value = false
  }
}
</script>

<template>
  <div>
    <h3 style="margin: 0 0 16px 0">设置</h3>

    <el-card style="margin-bottom: 16px">
      <template #header><span style="font-weight: 600">监控配置</span></template>
      <el-form label-width="140px">
        <el-form-item label="页面轮询间隔(秒)">
          <el-input-number v-model="pollInterval" :min="5" :max="300" />
          <span style="color: #909399; font-size: 12px; margin-left: 8px">
            仪表盘和持仓页面自动刷新频率
          </span>
        </el-form-item>
        <el-form-item label="价格监控间隔(分钟)">
          <el-input-number v-model="monitorInterval" :min="1" :max="60" />
          <span style="color: #909399; font-size: 12px; margin-left: 8px">
            后端定时拉取价格并检查止损的频率
          </span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="save">保存设置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <template #header><span style="font-weight: 600">手动操作</span></template>
      <el-button type="primary" @click="refreshPrices" :loading="refreshing">
        立即刷新所有持仓价格
      </el-button>
      <span style="color: #909399; font-size: 12px; margin-left: 8px">
        强制拉取最新价格并检查止损触发
      </span>
    </el-card>
  </div>
</template>
