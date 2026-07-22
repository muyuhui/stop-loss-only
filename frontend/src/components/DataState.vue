<script setup>
defineProps({
  kind: { type: String, default: 'empty' },
  title: { type: String, required: true },
  description: { type: String, default: '' },
  actionLabel: { type: String, default: '' },
})

defineEmits(['action'])
</script>

<template>
  <div class="data-state" :data-state="kind" role="status">
    <div class="data-state__content">
      <span class="data-state__icon" aria-hidden="true">
        {{ kind === 'error' ? '!' : kind === 'loading' ? '…' : '✓' }}
      </span>
      <p class="data-state__title">{{ title }}</p>
      <p v-if="description" class="data-state__description">{{ description }}</p>
      <el-button v-if="actionLabel" type="primary" plain @click="$emit('action')">
        {{ actionLabel }}
      </el-button>
    </div>
  </div>
</template>
