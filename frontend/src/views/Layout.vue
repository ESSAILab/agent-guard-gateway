<template>
  <div class="layout">
    <!-- 侧边导航 -->
    <aside class="sidebar">
      <div class="logo-area">
        <span class="logo-icon">AI智能体安全网关</span>
      </div>
      <nav class="menu">
        <a class="menu-item" href="#/dashboard" target="_blank">
          <span class="menu-icon">📺</span>数据大屏
        </a>
        <template v-for="m in menus" :key="m.path || m.label">
          <div v-if="m.children" class="menu-group" v-show="hasVisibleChild(m)">
            <div class="menu-item menu-group-title" :class="{ active: isGroupActive(m) }" @click="toggleMenu(m.label)">
              <span class="menu-icon">{{ m.icon }}</span>
              <span>{{ m.label }}</span>
              <span class="menu-arrow" :class="{ open: openedMenus.includes(m.label) }">▶</span>
            </div>
            <div class="submenu" v-show="openedMenus.includes(m.label)">
              <template v-for="sub in m.children" :key="sub.path || sub.href">
                <a v-if="sub.href" :href="sub.href" target="_blank"
                  class="menu-item submenu-item" v-show="!sub.admin || auth.isAdmin">
                  <span class="menu-icon">{{ sub.icon }}</span>{{ sub.label }}
                </a>
                <router-link v-else :to="sub.path" class="menu-item submenu-item"
                  v-show="!sub.admin || auth.isAdmin">
                  <span class="menu-icon">{{ sub.icon }}</span>{{ sub.label }}
                </router-link>
              </template>
            </div>
          </div>
          <router-link v-else :to="m.path" class="menu-item"
            v-show="!m.admin || auth.isAdmin">
            <span class="menu-icon">{{ m.icon }}</span>{{ m.label }}
          </router-link>
        </template>
      </nav>
    </aside>

    <!-- 主区域 -->
    <div class="main">
      <header class="topbar">
        <div class="user-area">
          <span class="user-name">👤 {{ auth.username }}（{{ auth.role === 'admin' ? '管理员' : '操作员' }}）</span>
          <button class="btn btn-ghost btn-sm" @click="logout">退出</button>
        </div>
      </header>
      <main class="content">
        <router-view />
      </main>
    </div>
    <Toast />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import Toast from '../components/Toast.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const menus = [
  { path: '/overview', label: '系统概览', icon: '📊' },
  { path: '/models', label: '检测能力', icon: '🧩' },
  { path: '/strategies', label: '策略编排', icon: '⚖️' },
  { path: '/api-paths', label: '检测场景', icon: '🛣️' },
  { path: '/observability', label: '检测记录', icon: '🔍' },
  {
    label: '系统设置',
    icon: '⚙️',
    children: [
      { path: '/tags', label: '安全标签', icon: '🏷️' },
      { path: '/users', label: '用户管理', icon: '👥', admin: true },
      { path: '/api-keys', label: 'API 密钥', icon: '🔑' },
      { href: '/docs', label: '接口文档', icon: '📘' }
    ]
  }
]

const openedMenus = ref(['系统设置'])

function toggleMenu(label) {
  if (openedMenus.value.includes(label)) {
    openedMenus.value = openedMenus.value.filter((l) => l !== label)
  } else {
    openedMenus.value.push(label)
  }
}

function hasVisibleChild(m) {
  return m.children.some((c) => !c.admin || auth.isAdmin)
}

function isGroupActive(m) {
  return m.children.some((c) => c.path === route.path)
}

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.layout {
  display: flex;
  height: 100%;
}
.sidebar {
  width: 220px;
  background: linear-gradient(180deg, #103a73 0%, #0b2a55 100%);
  color: #cfe0f5;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.logo-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 18px 22px;
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.logo-icon {
  font-size: 16px;
  letter-spacing: 1px;
}
.menu {
  padding: 10px 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 22px;
  color: #cfe0f5;
  font-size: 14px;
  transition: all 0.18s;
  border-left: 3px solid transparent;
}
.menu-item:hover {
  background: rgba(255, 255, 255, 0.07);
  color: #fff;
}
.menu-item.router-link-active {
  background: rgba(43, 143, 255, 0.25);
  color: #fff;
  border-left-color: var(--c-accent);
}
.menu-icon {
  font-size: 15px;
}
.menu-group-title {
  cursor: pointer;
  justify-content: flex-start;
}
.menu-group-title .menu-arrow {
  margin-left: auto;
  font-size: 10px;
  transition: transform 0.18s;
  opacity: 0.7;
}
.menu-group-title .menu-arrow.open {
  transform: rotate(90deg);
}
.menu-group-title.active {
  background: rgba(43, 143, 255, 0.15);
  color: #fff;
}
.submenu {
  background: rgba(0, 0, 0, 0.15);
}
.submenu-item {
  padding-left: 46px;
  font-size: 13px;
}
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.topbar {
  height: 56px;
  background: #fff;
  border-bottom: 1px solid var(--c-border);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 0 24px;
  flex-shrink: 0;
}
.user-area {
  display: flex;
  align-items: center;
  gap: 14px;
}
.user-name {
  font-size: 13px;
  color: var(--c-text-sub);
}
.content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}
</style>
