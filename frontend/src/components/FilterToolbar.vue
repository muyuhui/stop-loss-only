<script setup>
const props = defineProps({ query: Object, total: Number })
const emit = defineEmits(['update:query', 'reset'])
function update(key, value) { emit('update:query', { ...props.query, [key]: value, page: 1 }) }
</script>

<template>
  <form class="filter-toolbar" @submit.prevent>
    <el-input :model-value="query.search" clearable placeholder="搜索名称或代码" aria-label="搜索持仓" @update:model-value="value => update('search', value)" />
    <el-select :model-value="query.lifecycle" aria-label="生命周期筛选" @update:model-value="value => update('lifecycle', value)"><el-option label="全部生命周期" value="" /><el-option label="开放" value="open" /><el-option label="已关闭" value="closed" /></el-select>
    <el-select :model-value="query.risk" aria-label="风险状态筛选" @update:model-value="value => update('risk', value)"><el-option label="全部风险状态" value="" /><el-option label="正常" value="normal" /><el-option label="已触发" value="triggered" /><el-option label="已确认" value="acknowledged" /></el-select>
    <el-select :model-value="query.sort" aria-label="排序" @update:model-value="value => update('sort', value)"><el-option label="最新优先" value="newest" /><el-option label="风险优先" value="risk" /><el-option label="名称" value="name" /></el-select>
    <el-button text @click="emit('reset')">重置</el-button><small v-if="total !== undefined">{{ total }} 条</small>
  </form>
</template>

<style scoped>
.filter-toolbar { display: grid; grid-template-columns: minmax(180px, 2fr) repeat(3, minmax(130px, 1fr)) auto auto; gap: 10px; align-items: center; padding: 12px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 10px; }.filter-toolbar small { color: var(--color-text-muted); white-space: nowrap; }
@media (max-width: 767px) { .filter-toolbar { grid-template-columns: 1fr 1fr; }.filter-toolbar :first-child { grid-column: 1 / -1; } }
</style>
