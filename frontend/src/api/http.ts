import axios, { AxiosError } from 'axios'
import type { ApiError } from '../types/api'

const TOKEN_KEY = 'partfit.token'

export const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

http.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers = config.headers ?? {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiError>) => {
    if (error.response?.status === 401) {
      setToken(null)
      if (!location.pathname.startsWith('/login')) {
        location.href = `/login?redirect=${encodeURIComponent(location.pathname)}`
      }
    }
    const payload = error.response?.data
    const message =
      payload?.message ??
      (error.code === 'ECONNABORTED' ? '请求超时，请检查后端容器是否健康' : '网络异常，请稍后重试')
    return Promise.reject(Object.assign(new Error(message), { api: payload, status: error.response?.status }))
  },
)

export async function apiGet<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const { data } = await http.get<T>(url, { params })
  return data
}

export async function apiPost<T>(url: string, body?: unknown): Promise<T> {
  const { data } = await http.post<T>(url, body ?? {})
  return data
}

export async function apiPatch<T>(url: string, body: unknown): Promise<T> {
  const { data } = await http.patch<T>(url, body)
  return data
}

export async function apiPut<T>(url: string, body: unknown): Promise<T> {
  const { data } = await http.put<T>(url, body)
  return data
}

export async function apiDownload(url: string, filename: string): Promise<number | null> {
  const response = await http.get(url, { responseType: 'blob' })
  const blob = new Blob([response.data as BlobPart], { type: 'text/csv;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(link.href)
  const rows = response.headers['x-row-count']
  return rows ? Number(rows) : null
}
