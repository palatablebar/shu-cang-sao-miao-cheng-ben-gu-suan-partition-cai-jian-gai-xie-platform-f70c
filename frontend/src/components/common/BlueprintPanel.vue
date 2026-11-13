<script setup lang="ts">
defineProps<{ label: string }>()
</script>

<template>
  <div class="panel">
    <p class="panel-label">{{ label }}</p>
    <slot />
  </div>
</template>
