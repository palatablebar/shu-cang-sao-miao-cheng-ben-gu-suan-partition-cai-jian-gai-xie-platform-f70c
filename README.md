# partfit · 数仓扫描成本估算与分区裁剪改写台

把「一条 SQL 到底扫了多少字节、为什么裁剪失效、改写后能省多少」画在同一张工程蓝图上。

## 1. 真实场景

- **模拟客户**：澜图零售 · 数据平台组（8 人）。ADS 层 40 张表、每天约 300 条查询，月仓账单 1.8 万元。
- **现有工作流**：账单来了才知道贵；慢查询靠人翻执行计划，改写靠老工程师经验；分区字段做函数包裹这类反模式反复出现。
- **三个痛点**：① 单条查询扫描量不可见；② 分区谓词写错导致裁剪失效无人告警；③ 改写收益无法量化、无法排序。
- **上下游**：上游 = 查询日志 + 表/分区/列元数据（分区边界、行数、字节）→ 本系统替代「人工看执行计划 + 经验改写」→ 下游 = 数据开发改 SQL、平台组报预算。
- **一天的工作剧本**（seed 数据与之一致）：
  1. 08:40 沈知远打开「查询成本排行」，看到昨日 60 条查询合计扫描量与 Top1（`dwd_order_detail` 双 11 全量导出，12.40 GiB/次）。
  2. 08:50 点开 Top1 的 SQL 解析详情：谓词是 `to_char(dt,'YYYY-MM-DD') = '2026-11-11'`，被判定「分区列被函数包裹」，30 个分区全部命中。
  3. 09:05 对这条查询生成改写建议 `RW-QL-0001`：`dt = '2026-11-11'` + 建议投影列，节省 98.8%。
  4. 09:20 重估并把建议标记为采纳，导出 12 行优化清单 CSV 发给数据开发。
  5. 09:40 陈肃按清单改掉 8 条隐式类型转换（`dt = 20261112` → `dt = '2026-11-12'`）。
  6. 10:10 周娅（财务 BP，只读）打开预算页看子集 1,800 元预算占用（折算约 81%），无法触发估算/改写（后端 403）。
  7. 10:30 沈知远把 DWD 层单条扫描告警阈值从 8 GiB 调到 6 GiB，审计流水留痕。

## 2. 主要功能

| 模块 | 说明 |
|---|---|
| 查询成本排行 | 按扫描字节/费用/耗时排行，标注「可裁剪 / 裁剪失效 + 原因」，支持来源、表、关键字过滤 |
| SQL 解析详情 | sqlglot 解析结果：分区谓词逐条判定、命中分区、列裁剪比例、扫描量拆解、可解释结论 |
| 改写建议与前后对比 | 反模式识别 → 等价改写 SQL → 重估节省 → 按 `saving × confidence ÷ risk_weight` 排序，可采纳/导出 |
| 表与分区元数据 | 6 张表 / 90 个日分区 / 列字节统计 / 建议投影列；admin 可维护负责人与说明 |
| 预算策略与批次 | 子集月预算 1,800 元（全仓 1.8 万的 1/10）与 warn/critical 阈值、按表扫描分布、估算批次（Celery 异步）、审计流水（admin） |

## 3. 算法口径

### 算法 1：扫描量估算与裁剪判定（`backend/src/analysis/sql_analyzer.py`、`predicates.py`、`estimator.py`）

```
col_ratio  = Σ_{c ∈ 引用列且 c 不是分区键} bytes_c / Σ_{c ∈ 数据列} bytes_c
scan_bytes = Σ_{p ∈ P_hit} bytes_p × col_ratio
P_hit      = { p | 分区谓词在 p.dt 上求值为真 }
```

- 裸列比较（`dt = '2026-11-12'`、`BETWEEN`、`IN`、比较运算）= **可裁剪**；
- 分区列被函数/表达式包裹（`to_char(dt,..)`、`date(dt)`、`dt::date`、`substr(dt,1,7)`、`trunc(dt)`）= **不可裁剪**（`function_wrapped`）；
- 字面量类型与分区列不一致（date_str 列比整型 `20261112`）= 隐式转换（`implicit_cast`），**不可裁剪**；
- 完全没有分区谓词 = `missing_predicate`，**不可裁剪**；
- `SELECT *` 时 `col_ratio = 1.0`；纯聚合按最小列比例 0.03 计。
- 失败态：`unparsed`（sqlglot 解析失败）、`missing_table`（表不在元数据目录）都会显式返回，绝不静默记 0。

