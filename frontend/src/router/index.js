import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue'),
  },
  {
    path: '/holdings',
    name: 'Holdings',
    component: () => import('../views/Holdings.vue'),
  },
  {
    path: '/holdings/:id',
    name: 'HoldingDetail',
    component: () => import('../views/HoldingDetail.vue'),
  },
  {
    path: '/positions/:id',
    name: 'PositionDetail',
    component: () => import('../views/PositionDetail.vue'),
  },
  {
    path: '/alerts',
    name: 'Alerts',
    component: () => import('../views/Alerts.vue'),
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../views/Settings.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
