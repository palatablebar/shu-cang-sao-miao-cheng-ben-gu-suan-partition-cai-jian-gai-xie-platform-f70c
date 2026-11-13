<script setup lang="ts">
defineProps<{ label: string; tone?: 'rust' | 'mute' }>()
</script>

<template>
  <span class="anno" :class="tone === 'mute' ? 'anno--mute' : ''">
    <svg viewBox="0 0 46 14" width="46" height="14" aria-hidden="true">
      <path d="M0 12 L30 4" fill="none" stroke="currentColor" stroke-width="1" />
      <path d="M30 4 L24 2.4 M30 4 L26.5 8.6" fill="none" stroke="currentColor" stroke-width="1" />
    </svg>
    <span>{{ label }}</span>
  </span>
</template>

<style scoped>
.anno {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-family: var(--font-mono);
  font-size: 0.68rem;
  color: var(--rust);
  letter-spacing: 0.04em;
}
.anno--mute {
  color: var(--cream-mute);
}
</style>
