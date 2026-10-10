<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">系统概览</div>
        <div class="page-desc">护栏系统运行状态与检测统计一览。</div>
      </div>
    </div>

    <!-- 指标卡片 -->
    <div class="cards">
      <div class="card" v-for="c in cards" :key="c.label">
        <div class="card-icon" :style="{ background: c.bg }">{{ c.icon }}</div>
        <div>
          <div class="card-value">{{ c.value }}</div>
          <div class="card-label">{{ c.label }}</div>
        </div>
      </div>
    </div>

    <div class="row mt" style="gap: 16px; align-items: stretch">
      <div class="panel grow">
        <div class="panel-title">近 7 日检测趋势</div>
        <div ref="trendEl" style="height: 280px"></div>
      </div>
      <div class="panel" style="width: 360px">
        <div class="panel-title">风险类型分布</div>
        <div ref="pieEl" style="height: 280px"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import { obsApi } from '../api/resources'
import { toast, errMsg } from '../stores/toast'

const cards = ref([])
const trendEl = ref(null)
const pieEl = ref(null)
let trendChart, pieChart

async function load() {
  try {
    const { data } = await obsApi.stats()
    cards.value = [
      { label: '累计检测请求', value: data.total_requests, icon: '📨', bg: '#d9ecff' },
      { label: '安全通过', value: data.safe_count, icon: '✅', bg: '#d6f5e6' },
      { label: '拦截风险', value: data.unsafe_count, icon: '🚫', bg: '#ffe0dd' },
      { label: '平均耗时（ms）', value: data.avg_latency_ms, icon: '⚡', bg: '#fff2d6' },
      { label: '接入模型', value: data.model_count, icon: '🧩', bg: '#e6e0ff' },
      { label: '策略编排', value: data.strategy_count, icon: '⚖️', bg: '#d9f4ff' },
      { label: '检测场景', value: data.api_path_count, icon: '🛣️', bg: '#ffe6f0' }
    ]
    await nextTick()
    renderTrend(data.recent_trend)
    renderPie(data.risk_type_distribution)
  } catch (e) {
    toast.error(errMsg(e))
  }
}

function renderTrend(trend) {
  if (!trendChart) trendChart = echarts.init(trendEl.value)
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['检测总量', '拦截风险'], bottom: 0 },
    grid: { left: 40, right: 20, top: 20, bottom: 40 },
    xAxis: { type: 'category', data: trend.map((t) => t.date) },
    yAxis: { type: 'value' },
    series: [
      { name: '检测总量', type: 'line', smooth: true, data: trend.map((t) => t.total),
        areaStyle: { color: 'rgba(43,143,255,0.15)' }, itemStyle: { color: '#2b8fff' } },
      { name: '拦截风险', type: 'line', smooth: true, data: trend.map((t) => t.unsafe),
        areaStyle: { color: 'rgba(245,86,74,0.12)' }, itemStyle: { color: '#f5564a' } }
    ]
  })
}

function renderPie(dist) {
  if (!pieChart) pieChart = echarts.init(pieEl.value)
  const data = Object.entries(dist).map(([name, value]) => ({ name, value }))
  pieChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, type: 'scroll' },
    series: [
      {
        type: 'pie', radius: ['40%', '65%'], center: ['50%', '42%'],
        data: data.length ? data : [{ name: '暂无风险记录', value: 1 }],
        label: { formatter: '{b}: {c}' }
      }
    ],
    color: ['#f5564a', '#f0a020', '#2b8fff', '#16d6e6', '#8a6bff', '#1bbf73', '#9aa7bd']
  })
}

function onResize() {
  trendChart && trendChart.resize()
  pieChart && pieChart.resize()
}

onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  trendChart && trendChart.dispose()
  pieChart && pieChart.dispose()
})
</script>

<style scoped>
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}
.card {
  background: #fff;
  border: 1px solid var(--c-border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 16px 18px;
  display: flex;
  align-items: center;
  gap: 14px;
}
.card-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}
.card-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--c-text);
  line-height: 28px;
}
.card-label {
  font-size: 12px;
  color: var(--c-text-sub);
  margin-top: 2px;
}
</style>
