# DEV_NOTES

> 项目内部开发记录（非对外文档）  
> 用于保存当前进度、关键决策与下一步计划，确保开发中断后可快速恢复上下文。

---

## 项目概览

- 项目名称：**sql-orchestrator**
- 职责定位：
  - 将自然语言查询编排（orchestrate）为可解释、可校验的 SQL
  - 支持交互式追问（clarify），而非一次性黑盒生成
- 对应前端：
  - 前端项目：`sql-copilot-ui`
  - 前后端通过 `/api/chat` 交互，协议严格对齐

---

## 本地开发环境

- OS：macOS
- Python：3.9.6
- 虚拟环境：`venv`
- 后端端口：`8000`
- 前端端口：`5173`

### 虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate

```

### 提示词

```text
按 sql-orchestrator 的 DEV_NOTES.md 继续
```

---

## 当前完成状态（Backend）

### ✅ 已完成（可联调）

- FastAPI 服务可启动（Windows / macOS）
- `/health`、`/docs` 可用
- 已配置 CORS（支持前端跨域预检 OPTIONS）
- 已实现强类型交互协议（Pydantic v2）：
  - `models/interaction.py`
  - `ChatRequest`
  - `ChatResponse`（discriminated union：clarify/sql/blocked）
- `/api/chat` v0.1（hardcode demo）已完成：
  - 无 answers → 返回 `type=clarify`（销售额口径 single_select）
  - 带 `answers.metric` → 返回 `type=sql`（包含 sql/dialect/validation，可扩展 explanation）
- 已引入 Session 记忆（InMemorySessionStore）：
  - session_id 自动生成（无则生成，有则复用）
  - 可保存 last_user_message、answers、last_clarify
  - 支持 TTL 清理（可选）
- 已实现 pending clarify 状态机（防止答案乱写入）：
  - `pending_clarify_type`
  - `pending_fields`
  - 仅在 pending 时接收 answers 并写入 session
  - 生成 SQL 后清理 pending
- SqlResponse 已补全 explanation（结构化）：
  - summary / tables / joins / select / filters / group_by / order_by / limit
  - data_type 支持 logical_type（string/number/date_range 等）
  - 便于前端渲染 explanation 面板与 join 解释

### ✅ 新增：Session 记忆开关（可禁用）

- 支持通过环境变量控制是否启用记忆：
  - `SESSION_MEMORY_ENABLED=true|false`
- Memory OFF（stateless）模式行为：
  - 不读写 session，不启用 pending
  - 每次请求只依赖本次 payload（answers 仅本次有效）
- `/health` 会返回 `session_memory_enabled` 便于验证

---

## 当前目录结构（Backend 关键文件）

- `sql_orchestrator/models/interaction.py`：前后端协议真相源（Pydantic）
- `sql_orchestrator/api/chat.py`：POST /api/chat（demo + 可联调逻辑）
- `sql_orchestrator/services/session.py`：InMemorySessionStore + pending 支持
- `sql_orchestrator/config/settings.py`：Settings（SESSION_MEMORY_ENABLED 开关）
- `sql_orchestrator/main.py`：FastAPI 入口 + CORS + store 注入

---

## 下一步计划（建议顺序）

1. 让 `sql` 响应补全 `explanation`（tables/joins/filters/select 等），对齐前端 SqlPanel 展示
2. 将 demo 逻辑从 API 层抽离到 `orchestrator/`：
   - `conversation.py`（状态机/决策）
   - `clarify.py`（追问生成）
3. 引入真实 metadata/schema（先本地 JSON，再接数据库采集）
4. 再接 Embedding/Qdrant + LLM（adapter 化）


## 数据库 Schema & Seed 设计阶段总结（2026-01）

### 背景
为了支持 Text-to-SQL + 交互式 Clarify（口径追问、join 解释、指标歧义），数据库不仅需要“能查”，还必须具备**可被 LLM / RAG 理解的业务语义**。

### 关键架构决策
1. **不使用物理外键（FOREIGN KEY）**
   - 关联关系不通过数据库约束，而通过字段注释中的语义表达
   - 原因：
     - BI / 分析型场景不依赖 FK
     - FK 会限制造数、脏数据测试、多 join 路径探索
     - LLM 需要“解释语义”，而不是“强约束”

2. **关联关系全部写入 COMMENT**
   - 统一注释规范：
     ```
     <描述> | ref=table.column | join=N:1 | role=fact|dimension|bridge
     ```
   - 扩展标签：
     - `metric=`：指标口径
     - `semantic=`：业务语义（gmv / sales 等）
     - `time=event`：事件时间字段

3. **数据库即元数据源（Schema = Cards 原材料）**
   - schema + column COMMENT 是 schema_cards 的权威来源
   - 不依赖 LLM 猜测 join / 口径

---

### 已完成内容

#### 1️⃣ Schema（001_schema.sql）
- 完整无 FK 版本
- 明确区分：
  - fact / dimension / bridge 表
- 所有 join 字段均通过 COMMENT 声明：
  - ref / join / role
- 指标字段已标注：
  - order_amount（GMV）
  - paid_amount（销售额）
  - refund_amount（退款额）
- 时间字段标注 `time=event`
- 保留必要索引（created_at / paid_at / customer_id 等）

#### 2️⃣ Seed 数据（002_seed.sql，方案 B）
- 数据规模：
  - ~300 客户
  - ~120 商品
  - ~1000 订单
- 数据分布特征：
  - 地域偏斜（广东占比高，支持“广东”高频查询）
  - 渠道偏斜（广告/抖音更高）
  - VIP 客户约 18%
- 订单状态链路完整：
  - created / paid / shipped / completed / cancelled
  - 时间字段合理 NULL / 非 NULL
- 金额口径真实：
  - 有优惠 / 无优惠
  - 已下单未支付（paid_amount=0）
  - 部分退款 / 全额退款
- 多表覆盖：
  - order / order_item / payment / shipment / refund / coupon
  - 支持多行订单明细、一单多券
- 可直接触发：
  - 口径 Clarify（订单金额 vs 实付金额）
  - 多 join / left join / group by / TopN

---

### 当前价值
- 数据库已具备：
  - **真实业务分布**
  - **可解释 schema**
  - **适合 Text-to-SQL + Clarify 的训练/验证环境**
- 后续：
  - schema_cards 可自动从 information_schema + COMMENT 生成
  - Qdrant / Embedding 仅是“检索层替换”，不会推翻设计

---

## Schema Cards 导出 & 校验（阶段性完成）

### 背景
在进入 Text-to-SQL / LLM 之前，优先解决「Schema 是否**可解释、可验证、可连通**」的问题，避免后续 SQL 生成依赖模型猜测 join 和业务语义。

### 设计原则
- **现阶段不工程化**：全部采用单文件脚本（tools/），降低复杂度
- **数据库即元数据源**：
  - 表/字段 COMMENT 是唯一权威
  - 不使用物理外键（FK），所有关联通过注释表达
- **测试驱动验证**：所有关键能力都必须能通过 tests 触发

---

### 已完成能力

#### 1️⃣ Schema Cards 导出（tools/export_schema_cards.py）
- 单文件实现，配置全部来自 env
- 从 information_schema 自动抽取：
  - 表 / 字段 / 索引
  - COMMENT 解析（description + tags）
  - ref / join / role / metric / semantic / time
- 生成 `schema_cards.json`，包含：
  - tables（列级元数据）
  - relations（由 ref 聚合的 join 关系）
- 支持轻量 profiling（可开关）：
  - null_ratio / distinct_count
  - 数值 min/max/avg
  - 时间 min/max
  - top values（示例值）
- 可直接运行或通过 pytest 触发

#### 2️⃣ Schema Cards 结构校验（tools/validate_schema_cards.py）
- 校验项：
  - ref 指向的表/字段是否存在
  - join 是否为合法值（N:1 / 1:N / 1:1 / N:N）
  - role 是否合法（fact / dimension / bridge）
  - 列级 ref 必须配 join
- 表级提示：
  - 若表内无任何 role 标注，给 warning
- CLI + pytest 双入口
- 确保 schema 注释本身是“自洽的”

#### 3️⃣ Join Path 可达性校验（tools/validate_join_paths.py）
- 从指定事实表（默认 `fact_order`）出发：
  - 构建 join 无向图
  - BFS 校验所有 dimension 表是否可达
- 支持 env 指定 root fact（ROOT_FACT_TABLE）
- 输出：
  - 不可达维表清单
  - 总表数 / 可达表数
- CLI 负责 exit code
- 提供 `run()` 方法供 tests 调用（不 sys.exit）

#### 4️⃣ Tests 覆盖
- `tests/test_export_schema_cards.py`
  - 触发导出
  - 校验 schema_cards.json 生成成功
- `tests/test_validate_schema_cards.py`
  - 校验 schema_cards 结构正确性
- `tests/test_validate_join_paths.py`
  - 触发 join path 校验
  - 确保所有 dimension 从 root fact 可达
- tests 内通过显式 `sys.path` 注入 root，避免工程化依赖

---

### 当前状态总结
- ✅ schema → 可解释（COMMENT + tags）
- ✅ schema → 可验证（结构 / join / role）
- ✅ schema → 可连通（join path reachability）
- ❌ 尚未进入 LLM / embedding / SQL 生成阶段（刻意延后）

这一阶段结束后，**LLM 不需要猜 join，不需要猜口径，只负责“编排”**。

---

### 下一步（已明确，但未开始）
- 生成 `schema_cards_for_llm.json`（精简视图）
  - 去掉 profiling 噪音
  - 保留表/字段描述、tags、relations、少量示例值
- 基于 schema_cards 做 SQL 编排（非直接生成）
- 再引入 embedding / 向量检索（Qdrant）

> 今日到此为止，schema 元数据地基已打牢。