### 算法 2：改写建议与收益排序（`backend/src/analysis/rewriter.py`、`scoring.py`）

- 反模式：`partition_function_wrap` / `partition_implicit_cast` / `select_star` / `missing_partition_predicate`；
- 改写：裸列比较、同类型字面量、按表元数据建议投影列替换 `*`、补最近 7 天时间窗口；
- 风险与置信度：低风险 1.0/0.95、中风险 1.6/0.90、高风险 2.4/0.62（同一查询命中多类取最严 + 最低置信度）；
- **改写后扫描量不是估算系数**，而是把改写 SQL 重新喂给算法 1 求解，`saving = before − after`，`score = saving_bytes × confidence ÷ risk_weight`。

## 4. 快速启动

```bash
cp .env.example .env
docker compose up -d --build
# 等 5 个服务 healthy（约 60-90s），backend 启动时自动执行一次 seed
open http://localhost:18243
```

- 前端：<http://localhost:18243>
- 后端：<http://localhost:19243/docs>（健康检查 `/health`、`/api/health`）
- PostgreSQL：`localhost:17743`（库 `partfit_db`）

手工重跑 seed（幂等，最后一行固定输出 `SEED_SUMMARY brand=partfit tables=6 partitions=90 queries=60 estimates=2 suggestions=12 users=3`）：

```bash
docker compose exec -T backend python -m scripts.seed_demo
```

## 5. 演示账号（密码统一 `Demo@2026`）

| 邮箱 | 角色 | 能做什么 | 不能做什么 |
|---|---|---|---|
| `admin@partfit.io` | `admin` 平台负责人 | 表元数据维护、预算阈值、跑估算、生成/采纳改写、看审计 | — |
| `engineer@partfit.io` | `engineer` 数据开发 | 导入日志、跑估算、生成/采纳改写、重估 | 改表元数据（403）、改预算（403）、看审计（403） |
| `viewer@partfit.io` | `viewer` 财务 / BI 只读 | 看排行/解析详情/改写对比、导出 CSV | 跑估算（403）、生成改写（403）、导入日志（403）、改预算（403） |

> 权限是后端中间件 + RBAC 依赖实现的真实 403，不是前端隐藏按钮。

## 6. 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3.4 + TypeScript + Vite 5 + Pinia + vue-router + 自绘 SVG（无图表 CDN） |
| 后端 | Python 3.11 + FastAPI 0.115 + SQLAlchemy 2.0 + Pydantic 2 + PyJWT |
| 算法 | sqlglot 30.31（PostgreSQL 方言）真实解析 |
| 任务 | Celery 5.4 + Redis 7 |
| 数据库 | PostgreSQL 16 |
| 反代 | Nginx 1.27（`/api/` → backend:8000，SPA 回落） |
| 容器 | 恰好 5 服务：frontend / backend / worker / db / redis |

## 7. 目录

```
backend/
  src/{config,constants,models,schemas,analysis,services,controllers,routes,middlewares,utils,tasks}
  scripts/{seed_demo.py,demo_dataset.py}
  migrations/0001_initial.sql
worker/{Dockerfile,entrypoint.sh,healthy.py}
frontend/src/{api,stores,types,components/common,hooks,pages,router,utils,constants,styles}
docker-compose.yml  .env.example  README.md
```

## 8. 环境变量（`.env.example`）

