<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/authStore'
import { useEstimateStore } from '../stores/estimateStore'
import { useQueryStore } from '../stores/queryStore'
import { useFeedback } from '../hooks/useFeedback'
import BlueprintSheet from '../components/common/BlueprintSheet.vue'
import BlueprintPanel from '../components/common/BlueprintPanel.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorNotice from '../components/common/ErrorNotice.vue'
import MonoMetric from '../components/common/MonoMetric.vue'
import StatusStamp from '../components/common/StatusStamp.vue'
import { BLOCKED_REASON_LABEL, BLOCKED_REASON_SHORT, RUN_STATUS_LABEL } from '../constants/enums'
import { MSG_EMPTY_QUERY } from '../constants/messages'
import { cny, dateLabel, gibLabel, intLabel, pct, tone3 } from '../utils/format'

const auth = useAuthStore()
const queries = useQueryStore()
const estimates = useEstimateStore()
const feedback = useFeedback()
const router = useRouter()

const keyword = ref('')
const busy = ref('')

const maxScan = computed(() => Math.max(1, ...queries.items.map((item) => item.scan_bytes)))
const latestRun = computed(() => estimates.active)

function barWidth(bytes: number) {
  return `${Math.max(2, (bytes / maxScan.value) * 100)}%`
}

async function loadAll() {
  await Promise.all([queries.load(), queries.loadOverview(), estimates.load()])
}

async function importPack() {
  busy.value = 'import'
  try {
    const result = await queries.importPack()
    feedback.notify(result.message, 'ok')
  } catch (err) {
    feedback.notify((err as Error).message, 'bad')
  } finally {
    busy.value = ''
  }
}

async function runEstimate(scope: 'all' | 'blocked') {
  busy.value = 'estimate'
  try {
    const run = await estimates.run(scope, undefined, scope === 'all' ? '工作台手动全量估算' : '仅裁剪失效查询复核')
    if (run?.status === 'completed') {
      feedback.notify(
        `批次 ${run.run_no} 完成：${run.query_count} 条查询、裁剪失效 ${run.blocked_count} 条、Top1 扫描 ${gibLabel(run.top_scan_bytes)}`,
        'ok',
      )
    } else {
      feedback.notify(`批次 ${run?.run_no ?? ''} 状态 ${run?.status ?? 'unknown'}，请稍后刷新`, 'info')
    }
    await Promise.all([queries.load(), queries.loadOverview()])
  } catch (err) {
    feedback.notify((err as Error).message, 'bad')
  } finally {
    busy.value = ''
  }
}

function search() {
  queries.setFilter('keyword', keyword.value.trim() || undefined)
  queries.load()
}

onMounted(loadAll)
</script>

