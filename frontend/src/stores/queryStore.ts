import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  fetchQueries,
  fetchQueryDetail,
  fetchQueryStats,
  fetchRanking,
  importQueryPack,
  type QueryFilters,
} from '../api/queries'
import type { QueryDetail, QueryListItem, QueryStats } from '../types/query'

export const useQueryStore = defineStore('queries', () => {
  const items = ref<QueryListItem[]>([])
  const total = ref(0)
  const ranking = ref<QueryListItem[]>([])
  const stats = ref<QueryStats | null>(null)
  const detail = ref<QueryDetail | null>(null)
  const loading = ref(false)
  const error = ref('')
  const filters = ref<QueryFilters>({ page: 1, page_size: 20, sort: 'scan_bytes', order: 'desc' })

  async function load() {
    loading.value = true
    error.value = ''
    try {
      const page = await fetchQueries(filters.value)
      items.value = page.items
      total.value = page.total
    } catch (err) {
      error.value = (err as Error).message
    } finally {
      loading.value = false
    }
  }

  async function loadOverview() {
    try {
      const [top, summary] = await Promise.all([fetchRanking(8), fetchQueryStats()])
      ranking.value = top
      stats.value = summary
    } catch (err) {
      error.value = (err as Error).message
    }
  }

  async function loadDetail(id: number) {
    loading.value = true
    error.value = ''
    try {
      detail.value = await fetchQueryDetail(id)
      return detail.value
    } catch (err) {
      error.value = (err as Error).message
      return null
    } finally {
      loading.value = false
    }
  }

  async function importPack() {
    const result = await importQueryPack()
    await Promise.all([load(), loadOverview()])
    return result
  }

  function setFilter<K extends keyof QueryFilters>(key: K, value: QueryFilters[K]) {
    filters.value = { ...filters.value, [key]: value, page: key === 'page' ? (value as number) : 1 }
  }

  const blockedCount = computed(() => stats.value?.blocked_count ?? 0)

  return {
    items,
    total,
    ranking,
    stats,
    detail,
    loading,
    error,
    filters,
    blockedCount,
    load,
    loadOverview,
    loadDetail,
    importPack,
    setFilter,
  }
})
