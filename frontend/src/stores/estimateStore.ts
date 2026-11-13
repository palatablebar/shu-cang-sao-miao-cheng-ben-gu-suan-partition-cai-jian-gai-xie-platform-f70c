import { ref } from 'vue'
import { defineStore } from 'pinia'
import { createEstimate, fetchEstimate, fetchEstimates } from '../api/estimates'
import type { EstimateRun } from '../types/estimate'

export const useEstimateStore = defineStore('estimates', () => {
  const runs = ref<EstimateRun[]>([])
  const active = ref<EstimateRun | null>(null)
  const loading = ref(false)
  const error = ref('')

  async function load() {
    loading.value = true
    try {
      const page = await fetchEstimates(1, 8)
      runs.value = page.items
      active.value = page.items[0] ?? null
    } catch (err) {
      error.value = (err as Error).message
    } finally {
      loading.value = false
    }
  }

  async function run(scope: 'all' | 'table' | 'blocked' = 'all', scopeValue?: string, note = '') {
    loading.value = true
    error.value = ''
    try {
      const created = await createEstimate(scope, scopeValue, note)
      active.value = created
      // Celery 异步执行：轮询到 completed/failed 为止（最多 ~20s）
      for (let attempt = 0; attempt < 40; attempt += 1) {
        if (created.status === 'completed' || created.status === 'failed') break
        await new Promise((resolve) => setTimeout(resolve, 500))
        const latest = await fetchEstimate(created.id)
        active.value = latest
        created.status = latest.status
        created.query_count = latest.query_count
        created.blocked_count = latest.blocked_count
        created.total_scan_bytes = latest.total_scan_bytes
        created.monthly_projected_cost_cny = latest.monthly_projected_cost_cny
        if (latest.status === 'completed' || latest.status === 'failed') break
      }
      await load()
      return active.value
    } catch (err) {
      error.value = (err as Error).message
      throw err
    } finally {
      loading.value = false
    }
  }

  return { runs, active, loading, error, load, run }
})
