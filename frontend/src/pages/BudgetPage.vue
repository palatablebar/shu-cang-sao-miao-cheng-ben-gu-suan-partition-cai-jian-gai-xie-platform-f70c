<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/authStore'
import { useBudgetStore } from '../stores/budgetStore'
import { useEstimateStore } from '../stores/estimateStore'
import { useFeedback } from '../hooks/useFeedback'
import BlueprintSheet from '../components/common/BlueprintSheet.vue'
import BlueprintPanel from '../components/common/BlueprintPanel.vue'
import ErrorNotice from '../components/common/ErrorNotice.vue'
import MonoMetric from '../components/common/MonoMetric.vue'
import StatusStamp from '../components/common/StatusStamp.vue'
import { BUDGET_STATUS_LABEL, RUN_STATUS_LABEL } from '../constants/enums'
import { cny, dateLabel, gibLabel, intLabel, pct, ratio } from '../utils/format'

const auth = useAuthStore()
const store = useBudgetStore()
const estimates = useEstimateStore()
const feedback = useFeedback()

const editingId = ref<number | null>(null)
const budgetInput = ref(0)
const warnInput = ref(0.75)
const busy = ref(false)

const overview = computed(() => store.overview)
const share = computed(() => Math.min(1.25, overview.value?.month_share ?? 0))
const globalPolicy = computed(() => store.policies.find((policy) => policy.scope === 'global'))

function startEdit(id: number) {
  const policy = store.policies.find((item) => item.id === id)
  if (!policy) return
  editingId.value = id
  budgetInput.value = policy.monthly_budget_cny
  warnInput.value = policy.warn_ratio
}

async function save(id: number) {
  busy.value = true
  try {
    await store.savePolicy(id, {
      monthly_budget_cny: Number(budgetInput.value),
      warn_ratio: Number(warnInput.value),
    })
    editingId.value = null
    feedback.notify('预算策略已更新（审计已记录）', 'ok')
  } catch (err) {
    feedback.notify((err as Error).message, 'bad')
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  await Promise.all([store.load(), estimates.load()])
  if (auth.isAdmin) await store.loadAudit()
})
</script>

