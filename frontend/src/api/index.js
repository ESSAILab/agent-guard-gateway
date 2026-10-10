/**
 * Axios 封装：统一注入 JWT、处理 401 跳转登录。
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/',
  timeout: 30000
})

// 请求拦截：附加 Bearer 令牌
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截：401 时清理登录态并跳转
api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('token')
      if (location.hash.indexOf('/login') === -1) {
        location.hash = '#/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
