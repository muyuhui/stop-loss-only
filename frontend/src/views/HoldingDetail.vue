<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const route = useRoute()
const router = useRouter()
const holding = ref({})
const editMode = ref(false)
const editForm = reactive({
  name: '',
  stop_loss_method: '',
  stop_loss_value: null,
})
const closePrice = ref(null)

async function load() {
  const res = await api.get(`/holdings/${route.params.id}`)
  holding.value = res.data
  editForm.name = res.data.name
  editForm.stop_loss_method = res.data.stop_loss_method
  editForm.stop_loss_value = res.data.stop_loss_value
}

function format(v) {
  return v != null ? v.toFixed(2) : '--'
}

async function saveEdit() {
  await api.put(`/holdings/${route.params.id}`, {
    name: editForm.name,
    stop_loss_method: editForm.stop_loss_method,
    stop_loss_value: Number(editForm.stop_loss_value),
  })
  ElMessage.success('止损参数已更新')
  editMode.value = false
  await load()
}

async function closeHolding() {
  try {
    await ElMessageBox.confirm('确认手动平仓？', '确认', { type: 'warning' })
    await api.post(`/holdings/${route.params.id}/close`, {
      close_price: Number(closePrice.value),
    })
    ElMessage.success('已平仓')
    await load()
  } catch { /* cancelled */ }
}

async function deleteHolding() {
  try {
    await ElMessageBox.confirm('确认删除该持仓？此操作不可撤销。', '确认删除', { type: 'warning' })
    await api.delete(`/holdings/${route.params.id}`)
    ElMessage.success('已删除')
    router.push('/holdings')
  } catch { /* cancelled */ }
}

function methodLabel(m) {
  if (m === 'fixed') return '固定价格'
  if (m === 'percentage') return '百分比'
  if (m === 'trailing') return '移动（追踪）'
  return m
}

onMounted(load)
</script>

<template>
  <div v-if="holding.id">
    <el-page-header @back="router.push('/holdings')" :content="holding.name" style="margin-bottom: 20px" />

    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="color: #909399; font-size: 13px">代码</div>
          <div style="font-size: 18px; font-weight: 600; margin-top: 4px">{{ holding.code }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="color: #909399; font-size: 13px">类型</div>
          <div style="font-size: 18px; font-weight: 600; margin-top: 4px">
            {{ holding.type === 'stock' ? '股票' : '基金' }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="color: #909399; font-size: 13px">买入价 × 数量</div>
          <div style="font-size: 18px; font-weight: 600; margin-top: 4px">
            ¥{{ format(holding.buy_price) }} × {{ holding.quantity }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="color: #909399; font-size: 13px">状态</div>
          <div style="font-size: 18px; font-weight: 600; margin-top: 4px">
            <el-tag :type="holding.status === 'holding' ? 'success' : 'info'">
              {{ holding.status === 'holding' ? '持有中' : '已止损' }}
            </el-tag>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-bottom: 16px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-weight: 600">价格信息</span>
          <div>
            <el-button size="small" type="primary" link @click="router.push('/settings')">
              手动刷新价格
            </el-button>
          </div>
        </div>
      </template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="买入价">¥{{ format(holding.buy_price) }}</el-descriptions-item>
        <el-descriptions-item label="当前价">¥{{ format(holding.current_price) }}</el-descriptions-item>
        <el-descriptions-item label="历史最高价">¥{{ format(holding.highest_price) }}</el-descriptions-item>
        <el-descriptions-item label="止损价">¥{{ format(holding.stop_loss_price) }}</el-descriptions-item>
        <el-descriptions-item label="止损方式">{{ methodLabel(holding.stop_loss_method) }}</el-descriptions-item>
        <el-descriptions-item label="止损参数">
          {{ holding.stop_loss_value }}{{ holding.stop_loss_method === 'fixed' ? '元' : '%' }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card style="margin-bottom: 16px" v-if="!editMode">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-weight: 600">止损设置</span>
          <el-button size="small" type="primary" @click="editMode = true" v-if="holding.status === 'holding'">
            修改
          </el-button>
        </div>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="止损方式">{{ methodLabel(holding.stop_loss_method) }}</el-descriptions-item>
        <el-descriptions-item label="止损参数">
          {{ holding.stop_loss_value }}{{ holding.stop_loss_method === 'fixed' ? '元' : '%' }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card style="margin-bottom: 16px" v-if="editMode">
      <template #header>
        <span style="font-weight: 600">修改止损</span>
      </template>
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="名称">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="止损方式">
          <el-select v-model="editForm.stop_loss_method" style="width: 200px">
            <el-option label="百分比止损" value="percentage" />
            <el-option label="固定价格止损" value="fixed" />
            <el-option label="移动止损" value="trailing" />
          </el-select>
        </el-form-item>
        <el-form-item label="止损参数">
          <el-input-number
            v-model="editForm.stop_loss_value"
            :precision="editForm.stop_loss_method === 'fixed' ? 2 : 1"
            :min="0.01"
          />
          <span style="color: #909399; font-size: 12px; margin-left: 4px">
            {{ editForm.stop_loss_method === 'fixed' ? '元' : '%' }}
          </span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveEdit">保存修改</el-button>
          <el-button @click="editMode = false">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="holding.status === 'holding'">
      <template #header>
        <span style="font-weight: 600">操作</span>
      </template>
      <el-row :gutter="16">
        <el-col :span="12">
          <div style="display: flex; align-items: center; gap: 8px">
            <span>平仓价：</span>
            <el-input-number v-model="closePrice" :precision="2" :min="0.01" style="width: 140px" />
            <el-button type="warning" @click="closeHolding" :disabled="!closePrice">手动平仓</el-button>
          </div>
        </el-col>
        <el-col :span="12" style="text-align: right">
          <el-button type="danger" @click="deleteHolding">删除持仓</el-button>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>
