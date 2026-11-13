<script setup lang="ts">
import { useFeedback } from '../../hooks/useFeedback'

const { message, kind } = useFeedback()
</script>

<template>
  <Transition name="fade-slide">
    <div v-if="message" class="toast" :class="`toast--${kind}`" role="status">
      <span class="mono">{{ kind === 'ok' ? 'OK' : kind === 'bad' ? 'ERR' : 'NOTE' }}</span>
      <span>{{ message }}</span>
    </div>
  </Transition>
</template>

<style scoped>
.toast {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 50;
  display: flex;
  gap: var(--space-3);
  align-items: baseline;
  border: 1px solid var(--rule-strong);
  background: oklch(0.28 0.05 252 / 0.97);
  padding: 10px 16px;
  max-width: 460px;
  font-size: var(--step--1);
  box-shadow: 0 12px 30px oklch(0.16 0.04 254 / 0.5);
}
.toast--ok {
  border-color: oklch(0.75 0.09 155 / 0.6);
  color: oklch(0.9 0.05 150);
}
.toast--bad {
  border-color: oklch(0.67 0.14 27 / 0.7);
  color: oklch(0.9 0.06 35);
}
.toast--info {
  color: var(--cream-dim);
}
.mono {
  letter-spacing: 0.1em;
  color: var(--cream-mute);
}
</style>
