<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">API 密钥管理</div>
        <div class="page-desc">用于对外检测接口的安全认证，集成方在请求头 X-API-Key 中携带密钥。</div>
      </div>
      <button class="btn btn-primary" @click="openCreate">+ 生成 API 密钥</button>
    </div>

    <div class="panel">
      <table class="table">
        <thead>
          <tr>
            <th>密钥名称</th>
            <th>密钥</th>
            <th class="th-center">状态</th>
            <th>创建时间</th>
            <th class="col-actions">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="k in keys" :key="k.id">
            <td>{{ k.name }}</td>
            <td>
              <code class="code-inline" style="margin-right: 8px">{{ masked(k) }}</code>
              <button class="btn btn-sm" @click="toggleShow(k.id)">{{ shown[k.id] ? '隐藏' : '查看' }}</button>
              <button class="btn btn-sm" @click="copy(k.key_value)">复制</button>
            </td>
            <td class="td-center">
              <span class="badge" :class="k.enabled ? 'badge-success' : 'badge-danger'">
                {{ k.enabled ? '启用' : '停用' }}
              </span>
            </td>
            <td class="text-sub">{{ fmt(k.created_at) }}</td>
            <td class="col-actions">
              <button class="btn btn-sm" @click="toggle(k)">{{ k.enabled ? '停用' : '启用' }}</button>
              <button class="btn btn-sm btn-danger" @click="remove(k)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!keys.length" class="empty">暂无 API 密钥，请点击右上角「生成 API 密钥」。</div>
    </div>

    <Modal v-model="show" title="生成 API 密钥" :loading="saving" @confirm="save">
      <div class="form-item">
        <label>密钥名称（用于标识用途）</label>
        <input class="input" v-model="name" placeholder="例如：客服机器人接入" />
      </div>
    </Modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { keyApi } from '../api/resources'
import { toast, errMsg } from '../stores/toast'
import Modal from '../components/Modal.vue'

const keys = ref([])
const show = ref(false)
const saving = ref(false)
const name = ref('')
const shown = reactive({})

function masked(k) {
  if (shown[k.id]) return k.key_value
  return k.key_value.slice(0, 6) + '••••••••••••' + k.key_value.slice(-4)
}
function toggleShow(id) {
  shown[id] = !shown[id]
}
function fmt(s) {
  const str = String(s)
  const d = /[Zz]|[+-]\d{2}:?\d{2}$/.test(str) ? new Date(str) : new Date(str + 'Z')
  return d.toLocaleString('zh-CN')
}
async function copy(v) {
  try {
    await navigator.clipboard.writeText(v)
    toast.success('已复制到剪贴板')
  } catch {
    toast.info('请手动复制')
  }
}

async function load() {
  try {
    keys.value = (await keyApi.list()).data
  } catch (e) {
    toast.error(errMsg(e))
  }
}
function openCreate() {
  name.value = ''
  show.value = true
}
async function save() {
  if (!name.value.trim()) {
    toast.error('请填写密钥名称')
    return
  }
  saving.value = true
  try {
    await keyApi.create({ name: name.value })
    toast.success('已生成')
    show.value = false
    await load()
  } catch (e) {
    toast.error(errMsg(e))
  } finally {
    saving.value = false
  }
}
async function toggle(k) {
  try {
    await keyApi.toggle(k.id)
    await load()
  } catch (e) {
    toast.error(errMsg(e))
  }
}
async function remove(k) {
  if (!confirm(`确认删除密钥「${k.name}」？绑定该密钥的场景将无法认证。`)) return
  try {
    await keyApi.remove(k.id)
    toast.success('已删除')
    await load()
  } catch (e) {
    toast.error(errMsg(e))
  }
}
onMounted(load)
</script>