<template>
  <div class="screen">
    <!-- 顶栏 -->
    <header class="screen-header">
      <div class="title">
        AI智能体安全网关
      </div>
    </header>

    <div class="screen-body">
      <!-- 左侧统计 -->
      <div class="col-left">
        <!-- 日期时钟 -->
        <div class="datetime-box">
          <div class="date-display">{{ date }}</div>
          <div class="time-display">{{ clock }}</div>
        </div>
        <div class="stat-box">
          <div class="stat-num">{{ stats.total_requests }}</div>
          <div class="stat-label">累计检测请求</div>
        </div>
        <div class="stat-grid">
          <div class="mini-stat safe">
            <div class="mini-num">{{ stats.safe_count }}</div>
            <div class="mini-label">安全通过</div>
          </div>
          <div class="mini-stat danger">
            <div class="mini-num">{{ stats.unsafe_count }}</div>
            <div class="mini-label">拦截风险</div>
          </div>
          <div class="mini-stat">
            <div class="mini-num">{{ stats.avg_latency_ms }}</div>
            <div class="mini-label">平均耗时（ms）</div>
          </div>
          <div class="mini-stat">
            <div class="mini-num">{{ liveCount }}</div>
            <div class="mini-label">本次会话检测</div>
          </div>
        </div>
        <div class="panel-dark">
          <div class="ptitle">风险类型分布</div>
          <div ref="pieEl" style="height: 240px"></div>
        </div>
        <!-- 连接状态 -->
        <div class="conn-status" :class="{ on: connected }">
          <span class="conn-dot"></span>
          <span class="conn-text">{{ connected ? '实时在线' : '连接中' }}</span>
        </div>
      </div>

      <!-- 中央交互动画 -->
      <div class="col-center">
        <div class="flow-stage">
          <!-- AI 应用节点 -->
          <div class="node node-app" :class="{ pulse: appPulse }">
            <div class="node-icon"><img src="../assets/robot.png" alt="AI智能体" /></div>
            <div class="node-name">智能体</div>
          </div>

          <!-- 应用 <-> 护栏 连线 -->
          <div class="link link-main">
            <div v-for="p in appPackets" :key="p.id" class="packet" :class="p.dir"
              :style="{ '--c': p.color }"></div>
          </div>

          <!-- 护栏网关节点 -->
          <div class="node node-gw" :class="{ pulse: gwPulse }">
            <div class="node-icon"><img src="../assets/AI-Guard.png" alt="网关" /></div>
            <div class="node-name">AI网关</div>
            <div class="gw-verdict" :class="verdict.cls" v-if="verdict.text">{{ verdict.text }}</div>
          </div>

          <!-- 护栏 <-> 策略链 -->
          <div class="link link-fan"></div>

          <!-- 策略链与模型 -->
          <div class="strategy-col">
            <transition-group name="slide">
              <div v-for="s in activeStrategies" :key="s.key" class="strategy-block" :class="{ done: s.done, unsafe: s.done && !s.safe }">
                <div class="strategy-head">
                  <span class="strategy-name">⚖️ {{ s.name }}</span>
                  <span class="strategy-rule">{{ ruleLabel(s.rule_type) }}</span>
                </div>
                <!-- 检测模型判定 -->
                <div class="models-row">
                  <div v-for="(m, i) in s.models" :key="i" class="model-chip"
                    :class="chipClass(m)">
                    <span class="chip-dot"></span>
                    <span class="chip-name">{{ m.name }}</span>
                    <span class="chip-vote">{{ voteIcon(m) }}</span>
                  </div>
                  <div v-if="!s.models.length" class="model-waiting">调用中…</div>
                </div>
                <div v-if="s.done" class="strategy-verdict" :class="s.safe ? 'ok' : 'bad'">
                  {{ s.safe ? '✓ 判定安全' : '✕ 判定不安全' }}
                </div>
              </div>
            </transition-group>
            <div v-if="!activeStrategies.length" class="idle-hint">
              等待检测请求…
            </div>
          </div>
        </div>
        <!-- 近 7 日趋势 -->
        <div class="panel-dark trend-panel">
          <div class="ptitle">近 7 日趋势</div>
          <div ref="trendEl" style="height: 160px"></div>
        </div>
      </div>

      <!-- 右侧实时事件流 -->
      <div class="col-right">
        <div class="panel-dark fill">
          <div class="ptitle">实时事件</div>
          <div class="event-list">
            <transition-group name="evt">
              <div v-for="e in events" :key="e.id" class="event-item" :class="e.cls">
                <span class="evt-time">{{ e.time }}</span>
                <span class="evt-text">{{ e.text }}</span>
              </div>
            </transition-group>
            <div v-if="!events.length" class="idle-hint">暂无事件</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import { obsApi } from '../api/resources'

