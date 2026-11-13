import { apiGet, apiPost, apiPut } from './http'
import type { AuditLog, BudgetOverview, Policy } from '../types/budget'
import type { Page } from '../types/api'

export function fetchBudgetOverview() {
  return apiGet<BudgetOverview>('/budget/overview')
}

export function fetchPolicies() {
  return apiGet<Policy[]>('/budget/policies')
}

export function updatePolicy(
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
  return apiPut<Policy>(`/budget/policies/${id}`, payload)
}

export function createPolicy(payload: Record<string, unknown>) {
  return apiPost<Policy>('/budget/policies', payload)
}

export function fetchAuditLogs(pageSize = 12) {
  return apiGet<Page<AuditLog>>('/audit/logs', { page: 1, page_size: pageSize })
}
