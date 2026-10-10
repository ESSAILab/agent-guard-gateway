<template>
  <div class="login-page">
    <!-- 背景科技网格动画 -->
    <div class="grid-bg"></div>
    <div class="particles">
      <span v-for="n in 18" :key="n" :style="particleStyle(n)"></span>
    </div>

    <div class="login-card panel">
      <div class="brand">
        <div class="logo">🛡️</div>
        <div>
          <div class="brand-title">AI智能体安全网关</div>
          <div class="brand-sub">AI 智能体安全检测平台</div>
        </div>
      </div>

      <div class="form-item">
        <label>用户名</label>
        <input class="input" v-model="username" placeholder="请输入用户名" @keyup.enter="doLogin" />
      </div>
      <div class="form-item">
        <label>密码</label>
        <input class="input" type="password" v-model="password" placeholder="请输入密码" @keyup.enter="doLogin" />
      </div>
      <button class="btn btn-primary login-btn" :disabled="loading" @click="doLogin">
        {{ loading ? '登录中…' : '登 录' }}
      </button>
    </div>
    <Toast />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { toast, errMsg } from '../stores/toast'
import Toast from '../components/Toast.vue'

const username = ref('')
const password = ref('')
const loading = ref(false)
const router = useRouter()
const auth = useAuthStore()

async function doLogin() {
  if (!username.value || !password.value) {
    toast.error('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    toast.success('登录成功')
    router.push('/overview')
  } catch (e) {
    toast.error(errMsg(e, '登录失败'))
  } finally {
    loading.value = false
  }
}

// 随机生成漂浮粒子样式
function particleStyle(n) {
  const left = (n * 53) % 100
  const delay = (n % 6) * 0.8
  const size = 4 + (n % 4) * 2
  const dur = 9 + (n % 5) * 2
  return {
    left: left + '%',
    width: size + 'px',
    height: size + 'px',
    animationDelay: delay + 's',
    animationDuration: dur + 's'
  }
}
</script>

<style scoped>
.login-page {
  position: relative;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: linear-gradient(160deg, #e9f3ff 0%, #d2e6fb 100%);
}
.grid-bg {
  position: absolute;
  inset: 0;
  background-image: linear-gradient(rgba(43, 143, 255, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(43, 143, 255, 0.08) 1px, transparent 1px);
  background-size: 40px 40px;
  mask-image: radial-gradient(circle at center, #000 40%, transparent 80%);
}
.particles span {
  position: absolute;
  bottom: -10px;
  border-radius: 50%;
  background: rgba(43, 143, 255, 0.4);
  animation: rise linear infinite;
}
@keyframes rise {
  to {
    transform: translateY(-110vh);
    opacity: 0;
  }
}
.login-card {
  position: relative;
  z-index: 2;
  width: 380px;
  padding: 36px 34px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 28px;
}
.logo {
  font-size: 40px;
  filter: drop-shadow(0 4px 8px rgba(43, 143, 255, 0.4));
}
.brand-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--c-primary-deep);
}
.brand-sub {
  font-size: 12px;
  color: var(--c-text-sub);
  margin-top: 2px;
}
.login-btn {
  width: 100%;
  justify-content: center;
  padding: 11px;
  font-size: 15px;
  margin-top: 6px;
}
</style>
