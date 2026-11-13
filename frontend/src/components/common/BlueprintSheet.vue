<script setup lang="ts">
defineProps<{ title: string; code: string; note?: string }>()
</script>

<template>
  <section class="sheet">
    <div class="sheet-head">
      <div>
        <h2>{{ title }}</h2>
        <p v-if="note" class="hint" style="margin: 6px 0 0">{{ note }}</p>
      </div>
      <span class="sheet-code">{{ code }}</span>
    </div>
    <slot />
  </section>
</template>
