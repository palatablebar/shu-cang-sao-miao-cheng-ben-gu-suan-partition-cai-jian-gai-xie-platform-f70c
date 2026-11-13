<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/authStore'
import ErrorNotice from '../components/common/ErrorNotice.vue'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const email = ref('admin@partfit.io')
const password = ref('Demo@2026')
const error = ref('')

const accounts = [
  { email: 'admin@partfit.io', role: 'admin', label: '沈知远 · 平台负责人' },
  { email: 'engineer@partfit.io', role: 'engineer', label: '陈肃 · 数据开发' },
  { email: 'viewer@partfit.io', role: 'viewer', label: '周娅 · 财务 BP' },
]

async function submit() {
  error.value = ''
  try {
    await auth.login(email.value.trim(), password.value)
    const redirect = (route.query.redirect as string) || '/queries'
    router.push(redirect)
  } catch (err) {
    error.value = (err as Error).message
  }
}

function fill(account: string) {
  email.value = account
  password.value = 'Demo@2026'
}
</script>

<template>
  <div class="login">
    <section class="plate">
      <header class="plate-head">
        <span class="plate-code">PLATE A-01 · SCAN COST</span>
        <span class="plate-code">2026-11-12 / REV A</span>
      </header>

      <h1>
        把每条 SQL 的<br />
        <span class="accent">扫描量</span>画成蓝图
      </h1>
      <p class="plate-lead">
        澜图零售数据平台组每天约 300 条查询，月仓账单 1.8 万元。partfit 把查询日志、表/分区/列统计
        与改写建议画在同一张工程图上：先量出扫描量，再标出裁剪失效的位置，最后给出可排序的改写收益。
      </p>

      <div class="schematic" aria-hidden="true">
        <svg viewBox="0 0 520 190">
          <g stroke="var(--rule-strong)" fill="none">
            <rect x="10" y="26" width="118" height="104" />
            <rect x="150" y="46" width="96" height="64" />
            <rect x="278" y="26" width="150" height="104" />
          </g>
          <g font-family="var(--font-mono)" font-size="9" fill="var(--cream-mute)">
            <text x="18" y="20">TABLE · dwd_order_detail</text>
            <text x="158" y="40">PARTITIONS ×30</text>
            <text x="286" y="20">SCAN · 12.40 GiB</text>
          </g>
          <g fill="var(--plate-700)">
            <rect x="20" y="120" width="12" height="8" />
            <rect x="36" y="120" width="12" height="8" />
            <rect x="52" y="120" width="12" height="8" />
            <rect x="68" y="120" width="12" height="8" />
          </g>
          <g fill="var(--sand)" opacity="0.9">
            <rect x="84" y="120" width="12" height="8" />
            <rect x="100" y="120" width="12" height="8" />
          </g>
          <g fill="var(--rust)">
            <rect x="160" y="58" width="10" height="44" opacity="0.55" />
            <rect x="176" y="58" width="10" height="44" opacity="0.55" />
            <rect x="192" y="58" width="10" height="44" opacity="0.55" />
            <rect x="208" y="58" width="10" height="44" opacity="0.55" />
            <rect x="224" y="58" width="10" height="44" opacity="0.55" />
          </g>
          <g stroke="var(--rust)" fill="none">
            <path d="M256 92 L274 92" />
            <path d="M274 92 L267 88 M274 92 L267 96" />
          </g>
          <g stroke="var(--rust)" stroke-dasharray="3 3">
            <path d="M278 118 L428 118" />
            <path d="M278 112 L278 124 M428 112 L428 124" />
          </g>
          <g font-family="var(--font-mono)" font-size="9" fill="var(--rust)">
            <text x="312" y="140">to_char(dt) → 裁剪失效</text>
            <text x="286" y="150" fill="var(--cream-mute)">改写后 0.15 GiB / 次 · 节省 98.8%</text>
          </g>
        </svg>
      </div>

      <div class="facts">
        <div><span class="mono">60</span><p>条查询日志</p></div>
        <div><span class="mono">18</span><p>条裁剪失效</p></div>
        <div><span class="mono">12</span><p>条改写建议</p></div>
        <div><span class="mono">6</span><p>张分区表 / 90 分区</p></div>
      </div>
    </section>

    <section class="form-wrap">
      <div class="form-card">
        <p class="form-label">PLATFORM PASS · 平台通行证</p>
        <h2>登录扫描成本台</h2>
        <p class="hint" style="margin: 6px 0 22px">
          三个演示账号密码均为 <code>Demo@2026</code>；viewer 为财务只读，越权写接口会拿到真实 403。
        </p>

        <form @submit.prevent="submit">
          <label class="field">
            <span>企业邮箱</span>
            <input v-model="email" type="email" autocomplete="username" required />
          </label>
          <label class="field">
            <span>密码</span>
            <input v-model="password" type="password" autocomplete="current-password" required />
          </label>
          <button class="btn btn--primary" type="submit" :disabled="auth.loading" style="width: 100%; justify-content: center">
            {{ auth.loading ? '校验中…' : '进入工作台' }}
          </button>
        </form>

        <div v-if="error" style="margin-top: 16px">
          <ErrorNotice :message="error" @retry="submit" />
        </div>

        <div class="accounts">
          <p class="form-label" style="margin-bottom: 8px">演示账号（点击填入）</p>
          <button v-for="account in accounts" :key="account.email" type="button" class="account" @click="fill(account.email)">
            <span class="mono">{{ account.email }}</span>
            <span class="hint">{{ account.label }}</span>
          </button>
        </div>
      </div>
      <p class="hint" style="margin-top: 16px">
        后端 PostgreSQL 16 · 扫描单价 ￥0.30 / GiB · 所有估算与改写均由 Python 算法落库，前端不参与计算。
      </p>
    </section>
  </div>
