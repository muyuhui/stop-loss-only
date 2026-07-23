<script setup>
defineProps({ kind: { type: String, default: 'info' }, title: String, detail: String })
</script>

<template>
  <aside class="status-banner" :class="`status-banner--${kind}`" role="status" aria-live="polite">
    <strong>{{ title }}</strong><span v-if="detail">{{ detail }}</span>
  </aside>
</template>

<style scoped>
.status-banner { display: grid; gap: 3px; padding: 11px 14px; border: 1px solid var(--color-border); border-left: 4px solid var(--color-text-muted); border-radius: 9px; background: var(--color-surface); font-size: 13px; }
.status-banner span { color: var(--color-text-soft); font-size: 12px; }
.status-banner--warning { border-left-color: var(--color-warning); }.status-banner--danger { border-left-color: var(--color-danger); }.status-banner--success { border-left-color: var(--color-success); }
</style>
