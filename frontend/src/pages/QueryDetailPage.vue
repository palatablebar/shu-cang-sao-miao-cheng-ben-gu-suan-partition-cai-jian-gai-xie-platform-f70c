<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/authStore'
import { useQueryStore } from '../stores/queryStore'
import { useRewriteStore } from '../stores/rewriteStore'
import { fetchTable, fetchTables } from '../api/tables'
import type { TablePartition } from '../types/table'
import { useFeedback } from '../hooks/useFeedback'
import BlueprintSheet from '../components/common/BlueprintSheet.vue'
import BlueprintPanel from '../components/common/BlueprintPanel.vue'
import ErrorNotice from '../components/common/ErrorNotice.vue'
import MonoMetric from '../components/common/MonoMetric.vue'
import PartitionRuler from '../components/common/PartitionRuler.vue'
import StatusStamp from '../components/common/StatusStamp.vue'
import { BLOCKED_REASON_LABEL } from '../constants/enums'
import { cny, gibLabel, intLabel, pct, ratio } from '../utils/format'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const store = useQueryStore()
const rewrites = useRewriteStore()
const feedback = useFeedback()

const partitions = ref<TablePartition[]>([])
const busy = ref(false)

const detail = computed(() => store.detail)
const id = computed(() => Number(route.params.id))

async function load() {
  const row = await store.loadDetail(id.value)
  partitions.value = []
  if (!row?.target_table) return
  try {
    const tables = await fetchTables()
    const match = tables.find((table) => table.table_name === row.target_table)
    if (match) {
      const table = await fetchTable(match.id)
      partitions.value = table.partitions
    }
  } catch {
    partitions.value = []
  }
}

async function generate() {
  if (!detail.value) return
  busy.value = true
  try {
    const created = await rewrites.generate(detail.value.id)
    feedback.notify(`已生成改写 ${created.suggestion_no}：节省 ${pct(created.saving_pct)}`, 'ok')
    router.push({ name: 'rewrites' })
  } catch (err) {
    feedback.notify((err as Error).message, 'bad')
  } finally {
    busy.value = false
  }
}

onMounted(load)
watch(id, load)
</script>

