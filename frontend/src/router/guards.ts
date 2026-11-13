import type { Router } from 'vue-router'
import { useAuthStore } from '../stores/authStore'

export function installGuards(router: Router) {
  router.beforeEach((to) => {
    const auth = useAuthStore()
    auth.restore()
    if (to.meta.public) return true
    if (!auth.isAuthenticated) {
      return { name: 'login', query: { redirect: to.fullPath } }
    }
    return true
  })
  router.afterEach((to) => {
    const title = (to.meta.title as string) || 'partfit'
    document.title = `${title} · partfit 扫描成本台`
  })
}
