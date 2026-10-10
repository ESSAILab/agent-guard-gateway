<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">用户管理</div>
        <div class="page-desc">管理系统登录账户与角色权限。</div>
      </div>
      <button class="btn btn-primary" @click="openCreate">+ 新建用户</button>
    </div>

    <div class="panel">
      <table class="table">
        <thead>
          <tr>
            <th>用户名</th>
            <th class="th-center">角色</th>
            <th class="th-center">状态</th>
            <th>创建时间</th>
            <th class="col-actions">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>{{ u.username }}</td>
            <td class="td-center">
              <span class="badge">{{ u.role === 'admin' ? '管理员' : '操作员' }}</span>
            </td>
            <td class="td-center">
              <span class="badge" :class="u.enabled ? 'badge-success' : 'badge-danger'">
                {{ u.enabled ? '启用' : '禁用' }}
              </span>
            </td>
            <td class="text-sub">{{ fmt(u.created_at) }}</td>
            <td class="col-actions">
              <button class="btn btn-sm" @click="openEdit(u)">编辑</button>
              <button class="btn btn-sm" @click="openCopy(u)">复制</button>
              <button class="btn btn-sm" @click="toggleEnable(u)">{{ u.enabled ? '禁用' : '启用' }}</button>
              <button class="btn btn-sm btn-danger" @click="remove(u)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!users.length" class="empty">暂无用户，请点击右上角「新建用户」。</div>
    </div>

    <Modal v-model="show" :title="editing ? '编辑用户' : '新建用户'" :loading="saving" @confirm="save">
      <div class="form-item">
        <label>用户名</label>
        <input class="input" v-model="form.username" :disabled="editing" placeholder="登录用户名" />
      </div>
      <div class="form-item">
        <label>{{ editing ? '重置密码（留空则不修改）' : '密码' }}</label>
        <input class="input" type="password" v-model="form.password" placeholder="至少 4 位" />
      </div>
      <div class="form-item">
        <label>角色</label>
        <select class="select" v-model="form.role">
          <option value="operator">操作员</option>
          <option value="admin">管理员</option>
        </select>
      </div>
    </Modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { userApi } from '../api/resources'
import { toast, errMsg } from '../stores/toast'
import Modal from '../components/Modal.vue'

const users = ref([])
const show = ref(false)
const saving = ref(false)
const editing = ref(null)
const form = ref({ username: '', password: '', role: 'operator' })

function fmt(s) {
  const str = String(s)
  const d = /[Zz]|[+-]\d{2}:?\d{2}$/.test(str) ? new Date(str) : new Date(str + 'Z')
  return d.toLocaleString('zh-CN')
}
async function load() {
  try {
    users.value = (await userApi.list()).data
  } catch (e) {
    toast.error(errMsg(e))
  }
}
function openCreate() {
  editing.value = null
  form.value = { username: '', password: '', role: 'operator' }
  show.value = true
}
function openEdit(u) {
  editing.value = u
  form.value = { username: u.username, password: '', role: u.role }
  show.value = true
}
function openCopy(u) {
  editing.value = null
  form.value = { username: u.username + '-副本', password: '', role: u.role }
  show.value = true
}
async function save() {
  saving.value = true
  try {
    if (editing.value) {
      const payload = { role: form.value.role }
      if (form.value.password) payload.password = form.value.password
      await userApi.update(editing.value.id, payload)
    } else {
      if (!form.value.username || form.value.password.length < 4) {
        toast.error('请填写用户名与至少 4 位密码')
        return
      }
      await userApi.create(form.value)
    }
    toast.success('保存成功')
    show.value = false
    await load()
  } catch (e) {
    toast.error(errMsg(e))
  } finally {
    saving.value = false
  }
}
async function toggleEnable(u) {
  try {
    await userApi.update(u.id, { enabled: !u.enabled })
    await load()
  } catch (e) {
    toast.error(errMsg(e))
  }
}
async function remove(u) {
  if (!confirm(`确认删除用户「${u.username}」？`)) return
  try {
    await userApi.remove(u.id)
    toast.success('已删除')
    await load()
  } catch (e) {
    toast.error(errMsg(e))
  }
}
onMounted(load)
</script>
