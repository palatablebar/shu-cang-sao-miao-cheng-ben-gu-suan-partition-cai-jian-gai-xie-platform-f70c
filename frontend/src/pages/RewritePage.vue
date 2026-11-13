<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/authStore'
import { useQueryStore } from '../stores/queryStore'
import { useRewriteStore } from '../stores/rewriteStore'
import { useFeedback } from '../hooks/useFeedback'
import { downloadOptimisationCsv } from '../api/queries'
import BlueprintSheet from '../components/common/BlueprintSheet.vue'
import BlueprintPanel from '../components/common/BlueprintPanel.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorNotice from '../components/common/ErrorNotice.vue'
import MonoMetric from '../components/common/MonoMetric.vue'
import StatusStamp from '../components/common/StatusStamp.vue'
import { ANTI_PATTERN_LABEL, RISK_LABEL, SUGGESTION_STATUS_LABEL } from '../constants/enums'
import { MSG_EMPTY_REWRITE } from '../constants/messages'
import { cny, gibLabel, pct, ratio, scoreLabel } from '../utils/format'

const auth = useAuthStore()
const store = useRewriteStore()
const queries = useQueryStore()
const feedback = useFeedback()
const router = useRouter()

const busy = ref('')
const maxScore = computed(() => Math.max(1, ...store.items.map((item) => item.score)))
const detail = computed(() => store.detail)

async function load() {
  await store.load()
}

async function select(id: number) {
  try {
    await store.select(id)
  } catch (err) {
    feedback.notify((err as Error).message, 'bad')
  }
}

async function generateTop1() {
  busy.value = 'generate'
  try {
    await queries.loadOverview()
    const top = queries.ranking[0]
    if (!top) {
      feedback.notify('还没有查询日志，请先导入', 'bad')
      return
    }
    const created = await store.generate(top.id)
    await store.select(created.id)
    feedback.notify(`已对 ${top.external_id} 生成改写：节省 ${pct(created.saving_pct)}`, 'ok')
  } catch (err) {
    feedback.notify((err as Error).message, 'bad')
  } finally {
    busy.value = ''
  }
}

async function reevaluate() {
  if (!detail.value) return
  busy.value = 'reevaluate'
  try {
    const result = await store.reevaluate(detail.value.id)
    feedback.notify(`重估完成：节省 ${pct(result.saving_pct)}，月节省 ${cny(result.monthly_saving_cny, 2)}`, 'ok')
    await store.select(detail.value.id)
  } catch (err) {
    feedback.notify((err as Error).message, 'bad')
  } finally {
    busy.value = ''
  }
}

async function adopt() {
  if (!detail.value) return
  busy.value = 'adopt'
  try {
    await store.adopt(detail.value.id)
    feedback.notify(`已采纳 ${detail.value.suggestion_no}`, 'ok')
  } catch (err) {
    feedback.notify((err as Error).message, 'bad')
  } finally {
    busy.value = ''
  }
}

