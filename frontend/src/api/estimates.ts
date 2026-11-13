import { apiGet, apiPost } from './http'
import type { Page } from '../types/api'
import type { EstimateRun } from '../types/estimate'

export function fetchEstimates(page = 1, pageSize = 10) {
  return apiGet<Page<EstimateRun>>('/estimates', { page, page_size: pageSize })
}

export function createEstimate(scope: 'all' | 'table' | 'blocked', scopeValue?: string, note = '') {
  return apiPost<EstimateRun>('/estimates', { scope, scope_value: scopeValue ?? null, note })
}

export function fetchEstimate(id: number) {
  return apiGet<EstimateRun>(`/estimates/${id}`)
}