<template>
  <div class="page">
    <BlueprintSheet
      title="扫描成本排行"
      code="S-01 / COST LEDGER"
      note="按查询扫描字节倒序排列；扫描量 = Σ命中分区字节 × 列裁剪比例，全部由后端算法落库。"
    >
      <div class="metrics">
        <MonoMetric :value="intLabel(queries.stats?.query_count ?? 0)" unit="条" caption="查询日志 / LOG ROWS" />
        <MonoMetric
          :value="intLabel(queries.stats?.blocked_count ?? 0)"
          unit="条"
          caption="裁剪失效 / PRUNE BLOCKED"
        />
        <MonoMetric
          :value="gibLabel(queries.stats?.total_scan_bytes ?? 0, 1)"
          caption="日扫描合计 / DAILY SCAN"
        />
        <MonoMetric
          :value="gibLabel(queries.stats?.top_scan_bytes ?? 0)"
          caption="Top1 单次扫描 / PEAK"
        />
      </div>

      <div class="grid">
        <div class="left">
          <div class="toolbar">
            <div class="row">
              <button
                class="btn"
                :class="{ 'btn--primary': !queries.filters.status }"
                type="button"
                @click="queries.setFilter('status', undefined); queries.load()"
              >
                全部
              </button>
              <button
                class="btn"
                :class="{ 'btn--primary': queries.filters.status === 'blocked' }"
                type="button"
                @click="queries.setFilter('status', 'blocked'); queries.load()"
              >
                裁剪失效
              </button>
              <button
                class="btn"
                :class="{ 'btn--primary': queries.filters.status === 'prunable' }"
                type="button"
                @click="queries.setFilter('status', 'prunable'); queries.load()"
              >
                可裁剪
              </button>
            </div>
            <div class="spacer" />
            <select
              class="mini-select"
              :value="queries.filters.sort"
              @change="queries.setFilter('sort', ($event.target as HTMLSelectElement).value as 'scan_bytes'); queries.load()"
            >
              <option value="scan_bytes">按扫描字节</option>
              <option value="duration">按耗时</option>
              <option value="external_id">按编号</option>
            </select>
            <input
              v-model="keyword"
              class="mini-input"
              type="search"
              placeholder="搜索业务标题…"
              @keyup.enter="search"
            />
          </div>

          <ErrorNotice v-if="queries.error" :message="queries.error" @retry="loadAll" />

          <div v-else-if="!queries.items.length && !queries.loading">
            <EmptyState :title="MSG_EMPTY_QUERY" hint="可以点击右侧「导入查询日志」把 60 条演示日志写入 PostgreSQL。" action="重新加载" @action="loadAll" />
          </div>

          <table v-else class="grid-table">
            <thead>
              <tr>
                <th>编号</th>
                <th>业务查询</th>
                <th>判据</th>
                <th class="num">命中分区</th>
                <th class="num">扫描量</th>
                <th class="num">单次费用</th>
                <th />
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in queries.items" :key="item.id" @click="router.push({ name: 'query-detail', params: { id: item.id } })">
                <td class="mono id">{{ item.external_id }}</td>
                <td>
                  <p class="title">{{ item.title }}</p>
                  <p class="meta">
                    <span class="mono">{{ item.target_table || '—' }}</span>
                    · {{ item.source }} · {{ item.submitted_by }}
                    <span v-if="item.is_scheduled"> · 调度</span>
                  </p>
                </td>
                <td>
                  <StatusStamp
                    :label="BLOCKED_REASON_SHORT[item.blocked_reason] || item.blocked_reason"
                    :level="item.prunable ? 'prunable' : 'blocked'"
                  />
                </td>
                <td class="num mono">{{ item.hit_partition_count }}/{{ item.total_partition_count }}</td>
                <td class="num">
                  <span class="mono scan">{{ gibLabel(item.scan_bytes) }}</span>
                  <span class="bar"><i :style="{ width: barWidth(item.scan_bytes) }" /></span>
                </td>
                <td class="num mono">{{ cny(item.scan_cost_cny, 3) }}</td>
                <td class="arrow">→</td>
              </tr>
            </tbody>
          </table>

          <div v-if="queries.total > (queries.filters.page_size || 20)" class="pager">
            <button class="btn btn--ghost" type="button" :disabled="(queries.filters.page || 1) <= 1" @click="queries.setFilter('page', (queries.filters.page || 1) - 1); queries.load()">
              上一页
            </button>
            <span class="mono hint">
              第 {{ queries.filters.page }} 页 / 共 {{ Math.ceil(queries.total / (queries.filters.page_size || 20)) }} 页 ·
              {{ queries.total }} 条
            </span>
            <button
              class="btn btn--ghost"
              type="button"
              :disabled="(queries.filters.page || 1) * (queries.filters.page_size || 20) >= queries.total"
              @click="queries.setFilter('page', (queries.filters.page || 1) + 1); queries.load()"
            >
              下一页
            </button>
          </div>
        </div>

        <aside class="right">
          <BlueprintPanel label="TOP 扫描量 / PEAK">
            <ol class="rank">
              <li v-for="(item, index) in queries.ranking.slice(0, 6)" :key="item.id">
                <span class="rank-no mono">{{ String(index + 1).padStart(2, '0') }}</span>
                <div class="rank-body">
                  <p class="rank-title">{{ item.title }}</p>
                  <p class="rank-meta mono">{{ item.external_id }} · {{ item.target_table }}</p>
                  <span class="bar bar--wide"><i :style="{ width: `${(item.scan_bytes / (queries.ranking[0]?.scan_bytes || 1)) * 100}%` }" /></span>
                </div>
                <span class="rank-value mono">{{ gibLabel(item.scan_bytes) }}</span>
              </li>
            </ol>
            <button class="btn btn--ghost" type="button" style="margin-top: 10px" @click="router.push({ name: 'rewrites' })">
              查看改写建议 →
            </button>
          </BlueprintPanel>

          <BlueprintPanel label="估算批次 / ESTIMATE RUNS">
            <div v-if="latestRun" class="run">
              <div class="row">
                <StatusStamp :label="RUN_STATUS_LABEL[latestRun.status] || latestRun.status" :level="latestRun.status" />
                <span class="mono hint">{{ latestRun.run_no }}</span>
              </div>
              <dl class="run-grid">
                <div><dt>查询</dt><dd class="mono">{{ latestRun.query_count }}</dd></div>
                <div><dt>裁剪失效</dt><dd class="mono">{{ latestRun.blocked_count }}</dd></div>
                <div><dt>扫描合计</dt><dd class="mono">{{ gibLabel(latestRun.total_scan_bytes) }}</dd></div>
                <div><dt>月折算</dt><dd class="mono">{{ cny(latestRun.monthly_projected_cost_cny, 0) }}</dd></div>
                <div><dt>Top1</dt><dd class="mono">{{ gibLabel(latestRun.top_scan_bytes) }}</dd></div>
                <div><dt>完成</dt><dd class="mono">{{ dateLabel(latestRun.finished_at) }}</dd></div>
              </dl>
              <p class="hint" style="margin: 4px 0 0">{{ latestRun.note }}</p>
            </div>
            <p v-else class="hint">还没有估算批次。导入日志后点击「全量估算」。</p>

            <div v-if="auth.canWrite" class="row" style="margin-top: 12px">
              <button class="btn btn--primary" type="button" :disabled="busy === 'estimate'" @click="runEstimate('all')">
                {{ busy === 'estimate' ? '执行中…' : '全量估算' }}
              </button>
              <button class="btn" type="button" :disabled="busy === 'estimate'" @click="runEstimate('blocked')">
                仅失效复核
              </button>
            </div>
            <p v-else class="hint" style="margin-top: 10px">
              只读角色：可查看排行与批次，不能触发估算（后端会返回 403）。
            </p>
          </BlueprintPanel>

          <BlueprintPanel label="导入 / INGEST">
            <p class="hint" style="margin-top: 0">
              把 60 条演示查询日志按自然键 <code>external_id</code> 幂等导入，并立即解析分区谓词。
            </p>
            <button
              v-if="auth.canWrite"
              class="btn btn--primary"
              type="button"
              :disabled="busy === 'import'"
              @click="importPack"
            >
              {{ busy === 'import' ? '导入中…' : '导入查询日志' }}
            </button>
            <p v-else class="hint">只读角色不具备导入权限（403）。</p>
            <div class="divider" />
            <p class="hint" style="margin-bottom: 0">
              当前排序：<span class="mono">{{ queries.filters.sort }}</span> ·
              共 <span class="mono">{{ queries.total }}</span> 条 ·
              失效占比 <span class="mono">{{ pct(((queries.stats?.blocked_count ?? 0) / Math.max(1, queries.stats?.query_count ?? 1)) * 100) }}</span>
            </p>
          </BlueprintPanel>
        </aside>
      </div>
    </BlueprintSheet>
  </div>