// ---- 状态 ----
const date = ref('')
const clock = ref('')
const connected = ref(false)
const stats = reactive({ total_requests: 0, safe_count: 0, unsafe_count: 0, avg_latency_ms: 0 })
const liveCount = ref(0)
const events = ref([])
const activeStrategies = ref([])
const appPackets = ref([])
const appPulse = ref(false)
const gwPulse = ref(false)
const verdict = reactive({ text: '', cls: '' })

const pieEl = ref(null)
const trendEl = ref(null)
let pieChart, trendChart, ws, clockTimer, statsTimer
let seq = 0
let curStrategyKey = 0

// ---- 工具 ----
function today() {
  return new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', weekday: 'long' })
}
function now() {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false })
}
function pushEvent(text, cls = '') {
  events.value.unshift({ id: ++seq, time: now(), text, cls })
  if (events.value.length > 30) events.value.pop()
}
function spawnPacket(dir, color) {
  const id = ++seq
  appPackets.value.push({ id, dir, color })
  setTimeout(() => {
    const i = appPackets.value.findIndex((p) => p.id === id)
    if (i >= 0) appPackets.value.splice(i, 1)
  }, 1400)
}

function chipClass(m) {
  if (m.status === 'pending') return 'pending'
  if (m.status === 'timeout') return 'timeout'
  if (m.status === 'error') return 'error'
  return m.safe ? 'safe' : 'unsafe'
}
function voteIcon(m) {
  if (m.status === 'pending') return '…'
  if (m.status === 'timeout') return '⏱'
  if (m.status === 'error') return '⚠'
  return m.safe ? '✓' : '✕'
}
function ruleLabel(ruleType) {
  return ruleType === 'random' ? '随机检测' : '顺序检测'
}

// ---- WebSocket 事件处理 ----
function handleEvent(msg) {
  const { type, payload } = msg
  if (type === 'request_received') {
    liveCount.value++
    appPulse.value = true
    setTimeout(() => (appPulse.value = false), 600)
    spawnPacket('forward', '#16d6e6')
    verdict.text = ''
    activeStrategies.value = []
    pushEvent(`收到检测请求 · 路径 ${payload.api_path}`, 'info')
  } else if (type === 'strategy_start') {
    gwPulse.value = true
    setTimeout(() => (gwPulse.value = false), 600)
    const block = reactive({
      key: ++curStrategyKey, name: payload.strategy,
      rule_type: payload.rule_type || 'sequential',
      models: [], safe: true, done: false
    })
    activeStrategies.value.push(block)
    if (activeStrategies.value.length > 4) activeStrategies.value.shift()
    pushEvent(`启动策略「${payload.strategy}」（${payload.model_count} 个模型）`, 'info')
  } else if (type === 'strategy_result') {
    const block = activeStrategies.value.find((b) => b.name === payload.strategy && !b.done)
    if (block) {
      block.models = payload.models.map((m) => ({
        name: m.name, status: m.status, safe: m.safe
      }))
      block.safe = payload.safe
      block.done = true
    }
    const tag = payload.safe ? '安全' : '风险'
    pushEvent(
      `策略「${payload.strategy}」${ruleLabel(payload.rule_type)}完成（${payload.invoked} 个模型）→ ${tag}`,
      payload.safe ? 'ok' : 'bad'
    )
  } else if (type === 'final_result') {
    const safe = payload.result === 'safe'
    verdict.text = safe ? '安全放行' : '风险拦截'
    verdict.cls = safe ? 'ok' : 'bad'
    spawnPacket('back', safe ? '#1bbf73' : '#f5564a')
    pushEvent(
      `最终结果：${safe ? '安全' : '不安全'}${payload.risk_type ? ' · ' + payload.risk_type : ''} · 耗时 ${payload.latency_ms || '-'}ms`,
      safe ? 'ok' : 'bad'
    )
    loadStats()
  }
}

