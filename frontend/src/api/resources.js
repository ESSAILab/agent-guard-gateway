/**
 * 后端接口封装，按业务域分组。
 */
import api from './index'

// 认证
export const authApi = {
  login: (username, password) => {
    const form = new URLSearchParams()
    form.append('username', username)
    form.append('password', password)
    return api.post('/api/auth/login', form)
  },
  me: () => api.get('/api/auth/me')
}

// 用户管理
export const userApi = {
  list: () => api.get('/api/users'),
  create: (data) => api.post('/api/users', data),
  update: (id, data) => api.put(`/api/users/${id}`, data),
  remove: (id) => api.delete(`/api/users/${id}`)
}

// API Key
export const keyApi = {
  list: () => api.get('/api/api-keys'),
  create: (data) => api.post('/api/api-keys', data),
  toggle: (id) => api.put(`/api/api-keys/${id}/toggle`),
  remove: (id) => api.delete(`/api/api-keys/${id}`)
}

// 安全标签
export const tagApi = {
  list: () => api.get('/api/tags'),
  create: (data) => api.post('/api/tags', data),
  update: (id, data) => api.put(`/api/tags/${id}`, data),
  remove: (id) => api.delete(`/api/tags/${id}`)
}

// 检测能力
export const modelApi = {
  list: () => api.get('/api/models'),
  get: (id) => api.get(`/api/models/${id}`),
  create: (data) => api.post('/api/models', data),
  update: (id, data) => api.put(`/api/models/${id}`, data),
  remove: (id) => api.delete(`/api/models/${id}`),
  validate: (id) => api.post(`/api/models/${id}/validate`)
}

// 策略编排
export const strategyApi = {
  list: () => api.get('/api/strategies'),
  get: (id) => api.get(`/api/strategies/${id}`),
  create: (data) => api.post('/api/strategies', data),
  update: (id, data) => api.put(`/api/strategies/${id}`, data),
  remove: (id) => api.delete(`/api/strategies/${id}`)
}

// API 路径
export const pathApi = {
  list: () => api.get('/api/api-paths'),
  get: (id) => api.get(`/api/api-paths/${id}`),
  create: (data) => api.post('/api/api-paths', data),
  update: (id, data) => api.put(`/api/api-paths/${id}`, data),
  remove: (id) => api.delete(`/api/api-paths/${id}`)
}

// 可观测
export const obsApi = {
  level: () => api.get('/api/observability/level'),
  requestLogs: (params) => api.get('/api/observability/request-logs', { params }),
  detectionLogs: (params) => api.get('/api/observability/detection-logs', { params }),
  stats: () => api.get('/api/observability/stats'),
  purgeLogs: (days) => api.delete('/api/observability/request-logs/purge', { params: { days } })
}