</template>

<style scoped>
.metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-5);
  padding: var(--space-3) 0 var(--space-5);
  border-bottom: 1px solid var(--rule);
  margin-bottom: var(--space-4);
}
.grid {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(280px, 1fr);
  gap: var(--space-5);
}
.left {
  min-width: 0;
}
.toolbar {
  display: flex;
  gap: var(--space-2);
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: var(--space-3);
}
.mini-select,
.mini-input {
  background: oklch(0.225 0.045 254 / 0.9);
  border: 1px solid var(--rule);
  padding: 6px 9px;
  font-family: var(--font-mono);
  font-size: var(--step--1);
}
.mini-input {
  width: 180px;
}
.id {
  color: var(--cream-mute);
  white-space: nowrap;
}
.title {
  margin: 0;
  font-size: var(--step-0);
}
.meta {
  margin: 3px 0 0;
  font-size: 0.68rem;
  color: var(--cream-mute);
}
.scan {
  display: block;
}
.bar {
  display: block;
  height: 4px;
  background: oklch(0.42 0.04 250 / 0.45);
  margin-top: 4px;
  width: 92px;
  margin-left: auto;
}
.bar i {
  display: block;
  height: 100%;
  background: var(--sand);
}
.bar--wide {
  width: 100%;
  margin-left: 0;
}
.bar--wide i {
  background: var(--rust-dim);
}
.arrow {
  color: var(--cream-mute);
  font-family: var(--font-mono);
}
tbody tr {
  cursor: pointer;
}
.pager {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  justify-content: space-between;
  margin-top: var(--space-3);
}
.rank {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.rank li {
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr) auto;
  gap: 8px;
  align-items: start;
  border-bottom: 1px dashed var(--rule);
  padding-bottom: 8px;
}
.rank-no {
  color: var(--rust);
  font-size: 0.72rem;
}
.rank-title {
  margin: 0;
  font-size: var(--step--1);
  line-height: 1.4;
}
.rank-meta {
  margin: 2px 0 5px;
  font-size: 0.64rem;
  color: var(--cream-mute);
}
.rank-value {
  font-size: 0.74rem;
  color: var(--cream);
  white-space: nowrap;
}
.run-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 12px;
  margin: var(--space-3) 0 0;
}
.run-grid div {
  display: flex;
  justify-content: space-between;
  gap: 6px;
  border-bottom: 1px dashed var(--rule);
  padding-bottom: 3px;
}
.run-grid dt {
  font-size: 0.66rem;
  color: var(--cream-mute);
}
.run-grid dd {
  margin: 0;
  font-size: 0.72rem;
}
@media (max-width: 1180px) {
  .grid {
    grid-template-columns: 1fr;
  }
  .metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-4);
  }
}
</style>
