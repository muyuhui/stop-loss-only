<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, LegendComponent, MarkAreaComponent, MarkLineComponent, MarkPointComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import DataState from './DataState.vue'
import { formatAssetMoney } from '../utils/format'
import { buildHistoryChartOption, HISTORY_RANGES, historySummary } from '../utils/historyChart'

echarts.use([LineChart, GridComponent, LegendComponent, TooltipComponent, DataZoomComponent, MarkLineComponent, MarkAreaComponent, MarkPointComponent, CanvasRenderer])

const props = defineProps({
  data: { type: Object, default: null },
  assetType: { type: String, default: 'stock' },
  range: { type: String, default: '3m' },
  loading: Boolean,
  error: { type: String, default: '' },
})
const emit = defineEmits(['range-change', 'retry'])
const chartElement = ref(null)
let chart = null
let observer = null

const points = computed(() => props.data?.points || [])
const summary = computed(() => historySummary(points.value))
const money = value => formatAssetMoney(value, props.assetType)

function renderChart() {
  if (!chartElement.value || !points.value.length) return
  if (!chart) chart = echarts.init(chartElement.value)
  chart.setOption(buildHistoryChartOption(props.data, money), true)
}

watch(() => props.data, async () => { await nextTick(); renderChart() }, { deep: true })
onMounted(() => {
  renderChart()
  observer = new ResizeObserver(() => chart?.resize())
  if (chartElement.value) observer.observe(chartElement.value)
})
onBeforeUnmount(() => {
  observer?.disconnect()
  chart?.dispose()
  observer = null
  chart = null
})
</script>

<template>
  <section class="panel history-panel" aria-labelledby="history-title">
    <header class="panel__header history-header">
      <div><h2 id="history-title" class="panel__title">价格走势</h2><span class="panel-hint">止损线按当前规则计算</span></div>
      <div class="range-switch" aria-label="历史行情时间范围">
        <button v-for="item in HISTORY_RANGES" :key="item.value" type="button" :class="{ active: range === item.value }" :aria-pressed="range === item.value" @click="emit('range-change', item.value)">{{ item.label }}</button>
      </div>
    </header>

    <div v-if="data?.warning || error" class="history-notice" :class="{ 'is-error': error }">
      <span>{{ error || data.warning }}</span><button type="button" @click="emit('retry')">重试</button>
    </div>
    <DataState v-if="loading && !points.length" kind="loading" title="正在加载历史行情" />
    <DataState v-else-if="error && !points.length" kind="error" title="暂时无法加载价格走势" :description="error" action-label="重新加载" @action="emit('retry')" />
    <DataState v-else-if="!points.length" kind="empty" title="暂无历史行情" description="当前范围内没有可展示的交易日数据。" action-label="重新加载" @action="emit('retry')" />
    <template v-else>
      <div class="history-summary" aria-label="历史行情文字摘要">
        <span>最新 <strong class="number">{{ money(summary.latest) }}</strong></span>
        <span>最高 <strong class="number">{{ money(summary.highest) }}</strong></span>
        <span>最低 <strong class="number">{{ money(summary.lowest) }}</strong></span>
        <span>末日止损 <strong class="number">{{ money(summary.stopLoss) }}</strong></span>
      </div>
      <div ref="chartElement" class="history-chart" role="img" :aria-label="`价格走势，共 ${points.length} 个交易日，最新价格 ${money(summary.latest)}，末日止损 ${money(summary.stopLoss)}`" />
      <footer class="history-meta"><span>{{ data.source || '未知来源' }}</span><span>最后交易日 {{ data.last_trade_date || '暂无' }}</span><span v-if="loading">正在刷新…</span></footer>
    </template>
  </section>
</template>

<style scoped>
.history-panel { overflow: hidden; }
.history-header { gap: 16px; }
.history-header > div:first-child { display: grid; gap: 3px; }
.range-switch { display: inline-flex; padding: 3px; background: var(--color-background); border: 1px solid var(--color-border); border-radius: 9px; }
.range-switch button { min-width: 44px; padding: 6px 9px; color: var(--color-text-soft); background: transparent; border: 0; border-radius: 6px; cursor: pointer; }
.range-switch button.active { color: var(--color-brand); background: var(--color-surface); box-shadow: 0 1px 4px rgba(26, 51, 43, .12); font-weight: 600; }
.history-notice { margin: 12px 20px 0; padding: 8px 10px; display: flex; justify-content: space-between; gap: 10px; color: #806022; background: var(--color-warning-soft); border-radius: 8px; font-size: 12px; }
.history-notice.is-error { color: var(--color-danger); background: var(--color-danger-soft); }
.history-notice button { color: inherit; background: none; border: 0; cursor: pointer; font-weight: 600; }
.history-summary { padding: 14px 20px 0; display: flex; flex-wrap: wrap; gap: 10px 22px; color: var(--color-text-soft); font-size: 12px; }
.history-summary strong { margin-left: 4px; color: var(--color-text); }
.history-chart { width: 100%; height: 320px; }
.history-meta { padding: 0 20px 15px; display: flex; flex-wrap: wrap; gap: 8px 18px; color: var(--color-text-muted); font-size: 11px; }
@media (max-width: 767px) {
  .history-header { align-items: stretch; }
  .range-switch { width: 100%; }
  .range-switch button { min-width: 0; flex: 1; }
  .history-summary { padding: 12px 16px 0; display: grid; grid-template-columns: 1fr 1fr; gap: 8px 12px; }
  .history-chart { height: 240px; }
  .history-meta { padding: 0 16px 13px; }
}
</style>
