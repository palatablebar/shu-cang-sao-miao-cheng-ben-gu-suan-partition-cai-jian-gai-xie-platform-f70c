import { ref } from 'vue'
import { defineStore } from 'pinia'
import {
  adoptRewrite,
  fetchSuggestion,
  fetchSuggestions,
  generateRewrite,
  reevaluateRewrite,
} from '../api/rewrites'
import type { RewriteDetail, RewriteReevaluation, RewriteSuggestion } from '../types/rewrite'

export const useRewriteStore = defineStore('rewrites', () => {
  const items = ref<RewriteSuggestion[]>([])
  const detail = ref<RewriteDetail | null>(null)
  const reevaluation = ref<RewriteReevaluation | null>(null)
  const loading = ref(false)
  const error = ref('')

  async function load() {
    loading.value = true
    error.value = ''
    try {
      const page = await fetchSuggestions(undefined, 30)
      items.value = page.items
      if (!detail.value && page.items.length) {
        await select(page.items[0].id)
      }
    } catch (err) {
      error.value = (err as Error).message
    } finally {
      loading.value = false
    }
  }

  async function select(id: number) {
    loading.value = true
    try {
      detail.value = await fetchSuggestion(id)
      reevaluation.value = null
      return detail.value
    } catch (err) {
      error.value = (err as Error).message
      return null
    } finally {
      loading.value = false
    }
  }

  async function generate(queryId: number) {
    const created = await generateRewrite(queryId)
    await load()
    detail.value = created
    return created
  }

  async function reevaluate(id: number) {
    reevaluation.value = await reevaluateRewrite(id)
    await load()
    return reevaluation.value
  }

  async function adopt(id: number) {
    const updated = await adoptRewrite(id)
    const index = items.value.findIndex((item) => item.id === id)
    if (index >= 0) items.value[index] = { ...items.value[index], status: updated.status }
    if (detail.value?.id === id) detail.value.status = updated.status
    return updated
  }

  return { items, detail, reevaluation, loading, error, load, select, generate, reevaluate, adopt }
})
