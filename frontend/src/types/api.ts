export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface ApiError {
  code: string
  message: string
  request_id?: string
  detail?: Record<string, unknown>
}
