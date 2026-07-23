<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import DataState from '../components/DataState.vue'
import StatusBanner from '../components/StatusBanner.vue'
import { formatDecimal, formatMoney } from '../utils/format'

const route = useRoute(); const router = useRouter(); const position = ref(null); const history = ref(null); const error = ref(''); const loading = ref(true); const saving = ref(false)
const closeForm = reactive({ quantity: '', close_price: '', fees: '0', taxes: '0' }); const lotForm = reactive({ quantity: '', unit_cost: '', fees: '0', taxes: '0' }); const rearmForm = reactive({ method: 'fixed', value: '', reason: '' }); const acknowledgeReason = ref('')
const closed = computed(() => position.value?.lifecycle_status === 'closed'); const triggered = computed(() => position.value?.risk_status === 'triggered' || position.value?.risk_status === 'acknowledged')
async function load() { loading.value = true; error.value = ''; try { const [detail, timeline] = await Promise.all([api.get(`/positions/${route.params.id}`), api.get(`/positions/${route.params.id}/history`)]); position.value = detail.data; history.value = timeline.data } catch { error.value = '无法读取持仓详情。' } finally { loading.value = false } }
async function submit(path, body) { saving.value = true; try { await api.post(`/positions/${route.params.id}${path}`, body); await load() } catch { error.value = '操作未完成，请检查状态或输入。' } finally { saving.value = false } }
onMounted(load)
</script>

<template>
  <section aria-labelledby="position-title">
    <div class="page-heading"><div><el-button text @click="router.back()">返回持仓</el-button><h1 id="position-title" class="page-title">{{ position?.name || '持仓详情' }}</h1><p v-if="position" class="page-subtitle">{{ position.code }} · {{ position.asset_type }} · {{ position.lifecycle_status }}</p></div><el-button v-if="!closed" :loading="loading" @click="load">刷新</el-button></div>
    <DataState v-if="loading" kind="loading" title="正在加载持仓" /><DataState v-else-if="error && !position" kind="error" title="无法加载详情" :description="error" action-label="重试" @action="load" />
    <div v-else-if="position" class="detail-stack">
      <StatusBanner v-if="error" kind="warning" title="上一次操作未完成" :detail="error" />
      <StatusBanner :kind="triggered ? 'danger' : position.is_actionable ? 'success' : 'warning'" :title="triggered ? '风险需要处置' : position.is_actionable ? '行情可行动' : '行情不可行动'" :detail="`行情状态：${position.quote_state}；版本：${position.version}`" />
      <section class="metric-grid"><article><small>当前价</small><strong class="number">{{ formatMoney(position.current_price) }}</strong></article><article><small>剩余成本</small><strong class="number">{{ formatMoney(position.remaining_cost) }}</strong></article><article><small>剩余数量</small><strong class="number">{{ formatDecimal(position.remaining_quantity, 6) }}</strong></article><article><small>止损价</small><strong class="number">{{ formatMoney(position.active_stop_rule?.stop_price) }}</strong></article></section>
      <section v-if="closed" class="panel review"><h2>复盘模式</h2><p>该持仓已关闭，页面只展示已实现结果、批次与事件，不提供刷新、止损或处置操作。</p></section>
      <template v-else>
        <section v-if="triggered" class="panel action-panel"><h2>风险处置</h2><div class="action-grid"><el-input v-model="acknowledgeReason" placeholder="确认原因" aria-label="风险确认原因" /><el-button :loading="saving" @click="submit('/acknowledge', { expected_version: position.version, reason: acknowledgeReason })">确认风险</el-button><el-input v-model="rearmForm.reason" placeholder="重新布防原因" aria-label="重新布防原因" /><el-select v-model="rearmForm.method"><el-option label="固定价格" value="fixed" /><el-option label="百分比" value="percentage" /><el-option label="移动止损" value="trailing" /></el-select><el-input v-model="rearmForm.value" placeholder="新规则值" /><el-button :loading="saving" @click="submit('/rearm', { ...rearmForm, expected_version: position.version })">重新布防</el-button></div></section>
        <section class="panel action-panel"><h2>批次与平仓</h2><div class="action-grid"><el-input v-model="lotForm.quantity" placeholder="加仓数量" /><el-input v-model="lotForm.unit_cost" placeholder="单位成本" /><el-button :loading="saving" @click="submit('/lots', lotForm)">添加批次</el-button><el-input v-model="closeForm.quantity" placeholder="平仓数量" /><el-input v-model="closeForm.close_price" placeholder="平仓价格" /><el-button type="warning" :loading="saving" @click="submit('/close', closeForm)">记录平仓</el-button></div></section>
      </template>
      <section class="panel"><h2>批次</h2><p v-if="!history?.quotes?.length">暂无可展示的行情序列。</p><p v-else>已保留 {{ history.quotes.length }} 个行情点；关键事件不会因下采样而丢失。</p><h2>事件时间线</h2><ol><li v-for="item in history?.items" :key="item.id"><strong>{{ item.type }}</strong> <span>{{ item.occurred_at }}</span></li></ol></section>
    </div>
  </section>
</template>

<style scoped>
.detail-stack { display: grid; gap: 14px; }.metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }.metric-grid article { display: grid; gap: 5px; padding: 15px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 10px; }.metric-grid small { color: var(--color-text-muted); }.action-panel { padding: 16px; }.action-panel h2, .review h2 { margin-top: 0; }.action-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }.review { padding: 16px; } ol { display: grid; gap: 8px; padding-left: 22px; } li span { color: var(--color-text-muted); font-size: 12px; }
@media (max-width: 767px) { .metric-grid, .action-grid { grid-template-columns: 1fr; } }
</style>
