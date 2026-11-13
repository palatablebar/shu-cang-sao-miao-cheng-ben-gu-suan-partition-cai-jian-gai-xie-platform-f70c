export interface QueryListItem {
  id: number
  external_id: string
  title: string
  source: string
  submitted_by: string
  query_date: string
  duration_ms: number
  is_scheduled: boolean
  parse_status: 'parsed' | 'unparsed' | 'missing_table'
  target_table: string | null
  prunable: boolean
  blocked_reason: string
  scan_bytes: number
  scan_cost_cny: number
  hit_partition_count: number
  total_partition_count: number
  col_ratio: number
}

export interface Predicate {
  expression: string
  operator: string
  literal: string
  usable: boolean
  reason: string
  wrapper_kind: string | null
}

export interface QueryDetail extends QueryListItem {
  sql_text: string
  parse_error: string | null
  blocked_expression: string | null
  predicates: Predicate[]
  hit_partitions: string[]
  projected_columns: string[]
  referenced_columns: string[]
  has_star: boolean
  full_scan_bytes: number
  rationale: string
  suggestion_count: number
}

export interface QueryImportResult {
  imported: number
  updated: number
  total: number
  analysed: number
  blocked: number
  message: string
}

export interface QueryStats {
  query_count: number
  blocked_count: number
  prunable_count: number
  total_scan_bytes: number
  top_scan_bytes: number
  top_query_id: number | null
}
