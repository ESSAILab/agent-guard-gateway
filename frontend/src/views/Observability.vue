<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">检测记录</div>
        <div class="page-desc">查询用户请求、响应与各检测组件的调用记录。</div>
      </div>
      <div class="row">
        <input class="input" v-model.number="purgeDays" type="number" min="1" style="width: 110px" placeholder="天数" />
        <button class="btn btn-danger" @click="purge">删除 {{ purgeDays || '?' }} 天前记录</button>
        <button class="btn" @click="load">刷新</button>
      </div>
    </div>

    <!-- 过滤条件 -->
    <div class="panel">
      <div class="filter-bar">
        <div class="form-item" style="width: 160px">
          <label>检测结果</label>
          <select class="select" v-model="filter.result">
            <option value="">全部</option>
            <option value="safe">安全</option>
            <option value="unsafe">不安全</option>
          </select>
        </div>
        <div class="form-item" style="width: 240px">
          <label>对外路径（支持部分匹配）</label>
          <input class="input" v-model="filter.api_path" placeholder="例如：/chat" @keyup.enter="search" />
        </div>
        <div class="form-item">
          <button class="btn btn-primary" @click="search">查询</button>
        </div>
      </div>
    </div>

    <!-- 请求日志 -->
    <div class="panel mt">
      <table class="table">
        <thead>
          <tr>
            <th class="th-center">时间</th>
            <th>对外路径</th>
            <th class="th-center">来源 IP</th>
            <th class="th-center">结果</th>
            <th class="th-center">模型判定（安全/不安全）</th>
            <th>风险类型</th>
            <th class="th-center">耗时（ms）</th>
            <th class="col-actions">详情</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in logs" :key="r.id">
            <td class="td-center text-sub">{{ fmt(r.created_at) }}</td>
            <td><code class="code-inline">{{ r.api_path }}</code></td>
            <td class="td-center text-sub">{{ r.client_ip || '—' }}</td>
            <td class="td-center">
              <span class="badge" :class="r.result === 'safe' ? (r.unsafe_count > 0 ? 'badge-warning' : 'badge-success') : 'badge-danger'">
                {{ r.result === 'safe' ? '安全' : '不安全' }}
              </span>
            </td>
            <td class="td-center">{{ r.safe_count }} / {{ r.unsafe_count }}</td>
            <td>{{ r.risk_type || '—' }}</td>
            <td class="td-center">{{ r.latency_ms.toFixed(1) }}</td>
            <td class="col-actions"><button class="btn btn-sm" @click="openDetail(r)">查看</button></td>
          </tr>
        </tbody>
      </table>
      <div v-if="!logs.length" class="empty">暂无检测记录，请调整过滤条件后重新查询。</div>

      <!-- 分页 -->
      <div v-if="total > 0" class="row between pager">
        <div class="text-sub">
          共 {{ total }} 条，第 {{ page }} / {{ totalPages }} 页
        </div>
        <div class="row" style="gap: 8px">
          <button class="btn btn-sm" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
          <button class="btn btn-sm" :disabled="page >= totalPages" @click="goPage(page + 1)">下一页</button>
        </div>
      </div>
    </div>

    <!-- 明细弹窗 -->
    <transition name="fade">
      <div v-if="detail" class="modal-mask" @click.self="detail = null">
        <div class="modal detail-modal">
          <div class="modal-header">检测明细 · 请求 #{{ detail.id }}</div>
          <div class="modal-body">
            <div class="detail-sec">
              <div class="detail-label">用户请求</div>
              <pre class="code-block">{{ pretty(detail.request_body) }}</pre>
            </div>
            <div class="detail-sec">
              <div class="detail-label">护栏响应</div>
              <pre class="code-block">{{ pretty(detail.response_body) }}</pre>
            </div>
            <div class="detail-sec">
              <div class="detail-label">检测模型调用记录</div>
              <table class="table">
                <thead>
                  <tr>
                    <th>策略</th>
                    <th>模型</th>
                    <th class="th-center">接入方式</th>
                    <th class="th-center">结果</th>
                    <th class="th-center">耗时（ms）</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="d in detLogs" :key="d.id">
                    <td>{{ d.strategy_name }}</td>
                    <td>{{ d.model_name }}</td>
                    <td class="td-center">{{ d.access_type === 'rest' ? 'REST' : '脚本' }}</td>
                    <td class="td-center">
                      <span class="badge" :class="resultClass(d.result)">{{ resultLabel(d.result) }}</span>
                    </td>
                    <td class="td-center">{{ d.latency_ms.toFixed(1) }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-if="!detLogs.length" class="empty">暂无模型调用记录。</div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-ghost" @click="detail = null">关闭</button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { obsApi } from '../api/resources'
import { toast, errMsg } from '../stores/toast'

const PAGE_SIZE = 50

const logs = ref([])
const detail = ref(null)
const detLogs = ref([])
const filter = reactive({ result: '', api_path: '' })
const page = ref(1)
const total = ref(0)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const purgeDays = ref(30)

function fmt(s) {
  const str = String(s)
  const d = /[Zz]|[+-]\d{2}:?\d{2}$/.test(str) ? new Date(str) : new Date(str + 'Z')
  return d.toLocaleString('zh-CN')
}
function pretty(o) {
  return JSON.stringify(o, null, 2)
}
function resultLabel(r) {
  return { safe: '安全', unsafe: '不安全', timeout: '超时', error: '异常' }[r] || r
}
function resultClass(r) {
  if (r === 'safe') return 'badge-success'
  if (r === 'unsafe' || r === 'error') return 'badge-danger'
  return 'badge-gray'
}

async function load() {
  try {
    const params = { page: page.value, page_size: PAGE_SIZE }
    if (filter.result) params.result = filter.result
    if (filter.api_path) params.api_path = filter.api_path
    const data = (await obsApi.requestLogs(params)).data
    logs.value = data.items
    total.value = data.total
    // 删除/过滤后当前页可能超出范围，回退到最后一页
    if (page.value > totalPages.value) {
      page.value = totalPages.value
      await load()
    }
  } catch (e) {
    toast.error(errMsg(e))
  }
}

function search() {
  page.value = 1
  load()
}

function goPage(p) {
  if (p < 1 || p > totalPages.value) return
  page.value = p
  load()
}

async function purge() {
  const days = Number(purgeDays.value)
  if (!Number.isInteger(days) || days < 1) {
    toast.error('请输入不小于 1 的天数')
    return
  }
  if (!confirm(`确认删除 ${days} 天以前的全部检测记录？该操作不可恢复。`)) return
  try {
    const res = await obsApi.purgeLogs(days)
    toast.success(`已删除 ${res.data.deleted ?? 0} 条记录`)
    await load()
  } catch (e) {
    toast.error(errMsg(e))
  }
}

async function openDetail(r) {
  detail.value = r
  try {
    detLogs.value = (await obsApi.detectionLogs({ request_log_id: r.id })).data
  } catch (e) {
    detLogs.value = []
    toast.error(errMsg(e, '模型调用记录加载失败'))
  }
}

onMounted(load)
</script>

<style scoped>
.detail-modal {
  width: 720px;
}
.detail-sec {
  margin-bottom: 18px;
}
.detail-label {
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--c-primary-deep);
}
.code-block {
  background: #0e2748;
  color: #b8d4f5;
  padding: 12px;
  border-radius: 8px;
  font-size: 12px;
  overflow-x: auto;
  font-family: 'Consolas', monospace;
  white-space: pre-wrap;
  word-break: break-all;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}
</style>
