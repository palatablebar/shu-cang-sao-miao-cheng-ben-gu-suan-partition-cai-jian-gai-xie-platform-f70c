<script setup lang="ts">
import { computed, ref } from 'vue'
import { BLOCKED_REASON_SHORT } from '../../constants/enums'
import { gibLabel, intLabel } from '../../utils/format'
import StatusStamp from './StatusStamp.vue'
import type { TableRewriteChange } from '../../types/rewrite'
import type { TableAnalysis } from '../../types/query'

const props = defineProps<{
  changes: TableRewriteChange[]
  beforeTables: TableAnalysis[]
  afterTables: TableAnalysis[]
  beforeTotal: number
  afterTotal: number
  defaultOpen?: boolean
}>()

const open = ref<string[]>(props.defaultOpen ? props.changes.map((c) => c.alias || c.table_name) : [])

function keyOf(change: TableRewriteChange) {
  return change.alias || change.table_name
}

function isOpen(change: TableRewriteChange) {
  return open.value.includes(keyOf(change))
}

function toggle(change: TableRewriteChange) {
  const key = keyOf(change)
  open.value = isOpen(change) ? open.value.filter((k) => k !== key) : [...open.value, key]
}

function findTable(rows: TableAnalysis[], tableName: string, alias: string) {
  return rows.find((row) => row.table_name === tableName && (!alias || row.alias === alias))
    ?? rows.find((row) => row.table_name === tableName)
}

function beforeOf(change: TableRewriteChange) {
  return findTable(props.beforeTables, change.table_name, change.alias)
}

function afterOf(change: TableRewriteChange) {
  return findTable(props.afterTables, change.table_name, change.after_alias || change.alias)
}

function afterShare(change: TableRewriteChange) {
  if (!props.afterTotal) return '0'
  return ((change.after_scan_bytes / props.afterTotal) * 100).toFixed(1)
}

function hitDelta(change: TableRewriteChange) {
  return change.before_hit_partition_count - change.after_hit_partition_count
}

const beforeSum = computed(() => props.changes.reduce((acc, c) => acc + c.before_scan_bytes, 0))
const afterSum = computed(() => props.changes.reduce((acc, c) => acc + c.after_scan_bytes, 0))
const balanced = computed(
  () => beforeSum.value === props.beforeTotal && afterSum.value === props.afterTotal,
)
</script>

