export interface Policy {
  id: number
  policy_no: string
  name: string
  scope: string
  scope_value: string | null
  monthly_budget_cny: number
  unit_cost_per_gib_cny: number
  warn_ratio: number
  critical_ratio: number
  scan_alert_bytes: number
  is_active: boolean
  note: string
  updated_by: string | null
}

export interface TableScanRow {
  table_name: string
  layer: string
  scan_bytes: number
  query_count: number
  blocked_count: number
}

export interface BudgetOverview {
  monthly_budget_cny: number
  projected_cost_cny: number
  month_share: number
  status: 'ok' | 'warn' | 'critical' | 'over'
  unit_cost_per_gib_cny: number
  alert_bytes: number
  total_scan_bytes: number
  query_count: number
  blocked_count: number
  prunable_saving_bytes: number
  tables: TableScanRow[]
  policies: Policy[]
}

export interface AuditLog {
  id: number
  actor_email: string
  actor_role: string
  action: string
  resource_type: string
  resource_id: string | null
  method: string
  path: string
  status_code: number
  created_at: string
}