<template>
  <div class="page">
    <BlueprintSheet
      title="预算策略与估算批次"
      code="S-05 / BUDGET PLATE"
      note="演示子集月预算 1,800 元（全仓 1.8 万的 1/10）；扫描单价 ￥0.30/GiB；月折算 = 单日费用 × 30 天 × 5 倍放样。"
    >
      <ErrorNotice v-if="store.error" :message="store.error" @retry="store.load()" />

      <template v-if="overview">
        <div class="top">
          <div class="metrics">
            <MonoMetric :value="cny(overview.monthly_budget_cny, 0)" caption="月预算 / BUDGET" />
            <MonoMetric :value="cny(overview.projected_cost_cny, 0)" caption="按当前批次折算 / PROJECTED" />
            <MonoMetric :value="pct(overview.month_share * 100)" caption="预算占用 / SHARE" />
            <MonoMetric :value="gibLabel(overview.total_scan_bytes)" caption="单日扫描 / SCAN" />
          </div>

          <div class="gauge">
            <div class="gauge-head">
              <StatusStamp :label="BUDGET_STATUS_LABEL[overview.status] || overview.status" :level="overview.status" />
              <span class="mono hint">阈值 warn {{ ratio(globalPolicy?.warn_ratio ?? 0.75, 2) }} / critical {{ ratio(globalPolicy?.critical_ratio ?? 0.92, 2) }}</span>
            </div>
            <div class="gauge-track">
              <i class="gauge-fill" :style="{ width: `${Math.min(100, share * 100)}%` }" />
              <span class="gauge-mark" :style="{ left: `${(globalPolicy?.warn_ratio ?? 0.75) * 100}%` }" />
              <span class="gauge-mark gauge-mark--critical" :style="{ left: `${(globalPolicy?.critical_ratio ?? 0.92) * 100}%` }" />
            </div>
            <div class="gauge-axis mono">
              <span>0</span><span>warn</span><span>critical</span><span>{{ cny(overview.monthly_budget_cny, 0) }}</span>
            </div>
            <p class="hint" style="margin: 10px 0 0">
              查询 {{ intLabel(overview.query_count) }} 条 · 裁剪失效 {{ intLabel(overview.blocked_count) }} 条 ·
              改写可节省 <span class="mono">{{ gibLabel(overview.prunable_saving_bytes) }}</span>（约
              <span class="mono">{{ cny((overview.prunable_saving_bytes / 1024 ** 3) * overview.unit_cost_per_gib_cny, 2) }}</span> / 次）
            </p>
          </div>
        </div>

        <div class="grid">
          <BlueprintPanel label="按表扫描量 / SCAN BY TABLE">
            <table class="grid-table">
              <thead>
                <tr><th>表</th><th>层</th><th class="num">查询</th><th class="num">失效</th><th class="num">扫描字节</th><th class="num">占比</th></tr>
              </thead>
              <tbody>
                <tr v-for="row in overview.tables" :key="row.table_name">
                  <td class="mono">{{ row.table_name }}</td>
                  <td><span class="tag">{{ row.layer }}</span></td>
                  <td class="num mono">{{ row.query_count }}</td>
                  <td class="num mono" :style="{ color: row.blocked_count ? 'var(--bad)' : 'inherit' }">{{ row.blocked_count }}</td>
                  <td class="num mono">{{ gibLabel(row.scan_bytes) }}</td>
                  <td class="num mono">{{ ratio(row.scan_bytes / Math.max(1, overview.total_scan_bytes), 3) }}</td>
                </tr>
              </tbody>
            </table>
          </BlueprintPanel>

          <BlueprintPanel label="估算批次 / RUNS">
            <table class="grid-table">
              <thead>
                <tr><th>批次</th><th>状态</th><th class="num">查询</th><th class="num">失效</th><th class="num">Top1</th><th class="num">月折算</th></tr>
              </thead>
              <tbody>
                <tr v-for="run in estimates.runs" :key="run.id">
                  <td>
                    <p class="mono" style="margin: 0">{{ run.run_no }}</p>
                    <p class="meta">{{ run.note || run.scope }}</p>
                  </td>
                  <td><StatusStamp :label="RUN_STATUS_LABEL[run.status] || run.status" :level="run.status" /></td>
                  <td class="num mono">{{ run.query_count }}</td>
                  <td class="num mono">{{ run.blocked_count }}</td>
                  <td class="num mono">{{ gibLabel(run.top_scan_bytes) }}</td>
                  <td class="num mono">{{ cny(run.monthly_projected_cost_cny, 0) }}</td>
                </tr>
              </tbody>
            </table>
          </BlueprintPanel>
        </div>

        <BlueprintPanel label="预算策略 / POLICIES">
          <table class="grid-table">
            <thead>
              <tr>
                <th>编号 / 名称</th>
                <th>范围</th>
                <th class="num">月预算</th>
                <th class="num">warn / critical</th>
                <th class="num">单条告警阈值</th>
                <th>维护</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="policy in store.policies" :key="policy.id">
                <td>
                  <p class="mono" style="margin: 0">{{ policy.policy_no }}</p>
                  <p class="meta">{{ policy.name }}</p>
                </td>
                <td><span class="tag">{{ policy.scope }}{{ policy.scope_value ? ` · ${policy.scope_value}` : '' }}</span></td>
                <td class="num mono">
                  <template v-if="editingId === policy.id">
                    <input v-model.number="budgetInput" class="inline-input" type="number" step="100" />
                  </template>
                  <template v-else>{{ cny(policy.monthly_budget_cny, 0) }}</template>
                </td>
                <td class="num mono">
                  <template v-if="editingId === policy.id">
                    <input v-model.number="warnInput" class="inline-input" type="number" step="0.01" min="0.1" max="0.99" />
                    / {{ ratio(policy.critical_ratio, 2) }}
                  </template>
                  <template v-else>{{ ratio(policy.warn_ratio, 2) }} / {{ ratio(policy.critical_ratio, 2) }}</template>
                </td>
                <td class="num mono">{{ gibLabel(policy.scan_alert_bytes, 1) }}</td>
                <td>
                  <template v-if="auth.isAdmin">
                    <button v-if="editingId !== policy.id" class="btn btn--ghost" type="button" @click="startEdit(policy.id)">编辑</button>
                    <span v-else class="row">
                      <button class="btn btn--primary" type="button" :disabled="busy" @click="save(policy.id)">保存</button>
                      <button class="btn btn--ghost" type="button" @click="editingId = null">取消</button>
                    </span>
                  </template>
                  <span v-else class="hint">仅 admin 可改</span>
                </td>
              </tr>
            </tbody>
          </table>
          <p class="hint" style="margin: 10px 0 0">
            维护人：<span class="mono">{{ globalPolicy?.updated_by || '—' }}</span> · 只读角色请求 PUT /budget/policies 会拿到真实 403。
          </p>
        </BlueprintPanel>

        <BlueprintPanel v-if="auth.isAdmin && store.audit.length" label="审计流水 / AUDIT TRAIL（最近 14 条）">
          <table class="grid-table">
            <thead>
              <tr><th>时间</th><th>操作者</th><th>角色</th><th>动作</th><th>路径</th><th class="num">状态</th></tr>
            </thead>
            <tbody>
              <tr v-for="row in store.audit" :key="row.id">
                <td class="mono hint">{{ dateLabel(row.created_at) }}</td>
                <td class="mono">{{ row.actor_email }}</td>
                <td><span class="tag">{{ row.actor_role }}</span></td>
                <td class="mono">{{ row.action }}</td>
                <td class="mono hint">{{ row.method }} {{ row.path }}</td>
                <td class="num mono" :style="{ color: row.status_code >= 400 ? 'var(--bad)' : 'inherit' }">{{ row.status_code }}</td>
              </tr>
            </tbody>
          </table>
        </BlueprintPanel>
      </template>
    </BlueprintSheet>
  </div>
</template>

<style scoped>
.top {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr);
  gap: var(--space-5);
  border-bottom: 1px solid var(--rule);
  padding-bottom: var(--space-4);
  margin-bottom: var(--space-4);
}
.metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-5);
}
.gauge-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.gauge-track {
  position: relative;
  height: 14px;
  border: 1px solid var(--rule);
  background: oklch(0.22 0.045 254 / 0.9);
}
.gauge-fill {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, oklch(0.68 0.09 150), oklch(0.74 0.1 120));
}
.gauge-mark {
  position: absolute;
  top: -4px;
  width: 1px;
  height: 20px;
  background: var(--warn);
}
.gauge-mark--critical {
  background: var(--bad);
}
.gauge-axis {
  display: flex;
  justify-content: space-between;
  font-size: 0.64rem;
  color: var(--cream-mute);
  margin-top: 6px;
}
.grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-4);
}
.meta {
  margin: 2px 0 0;
  font-size: 0.66rem;
  color: var(--cream-mute);
}
.inline-input {
  width: 100px;
  background: oklch(0.225 0.045 254 / 0.9);
  border: 1px solid var(--rule-strong);
  padding: 3px 6px;
  font-family: var(--font-mono);
  font-size: 0.72rem;
  text-align: right;
}
@media (max-width: 1080px) {
  .top {
    grid-template-columns: 1fr;
  }
}
</style>