async function exportCsv() {
  busy.value = 'export'
  try {
    const rows = await downloadOptimisationCsv()
    feedback.notify(`优化清单已导出（${rows ?? store.items.length} 行 CSV）`, 'ok')
  } catch (err) {
    feedback.notify((err as Error).message, 'bad')
  } finally {
    busy.value = ''
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <BlueprintSheet
      title="改写建议与前后对比"
      code="S-03 / REWRITE ORDERS"
      note="排序口径：score = 节省字节 × 置信度 ÷ 风险权重；改写后的扫描量由后端对改写 SQL 重新跑算法 1 得到。"
    >
      <div class="toolbar">
        <button v-if="auth.canWrite" class="btn btn--primary" type="button" :disabled="busy === 'generate'" @click="generateTop1">
          {{ busy === 'generate' ? '生成中…' : '对 Top1 扫描量生成改写' }}
        </button>
        <button class="btn" type="button" :disabled="busy === 'export'" @click="exportCsv">
          {{ busy === 'export' ? '导出中…' : '导出优化清单 CSV' }}
        </button>
        <div class="spacer" />
        <span class="hint">
          共 <span class="mono">{{ store.items.length }}</span> 条建议 ·
          待采纳 <span class="mono">{{ store.items.filter((item) => item.status === 'pending').length }}</span> 条 ·
          已采纳 <span class="mono">{{ store.items.filter((item) => item.status === 'adopted').length }}</span> 条
        </span>
      </div>

      <ErrorNotice v-if="store.error" :message="store.error" @retry="load" />

      <div v-if="!store.items.length && !store.loading" class="empty-wrap">
        <EmptyState :title="MSG_EMPTY_REWRITE" hint="先跑一次估算批次，再对裁剪失效的查询生成改写。" action="刷新" @action="load" />
      </div>

      <div v-else class="grid">
        <div class="list">
          <ul class="sug-list">
            <li
              v-for="item in store.items"
              :key="item.id"
              :class="{ 'is-active': detail?.id === item.id }"
              @click="select(item.id)"
            >
              <div class="sug-head">
                <span class="mono sug-no">{{ item.suggestion_no }}</span>
                <span class="mono sug-pct">{{ pct(item.saving_pct) }}</span>
                <StatusStamp :label="RISK_LABEL[item.risk_level]" :level="item.risk_level" />
              </div>
              <p class="sug-title">{{ item.query_title }}</p>
              <div class="sug-tags">
                <span v-for="pattern in item.anti_patterns" :key="pattern" class="tag tag--rust">
                  {{ ANTI_PATTERN_LABEL[pattern] || pattern }}
                </span>
              </div>
              <span class="save-bar"><i :style="{ width: `${(item.score / maxScore) * 100}%` }" /></span>
              <p class="sug-sub mono">
                {{ item.query_external_id }} · 节省 {{ gibLabel(item.saving_bytes) }} · score {{ scoreLabel(item.score) }}
              </p>
            </li>
          </ul>
        </div>

        <aside v-if="detail" class="detail">
          <div class="detail-head">
            <div>
              <p class="mono hint" style="margin: 0">{{ detail.suggestion_no }}</p>
              <h3>{{ detail.query_title }}</h3>
            </div>
            <StatusStamp :label="SUGGESTION_STATUS_LABEL[detail.status] || detail.status" :level="detail.status" />
          </div>
          <div class="row" style="margin-bottom: var(--space-3)">
            <span class="tag">{{ detail.query_external_id }}</span>
            <span class="tag">{{ detail.target_table }}</span>
            <StatusStamp :label="RISK_LABEL[detail.risk_level]" :level="detail.risk_level" />
            <span class="tag">置信度 {{ ratio(detail.confidence, 2) }}</span>
          </div>

          <div class="compare">
            <BlueprintPanel label="改写前 / BEFORE">
              <pre class="sql-block sql-block--before">{{ detail.original_sql }}</pre>
              <p class="hint mono" style="margin: 6px 0 0">{{ gibLabel(detail.before_scan_bytes) }} · {{ detail.before_rationale }}</p>
            </BlueprintPanel>
            <BlueprintPanel label="改写后 / AFTER">
              <pre class="sql-block">{{ detail.rewritten_sql }}</pre>
              <p class="hint mono" style="margin: 6px 0 0">
                {{ gibLabel(detail.after_scan_bytes) }} · 命中 {{ detail.after_hit_partition_count }}/{{ detail.after_total_partition_count }} 个分区 ·
                {{ detail.after_prunable ? '裁剪生效' : '裁剪仍失效' }}
              </p>
            </BlueprintPanel>
          </div>

          <BlueprintPanel label="等价改写动作 / FIXES">
            <ol class="fixes">
              <li v-for="fix in detail.fixes" :key="fix">{{ fix }}</li>
            </ol>
            <p class="hint" style="margin: 0">{{ detail.rationale }}</p>
          </BlueprintPanel>

          <div class="metrics">
            <MonoMetric :value="gibLabel(detail.saving_bytes)" caption="节省扫描 / SAVING" />
            <MonoMetric :value="pct(detail.saving_pct)" caption="节省比例" />
            <MonoMetric :value="cny(detail.saving_cost_cny, 3)" caption="单次节省 / CNY" />
            <MonoMetric :value="scoreLabel(detail.score)" caption="排序分 / SCORE" />
          </div>

          <div v-if="store.reevaluation" class="notice notice--info" style="margin-top: var(--space-3)">
            <span class="mono">重估</span>
            <span>
              节省 {{ pct(store.reevaluation.saving_pct) }} · 单次 {{ cny(store.reevaluation.saving_cost_cny, 3) }} ·
              按 30 天折算月节省 {{ cny(store.reevaluation.monthly_saving_cny, 2) }}
            </span>
          </div>

          <div class="row" style="margin-top: var(--space-3)">
            <template v-if="auth.canWrite">
              <button class="btn btn--primary" type="button" :disabled="busy === 'reevaluate'" @click="reevaluate">
                {{ busy === 'reevaluate' ? '重估中…' : '重估节省' }}
              </button>
              <button class="btn" type="button" :disabled="busy === 'adopt' || detail.status === 'adopted'" @click="adopt">
                {{ detail.status === 'adopted' ? '已采纳' : '采纳建议' }}
              </button>
            </template>
            <span v-else class="hint">只读角色可查看与导出报告，采纳/重估需要 admin 或 engineer（后端 403）。</span>
            <div class="spacer" />
            <button class="btn btn--ghost" type="button" @click="router.push({ name: 'query-detail', params: { id: detail.query_log_id } })">
              查看该查询解析 →
            </button>
          </div>
        </aside>
      </div>
    </BlueprintSheet>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  gap: var(--space-2);
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--rule);
}
.empty-wrap {
  padding: var(--space-4) 0;
}
.grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.35fr);
  gap: var(--space-5);
}
.list {
  min-width: 0;
  overflow-x: auto;
}
.list :deep(table) {
  min-width: 460px;
}
.sug-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
  border-top: 1px solid var(--rule);
}
.sug-list li {
  padding: 11px 10px 12px;
  border-bottom: 1px dashed var(--rule);
  border-left: 2px solid transparent;
  cursor: pointer;
  transition:
    background 0.18s var(--ease-out),
    border-color 0.18s var(--ease-out);
}
.sug-list li:hover {
  background: oklch(0.32 0.05 252 / 0.5);
}
.sug-list li.is-active {
  background: oklch(0.345 0.052 251 / 0.62);
  border-left-color: var(--rust);
}
.sug-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.sug-no {
  font-size: 0.74rem;
  color: var(--cream);
  white-space: nowrap;
}
.sug-pct {
  font-size: 0.92rem;
  color: var(--sand);
  margin-left: auto;
}
.sug-title {
  margin: 5px 0 4px;
  font-size: var(--step--1);
  line-height: 1.45;
}
.sug-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.sug-sub {
  margin: 6px 0 0;
  font-size: 0.64rem;
  color: var(--cream-mute);
  line-height: 1.5;
}
.meta {
  margin: 3px 0 0;
  font-size: 0.68rem;
  color: var(--cream-mute);
}
.strong {
  font-size: 0.86rem;
  color: var(--sand);
}
.save-bar {
  display: block;
  height: 4px;
  width: 100%;
  background: oklch(0.42 0.04 250 / 0.4);
  margin: 4px 0 3px;
}
.save-bar i {
  display: block;
  height: 100%;
  background: var(--rust);
}
tbody tr {
  cursor: pointer;
}
.detail {
  min-width: 0;
}
.detail-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  align-items: flex-start;
  margin-bottom: var(--space-2);
}
.detail-head h3 {
  font-size: var(--step-1);
  margin-top: 3px;
}
.compare {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-3);
}
.sql-block--before {
  border-left-color: var(--cream-mute);
  color: var(--cream-dim);
}
.fixes {
  margin: 0 0 var(--space-3);
  padding-left: 20px;
  font-size: var(--step--1);
  line-height: 1.7;
  color: var(--cream-dim);
}
.fixes li::marker {
  color: var(--rust);
  font-family: var(--font-mono);
}
.metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
  border-top: 1px solid var(--rule);
  padding-top: var(--space-4);
  margin-top: var(--space-4);
}
@media (max-width: 1180px) {
  .grid {
    grid-template-columns: 1fr;
  }
  .metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
