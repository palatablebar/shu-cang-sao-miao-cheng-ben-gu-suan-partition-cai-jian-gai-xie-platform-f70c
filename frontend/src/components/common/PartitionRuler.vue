<script setup lang="ts">
import { computed } from 'vue'
import { gibLabel } from '../../utils/format'

interface PartitionLike {
  dt: string
  bytes: number
}

const props = defineProps<{
  partitions: PartitionLike[]
  hit: string[]
  prunable: boolean
  dense?: boolean
}>()

const hitSet = computed(() => new Set(props.hit))
const maxBytes = computed(() => Math.max(1, ...props.partitions.map((p) => p.bytes)))
const height = computed(() => (props.dense ? 46 : 104))
const width = 720
const step = computed(() => (props.partitions.length ? width / props.partitions.length : width))
const barWidth = computed(() => Math.max(2, step.value * 0.62))

const bars = computed(() =>
  props.partitions.map((partition, index) => {
    const barHeight = Math.max(4, (partition.bytes / maxBytes.value) * (height.value - 16))
    return {
      ...partition,
      x: index * step.value + (step.value - barWidth.value) / 2,
      y: height.value - 10 - barHeight,
      height: barHeight,
      hit: hitSet.value.has(partition.dt),
    }
  }),
)

const firstDate = computed(() => props.partitions[0]?.dt ?? '—')
const lastDate = computed(() => props.partitions[props.partitions.length - 1]?.dt ?? '—')
const hitBytes = computed(() =>
  props.partitions.filter((p) => hitSet.value.has(p.dt)).reduce((total, p) => total + p.bytes, 0),
)
const allBytes = computed(() => props.partitions.reduce((total, p) => total + p.bytes, 0))
</script>

<template>
  <div class="ruler">
    <svg :viewBox="`0 0 ${width} ${height + 22}`" preserveAspectRatio="none" role="img" :aria-label="`分区命中 ${hit.length} / ${partitions.length}`">
      <line :x1="0" :x2="width" :y1="height" :y2="height" stroke="currentColor" stroke-opacity="0.35" stroke-width="1" />
      <g v-for="bar in bars" :key="bar.dt">
        <rect
          :x="bar.x"
          :y="bar.y"
          :width="barWidth"
          :height="bar.height"
          :fill="bar.hit ? 'var(--sand)' : 'var(--plate-700)'"
          :fill-opacity="bar.hit ? (prunable ? 0.92 : 0.66) : 0.5"
          :stroke="bar.hit ? 'var(--cream)' : 'transparent'"
          stroke-width="0.6"
        >
          <title>{{ bar.dt }} · {{ gibLabel(bar.bytes) }}{{ bar.hit ? ' · 命中' : ' · 未命中' }}</title>
        </rect>
        <text
          v-if="!dense && (bar.dt.endsWith('-01') || bar.dt === lastDate)"
          :x="bar.x + barWidth / 2"
          :y="height + 14"
          fill="var(--cream-mute)"
          font-size="9"
          font-family="var(--font-mono)"
          text-anchor="middle"
        >
          {{ bar.dt.slice(5) }}
        </text>
      </g>
    </svg>
    <div class="ruler-axis">
      <span class="mono">{{ firstDate }}</span>
      <span class="mono">{{ hit.length }} / {{ partitions.length }} 分区命中 · {{ gibLabel(hitBytes) }} / {{ gibLabel(allBytes) }}</span>
      <span class="mono">{{ lastDate }}</span>
    </div>
  </div>
</template>

<style scoped>
.ruler {
  width: 100%;
}
svg {
  width: 100%;
  height: auto;
  color: var(--rule-strong);
  display: block;
}
.ruler-axis {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  font-size: 0.66rem;
  color: var(--cream-mute);
  border-top: 1px solid var(--rule);
  padding-top: 4px;
  flex-wrap: wrap;
}
</style>
