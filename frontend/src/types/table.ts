export interface TableColumn {
  id: number
  name: string
  data_type: string
  bytes: number
  byte_ratio: number
  ordinal: number
  is_partition_key: boolean
  note: string
}

export interface TablePartition {
  id: number
  dt: string
  bytes: number
  row_count: number
  file_count: number
  is_current: boolean
}

export interface TableListItem {
  id: number
  schema_name: string
  table_name: string
  layer: string
  storage_format: string
  partition_key: string
  partition_count: number
  row_count: number
  total_bytes: number
  data_column_count: number
  owner: string
  description: string
  suggested_columns: string[]
  query_count: number
  blocked_query_count: number
}

export interface TableDetail extends TableListItem {
  columns: TableColumn[]
  partitions: TablePartition[]
}
