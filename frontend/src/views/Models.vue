<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">检测能力</div>
        <div class="page-desc">接入外部 AI 安全检测服务或自定义脚本，统一管理检测模型资源池。</div>
      </div>
      <button class="btn btn-primary" @click="openCreate">+ 接入模型</button>
    </div>

    <div class="panel">
      <table class="table">
        <thead>
          <tr>
            <th>名称</th>
            <th class="th-center">接入方式</th>
            <th>安全标签</th>
            <th class="th-center">状态</th>
            <th class="col-actions">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in models" :key="m.id">
            <td>
              <div>{{ m.name }}</div>
              <div class="cell-desc">{{ m.description || '—' }}</div>
            </td>
            <td class="td-center">
              <span class="badge" :class="m.access_type === 'rest' ? '' : 'badge-gray'">
                {{ m.access_type === 'rest' ? 'REST 接口' : 'Python 脚本' }}
              </span>
            </td>
            <td>
              <span v-for="t in m.tags" :key="t.id" class="badge">{{ t.name }}</span>
              <span v-if="!m.tags.length" class="text-sub">未绑定</span>
            </td>
            <td class="td-center">
              <span class="badge" :class="m.enabled ? 'badge-success' : 'badge-danger'">
                {{ m.enabled ? '启用' : '停用' }}
              </span>
            </td>
            <td class="col-actions">
              <button class="btn btn-sm" @click="validate(m)" :disabled="validating === m.id">
                {{ validating === m.id ? '检测中…' : '有效性检测' }}
              </button>
              <button class="btn btn-sm" @click="openEdit(m)">编辑</button>
              <button class="btn btn-sm" @click="openCopy(m)">复制</button>
              <button class="btn btn-sm btn-danger" @click="remove(m)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!models.length" class="empty">暂无检测模型，请点击右上角「接入模型」开始配置。</div>
    </div>

    <!-- 新建/编辑弹窗 -->
    <Modal v-model="show" :title="editing ? '编辑' : '接入模型'" :loading="saving" @confirm="save">
      <div class="form-item">
        <label>模型名称</label>
        <input class="input" v-model="form.name" placeholder="例如：个人信息检测服务" />
      </div>
      <div class="form-item">
        <label>说明</label>
        <input class="input" v-model="form.description" placeholder="可选" />
      </div>
      <div class="form-item">
        <label>接入方式</label>
        <select class="select" v-model="form.access_type" :disabled="editing">
          <option value="rest">REST 接口</option>
          <option value="script">Python 脚本</option>
        </select>
      </div>

      <!-- REST 配置 -->
      <template v-if="form.access_type === 'rest'">
        <div class="form-item">
          <label>接口地址</label>
          <input class="input" v-model="form.endpoint_url" placeholder="https://example.com/detect" />
        </div>
        <div class="form-item">
          <label>请求方法</label>
          <select class="select" v-model="form.http_method">
            <option>POST</option>
            <option>GET</option>
          </select>
        </div>
        <div class="form-item">
          <label>请求头（JSON，可选）</label>
          <textarea class="textarea" v-model="headersText" placeholder='{"Authorization": "Bearer xxx"}'></textarea>
        </div>
        <div class="form-item">
          <label>请求体模板（JSON，使用 {content} 注入被检测内容）</label>
          <textarea class="textarea" v-model="bodyText" placeholder='{"text": "{content}"}'></textarea>
        </div>
        <div class="section-title">安全判定条件</div>
        <div class="form-item">
          <label>响应状态码等于（留空则不校验）</label>
          <input class="input" v-model.number="form.safe_status_code" type="number" placeholder="例如：200" />
        </div>
        <div class="row">
          <div class="form-item grow">
            <label>响应体取值路径（JsonPath）</label>
            <input class="input" v-model="form.safe_jsonpath" placeholder="例如：$.result" />
          </div>
          <div class="form-item grow">
            <label>该值需等于（不区分大小写）</label>
            <input class="input" v-model="form.safe_expected_value" placeholder="例如：safe" />
          </div>
        </div>
        <div class="hint">满足以上条件即判定为「安全」；多个条件需同时满足。</div>
        <div class="form-item mt">
          <label>不安全提示信息提取路径（JsonPath）</label>
          <input class="input" v-model="form.prompt_jsonpath" placeholder="例如：$.message" />
          <div class="hint">检测不通过时，从响应体提取该字段作为风险提示。</div>
        </div>
      </template>

      <!-- 脚本配置 -->
      <template v-else>
        <div class="form-item">
          <label>Python 脚本</label>
          <textarea class="textarea" v-model="form.script_content" style="min-height: 160px"
            :placeholder="scriptPlaceholder"></textarea>
          <div class="hint">
            约定定义 detect(content) 函数，返回两个值：第一个为 0 表示安全（非 0 表示不安全），第二个为风险提示信息；安全时第二个值可留空。
          </div>
        </div>
      </template>

      <div class="form-item">
        <label>安全标签（可多选）</label>
        <div class="tag-picker">
          <span v-for="t in tags" :key="t.id" class="tag-opt" :class="{ active: form.tag_ids.includes(t.id) }"
            @click="toggleTag(t.id)">{{ t.name }}</span>
        </div>
      </div>
      <div class="form-item">
        <label class="row" style="cursor: pointer" @click="form.enabled = !form.enabled">
          <span class="switch" :class="{ on: form.enabled }"></span> 启用该模型
        </label>
      </div>
    </Modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { modelApi, tagApi } from '../api/resources'
