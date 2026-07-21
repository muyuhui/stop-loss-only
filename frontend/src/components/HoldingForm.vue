<script setup>
import { ref, reactive } from 'vue'
import api from '../api'

const emit = defineEmits(['success', 'cancel'])

const formRef = ref(null)
const form = reactive({
  code: '',
  name: '',
  type: 'stock',
  buy_price: null,
  quantity: null,
  buy_date: '',
  stop_loss_method: 'percentage',
  stop_loss_value: null,
})

const rules = {
  code: [{ required: true, message: '请输入代码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  buy_price: [{ required: true, message: '请输入买入价', trigger: 'blur' }],
  quantity: [{ required: true, message: '请输入数量', trigger: 'blur' }],
  buy_date: [{ required: true, message: '请选择买入日期', trigger: 'change' }],
  stop_loss_value: [{ required: true, message: '请输入止损参数', trigger: 'blur' }],
}

function stopLossPlaceholder() {
  if (form.stop_loss_method === 'fixed') return '止损价格，如 9.00'
  if (form.stop_loss_method === 'percentage') return '止损百分比，如 10（表示-10%）'
  return '回落百分比，如 10（从最高点回落10%止损）'
}

async function submit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    await api.post('/holdings', {
      ...form,
      buy_price: Number(form.buy_price),
      quantity: Number(form.quantity),
      stop_loss_value: Number(form.stop_loss_value),
    })
    emit('success')
  } catch { /* api interceptor handles */ }
}
</script>

<template>
  <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
    <el-form-item label="类型" prop="type">
      <el-radio-group v-model="form.type">
        <el-radio value="stock">股票</el-radio>
        <el-radio value="fund">基金</el-radio>
      </el-radio-group>
    </el-form-item>
    <el-row :gutter="16">
      <el-col :span="12">
        <el-form-item label="代码" prop="code">
          <el-input v-model="form.code" placeholder="000001 / 510050" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="平安银行 / 上证50ETF" />
        </el-form-item>
      </el-col>
    </el-row>
    <el-row :gutter="16">
      <el-col :span="12">
        <el-form-item label="买入价" prop="buy_price">
          <el-input-number v-model="form.buy_price" :precision="2" :min="0.01" style="width: 100%" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="数量" prop="quantity">
          <el-input-number v-model="form.quantity" :min="1" style="width: 100%" />
        </el-form-item>
      </el-col>
    </el-row>
    <el-form-item label="买入日期" prop="buy_date">
      <el-date-picker v-model="form.buy_date" type="date" placeholder="选择日期" style="width: 100%" value-format="YYYY-MM-DD" />
    </el-form-item>
    <el-form-item label="止损方式" prop="stop_loss_method">
      <el-select v-model="form.stop_loss_method" style="width: 100%">
        <el-option label="百分比止损" value="percentage" />
        <el-option label="固定价格止损" value="fixed" />
        <el-option label="移动止损" value="trailing" />
      </el-select>
    </el-form-item>
    <el-form-item label="止损参数" prop="stop_loss_value">
      <el-input-number
        v-model="form.stop_loss_value"
        :precision="form.stop_loss_method === 'fixed' ? 2 : 1"
        :min="0.01"
        style="width: 100%"
        :placeholder="stopLossPlaceholder()"
      />
      <span style="color: #909399; font-size: 12px; margin-left: 4px">
        {{ form.stop_loss_method === 'fixed' ? '元' : '%' }}
      </span>
    </el-form-item>
    <el-form-item>
      <el-button type="primary" @click="submit">保存</el-button>
      <el-button @click="emit('cancel')">取消</el-button>
    </el-form-item>
  </el-form>
</template>
