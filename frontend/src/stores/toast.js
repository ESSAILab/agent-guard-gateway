/**
 * 极简全局消息提示。挂载一个容器，提供 toast.success/error/info。
 */
import { reactive } from 'vue'

export const toastState = reactive({ items: [] })
let seq = 0

function push(text, type) {
  const id = ++seq
  toastState.items.push({ id, text, type })
  setTimeout(() => {
    const idx = toastState.items.findIndex((t) => t.id === id)
    if (idx >= 0) toastState.items.splice(idx, 1)
  }, 3000)
}

export const toast = {
  success: (t) => push(t, 'success'),
  error: (t) => push(t, 'error'),
  info: (t) => push(t, 'info')
}

// 从 axios 错误中提取后端 detail 信息
export function errMsg(e, fallback = '操作失败') {
  return e?.response?.data?.detail || e?.message || fallback
}