import { toast, errMsg } from '../stores/toast'
import Modal from '../components/Modal.vue'

const models = ref([])
const tags = ref([])
const show = ref(false)
const saving = ref(false)
const editing = ref(null)
const validating = ref(0)
const headersText = ref('')
const bodyText = ref('')

const scriptPlaceholder = `def detect(content):
    # content 为被检测的文本内容
    if "敏感词" in content:
        return 1, "内容包含敏感词"
    return 0, ""`

const blank = () => ({
  name: '', description: '', access_type: 'rest', enabled: true,
  endpoint_url: '', http_method: 'POST', headers: {}, body_template: {},
  safe_status_code: null, safe_jsonpath: '', safe_expected_value: '', prompt_jsonpath: '',
  script_content: '', tag_ids: []
})
const form = ref(blank())

async function load() {
  try {
    models.value = (await modelApi.list()).data
    tags.value = (await tagApi.list()).data
  } catch (e) {
    toast.error(errMsg(e))
  }
}

function toggleTag(id) {
  const i = form.value.tag_ids.indexOf(id)
  if (i >= 0) form.value.tag_ids.splice(i, 1)
  else form.value.tag_ids.push(id)
}

function openCreate() {
  editing.value = null
  form.value = blank()
  headersText.value = ''
  bodyText.value = ''
  show.value = true
}
function openEdit(m) {
  editing.value = m
  form.value = {
    ...blank(), ...m,
    tag_ids: m.tags.map((t) => t.id)
  }
  headersText.value = Object.keys(m.headers || {}).length ? JSON.stringify(m.headers, null, 2) : ''
  bodyText.value = Object.keys(m.body_template || {}).length ? JSON.stringify(m.body_template, null, 2) : ''
  show.value = true
}
function openCopy(m) {
  editing.value = null
  form.value = {
    ...blank(), ...m,
    name: m.name + '-副本',
    tag_ids: m.tags.map((t) => t.id)
  }
  headersText.value = Object.keys(m.headers || {}).length ? JSON.stringify(m.headers, null, 2) : ''
  bodyText.value = Object.keys(m.body_template || {}).length ? JSON.stringify(m.body_template, null, 2) : ''
  show.value = true
}

function parseJson(text, label) {
  if (!text.trim()) return {}
  try {
    return JSON.parse(text)
  } catch {
    throw new Error(`${label} 不是合法的 JSON`)
  }
}

async function save() {
  saving.value = true
  try {
    if (form.value.access_type === 'rest') {
      form.value.headers = parseJson(headersText.value, '请求头')
      form.value.body_template = parseJson(bodyText.value, '请求体模板')
      if (!form.value.endpoint_url) throw new Error('请填写接口地址')
    } else {
      if (!form.value.script_content.trim()) throw new Error('请填写脚本内容')
    }
    if (!form.value.name.trim()) throw new Error('请填写模型名称')

    if (editing.value) {
      await modelApi.update(editing.value.id, form.value)
    } else {
      await modelApi.create(form.value)
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

async function validate(m) {
  validating.value = m.id
  try {
    const { data } = await modelApi.validate(m.id)
    if (data.ok) toast.success(data.message)
    else toast.error(data.message + (data.detail ? '：' + data.detail.slice(0, 80) : ''))
  } catch (e) {
    toast.error(errMsg(e))
  } finally {
    validating.value = 0
  }
}

async function remove(m) {
  if (!confirm(`确认删除模型「${m.name}」？`)) return
  try {
    await modelApi.remove(m.id)
    toast.success('已删除')
    await load()
  } catch (e) {
    toast.error(errMsg(e))
  }
}

onMounted(load)
</script>
