import { apiGet, apiPatch } from './http'
import type { TableDetail, TableListItem } from '../types/table'

export function fetchTables(layer?: string) {
  return apiGet<TableListItem[]>('/tables', layer ? { layer } : undefined)
}

export function fetchTable(id: number) {
  return apiGet<TableDetail>(`/tables/${id}`)
}

export function updateTable(
  id: number,
  payload: { owner?: string; description?: string; suggested_columns?: string[] },
) {
  return apiPatch<TableDetail>(`/tables/${id}`, payload)
}