<template>
  <BlueprintSheet
    v-if="detail"
    :title="detail.title"
    :code="`S-02 / ${detail.external_id}`"
    :note="`来源 ${detail.source} · 提交人 ${detail.submitted_by} · 查询日 ${detail.query_date} · 耗时 ${detail.duration_ms} ms`"
  >
    <div class="row" style="margin-bottom: var(--space-4)">
      <StatusStamp :label="detail.parse_status === 'parsed' ? '解析成功' : detail.parse_status" :level="detail.parse_status === 'parsed' ? 'ok' : 'bad'" />
      <StatusStamp
        :label="BLOCKED_REASON_LABEL[detail.blocked_reason] || detail.blocked_reason"
        :level="detail.prunable ? 'prunable' : 'blocked'"
      />
      <span class="tag">目标表 {{ detail.target_table || '—' }}</span>
      <span class="tag">分区键 {{ detail.total_partition_count }} 个</span>
      <span v-if="detail.has_star" class="tag tag--rust">SELECT *</span>
      <div class="spacer" />
      <button class="btn btn--ghost" type="button" @click="router.push({ name: 'queries' })">← 返回排行</button>
    </div>

    <div class="grid">
      <div>
        <BlueprintPanel label="原始 SQL / STATEMENT">
          <pre class="sql-block">{{ detail.sql_text }}</pre>
        </BlueprintPanel>

        <BlueprintPanel label="分区谓词判定 / PARTITION PREDICATES">
          <table v-if="detail.predicates.length" class="grid-table">
            <thead>
              <tr>
                <th>谓词</th>
                <th>判定</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="predicate in detail.predicates" :key="predicate.expression">
                <td class="mono" style="word-break: break-all">{{ predicate.expression }}</td>
                <td>
                  <StatusStamp :label="predicate.usable ? '可裁剪' : BLOCKED_REASON_LABEL[predicate.reason] || predicate.reason" :level="predicate.usable ? 'ok' : 'bad'" />
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
          <p v-else class="hint">该查询没有出现分区列谓词 —— 算法判定为「缺少分区谓词」，会扫描全部分区。</p>
        </BlueprintPanel>

        <BlueprintPanel label="算法结论 / RATIONALE">
          <p class="rationale">{{ detail.rationale }}</p>
          <div class="divider" />
          <div class="row">
            <span class="hint">引用列（列裁剪分子）：</span>
            <span v-for="column in detail.referenced_columns" :key="column" class="tag">{{ column }}</span>
            <span v-if="!detail.referenced_columns.length" class="hint">无（聚合查询按最小列比例计）</span>
          </div>
          <div class="row" style="margin-top: 8px">
            <span class="hint">投影列：</span>
            <span v-for="column in detail.projected_columns.slice(0, 12)" :key="column" class="tag">{{ column }}</span>
            <span v-if="detail.projected_columns.length > 12" class="hint">+{{ detail.projected_columns.length - 12 }}</span>
          </div>
        </BlueprintPanel>
      </div>

      <aside>
        <BlueprintPanel label="扫描量拆解 / SCAN BREAKDOWN">
          <div class="stack">
            <MonoMetric :value="gibLabel(detail.scan_bytes)" caption="本次扫描 / SCAN" />
            <div class="kv">
              <div><dt>整表原始字节</dt><dd class="mono">{{ gibLabel(detail.full_scan_bytes) }}</dd></div>
              <div><dt>命中分区</dt><dd class="mono">{{ intLabel(detail.hit_partition_count) }} / {{ intLabel(detail.total_partition_count) }}</dd></div>
              <div><dt>列裁剪比例</dt><dd class="mono">{{ ratio(detail.col_ratio, 3) }}</dd></div>
              <div><dt>单次扫描费用</dt><dd class="mono">{{ cny(detail.scan_cost_cny, 4) }}</dd></div>
              <div><dt>全月折算（30 天）</dt><dd class="mono">{{ cny(detail.scan_cost_cny * 30, 2) }}</dd></div>
            </div>
          </div>
        </BlueprintPanel>

        <BlueprintPanel label="分区命中图 / PARTITION HITS">
          <PartitionRuler
            v-if="partitions.length"
            :partitions="partitions"
            :hit="detail.hit_partitions"
            :prunable="detail.prunable"
          />
          <p v-else class="hint">未取到分区明细（表元数据缺失）。</p>
          <p class="hint" style="margin: 8px 0 0">
            <span class="mono">■</span> 米白 = 命中分区 · <span class="mono">■</span> 深蓝 = 未命中（被裁剪）
          </p>
        </BlueprintPanel>

        <BlueprintPanel label="动作 / ACTIONS">
          <button
            v-if="auth.canWrite"
            class="btn btn--primary"
            type="button"
            :disabled="busy || detail.prunable"
            @click="generate"
          >
            {{ busy ? '生成中…' : '生成改写建议' }}
          </button>
          <p v-else class="hint">只读角色不能生成改写（后端返回 403）。</p>
          <p v-if="detail.prunable" class="hint" style="margin-top: 8px">
            该查询分区裁剪已生效，算法未命中反模式，无需改写。
          </p>
          <p v-if="detail.suggestion_count" class="hint" style="margin-top: 8px">
            已存在 {{ detail.suggestion_count }} 条改写建议。
          </p>
        </BlueprintPanel>
      </aside>
    </div>
  </BlueprintSheet>

  <ErrorNotice v-else-if="store.error" :message="store.error" @retry="load" />
  <p v-else class="hint">正在解析 SQL 与分区元数据…</p>
</template>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(280px, 1fr);
  gap: var(--space-5);
}
.rationale {
  margin: 0;
  font-size: var(--step-0);
  line-height: 1.75;
  color: var(--cream-dim);
  border-left: 2px solid var(--rust);
  padding-left: var(--space-3);
}
.stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.kv {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.kv div {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  border-bottom: 1px dashed var(--rule);
  padding-bottom: 4px;
}
.kv dt {
  font-size: 0.7rem;
  color: var(--cream-mute);
}
.kv dd {
  margin: 0;
  font-size: 0.74rem;
}
@media (max-width: 1080px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
