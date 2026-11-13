import { apiDownload, apiGet, apiPost } from './http'
import type { Page } from '../types/api'
import type { QueryDetail, QueryImportResult, QueryListItem, QueryStats } from '../types/query'

export interface QueryFilters {
  page?: number
  page_size?: number
  sort?: string
  order?: 'asc' | 'desc'
  status?: string
  table?: string
  keyword?: string
}

export function fetchQueries(filters: QueryFilters) {
  return apiGet<Page<QueryListItem>>('/queries', filters as Record<string, unknown>)
}

export function fetchRanking(limit = 10) {
  return apiGet<QueryListItem[]>('/queries/ranking', { limit })
}

export function fetchQueryStats() {
  return apiGet<QueryStats>('/queries/stats')
}

export function fetchQueryDetail(id: number) {
  return apiGet<QueryDetail>(`/queries/${id}`)
}

export function analyzeQuery(id: number) {
  return apiPost<QueryDetail>(`/queries/${id}/analyze`)
}

export function importQueryPack() {
  return apiPost<QueryImportResult>('/queries/import')
}

export function downloadOptimisationCsv() {
  return apiDownload('/rewrites/export.csv', 'partfit-optimisation-list.csv')
}
