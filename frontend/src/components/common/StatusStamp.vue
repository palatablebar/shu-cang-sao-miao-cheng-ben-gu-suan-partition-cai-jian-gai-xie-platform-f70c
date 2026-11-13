<script setup lang="ts">
import { computed } from 'vue'
import { tone3 } from '../../utils/format'

const props = defineProps<{ label: string; level?: string; tone?: 'ok' | 'warn' | 'bad' | 'info' | 'mute' }>()
const resolved = computed(() => props.tone ?? tone3(props.level))
</script>

<template>
  <span class="stamp" :class="`stamp--${resolved}`">{{ label }}</span>
</template>
