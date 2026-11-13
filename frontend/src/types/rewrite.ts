export interface RewriteSuggestion {
  id: number
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
}
