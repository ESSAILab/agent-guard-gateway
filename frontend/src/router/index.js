/**
 * 路由配置：登录页 + 大屏（独立全屏）+ 管理后台（带侧边栏布局）。
 */
import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', component: () => import('../views/Login.vue'), meta: { public: true } },
  { path: '/dashboard', component: () => import('../views/Dashboard.vue') },
  {
    path: '/',
    component: () => import('../views/Layout.vue'),
    redirect: '/overview',
    children: [
      { path: 'overview', component: () => import('../views/Overview.vue') },
      { path: 'models', component: () => import('../views/Models.vue') },
      { path: 'tags', component: () => import('../views/Tags.vue') },
      { path: 'strategies', component: () => import('../views/Strategies.vue') },
      { path: 'api-paths', component: () => import('../views/ApiPaths.vue') },
      { path: 'observability', component: () => import('../views/Observability.vue') },
      { path: 'users', component: () => import('../views/Users.vue') },
      { path: 'api-keys', component: () => import('../views/ApiKeys.vue') }
    ]
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

// 全局守卫：未登录跳转登录页
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isLoggedIn) {
    return '/login'
  }
  if (to.path === '/login' && auth.isLoggedIn) {
    return '/overview'
  }
})

export default router