| 变量 | 默认 | 说明 |
|---|---|---|
| `COMPOSE_PROJECT_NAME` | `partfit` | 容器名前缀 |
| `FRONTEND_PORT` / `BACKEND_PORT` / `DB_PORT` | 18243 / 19243 / 17743 | 端口映射 |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | partfit_db / partfit_user / partfit_pwd | PostgreSQL |
| `JWT_SECRET` / `JWT_EXPIRE_HOURS` | dev secret / 8 | 登录令牌 |
| `COST_PER_GIB_CNY` | 0.30 | 每 GiB 扫描单价（元） |
| `QUERY_VOLUME_SCALE` | 5 | 60 条样本 → 日均 300 条查询的放样倍数 |
| `MONTHLY_QUERY_DAYS` | 30 | 月账单折算天数 |
| `DEFAULT_MONTHLY_BUDGET_CNY` | 1800 | 演示子集月预算兜底（全仓 1.8 万的 1/10） |
| `REWRITE_WINDOW_DAYS` | 7 | 补分区谓词的默认窗口 |
| `ESTIMATE_INLINE` | false | true 时不走 Celery（本地调试） |
| `RATE_WINDOW_MAX` | 240 | 限流：每窗口最大请求数 |
| `SEED_DEMO` | true | 启动自动 seed |

## 9. Docker 说明

- 5 个服务全部带 healthcheck：db(`pg_isready`) / redis(`redis-cli ping`) / backend(`/health` 探活) / worker(心跳文件 `/tmp/partfit-worker-heartbeat`) / frontend(`/healthz`)。
- 依赖用 `service_healthy` 串联：backend、worker 等 db+redis；frontend 等 backend。
- 命名卷：`pg_data`、`redis_data`、`warehouse_data`（后端/worker 共享产物目录）。
- 估算批次走 Celery：`POST /api/estimates` 落库 queued → worker 执行 → 前端轮询到 completed。
- 只用本机已有镜像 tag（python:3.11-slim / node:20-alpine / nginx:1.27-alpine / postgres:16-alpine / redis:7-alpine），pip 走清华源。

## 10. 枚举出现位置

| 枚举 | 后端 | 前端 |
|---|---|---|
| `Role` (admin/engineer/viewer) | `backend/src/constants/enums.py`、`middlewares/rbac.py`、`models/user.py`、`scripts/demo_dataset.py` | `frontend/src/types/user.ts`、`constants/enums.ts`(ROLE_LABEL)、`stores/authStore.ts` |
| `PruneBlockReason` | `constants/enums.py`、`analysis/predicates.py`、`analysis/sql_analyzer.py`、`models/query_log.py` | `constants/enums.ts`(BLOCKED_REASON_LABEL)、`pages/QueryCostPage.vue`、`pages/QueryDetailPage.vue` |
| `AntiPattern` | `constants/enums.py`、`analysis/rewriter.py`、`analysis/scoring.py` | `constants/enums.ts`(ANTI_PATTERN_LABEL)、`pages/RewritePage.vue` |
| `RiskLevel` | `constants/enums.py`、`analysis/scoring.py`、`models/rewrite_suggestion.py` | `constants/enums.ts`(RISK_LABEL)、`pages/RewritePage.vue` |
| `RunStatus` / `SuggestionStatus` | `constants/enums.py`、`services/estimate_service.py`、`services/rewrite_service.py` | `constants/enums.ts`(RUN_STATUS_LABEL / SUGGESTION_STATUS_LABEL)、`pages/BudgetPage.vue` |
| `BudgetStatus` | `constants/enums.py`、`services/estimate_service.py`、`services/budget_service.py` | `constants/enums.ts`(BUDGET_STATUS_LABEL)、`pages/BudgetPage.vue` |
| `TableLayer` | `constants/enums.py`、`models/table_meta.py` | `constants/enums.ts`(LAYER_LABEL)、`pages/TablesPage.vue` |

## 11. 本地开发

```bash
# backend（需要本机 PostgreSQL/Redis 时改 .env 的 DB_HOST=127.0.0.1）
cd backend && pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
uvicorn src.main:app --reload --port 19243

# frontend（vite 代理 /api → localhost:19243）
cd frontend && npm install && npm run dev   # http://localhost:18243
```

## 12. 视觉方向

工程蓝图风：普鲁士蓝底 + 米白坐标网格、标注箭头与尺寸线、图章式状态、等宽数字；双字体
**Archivo**（界面）+ **Space Mono**（数字/代码/标签）；`oklch()` 低饱和色板，无青蓝霓虹、无渐变文字；
响应式 ≥1280 / ≥768 / <768 三档。

## 13. License

MIT（演示项目，数据均为虚构）。
