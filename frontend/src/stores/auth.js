/**
 * 认证状态管理（Pinia）。
 */
import { defineStore } from 'pinia'
import { authApi } from '../api/resources'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    username: localStorage.getItem('username') || '',
    role: localStorage.getItem('role') || ''
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    isAdmin: (s) => s.role === 'admin'
  },
  actions: {
    async login(username, password) {
      const { data } = await authApi.login(username, password)
      this.token = data.access_token
      this.username = data.username
      this.role = data.role
      localStorage.setItem('token', data.access_token)
      localStorage.setItem('username', data.username)
      localStorage.setItem('role', data.role)
    },
    logout() {
      this.token = ''
      this.username = ''
      this.role = ''
      localStorage.removeItem('token')
      localStorage.removeItem('username')
      localStorage.removeItem('role')
    }
  }
})
