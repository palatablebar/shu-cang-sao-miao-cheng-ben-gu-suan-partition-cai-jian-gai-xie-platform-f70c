// 与 backend/src/constants/enums.py 一一对应的枚举（README §枚举出现位置）
export const ROLE_LABEL: Record<string, string> = {
  admin: '平台负责人',
  engineer: '数据开发',
  viewer: '财务 / BI 只读',
}

export const BLOCKED_REASON_LABEL: Record<string, string> = {
  none: '可裁剪',
  function_wrapped: '分区列被函数包裹',
  implicit_cast: '隐式类型转换',
  missing_predicate: '缺少分区谓词',
  expression_not_usable: '表达式不可裁剪',
  table_not_partitioned: '表未分区',
  unparsed: '解析失败',
  missing_table: '目标表缺失',
}

export const BLOCKED_REASON_SHORT: Record<string, string> = {
  none: '可裁剪',
  function_wrapped: '函数包裹',
  implicit_cast: '隐式转换',
  missing_predicate: '缺谓词',
  expression_not_usable: '表达式',
  table_not_partitioned: '未分区',
  unparsed: '解析失败',
  missing_table: '表缺失',
}

export const ANTI_PATTERN_LABEL: Record<string, string> = {
  partition_function_wrap: '分区列函数包裹',
  partition_implicit_cast: '分区隐式类型转换',
  select_star: 'SELECT * 全列',
  missing_partition_predicate: '缺分区谓词',
}

export const RISK_LABEL: Record<string, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
}

export const BUDGET_STATUS_LABEL: Record<string, string> = {
  ok: '预算内',
  warn: '接近阈值',
  critical: '临界',
  over: '超预算',
}

export const RUN_STATUS_LABEL: Record<string, string> = {
  queued: '排队中',
  running: '执行中',
  completed: '已完成',
  failed: '失败',
}

export const SUGGESTION_STATUS_LABEL: Record<string, string> = {
  pending: '待采纳',
  adopted: '已采纳',
  rejected: '已驳回',
}

export const LAYER_LABEL: Record<string, string> = {
  ODS: '贴源层',
  DWD: '明细层',
  DWS: '汇总层',
  ADS: '应用层',
}
