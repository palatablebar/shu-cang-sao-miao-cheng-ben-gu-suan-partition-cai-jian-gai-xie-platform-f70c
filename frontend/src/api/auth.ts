import { apiGet, apiPost } from './http'
import type { TokenPayload, User } from '../types/user'

export function login(email: string, password: string) {
  return apiPost<TokenPayload>('/auth/login', { email, password })
}

export function fetchMe() {
  return apiGet<User>('/auth/me')
}
