<script setup lang="ts">
defineProps<{ message: string }>()
defineEmits<{ (e: 'retry'): void }>()
</script>

<template>
  <div class="notice" role="alert">
    <span class="mono" style="letter-spacing: 0.1em">ERR</span>
    <div style="flex: 1">
      <p style="margin: 0">{{ message }}</p>
      <button class="btn btn--ghost" type="button" style="margin-top: 8px" @click="$emit('retry')">重试</button>
    </div>
  </div>
</template>
