import { createRouter, createWebHistory } from 'vue-router'
import { installGuards } from './guards'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/queries' },
    {
      path: '/login',
      name: 'login',
      component: () => import('../pages/LoginPage.vue'),
      meta: { public: true, title: '登录 · 平台通行证' },
    },
    {
      path: '/queries',
      name: 'queries',
      component: () => import('../pages/QueryCostPage.vue'),
      meta: { title: '查询成本排行', sheet: 'S-01' },
    },
    {
      path: '/queries/:id',
      name: 'query-detail',
      component: () => import('../pages/QueryDetailPage.vue'),
      meta: { title: 'SQL 解析详情', sheet: 'S-02' },
    },
    {
      path: '/rewrites',
      name: 'rewrites',
      component: () => import('../pages/RewritePage.vue'),
      meta: { title: '改写建议与前后对比', sheet: 'S-03' },
    },
    {
      path: '/tables',
      name: 'tables',
      component: () => import('../pages/TablesPage.vue'),
      meta: { title: '表与分区元数据', sheet: 'S-04' },
    },
    {
      path: '/budget',
      name: 'budget',
      component: () => import('../pages/BudgetPage.vue'),
      meta: { title: '预算策略与批次', sheet: 'S-05' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/queries' },
  ],
})

installGuards(router)
export default router
