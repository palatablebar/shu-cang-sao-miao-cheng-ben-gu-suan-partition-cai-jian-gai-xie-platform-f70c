<script setup lang="ts">
defineProps<{ value: string; unit?: string; caption: string }>()
</script>

<template>
  <div class="metric">
    <p class="metric-value mono-num">
      {{ value }}<span v-if="unit" class="metric-unit">{{ unit }}</span>
    </p>
    <div class="dimension"><span>{{ caption }}</span></div>
  </div>
</template>

<style scoped>
.metric {
  min-width: 0;
}
.metric-value {
  margin: 0;
  font-size: var(--step-3);
  line-height: 1.05;
  color: var(--cream);
  letter-spacing: -0.01em;
}
.metric-unit {
  font-size: var(--step-0);
  color: var(--cream-mute);
  margin-left: 6px;
  letter-spacing: 0.06em;
}
.dimension {
  margin-top: var(--space-4);
  margin-bottom: 0;
}
.dimension > span {
  top: calc(-1.05em + 0px);
  background: var(--plate-850);
  padding: 0 8px;
}
</style>
