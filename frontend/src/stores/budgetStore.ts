import { ref } from 'vue'
import { defineStore } from 'pinia'
import { fetchAuditLogs, fetchBudgetOverview, updatePolicy } from '../api/budget'
import type { AuditLog, BudgetOverview, Policy } from '../types/budget'

export const useBudgetStore = defineStore('budget', () => {
  const overview = ref<BudgetOverview | null>(null)
  const policies = ref<Policy[]>([])
  const audit = ref<AuditLog[]>([])
  const loading = ref(false)
  const error = ref('')

  async function load() {
    loading.value = true
    error.value = ''
    try {
      const data = await fetchBudgetOverview()
      overview.value = data
      policies.value = data.policies
    } catch (err) {
      error.value = (err as Error).message
    } finally {
      loading.value = false
    }
  }

  async function loadAudit() {
    try {
      const page = await fetchAuditLogs(14)
      audit.value = page.items
    } catch {
      audit.value = []
    }
  }

  async function savePolicy(
    id: number,
    payload: {
      name?: string
      monthly_budget_cny?: number
      warn_ratio?: number
      critical_ratio?: number
      scan_alert_gib?: number
      note?: string
    },
  ) {
    const updated = await updatePolicy(id, payload)
    policies.value = policies.value.map((policy) => (policy.id === id ? updated : policy))
    await load()
    return updated
  }

  return { overview, policies, audit, loading, error, load, loadAudit, savePolicy }
})
