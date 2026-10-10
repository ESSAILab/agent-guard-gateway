<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">安全标签</div>
        <div class="page-desc">系统内置标签固定提供；可创建自定义标签，并指定用于检测输入或输出。</div>
      </div>
      <button class="btn btn-primary" @click="openCreate">+ 新建自定义标签</button>
    </div>

    <div class="panel">
      <table class="table">
        <thead>
          <tr>
            <th>标签名称</th>
            <th class="th-center">类型</th>
            <th class="th-center">检测方向</th>
            <th>风险类型</th>
            <th>说明</th>
            <th class="col-actions">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in tags" :key="t.id">
            <td>{{ t.name }}</td>
            <td class="td-center">
              <span class="badge" :class="t.is_builtin ? 'badge-gray' : ''">
                {{ t.is_builtin ? '内置' : '自定义' }}
              </span>
            </td>
            <td class="td-center">{{ directionLabel(t.direction) }}</td>
            <td>{{ t.risk_type }}</td>
            <td class="text-sub">{{ t.description || '—' }}</td>
            <td class="col-actions">
              <button class="btn btn-sm" @click="openEdit(t)">编辑</button>
              <button class="btn btn-sm" @click="openCopy(t)">复制</button>
              <button v-if="!t.is_builtin" class="btn btn-sm btn-danger" @click="remove(t)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!tags.length" class="empty">暂无安全标签，请点击右上角「新建自定义标签」。</div>
    </div>

    <Modal v-model="show" :title="editing ? '编辑标签' : '新建自定义标签'" :loading="saving" @confirm="save">
      <div class="form-item">
        <label>标签名称</label>
        <input class="input" v-model="form.name" :disabled="editing" placeholder="例如：商业机密检测" />
      </div>
      <div class="form-item">
        <label>检测方向</label>
        <select class="select" v-model="form.direction">
          <option value="both">输入与输出</option>
          <option value="input">仅检测输入</option>
          <option value="output">仅检测输出</option>
        </select>
      </div>
      <div class="form-item">
        <label>风险类型（用于检测结果归类）</label>
        <select class="select" v-model="form.risk_type" :disabled="editing && editing.is_builtin">
          <option v-for="r in riskTypes" :key="r" :value="r">{{ r }}</option>
        </select>
      </div>
      <div class="form-item">
        <label>说明</label>
        <textarea class="textarea" v-model="form.description" style="min-height: 60px"></textarea>
      </div>
    </Modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { tagApi } from '../api/resources'
import { toast, errMsg } from '../stores/toast'
import Modal from '../components/Modal.vue'

const tags = ref([])
const show = ref(false)
const saving = ref(false)
const editing = ref(null)
const riskTypes = ['个人信息检测', '偏离主题检测', '越狱攻击检测', '幻觉/虚构检测', '不当言论/低俗内容检测', '提及竞品', '其他']
const form = ref({ name: '', direction: 'both', risk_type: '其他', description: '' })

function directionLabel(d) {
  return { both: '输入与输出', input: '仅输入', output: '仅输出' }[d] || d
}

async function load() {
  try {
    tags.value = (await tagApi.list()).data
  } catch (e) {
    toast.error(errMsg(e))
  }
}

function openCreate() {
  editing.value = null
  form.value = { name: '', direction: 'both', risk_type: '其他', description: '' }
  show.value = true
}
function openEdit(t) {
  editing.value = t
  form.value = { name: t.name, direction: t.direction, risk_type: t.risk_type, description: t.description }
  show.value = true
}
function openCopy(t) {
  editing.value = null
  form.value = { name: t.name + '-副本', direction: t.direction, risk_type: t.risk_type, description: t.description }
  show.value = true
}

async function save() {
  if (!editing.value && !form.value.name.trim()) {
    toast.error('请填写标签名称')
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      const payload = {
        direction: form.value.direction,
        description: form.value.description
      }
      // 内置标签风险类型固定，仅自定义标签允许修改
      if (!editing.value.is_builtin) payload.risk_type = form.value.risk_type
      await tagApi.update(editing.value.id, payload)
    } else {
      await tagApi.create(form.value)
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

async function remove(t) {
  if (!confirm(`确认删除标签「${t.name}」？`)) return
  try {
    await tagApi.remove(t.id)
    toast.success('已删除')
    await load()
  } catch (e) {
    toast.error(errMsg(e))
  }
}

onMounted(load)
</script>
