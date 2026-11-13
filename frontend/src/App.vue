<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from './components/common/AppShell.vue'
import ToastBar from './components/common/ToastBar.vue'

const route = useRoute()
const chrome = computed(() => route.name !== 'login')
</script>

<template>
  <AppShell v-if="chrome">
    <router-view />
  </AppShell>
  <router-view v-else />
  <ToastBar />
</template>