<template>
  <div class="compare-tables">
    <ul class="table-list">
      <li
        v-for="change in changes"
        :key="keyOf(change)"
        class="table-item"
        :class="{ 'is-blocked': !change.before_prunable }"
      >
        <button class="table-head" type="button" :aria-expanded="isOpen(change)" @click="toggle(change)">
          <span class="caret mono">{{ isOpen(change) ? '▾' : '▸' }}</span>
          <span class="table-name mono">{{ change.table_name }}</span>
          <span v-if="change.alias && change.alias !== change.table_name" class="alias mono">as {{ change.alias }}</span>
          <StatusStamp
            :label="BLOCKED_REASON_SHORT[change.before_blocked_reason] || change.before_blocked_reason"
            :level="change.before_prunable ? 'prunable' : 'blocked'"
          />
          <span class="arrow mono">→</span>
          <StatusStamp
            :label="BLOCKED_REASON_SHORT[change.after_blocked_reason] || change.after_blocked_reason"
            :level="change.after_prunable ? 'prunable' : 'blocked'"
          />
          <div class="spacer" />
          <span class="table-scan mono" :class="{ 'is-down': change.after_scan_bytes < change.before_scan_bytes }">
            {{ gibLabel(change.before_scan_bytes) }} → {{ gibLabel(change.after_scan_bytes) }}
          </span>
        </button>

        <div v-if="isOpen(change)" class="table-body">
          <table class="grid-table inner">
            <thead>
              <tr>
                <th>口径</th>
                <th class="num">扫描字节</th>
                <th class="num">命中分区</th>
                <th>裁剪判定</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>改写前</td>
                <td class="num mono">{{ gibLabel(change.before_scan_bytes) }}</td>
                <td class="num mono">{{ intLabel(change.before_hit_partition_count) }} / {{ intLabel(change.before_total_partition_count) }}</td>
                <td>
                  <StatusStamp
                    :label="BLOCKED_REASON_SHORT[change.before_blocked_reason] || change.before_blocked_reason"
                    :level="change.before_prunable ? 'prunable' : 'blocked'"
                  />
                </td>
              </tr>
              <tr>
                <td>改写后</td>
                <td class="num mono">{{ gibLabel(change.after_scan_bytes) }}</td>
                <td class="num mono">{{ intLabel(change.after_hit_partition_count) }} / {{ intLabel(change.after_total_partition_count) }}</td>
                <td>
                  <StatusStamp
                    :label="BLOCKED_REASON_SHORT[change.after_blocked_reason] || change.after_blocked_reason"
                    :level="change.after_prunable ? 'prunable' : 'blocked'"
                  />
                </td>
              </tr>
            </tbody>
          </table>

          <div class="kv">
            <div><dt>表级节省</dt><dd class="mono">{{ gibLabel(Math.max(0, change.before_scan_bytes - change.after_scan_bytes)) }}</dd></div>
            <div><dt>少扫分区</dt><dd class="mono">{{ intLabel(Math.max(0, hitDelta(change))) }} 个</dd></div>
            <div><dt>改写后占比</dt><dd class="mono">{{ afterShare(change) }}%</dd></div>
            <div><dt>列裁剪比例</dt><dd class="mono">
              前 {{ beforeOf(change)?.col_ratio ?? '—' }} → 后 {{ afterOf(change)?.col_ratio ?? '—' }}
            </dd></div>
          </div>

          <div class="row" style="margin-top: 8px">
            <span class="hint">改写后投影：</span>
            <span v-for="column in afterOf(change)?.projected_columns.slice(0, 8) ?? []" :key="column" class="tag">{{ column }}</span>
            <span v-if="(afterOf(change)?.projected_columns.length ?? 0) > 8" class="hint">
              +{{ (afterOf(change)?.projected_columns.length ?? 0) - 8 }}
            </span>
          </div>
          <p class="hint" style="margin: 8px 0 0">{{ afterOf(change)?.rationale }}</p>
        </div>
      </li>
    </ul>

    <div class="reconcile" :class="{ 'is-bad': !balanced }">
      <span class="mono">对账</span>
      <span class="hint">
        表级合计 <span class="mono">{{ gibLabel(beforeSum) }} → {{ gibLabel(afterSum) }}</span>
        · 查询总量 <span class="mono">{{ gibLabel(beforeTotal) }} → {{ gibLabel(afterTotal) }}</span>
        <template v-if="balanced"> · 两侧一致</template>
        <template v-else> · 差额 {{ gibLabel(Math.abs(beforeTotal - beforeSum + afterTotal - afterSum)) }}</template>
      </span>
    </div>
  </div>
</template>

<style scoped>
.table-list {
  list-style: none;
  margin: 0;
  padding: 0;
  border-top: 1px solid var(--rule);
}
.table-item {
  border-bottom: 1px dashed var(--rule);
}
.table-item.is-blocked {
  box-shadow: inset 2px 0 0 var(--bad);
}
.table-head {
  display: flex;
  align-items: center;
  gap: 7px;
  width: 100%;
  background: transparent;
  border: 0;
  color: inherit;
  padding: 9px 8px;
  cursor: pointer;
  text-align: left;
  flex-wrap: wrap;
}
.table-head:hover {
  background: oklch(0.33 0.045 252 / 0.5);
}
.caret {
  color: var(--rust);
  width: 10px;
  flex: none;
}
.table-name {
  font-size: 0.78rem;
  color: var(--cream);
}
.alias {
  font-size: 0.62rem;
  color: var(--cream-mute);
}
.arrow {
  color: var(--cream-mute);
  font-size: 0.72rem;
}
.table-scan {
  font-size: 0.72rem;
  color: var(--cream-mute);
  white-space: nowrap;
}
.table-scan.is-down {
  color: var(--ok);
}
.table-body {
  padding: 4px 10px 12px 26px;
}
.inner {
  margin-top: 4px;
  font-size: var(--step--1);
}
.kv {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px 14px;
  margin-top: 8px;
}
.kv div {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  border-bottom: 1px dashed var(--rule);
  padding-bottom: 3px;
}
.kv dt {
  font-size: 0.66rem;
  color: var(--cream-mute);
}
.kv dd {
  margin: 0;
  font-size: 0.72rem;
}
.reconcile {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-3);
  padding-top: 6px;
  border-top: 1px solid var(--rule);
  color: var(--ok);
}
.reconcile.is-bad {
  color: var(--bad);
}
.reconcile .mono {
  font-size: 0.68rem;
  letter-spacing: 0.1em;
}
</style>
