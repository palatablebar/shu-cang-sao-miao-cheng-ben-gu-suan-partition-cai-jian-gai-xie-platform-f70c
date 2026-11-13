<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '../stores/authStore'
import { useTableStore } from '../stores/tableStore'
import { useFeedback } from '../hooks/useFeedback'
import BlueprintSheet from '../components/common/BlueprintSheet.vue'
import BlueprintPanel from '../components/common/BlueprintPanel.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorNotice from '../components/common/ErrorNotice.vue'
import MonoMetric from '../components/common/MonoMetric.vue'
import PartitionRuler from '../components/common/PartitionRuler.vue'
import StatusStamp from '../components/common/StatusStamp.vue'
import { LAYER_LABEL } from '../constants/enums'
import { cny, gibLabel, intLabel, ratio } from '../utils/format'

const auth = useAuthStore()
const store = useTableStore()
const feedback = useFeedback()

const owner = ref('')
const description = ref('')
const editing = ref(false)

const detail = computed(() => store.detail)
const layerTotals = computed(() => {
  const totals = new Map<string, number>()
  for (const table of store.items) {
    totals.set(table.layer, (totals.get(table.layer) || 0) + table.total_bytes)
  }
  return Array.from(totals.entries()).sort((a, b) => b[1] - a[1])
})

function syncForm() {
  owner.value = detail.value?.owner ?? ''
  description.value = detail.value?.description ?? ''
}

async function select(id: number) {
  editing.value = false
  await store.select(id)
  syncForm()
}

async function save() {
  if (!detail.value) return
  try {
    await store.save(detail.value.id, { owner: owner.value, description: description.value })
    editing.value = false
    feedback.notify('表元数据已更新（审计已记录）', 'ok')
  } catch (err) {
    feedback.notify((err as Error).message, 'bad')
  }
}

onMounted(async () => {
  await store.load()
  syncForm()
})
watch(() => detail.value?.id, syncForm)
</script>

