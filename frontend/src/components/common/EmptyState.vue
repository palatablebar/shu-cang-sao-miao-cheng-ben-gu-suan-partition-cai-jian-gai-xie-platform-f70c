<script setup lang="ts">
defineProps<{ title: string; hint?: string; action?: string }>()
defineEmits<{ (e: 'action'): void }>()
</script>

<template>
  <div class="empty">
    <div class="empty-mark">⌗</div>
    <p class="empty-title">{{ title }}</p>
    <p v-if="hint" class="hint">{{ hint }}</p>
    <button v-if="action" class="btn" type="button" @click="$emit('action')">{{ action }}</button>
  </div>
</template>

<style scoped>
.empty {
  border: 1px dashed var(--rule-strong);
  padding: var(--space-6) var(--space-4);
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  align-items: flex-start;
  max-width: 560px;
}
.empty-mark {
  font-family: var(--font-mono);
  font-size: 2rem;
  color: var(--plate-600);
  line-height: 1;
}
.empty-title {
  margin: 0;
  font-size: var(--step-1);
}
</style>
