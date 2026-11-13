<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/authStore'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const nav = [
  { name: 'queries', label: '查询成本排行', code: 'S-01' },
  { name: 'rewrites', label: '改写建议', code: 'S-03' },
  { name: 'tables', label: '表与分区元数据', code: 'S-04' },
  { name: 'budget', label: '预算策略与批次', code: 'S-05' },
]

const activeName = computed(() => (route.name === 'query-detail' ? 'queries' : String(route.name ?? '')))

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="app">
    <aside class="rail">
      <div class="brand">
        <span class="brand-mark">▤</span>
        <div>
          <p class="brand-name">partfit</p>
          <p class="brand-sub">扫描成本台 · 蓝图卷</p>
        </div>
      </div>

      <div class="rail-meta">
        <p><span>PROJECT</span> 澜图零售 · ADS 层</p>
        <p><span>PLATE</span> LANTU-ADS-2026</p>
        <p><span>SCALE</span> 1 : 1 GiB</p>
      </div>

      <nav class="rail-nav">
        <router-link
          v-for="item in nav"
          :key="item.name"
          :to="{ name: item.name }"
          class="rail-link"
          :class="{ 'is-active': activeName === item.name }"
        >
          <span class="rail-code">{{ item.code }}</span>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="rail-foot">
        <div class="who">
          <p class="who-name">{{ auth.user?.display_name || '未登录' }}</p>
          <p class="who-role">{{ auth.roleLabel }} · {{ auth.user?.team || '' }}</p>
        </div>
        <button class="btn btn--ghost" type="button" @click="logout">退出</button>
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <div class="topbar-left">
          <span class="sheet-no">{{ route.meta.sheet || 'S-00' }}</span>
          <h1>{{ route.meta.title }}</h1>
        </div>
        <div class="topbar-right">
          <span class="tag">PostgreSQL 16 · parquet 分区表</span>
          <span class="tag tag--rust">￥0.30 / GiB 扫描</span>
        </div>
      </header>

      <slot />

      <footer class="title-block">
        <div>
          <p class="tb-label">DRAWING</p>
          <p class="tb-value">partfit · 数仓扫描成本估算与分区裁剪改写台</p>
        </div>
        <div>
          <p class="tb-label">CLIENT</p>
          <p class="tb-value">澜图零售 · 数据平台组（8 人）</p>
        </div>
        <div>
          <p class="tb-label">ROLE</p>
          <p class="tb-value">{{ auth.roleLabel }} · {{ auth.user?.email }}</p>
        </div>
        <div>
          <p class="tb-label">REV</p>
          <p class="tb-value mono">2026-11-12 / A</p>
        </div>
      </footer>
    </main>
  </div>
</template>

<style scoped>
.app {
  display: grid;
  grid-template-columns: var(--rail) minmax(0, 1fr);
  min-height: 100vh;
}

.rail {
  border-right: 1px solid var(--rule);
  padding: var(--space-5) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  background: oklch(0.225 0.05 254 / 0.72);
  position: sticky;
  top: 0;
  height: 100vh;
}

.brand {
  display: flex;
  gap: var(--space-3);
  align-items: center;
}
.brand-mark {
  font-size: 1.5rem;
  color: var(--rust);
  line-height: 1;
}
.brand-name {
  margin: 0;
  font-family: var(--font-mono);
  font-size: var(--step-1);
  letter-spacing: 0.16em;
  text-transform: uppercase;
}
.brand-sub {
  margin: 2px 0 0;
  font-size: var(--step--1);
  color: var(--cream-mute);
}

.rail-meta {
  border-top: 1px solid var(--rule);
  border-bottom: 1px solid var(--rule);
  padding: var(--space-3) 0;
  font-family: var(--font-mono);
  font-size: 0.68rem;
  line-height: 1.8;
  color: var(--cream-dim);
}
.rail-meta p {
  margin: 0;
  display: flex;
  justify-content: space-between;
  gap: 6px;
}
.rail-meta span {
  color: var(--cream-mute);
  letter-spacing: 0.1em;
}

.rail-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.rail-link {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 9px 10px;
  color: var(--cream-dim);
  text-decoration: none;
  border-left: 2px solid transparent;
  font-size: var(--step-0);
  transition:
    background 0.2s var(--ease-out),
    border-color 0.2s var(--ease-out);
}
.rail-link:hover {
  background: oklch(0.32 0.05 252 / 0.6);
  color: var(--cream);
}
.rail-link.is-active {
  border-left-color: var(--rust);
  background: oklch(0.335 0.052 251 / 0.72);
  color: var(--cream);
}
.rail-code {
  font-family: var(--font-mono);
  font-size: 0.66rem;
  color: var(--cream-mute);
  letter-spacing: 0.08em;
}

.rail-foot {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  border-top: 1px solid var(--rule);
  padding-top: var(--space-3);
}
.who-name {
  margin: 0;
  font-size: var(--step-0);
}
.who-role {
  margin: 2px 0 0;
  font-size: 0.68rem;
  color: var(--cream-mute);
  line-height: 1.5;
}

.main {
  padding: var(--space-5) var(--space-6) var(--space-4);
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: var(--space-4);
  flex-wrap: wrap;
}
.topbar-left {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
}
.sheet-no {
  font-family: var(--font-mono);
  font-size: var(--step--1);
  color: var(--rust);
  border: 1px solid oklch(0.7 0.11 45 / 0.55);
  padding: 1px 7px;
  letter-spacing: 0.1em;
}
.topbar h1 {
  font-size: var(--step-2);
  font-weight: 600;
}
.topbar-right {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.title-block {
  margin-top: auto;
  border: 1px solid var(--rule);
  display: grid;
  grid-template-columns: 2fr 1.6fr 1.6fr 0.9fr;
  font-size: var(--step--1);
}
.title-block > div {
  padding: 8px 12px;
  border-right: 1px solid var(--rule);
}
.title-block > div:last-child {
  border-right: none;
}
.tb-label {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 0.62rem;
  letter-spacing: 0.16em;
  color: var(--cream-mute);
}
.tb-value {
  margin: 2px 0 0;
  color: var(--cream-dim);
}

@media (max-width: 1180px) {
  .app {
    grid-template-columns: 1fr;
  }
  .rail {
    position: static;
    height: auto;
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    border-right: none;
    border-bottom: 1px solid var(--rule);
  }
  .rail-meta {
    display: none;
  }
  .rail-nav {
    flex-direction: row;
    flex: 1;
  }
  .rail-foot {
    margin-top: 0;
    border-top: none;
    padding-top: 0;
    flex-direction: row;
    align-items: center;
  }
  .main {
    padding: var(--space-4);
  }
  .title-block {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 720px) {
  .rail-nav {
    flex-wrap: wrap;
  }
  .rail-code {
    display: none;
  }
  .topbar h1 {
    font-size: var(--step-1);
  }
  .title-block {
    grid-template-columns: 1fr;
  }
  .title-block > div {
    border-right: none;
    border-bottom: 1px solid var(--rule);
  }
}
</style>