function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  ws = new WebSocket(`${proto}://${location.host}/ws/dashboard`)
  ws.onopen = () => {
    connected.value = true
    ws.send('hello')
  }
  ws.onmessage = (ev) => {
    try {
      handleEvent(JSON.parse(ev.data))
    } catch {
      // 大屏为只读展示，忽略无法解析的推送，避免影响后续消息
    }
  }
  ws.onclose = () => {
    connected.value = false
    setTimeout(connect, 3000)
  }
  ws.onerror = () => ws.close()
}

// ---- 统计 ----
async function loadStats() {
  try {
    const { data } = await obsApi.stats()
    stats.total_requests = data.total_requests
    stats.safe_count = data.safe_count
    stats.unsafe_count = data.unsafe_count
    stats.avg_latency_ms = data.avg_latency_ms
    await nextTick()
    renderPie(data.risk_type_distribution)
    renderTrend(data.recent_trend)
  } catch {
    // 统计加载失败时保留上一次渲染结果，大屏静默处理不弹提示
  }
}

function renderPie(dist) {
  if (!pieChart) pieChart = echarts.init(pieEl.value, 'dark')
  const data = Object.entries(dist).map(([name, value]) => ({ name, value }))
  pieChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, textStyle: { color: '#9fc3ef' }, type: 'scroll' },
    series: [{
      type: 'pie', radius: ['38%', '62%'], center: ['50%', '42%'],
      data: data.length ? data : [{ name: '暂无风险', value: 1 }],
      label: { color: '#cfe0f5', formatter: '{b}\n{c}' }
    }],
    color: ['#f5564a', '#f0a020', '#2b8fff', '#16d6e6', '#8a6bff', '#1bbf73', '#9aa7bd']
  })
}
function renderTrend(trend) {
  if (!trendChart) trendChart = echarts.init(trendEl.value, 'dark')
  trendChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 34, right: 12, top: 14, bottom: 24 },
    xAxis: { type: 'category', data: trend.map((t) => t.date), axisLabel: { color: '#9fc3ef' } },
    yAxis: { type: 'value', axisLabel: { color: '#9fc3ef' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } } },
    series: [
      { name: '检测总量', type: 'line', smooth: true, data: trend.map((t) => t.total),
        areaStyle: { color: 'rgba(43,143,255,0.25)' }, itemStyle: { color: '#2b8fff' } },
      { name: '拦截', type: 'line', smooth: true, data: trend.map((t) => t.unsafe),
        itemStyle: { color: '#f5564a' } }
    ]
  })
}

function onResize() {
  pieChart && pieChart.resize()
  trendChart && trendChart.resize()
}

onMounted(() => {
  date.value = today()
  clock.value = now()
  clockTimer = setInterval(() => {
    date.value = today()
    clock.value = now()
  }, 1000)
  loadStats()
  statsTimer = setInterval(loadStats, 15000)
  connect()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  clearInterval(clockTimer)
  clearInterval(statsTimer)
  ws && ws.close()
  window.removeEventListener('resize', onResize)
  pieChart && pieChart.dispose()
  trendChart && trendChart.dispose()
})
</script>

<style scoped>
@import '../styles/dashboard.css';
</style>
