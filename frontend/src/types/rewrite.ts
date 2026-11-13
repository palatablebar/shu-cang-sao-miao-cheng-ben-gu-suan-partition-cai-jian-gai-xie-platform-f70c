import type { Reconciliation, TableAnalysis } from './query'

export interface RewriteSuggestion {  id: number
  suggestion_no: string
  query_log_id: number
  query_external_id: string
  query_title: string
  target_table: string | null
  anti_patterns: string[]
  risk_level: 'low' | 'medium' | 'high'
  confidence: number
  before_scan_bytes: number
  after_scan_bytes: number
  saving_bytes: number
  saving_cost_cny: number
  saving_pct: number
  score: number
  status: 'pending' | 'adopted' | 'rejected'
  rationale: string
  table_count: number
  table_changes: TableRewriteChange[]
}

export interface TableRewriteChange {
  table_name: string
  alias: string
  after_alias: string
  before_scan_bytes: number
  after_scan_bytes: number
  before_hit_partition_count: number
  after_hit_partition_count: number
  before_total_partition_count: number
  after_total_partition_count: number
  before_prunable: boolean
  after_prunable: boolean
  before_blocked_reason: string
  after_blocked_reason: string
  changed: boolean
}

export interface RewriteDetail extends RewriteSuggestion {
  original_sql: string
  rewritten_sql: string
  fixes: string[]
  before_rationale: string
  after_rationale: string
  after_prunable: boolean
  after_hit_partition_count: number
  after_total_partition_count: number
  before_tables: TableAnalysis[]
  after_tables: TableAnalysis[]
  before_reconciliation: Reconciliation | null
  after_reconciliation: Reconciliation | null
  qualified: boolean
  rejection_reason: string
}

export interface RewriteReevaluation {
  suggestion_no: string
  before_scan_bytes: number
  after_scan_bytes: number
  saving_bytes: number
  saving_pct: number
  saving_cost_cny: number
  monthly_saving_cny: number
  after_prunable: boolean
  after_hit_partition_count: number
  after_total_partition_count: number
  rationale: string
  table_changes: TableRewriteChange[]
}
