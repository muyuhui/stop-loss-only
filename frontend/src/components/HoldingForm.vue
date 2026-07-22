<script setup>
import { computed, reactive, ref } from 'vue'
import api from '../api'
import { holdingPayload, priceInputMeta, stopLossInputMeta } from '../utils/holdingForm'

const emit = defineEmits(['success', 'cancel'])
const formRef = ref(null)
const submitting = ref(false)
const form = reactive({
  code: '', name: '', type: 'stock', buy_price: null, quantity: null,
  buy_date: '', stop_loss_method: 'percentage', stop_loss_value: null,
})
const priceMeta = computed(() => priceInputMeta(form.type))
const stopLossMeta = computed(() => stopLossInputMeta(form.stop_loss_method, form.type))

const rules = {
  code: [{ required: true, message: '请输入代码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  buy_price: [{ required: true, message: '请输入买入价', trigger: 'blur' }],
  quantity: [{ required: true, message: '请输入数量', trigger: 'blur' }],
  buy_date: [{ required: true, message: '请选择买入日期', trigger: 'change' }],
  stop_loss_value: [{ required: true, message: '请输入止损参数', trigger: 'blur' }],
}

async function submit() {
  if (submitting.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    await api.post('/holdings', holdingPayload(form))
    emit('success')
  } catch {
    // API interceptor displays the error.
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="holding-form" @submit.prevent="submit">
    <el-form-item label="资产类型" prop="type">
      <el-radio-group v-model="form.type">
        <el-radio value="stock">股票</el-radio>
        <el-radio value="fund">基金</el-radio>
      </el-radio-group>
    </el-form-item>

    <div class="form-grid">
      <el-form-item label="代码" prop="code">
        <el-input v-model="form.code" placeholder="例如 000001" />
      </el-form-item>
      <el-form-item label="名称" prop="name">
        <el-input v-model="form.name" placeholder="例如 平安银行" />
      </el-form-item>
      <el-form-item label="买入价" prop="buy_price">
        <el-input-number v-model="form.buy_price" :precision="priceMeta.precision" :step="priceMeta.step" :min="priceMeta.min" :controls="false" />
      </el-form-item>
      <el-form-item label="数量" prop="quantity">
        <el-input-number v-model="form.quantity" :step="1" :min="1" :controls="false" />
      </el-form-item>
    </div>

    <el-form-item label="买入日期" prop="buy_date">
      <el-date-picker v-model="form.buy_date" type="date" placeholder="选择日期" value-format="YYYY-MM-DD" />
    </el-form-item>

    <div class="form-grid form-grid--stop">
      <el-form-item label="止损方式" prop="stop_loss_method">
        <el-select v-model="form.stop_loss_method">
          <el-option label="百分比止损" value="percentage" />
          <el-option label="固定价格止损" value="fixed" />
          <el-option label="移动止损" value="trailing" />
        </el-select>
      </el-form-item>
      <el-form-item :label="`止损参数（${stopLossMeta.unit}）`" prop="stop_loss_value">
        <el-input-number v-model="form.stop_loss_value" :precision="stopLossMeta.precision" :step="stopLossMeta.step" :min="stopLossMeta.min" :controls="false" />
      </el-form-item>
    </div>
    <p class="form-help">{{ stopLossMeta.help }}</p>

    <div class="form-actions">
      <el-button @click="emit('cancel')">取消</el-button>
      <el-button type="primary" native-type="submit" :loading="submitting">保存持仓</el-button>
    </div>
  </el-form>
</template>

<style scoped>
.holding-form :deep(.el-form-item) { margin-bottom: 16px; }
.holding-form :deep(.el-input-number), .holding-form :deep(.el-date-editor), .holding-form :deep(.el-select) { width: 100%; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 16px; }
.form-help { margin: -6px 0 20px; color: var(--color-text-soft); font-size: 12px; line-height: 1.6; }
.form-actions { display: flex; justify-content: flex-end; gap: 8px; }
@media (max-width: 767px) { .form-grid { grid-template-columns: 1fr; } .form-actions { position: sticky; bottom: 0; padding-top: 12px; background: var(--color-surface); } .form-actions .el-button { flex: 1; } }
</style>