<template>
  <div class="page">
    <BlueprintSheet
      title="表与分区元数据"
      code="S-04 / CATALOG SHEET"
      note="算法 1 的输入全部来自这里：分区边界、分区字节、列字节与建议投影列。"
    >
      <div class="metrics">
        <MonoMetric :value="String(store.items.length)" unit="张" caption="登记表 / TABLES" />
        <MonoMetric :value="String(store.items.reduce((total, table) => total + table.partition_count, 0))" unit="个" caption="日分区 / PARTITIONS" />
        <MonoMetric
          :value="gibLabel(store.items.reduce((total, table) => total + table.total_bytes, 0), 1)"
          caption="登记总字节 / CATALOG BYTES"
        />
        <MonoMetric
          :value="cny(store.items.reduce((total, table) => total + table.total_bytes, 0) / 1024 ** 3 * 0.3, 2)"
          caption="整表全扫一遍的成本"
        />
      </div>

      <ErrorNotice v-if="store.error" :message="store.error" @retry="store.load()" />

      <div class="grid">
        <div class="list">
          <table class="grid-table">
            <thead>
              <tr>
                <th>表</th>
                <th>层</th>
                <th class="num">分区</th>
                <th class="num">总字节</th>
                <th class="num">查询 / 失效</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="table in store.items"
                :key="table.id"
                :class="{ 'is-active': detail?.id === table.id }"
                @click="select(table.id)"
              >
                <td>
                  <p class="mono table-name">{{ table.table_name }}</p>
                  <p class="meta">{{ table.owner }}</p>
                </td>
                <td><span class="tag">{{ table.layer }}</span></td>
                <td class="num mono">{{ table.partition_count }}</td>
                <td class="num mono">{{ gibLabel(table.total_bytes) }}</td>
                <td class="num mono">{{ table.query_count }} / <span :style="{ color: table.blocked_query_count ? 'var(--bad)' : 'inherit' }">{{ table.blocked_query_count }}</span></td>
              </tr>
            </tbody>
          </table>

          <div class="layer-strip">
            <p class="panel-label" style="margin-top: var(--space-4)">层字节分布 / BY LAYER</p>
            <div v-for="[layer, bytes] in layerTotals" :key="layer" class="layer-row">
              <span class="tag">{{ layer }} · {{ LAYER_LABEL[layer] }}</span>
              <span class="layer-bar"><i :style="{ width: `${(bytes / (layerTotals[0]?.[1] || 1)) * 100}%` }" /></span>
              <span class="mono hint">{{ gibLabel(bytes) }}</span>
            </div>
          </div>
        </div>

        <aside v-if="detail">
          <BlueprintPanel :label="`表详情 / ${detail.table_name}`">
            <div class="row">
              <StatusStamp :label="LAYER_LABEL[detail.layer] || detail.layer" tone="info" />
              <span class="tag">{{ detail.schema_name }}.{{ detail.table_name }}</span>
              <span class="tag">{{ detail.storage_format }}</span>
              <span class="tag">分区键 {{ detail.partition_key }}</span>
            </div>
            <p class="hint" style="margin: 10px 0 0">{{ detail.description }}</p>

            <dl class="kv">
              <div><dt>行数</dt><dd class="mono">{{ intLabel(detail.row_count) }}</dd></div>
              <div><dt>数据列</dt><dd class="mono">{{ detail.data_column_count }}</dd></div>
              <div><dt>分区数量</dt><dd class="mono">{{ detail.partition_count }}</dd></div>
              <div><dt>整表字节</dt><dd class="mono">{{ gibLabel(detail.total_bytes) }}</dd></div>
            </dl>
            <PartitionRuler
              :partitions="detail.partitions"
              :hit="detail.partitions.map((p) => p.dt)"
              :prunable="true"
              dense
            />
          </BlueprintPanel>

          <BlueprintPanel label="列统计 / COLUMN STATS">
            <table class="grid-table">
              <thead>
                <tr><th>列</th><th>类型</th><th class="num">字节</th><th class="num">占比</th></tr>
              </thead>
              <tbody>
                <tr v-for="column in detail.columns" :key="column.id">
                  <td>
                    <span class="mono">{{ column.name }}</span>
                    <span v-if="column.is_partition_key" class="tag" style="margin-left: 6px">PK</span>
                  </td>
                  <td class="mono hint">{{ column.data_type }}</td>
                  <td class="num mono">{{ gibLabel(column.bytes, 2) }}</td>
                  <td class="num mono">{{ ratio(column.byte_ratio, 3) }}</td>
                </tr>
              </tbody>
            </table>
          </BlueprintPanel>

          <BlueprintPanel label="建议投影列 / SUGGESTED PROJECTION">
            <div class="row">
              <span v-for="column in detail.suggested_columns" :key="column" class="tag">{{ column }}</span>
            </div>
            <p class="hint" style="margin: 10px 0 0">
              算法 2 的 <code>SELECT *</code> 改写会替换为这组列；改写后的列裁剪比例由后端重新计算。
            </p>
          </BlueprintPanel>

          <BlueprintPanel label="维护 / MAINTAIN">
            <template v-if="auth.isAdmin">
              <template v-if="!editing">
                <div class="kv">
                  <div><dt>负责人</dt><dd>{{ detail.owner }}</dd></div>
                  <div><dt>最近分析</dt><dd class="mono">{{ detail.last_analyzed_dt }}</dd></div>
                </div>
                <button class="btn" type="button" style="margin-top: 10px" @click="editing = true">编辑元数据</button>
              </template>
              <template v-else>
                <label class="field"><span>负责人</span><input v-model="owner" /></label>
                <label class="field"><span>表说明</span><textarea v-model="description" rows="3" /></label>
                <div class="row">
                  <button class="btn btn--primary" type="button" @click="save">保存</button>
                  <button class="btn btn--ghost" type="button" @click="editing = false; syncForm()">取消</button>
                </div>
              </template>
            </template>
            <p v-else class="hint">表元数据维护仅限 admin；engineer / viewer 调用 PATCH 会返回 403。</p>
          </BlueprintPanel>
        </aside>

        <EmptyState v-else title="没有匹配的表元数据。" hint="检查后端 seed 是否执行成功。" />
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
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.25fr);
  gap: var(--space-5);
}
.table-name {
  margin: 0;
  font-size: 0.78rem;
}
.meta {
  margin: 2px 0 0;
  font-size: 0.68rem;
  color: var(--cream-mute);
}
tbody tr {
  cursor: pointer;
}
.layer-strip {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.layer-row {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr) 84px;
  gap: var(--space-2);
  align-items: center;
}
.layer-bar {
  height: 5px;
  background: oklch(0.42 0.04 250 / 0.4);
}
.layer-bar i {
  display: block;
  height: 100%;
  background: var(--sand);
}
.kv {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin: var(--space-3) 0;
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
@media (max-width: 1180px) {
  .grid {
    grid-template-columns: 1fr;
  }
  .metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
