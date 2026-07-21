<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const alerts = ref([])

async function load() {
  const res = await api.get('/alerts')
  alerts.value = res.data.items || []
}

async function markRead(id) {
  await api.put(`/alerts/${id}/read`)
  await load()
}

async function markAllRead() {
  await api.put('/alerts/read-all')
  await load()
}

function format(v) {
  return v != null ? v.toFixed(2) : '--'
}

function formatTime(t) {
  if (!t) return ''
  return new Date(t).toLocaleString('zh-CN')
}

onMounted(load)
</script>

<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h3 style="margin: 0">告警历史</h3>
      <el-button @click="markAllRead" :disabled="alerts.every(a => a.read)">全部标记已读</el-button>
    </div>
    <el-table :data="alerts" stripe empty-text="暂无告警记录" :row-class-name="({ row }) => row.read ? '' : 'unread-row'">
      <el-table-column prop="holding_name" label="持仓" width="150" />
      <el-table-column prop="holding_code" label="代码" width="100" />
      <el-table-column label="当前价" width="110">
        <template #default="{ row }">¥{{ format(row.current_price) }}</template>
      </el-table-column>
      <el-table-column label="止损价" width="110">
        <template #default="{ row }">¥{{ format(row.trigger_price) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.read ? 'info' : 'warning'" size="small">
            {{ row.read ? '已读' : '未读' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="触发时间" min-width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button v-if="!row.read" size="small" type="primary" link @click="markRead(row.id)">
            标记已读
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
:deep(.unread-row) {
  background-color: #fdf6ec !important;
}
</style>
