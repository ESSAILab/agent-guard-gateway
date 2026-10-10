<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">检测场景</div>
        <div class="page-desc">将检测策略按顺序挂载到对外路径，形成可接入的多维度检测场景。</div>
      </div>
      <button class="btn btn-primary" @click="openCreate">+ 新建场景</button>
    </div>

    <div class="panel">
      <table class="table">
        <thead>
          <tr>
            <th>场景名称</th>
            <th>对外路径</th>
            <th>策略链</th>
            <th class="th-center">认证</th>
            <th class="th-center">状态</th>
            <th class="col-actions">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in paths" :key="p.id">
            <td>{{ p.name }}</td>
            <td><code class="code-inline">POST /guard{{ p.path }}</code></td>
            <td>
              <template v-if="p.strategies.length">
                <span v-for="(s, i) in p.strategies" :key="s.id" class="badge">{{ i + 1 }}. {{ s.name }}</span>
              </template>
              <span v-else class="text-sub">未配置</span>
            </td>
            <td class="td-center">
              <span class="badge" :class="p.api_key_id ? '' : 'badge-gray'">{{ keyName(p.api_key_id) }}</span>
            </td>
            <td class="td-center">
              <span class="switch" :class="{ on: p.enabled }" @click="toggleEnable(p)" style="cursor: pointer"></span>
            </td>
            <td class="col-actions">
              <button class="btn btn-sm" @click="openEdit(p)">编辑</button>
              <button class="btn btn-sm" @click="openCopy(p)">复制</button>
              <button class="btn btn-sm btn-danger" @click="remove(p)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!paths.length" class="empty">暂无检测场景，请点击右上角「新建场景」开始配置。</div>
    </div>

    <Modal v-model="show" :title="editing ? '编辑场景' : '新建场景'" :loading="saving" @confirm="save">
      <div class="form-item">
        <label>场景名称</label>
        <input class="input" v-model="form.name" placeholder="例如：聊天输入检测" />
      </div>
      <div class="form-item">
        <label>对外路径</label>
        <input class="input" v-model="form.path" placeholder="/chat-input" />
        <div class="hint">集成方通过 POST /guard{{ normalizedPath }} 调用该场景。</div>
      </div>
      <div class="form-item">
        <label>认证密钥</label>
        <select class="select" v-model="form.api_key_id">
          <option :value="null">不绑定（开放访问，不建议生产使用）</option>
          <option v-for="k in keys" :key="k.id" :value="k.id">{{ k.name }}</option>
        </select>
      </div>

      <div class="form-item">
        <label>策略链（按顺序调用，任一策略判定不安全即整体不安全）</label>
        <div class="chain">
          <div v-for="(sid, idx) in form.strategy_ids" :key="sid" class="chain-item">
            <span class="order">{{ idx + 1 }}</span>
            <span class="grow">{{ strategyName(sid) }}</span>
            <button class="btn btn-sm btn-ghost" :disabled="idx === 0" @click="move(idx, -1)">↑</button>
            <button class="btn btn-sm btn-ghost" :disabled="idx === form.strategy_ids.length - 1" @click="move(idx, 1)">↓</button>
            <button class="btn btn-sm btn-danger" @click="removeStrategy(idx)">移除</button>
          </div>
          <div v-if="!form.strategy_ids.length" class="hint">尚未添加策略</div>
        </div>
        <div class="row mt">
          <select class="select grow" v-model.number="addSel">
            <option :value="0" disabled>选择要加入的策略…</option>
            <option v-for="s in addableStrategies" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
          <button class="btn" @click="addStrategy">加入策略链</button>
        </div>
      </div>

      <div class="form-item">
        <label class="row" style="cursor: pointer" @click="form.enabled = !form.enabled">
          <span class="switch" :class="{ on: form.enabled }"></span> 该路径生效
        </label>
      </div>
    </Modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { pathApi, strategyApi, keyApi } from '../api/resources'
import { toast, errMsg } from '../stores/toast'
import Modal from '../components/Modal.vue'

const paths = ref([])
const strategies = ref([])
const keys = ref([])
const show = ref(false)
const saving = ref(false)
const editing = ref(null)
const addSel = ref(0)

const blank = () => ({ name: '', path: '', api_key_id: null, enabled: true, strategy_ids: [] })
const form = ref(blank())

const normalizedPath = computed(() => {
  let p = (form.value.path || '').trim()
  if (p && !p.startsWith('/')) p = '/' + p
  return p
})
const addableStrategies = computed(() =>
  strategies.value.filter((s) => !form.value.strategy_ids.includes(s.id))
)

function strategyName(id) {
  const s = strategies.value.find((x) => x.id === id)
  return s ? s.name : `策略#${id}`
}
function keyName(id) {
  if (!id) return '未绑定'
  const k = keys.value.find((x) => x.id === id)
  return k ? k.name : `#${id}`
}

async function load() {
  try {
    paths.value = (await pathApi.list()).data
    strategies.value = (await strategyApi.list()).data
    keys.value = (await keyApi.list()).data
  } catch (e) {
    toast.error(errMsg(e))
  }
}

function move(idx, dir) {
  const arr = form.value.strategy_ids
  const j = idx + dir
  if (j < 0 || j >= arr.length) return
  ;[arr[idx], arr[j]] = [arr[j], arr[idx]]
}
function addStrategy() {
  if (!addSel.value) return
  form.value.strategy_ids.push(addSel.value)
  addSel.value = 0
}
function removeStrategy(idx) {
  form.value.strategy_ids.splice(idx, 1)
}

function openCreate() {
  editing.value = null
  form.value = blank()
  addSel.value = 0
  show.value = true
}
function openEdit(p) {
  editing.value = p
  form.value = {
    name: p.name, path: p.path, api_key_id: p.api_key_id, enabled: p.enabled,
    strategy_ids: p.strategies.map((s) => s.id)
  }
  addSel.value = 0
  show.value = true
}
function openCopy(p) {
  editing.value = null
  form.value = {
    name: p.name + '-副本', path: p.path + '-copy', api_key_id: p.api_key_id, enabled: p.enabled,
    strategy_ids: p.strategies.map((s) => s.id)
  }
  addSel.value = 0
  show.value = true
}

async function save() {
  if (!form.value.name.trim()) return toast.error('请填写名称')
  if (!normalizedPath.value) return toast.error('请填写对外路径')
  saving.value = true
  try {
    const payload = { ...form.value, path: normalizedPath.value }
    if (editing.value) await pathApi.update(editing.value.id, payload)
    else await pathApi.create(payload)
    toast.success('保存成功')
    show.value = false
    await load()
  } catch (e) {
    toast.error(errMsg(e))
  } finally {
    saving.value = false
  }
}

async function toggleEnable(p) {
  try {
    await pathApi.update(p.id, { enabled: !p.enabled })
    await load()
  } catch (e) {
    toast.error(errMsg(e))
  }
}
async function remove(p) {
  if (!confirm(`确认删除场景「${p.name}」？`)) return
  try {
    await pathApi.remove(p.id)
    toast.success('已删除')
    await load()
  } catch (e) {
    toast.error(errMsg(e))
  }
}

onMounted(load)
</script>

<style scoped>
.chain {
  border: 1px dashed var(--c-border);
  border-radius: 8px;
  padding: 12px;
  min-height: 50px;
}
.chain-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  background: #f6faff;
  border-radius: 7px;
  margin-bottom: 8px;
}
.order {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--c-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}
</style>
