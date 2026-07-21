<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { useSettingsStore } from '../stores/settings'
import { holdingStatusLabel, holdingStatusTag } from '../utils/holdingStatus'
import { createPoller } from '../utils/poller'

const dashboard = ref({
  active_cost: 0, active_market_value: 0, unrealized_profit_loss: 0,
  unrealized_profit_loss_pct: 0, realized_profit_loss: 0,
  holding_count: 0, triggered_count: 0, closed_count: 0, active_alerts_count: 0,
  holdings: [],
})
const settingsStore = useSettingsStore()
const poller = createPoller(load)

async function load() {
  try {
    const res = await api.get('/dashboard')
    dashboard.value = res.data
  } catch { /* skip */ }
}

function startPolling() {
  poller.start(settingsStore.pollInterval)
}

onMounted(async () => {
  await settingsStore.fetchSettings()
  load()
  startPolling()
})

watch(() => settingsStore.pollInterval, startPolling)

onUnmounted(() => poller.stop())

const router = useRouter()

function formatPrice(v) {
  return v != null ? v.toFixed(2) : '--'
}
</script>

<template>
  <div>
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="color: #909399; font-size: 13px">总市值</div>
          <div style="font-size: 24px; font-weight: 700; margin-top: 4px">
            ¥{{ formatPrice(dashboard.active_market_value) }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="color: #909399; font-size: 13px">总成本</div>
          <div style="font-size: 24px; font-weight: 700; margin-top: 4px">
            ¥{{ formatPrice(dashboard.active_cost) }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="color: #909399; font-size: 13px">总盈亏</div>
          <div
            style="font-size: 24px; font-weight: 700; margin-top: 4px"
            :style="{ color: dashboard.unrealized_profit_loss >= 0 ? '#e53e3e' : '#38a169' }"
          >
            ¥{{ formatPrice(dashboard.unrealized_profit_loss) }}
            <span style="font-size: 14px">({{ formatPrice(dashboard.unrealized_profit_loss_pct) }}%)</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="color: #909399; font-size: 13px">未读告警</div>
          <div
            style="font-size: 24px; font-weight: 700; margin-top: 4px"
            :style="{ color: dashboard.active_alerts_count > 0 ? '#e6a23c' : '#909399' }"
          >
            {{ dashboard.active_alerts_count }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <template #header>
        <span style="font-weight: 600">持仓概览</span>
      </template>
      <el-table :data="dashboard.holdings" stripe empty-text="暂无持仓，去添加一个吧">
        <el-table-column prop="code" label="代码" width="100" />
        <el-table-column prop="name" label="名称" width="150" />
        <el-table-column label="买入价" width="100">
          <template #default="{ row }">¥{{ formatPrice(row.buy_price) }}</template>
        </el-table-column>
        <el-table-column label="当前价" width="100">
          <template #default="{ row }">¥{{ formatPrice(row.current_price) }}</template>
        </el-table-column>
        <el-table-column label="止损价" width="100">
          <template #default="{ row }">¥{{ formatPrice(row.stop_loss_price) }}</template>
        </el-table-column>
        <el-table-column label="盈亏%" width="100">
          <template #default="{ row }">
            <span :style="{ color: row.profit_loss_pct >= 0 ? '#e53e3e' : '#38a169' }">
              {{ formatPrice(row.profit_loss_pct) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="距止损" width="100">
          <template #default="{ row }">
            <el-tag
              :type="row.stop_loss_distance_pct < 3 ? 'danger' : row.stop_loss_distance_pct < 8 ? 'warning' : 'success'"
              size="small"
            >
              {{ formatPrice(row.stop_loss_distance_pct) }}%
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="holdingStatusTag(row.status)" size="small">
              {{ holdingStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="router.push(`/holdings/${row.id}`)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card style="margin-top: 16px">
      <template #header><span style="font-weight: 600">今日告警</span></template>
      <div v-if="dashboard.latest_alert">
        今日共 {{ dashboard.today_alert_count }} 条，最新：
        {{ dashboard.latest_alert.holding_name }}（{{ dashboard.latest_alert.holding_code }}）
        当前价 ¥{{ formatPrice(dashboard.latest_alert.current_price) }}，
        止损价 ¥{{ formatPrice(dashboard.latest_alert.trigger_price) }}
      </div>
      <el-empty v-else description="今日暂无告警" :image-size="60" />
    </el-card>
  </div>
</template>
