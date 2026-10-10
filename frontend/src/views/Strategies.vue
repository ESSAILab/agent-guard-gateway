<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">策略编排</div>
        <div class="page-desc">将多个检测模型编排为检测策略，按规则调用并汇总判定结果。</div>
      </div>
      <button class="btn btn-primary" @click="openCreate">+ 新建策略</button>
    </div>

    <div class="panel">
      <table class="table">
        <thead>
          <tr>
            <th>策略名称</th>
            <th>安全标签</th>
            <th>调用规则</th>
            <th class="th-center">模型数量</th>
            <th class="th-center">状态</th>
            <th class="col-actions">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in strategies" :key="s.id">
            <td>{{ s.name }}</td>
            <td><span class="badge">{{ tagName(s.tag_id) }}</span></td>
            <td>
              <div>
                {{ ruleLabel(s.rule_type) }}
                <div class="cell-desc">{{ ruleDesc(s.rule_type) }}</div>
              </div>
            </td>
            <td class="td-center">{{ s.models.length }}</td>
            <td class="td-center">
              <span class="badge" :class="s.enabled ? 'badge-success' : 'badge-danger'">
                {{ s.enabled ? '启用' : '停用' }}
              </span>
            </td>
            <td class="col-actions">
              <button class="btn btn-sm" @click="openEdit(s)">编辑</button>
              <button class="btn btn-sm" @click="openCopy(s)">复制</button>
              <button class="btn btn-sm btn-danger" @click="remove(s)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!strategies.length" class="empty">暂无检测策略，请点击右上角「新建策略」开始编排。</div>
    </div>

    <Modal v-model="show" :title="editing ? '编辑策略' : '新建策略'" :loading="saving" @confirm="save">
      <div class="form-item">
        <label>策略名称</label>
        <input class="input" v-model="form.name" placeholder="例如：个人信息检测策略" />
      </div>
      <div class="form-item">
        <label>安全标签</label>
        <select class="select" v-model.number="form.tag_id" @change="filterModels">
          <option :value="0" disabled>请选择安全标签</option>
          <option v-for="t in tags" :key="t.id" :value="t.id">{{ t.name }}</option>
        </select>
        <div class="hint">仅可选择带有该标签的检测模型组成模型集合。</div>
      </div>

      <div class="form-item">
        <label>检测模型（至少选择 1 个）</label>
        <div class="tag-picker" v-if="availableModels.length">
          <span v-for="m in availableModels" :key="m.id" class="tag-opt"
            :class="{ active: form.model_ids.includes(m.id) }" @click="toggleModel(m.id)">
            {{ m.name }}（{{ m.access_type === 'rest' ? 'REST' : '脚本' }}）
          </span>
        </div>
        <div v-else class="hint">该标签下暂无可用模型，请先在「检测能力」中为模型绑定该标签。</div>
        <div class="hint">已选择 {{ form.model_ids.length }} 个模型</div>
      </div>

      <div class="form-item">
        <label>调用规则</label>
        <div class="tag-picker">
          <span class="tag-opt" :class="{ active: form.rule_type === 'sequential' }"
            @click="form.rule_type = 'sequential'">顺序检测</span>
          <span class="tag-opt" :class="{ active: form.rule_type === 'random' }"
            @click="form.rule_type = 'random'">随机检测</span>
        </div>
        <div class="hint">{{ ruleDesc(form.rule_type) }}</div>
      </div>

      <div class="row">
        <div class="form-item grow">
          <label>最长等待时间（秒）</label>
          <input class="input" type="number" v-model.number="form.max_wait_seconds" min="1" />
        </div>
        <div class="form-item grow">
          <label>单模型超时处理</label>
          <select class="select" v-model="form.timeout_policy">
            <option value="unsafe">按不安全计入</option>
            <option value="safe">按安全计入</option>
          </select>
        </div>
      </div>

      <div class="form-item">
        <label class="row" style="cursor: pointer" @click="form.enabled = !form.enabled">
          <span class="switch" :class="{ on: form.enabled }"></span> 启用该策略
        </label>
      </div>
    </Modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { strategyApi, modelApi, tagApi } from '../api/resources'
import { toast, errMsg } from '../stores/toast'
import Modal from '../components/Modal.vue'

const strategies = ref([])
const models = ref([])
const tags = ref([])
const show = ref(false)
const saving = ref(false)
const editing = ref(null)

const blank = () => ({
  name: '', tag_id: 0, enabled: true, rule_type: 'sequential',
  max_wait_seconds: 60, timeout_policy: 'unsafe', model_ids: []
})
const form = ref(blank())

// 仅展示带选定标签的模型
const availableModels = computed(() => {
  if (!form.value.tag_id) return []
  return models.value.filter((m) => m.tags.some((t) => t.id === form.value.tag_id))
})

function tagName(id) {
  const t = tags.value.find((x) => x.id === id)
  return t ? t.name : '—'
}

function ruleLabel(ruleType) {
  return ruleType === 'random' ? '随机检测' : '顺序检测'
}
function ruleDesc(ruleType) {
  return ruleType === 'random'
    ? '从模型池中随机挑选 1 个检测能力调用，以其判定作为整体结果'
    : '按所选顺序逐个调用模型，任一模型判定不安全即终止，整体判定为不安全'
}

async function load() {
  try {
    strategies.value = (await strategyApi.list()).data
    models.value = (await modelApi.list()).data
    tags.value = (await tagApi.list()).data
  } catch (e) {
    toast.error(errMsg(e))
  }
}

function filterModels() {
  // 切换标签时，移除不再符合标签的已选模型
  form.value.model_ids = form.value.model_ids.filter((id) =>
    availableModels.value.some((m) => m.id === id)
  )
}
function toggleModel(id) {
  const i = form.value.model_ids.indexOf(id)
  if (i >= 0) form.value.model_ids.splice(i, 1)
  else form.value.model_ids.push(id)
}

function openCreate() {
  editing.value = null
  form.value = blank()
  show.value = true
}
function openEdit(s) {
  editing.value = s
  form.value = {
    name: s.name, tag_id: s.tag_id, enabled: s.enabled,
    rule_type: s.rule_type || 'sequential',
    max_wait_seconds: s.max_wait_seconds, timeout_policy: s.timeout_policy,
    model_ids: s.models.map((m) => m.id)
  }
  show.value = true
}
function openCopy(s) {
  editing.value = null
  form.value = {
    name: s.name + '-副本', tag_id: s.tag_id, enabled: s.enabled,
    rule_type: s.rule_type || 'sequential',
    max_wait_seconds: s.max_wait_seconds, timeout_policy: s.timeout_policy,
    model_ids: s.models.map((m) => m.id)
  }
  show.value = true
}

async function save() {
  if (!form.value.name.trim()) return toast.error('请填写策略名称')
  if (!form.value.tag_id) return toast.error('请选择安全标签')
  if (!form.value.model_ids.length) return toast.error('请至少选择 1 个检测模型')

  saving.value = true
  try {
    const payload = { ...form.value }
    if (editing.value) await strategyApi.update(editing.value.id, payload)
    else await strategyApi.create(payload)
    toast.success('保存成功')
    show.value = false
    await load()
  } catch (e) {
    toast.error(errMsg(e))
  } finally {
    saving.value = false
  }
}

async function remove(s) {
  if (!confirm(`确认删除策略「${s.name}」？`)) return
  try {
    await strategyApi.remove(s.id)
    toast.success('已删除')
    await load()
  } catch (e) {
    toast.error(errMsg(e))
  }
}

onMounted(load)
</script>
