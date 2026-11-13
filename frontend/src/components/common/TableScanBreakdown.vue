<script setup lang="ts">
import { computed, ref } from 'vue'
import { BLOCKED_REASON_LABEL, BLOCKED_REASON_SHORT } from '../../constants/enums'
import { gibLabel, intLabel, ratio } from '../../utils/format'
import StatusStamp from './StatusStamp.vue'
import type { TableAnalysis } from '../../types/query'

const props = defineProps<{
  tables: TableAnalysis[]
  totalBytes?: number
  defaultOpen?: boolean
}>()

const open = ref<string[]>(props.defaultOpen ? props.tables.map((t) => t.alias || t.table_name) : [])
const total = computed(() => Number(props.totalBytes ?? 0))
const sum = computed(() => props.tables.filter((t) => t.counted_in_total).reduce((acc, t) => acc + t.scan_bytes, 0))
const balanced = computed(() => total.value === 0 || sum.value === total.value)

function keyOf(table: TableAnalysis) {
  return table.alias || table.table_name
}

function toggle(key: string) {
  open.value = open.value.includes(key) ? open.value.filter((k) => k !== key) : [...open.value, key]
}

function isOpen(table: TableAnalysis) {
  return open.value.includes(keyOf(table))
}

function share(table: TableAnalysis) {
  if (!total.value) return 0
  return Math.round((table.scan_bytes / total.value) * 1000) / 10
}

function hitLabel(table: TableAnalysis) {
  if (table.status === 'missing_table') return '—'
  return `${intLabel(table.hit_partition_count)} / ${intLabel(table.total_partition_count)}`
}
</script>

<template>
  <div class="tables">
    <ul class="table-list">
      <li v-for="table in tables" :key="keyOf(table)" class="table-item" :class="{ 'is-blocked': !table.prunable && table.status === 'analyzed' }">
        <button class="table-head" type="button" :aria-expanded="isOpen(table)" @click="toggle(keyOf(table))">
          <span class="caret mono">{{ isOpen(table) ? '▾' : '▸' }}</span>
          <span class="table-name mono">{{ table.table_name }}</span>
          <span v-if="table.alias && table.alias !== table.table_name" class="alias mono">as {{ table.alias }}</span>
          <StatusStamp
            :label="table.status === 'missing_table' ? '表缺失' : BLOCKED_REASON_SHORT[table.blocked_reason] || table.blocked_reason"
            :level="table.status === 'missing_table' ? 'bad' : table.prunable ? 'prunable' : 'blocked'"
          />
          <div class="spacer" />
          <span class="table-scan mono">{{ gibLabel(table.scan_bytes) }}</span>
          <span class="table-share mono">{{ share(table) }}%</span>
          <span class="table-hit mono">{{ hitLabel(table) }} 分区</span>
        </button>

        <div v-if="isOpen(table)" class="table-body">
          <div class="kv">
            <div><dt>表级扫描</dt><dd class="mono">{{ gibLabel(table.scan_bytes) }}</dd></div>
            <div><dt>命中分区</dt><dd class="mono">{{ hitLabel(table) }}</dd></div>
            <div><dt>命中分区字节</dt><dd class="mono">{{ gibLabel(table.hit_bytes) }}</dd></div>
            <div><dt>整表原始字节</dt><dd class="mono">{{ gibLabel(table.full_scan_bytes) }}</dd></div>
            <div><dt>列裁剪比例</dt><dd class="mono">{{ ratio(table.col_ratio, 3) }}</dd></div>
            <div><dt>裁剪原因</dt><dd class="mono">{{ BLOCKED_REASON_LABEL[table.blocked_reason] || table.blocked_reason }}</dd></div>
          </div>

          <p class="hint" style="margin: 10px 0 0">{{ table.rationale }}</p>

          <table v-if="table.predicates.length" class="grid-table inner">
            <thead>
              <tr>
                <th>分区谓词</th>
                <th>判定</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="predicate in table.predicates" :key="predicate.expression">
                <td class="mono" style="word-break: break-all">{{ predicate.expression }}</td>
                <td>
                  <StatusStamp
                    :label="predicate.usable ? '可裁剪' : BLOCKED_REASON_LABEL[predicate.reason] || predicate.reason"
                    :level="predicate.usable ? 'ok' : 'bad'"
                  />
                </td>
                <td class="hint">
                  <span v-if="predicate.usable">裸列比较 {{ predicate.operator }} {{ predicate.literal }}，分区裁剪可用</span>
                  <span v-else>
                    {{ predicate.wrapper_kind ? `包裹方式：${predicate.wrapper_kind}` : '谓词不可用于裁剪' }}，
                    {{ predicate.reason === 'implicit_cast' ? '字面量类型与分区列不一致' : '分区列未以裸列形式出现' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-else class="hint" style="margin: 10px 0 0">该表没有出现分区列谓词 —— 缺少分区谓词，会扫描全部分区。</p>

          <div v-if="table.hit_partitions.length" class="hits">
            <span class="hint">命中分区：</span>
            <span class="mono hits-text">{{ table.hit_partitions.join(' · ') }}</span>
          </div>
          <div v-else-if="table.status === 'analyzed'" class="hits">
            <span class="hint">命中分区：未命中任何分区（裁剪后扫描 0 字节）</span>
          </div>

          <div class="row" style="margin-top: 8px">
            <span class="hint">投影列：</span>
            <span v-for="column in table.projected_columns.slice(0, 10)" :key="column" class="tag">{{ column }}</span>
            <span v-if="table.projected_columns.length > 10" class="hint">+{{ table.projected_columns.length - 10 }}</span>
            <span v-if="table.has_star" class="tag tag--rust">SELECT *</span>
          </div>
        </div>
      </li>
    </ul>

    <div class="reconcile" :class="{ 'is-bad': !balanced }">
      <span class="mono">对账</span>
      <span class="hint">
        表级明细合计 <span class="mono">{{ gibLabel(sum) }}</span> ·
        查询总量 <span class="mono">{{ gibLabel(total) }}</span>
        <template v-if="balanced"> · 一致</template>
        <template v-else> · 差额 {{ gibLabel(Math.abs(total - sum)) }}</template>
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
  gap: 8px;
  width: 100%;
  background: transparent;
  border: 0;
  color: inherit;
  padding: 9px 8px;
  cursor: pointer;
  text-align: left;
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
  font-size: 0.64rem;
  color: var(--cream-mute);
}
.table-scan {
  font-size: 0.76rem;
  color: var(--sand);
}
.table-share {
  font-size: 0.64rem;
  color: var(--cream-mute);
  width: 46px;
  text-align: right;
}
.table-hit {
  font-size: 0.64rem;
  color: var(--cream-mute);
}
.table-body {
  padding: 4px 10px 12px 26px;
}
.kv {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px 14px;
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
.inner {
  margin-top: 10px;
  font-size: var(--step--1);
}
.hits {
  margin-top: 10px;
  word-break: break-word;
  line-height: 1.6;
}
.hits-text {
  font-size: 0.66rem;
  color: var(--cream-dim);
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
