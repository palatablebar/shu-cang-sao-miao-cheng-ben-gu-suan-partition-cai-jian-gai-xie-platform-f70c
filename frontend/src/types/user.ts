export type Role = 'admin' | 'engineer' | 'viewer'

export interface User {
  id: number
  email: string
  display_name: string
  role: Role
  team: string
}

export interface TokenPayload {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}