</template>

<style scoped>
.login {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 0.85fr);
  min-height: 100vh;
}

.plate {
  padding: var(--space-6) var(--space-6) var(--space-5);
  border-right: 1px solid var(--rule);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  background: oklch(0.235 0.05 254 / 0.6);
}
.plate-head {
  display: flex;
  justify-content: space-between;
  font-family: var(--font-mono);
  font-size: 0.66rem;
  letter-spacing: 0.16em;
  color: var(--cream-mute);
  border-bottom: 1px solid var(--rule);
  padding-bottom: var(--space-2);
}
.plate h1 {
  font-size: var(--step-4);
  font-weight: 600;
  letter-spacing: -0.015em;
  line-height: 1.12;
}
.accent {
  color: var(--rust);
}
.plate-lead {
  margin: 0;
  max-width: 56ch;
  color: var(--cream-dim);
  font-size: var(--step-0);
  line-height: 1.7;
}
.schematic svg {
  width: 100%;
  max-width: 560px;
  height: auto;
  border: 1px solid var(--rule);
  background: oklch(0.225 0.045 254 / 0.5);
  padding: 8px;
}
.facts {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
  border-top: 1px solid var(--rule);
  padding-top: var(--space-3);
}
.facts span {
  font-size: var(--step-2);
  color: var(--cream);
}
.facts p {
  margin: 2px 0 0;
  font-size: var(--step--1);
  color: var(--cream-mute);
}

.form-wrap {
  padding: var(--space-7) var(--space-6);
  display: flex;
  flex-direction: column;
  justify-content: center;
  max-width: 520px;
}
.form-card {
  border: 1px solid var(--rule);
  background: oklch(0.26 0.05 253 / 0.75);
  padding: var(--space-5);
  position: relative;
}
.form-card::before {
  content: '';
  position: absolute;
  inset: 6px;
  border: 1px solid oklch(0.88 0.03 88 / 0.08);
  pointer-events: none;
}
.form-card h2 {
  font-size: var(--step-2);
}
.form-label {
  font-family: var(--font-mono);
  font-size: 0.66rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--cream-mute);
  margin: 0 0 var(--space-2);
}
.accounts {
  margin-top: var(--space-5);
  border-top: 1px solid var(--rule);
  padding-top: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.account {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  align-items: baseline;
  background: transparent;
  border: 1px dashed var(--rule);
  padding: 7px 10px;
  cursor: pointer;
  color: var(--cream-dim);
  text-align: left;
  font-size: var(--step--1);
  transition: border-color 0.2s var(--ease-out);
}
.account:hover {
  border-color: var(--rust);
  color: var(--cream);
}

@media (max-width: 980px) {
  .login {
    grid-template-columns: 1fr;
  }
  .plate {
    border-right: none;
    border-bottom: 1px solid var(--rule);
    padding: var(--space-5) var(--space-4);
  }
  .form-wrap {
    padding: var(--space-5) var(--space-4);
    max-width: none;
  }
}
</style>
