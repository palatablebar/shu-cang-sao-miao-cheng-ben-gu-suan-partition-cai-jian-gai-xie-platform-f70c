import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { fetchMe, login as loginApi } from '../api/auth'
import { getToken, setToken } from '../api/http'
import type { User } from '../types/user'

const USER_KEY = 'partfit.user'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(getToken())
  const user = ref<User | null>(null)
  const loading = ref(false)

  function restore() {
    token.value = getToken()
    const cached = localStorage.getItem(USER_KEY)
    if (cached && !user.value) {
      try {
        user.value = JSON.parse(cached) as User
      } catch {
        localStorage.removeItem(USER_KEY)
      }
    }
  }

  function persistUser(next: User | null) {
    user.value = next
    if (next) localStorage.setItem(USER_KEY, JSON.stringify(next))
    else localStorage.removeItem(USER_KEY)
  }

  async function login(email: string, password: string) {
    loading.value = true
    try {
      const payload = await loginApi(email, password)
      setToken(payload.access_token)
      token.value = payload.access_token
      persistUser(payload.user)
      return payload.user
    } finally {
      loading.value = false
    }
  }

  async function refreshMe() {
    if (!token.value) return null
    try {
      const me = await fetchMe()
      persistUser(me)
      return me
    } catch {
      return null
    }
  }

  function logout() {
    setToken(null)
    token.value = null
    persistUser(null)
  }

  const isAuthenticated = computed(() => Boolean(token.value))
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isViewer = computed(() => user.value?.role === 'viewer')
  const canWrite = computed(() => user.value?.role === 'admin' || user.value?.role === 'engineer')
  const roleLabel = computed(() =>
    user.value ? { admin: '平台负责人', engineer: '数据开发', viewer: '财务 / BI 只读' }[user.value.role] : '',
  )

  return {
    token,
    user,
    loading,
    restore,
    login,
    refreshMe,
    logout,
    isAuthenticated,
    isAdmin,
    isViewer,
    canWrite,
    roleLabel,
  }
})
