import { apiGet, apiPost } from './http'
import type { Page } from '../types/api'
import type { RewriteDetail, RewriteReevaluation, RewriteSuggestion } from '../types/rewrite'

export function fetchSuggestions(status?: string, pageSize = 20) {
  return apiGet<Page<RewriteSuggestion>>('/rewrites', {
    page: 1,
    page_size: pageSize,
    sort: 'score',
    ...(status ? { status } : {}),
  })
}

export function fetchSuggestion(id: number) {
  return apiGet<RewriteDetail>(`/rewrites/${id}`)
}

export function generateRewrite(queryId: number) {
  return apiPost<RewriteDetail>('/rewrites/generate', { query_id: queryId, limit: 1 })
}

export function reevaluateRewrite(id: number) {
  return apiPost<RewriteReevaluation>(`/rewrites/${id}/reevaluate`)
}

export function adoptRewrite(id: number) {
  return apiPost<RewriteSuggestion>(`/rewrites/${id}/adopt`)
}
