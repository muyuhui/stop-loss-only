<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import HoldingForm from '../components/HoldingForm.vue'
import { holdingStatusLabel, holdingStatusTag } from '../utils/holdingStatus'

const holdings = ref([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const dialogVisible = ref(false)
const router = useRouter()

async function load() {
  const res = await api.get('/holdings', { params: { page: page.value, size: size.value } })
  holdings.value = res.data.items || []
  total.value = res.data.total || 0
}

function format(v) {
  return v != null ? v.toFixed(2) : '--'
}

function onCreated() {
  dialogVisible.value = false
  load()
}

onMounted(load)
</script>

<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h3 style="margin: 0">持仓管理</h3>
      <el-button type="primary" @click="dialogVisible = true">新增持仓</el-button>
    </div>

    <el-table :data="holdings" stripe empty-text="暂无持仓">
      <el-table-column prop="code" label="代码" width="100" />
      <el-table-column prop="name" label="名称" width="150" />
      <el-table-column label="买入价" width="110">
        <template #default="{ row }">¥{{ format(row.buy_price) }}</template>
      </el-table-column>
      <el-table-column prop="quantity" label="数量" width="90" />
      <el-table-column label="当前价" width="110">
        <template #default="{ row }">¥{{ format(row.current_price) }}</template>
      </el-table-column>
      <el-table-column label="止损价" width="110">
        <template #default="{ row }">¥{{ format(row.stop_loss_price) }}</template>
      </el-table-column>
      <el-table-column label="盈亏%" width="100">
        <template #default="{ row }">
          <span :style="{ color: row.profit_loss_pct >= 0 ? '#e53e3e' : '#38a169' }">
            {{ format(row.profit_loss_pct) }}%
          </span>
        </template>
      </el-table-column>
      <el-table-column label="距止损" width="100">
        <template #default="{ row }">
          <el-tag
            :type="row.stop_loss_distance_pct < 3 ? 'danger' : row.stop_loss_distance_pct < 8 ? 'warning' : 'success'"
            size="small"
          >
            {{ format(row.stop_loss_distance_pct) }}%
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="止损方式" width="90">
        <template #default="{ row }">
          {{ row.stop_loss_method === 'fixed' ? '固定价' : row.stop_loss_method === 'percentage' ? '百分比' : '追踪' }}
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

    <el-pagination
      v-if="total > size"
      v-model:current-page="page"
      v-model:page-size="size"
      :total="total"
      layout="prev, pager, next, total"
      style="margin-top: 16px; justify-content: flex-end"
      @current-change="load"
    />

    <el-dialog v-model="dialogVisible" title="新增持仓" width="560px" destroy-on-close>
      <HoldingForm @success="onCreated" @cancel="dialogVisible = false" />
    </el-dialog>
  </div>
</template>
