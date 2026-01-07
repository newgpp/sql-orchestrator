# DEV_NOTES — sql-orchestrator

> 项目内部开发记录（非对外文档）  
> 用于在 **中断 / 新会话 / 跨环境** 后快速恢复完整上下文  
> 本文件是本项目的 **唯一决策真相源**

---

## 如何恢复上下文（重要）

- 本项目所有**关键技术决策**以本文件为准  
- 新会话 / 新协作者 / AI 助手：
  1. **先完整阅读本文件**
  2. 再继续开发
- 未在本文件中出现的方案：
  - 视为 **未开始** 或 **已否定**
- 本项目刻意 **分阶段推进**，不要提前引入 LLM / Embedding

---

## 一、项目总览

### 项目名称
**sql-orchestrator**

### 职责定位
- 将**自然语言查询**编排（orchestrate）为：
  - 可解释
  - 可校验
  - 可交互澄清（clarify）
  的 SQL
- 明确目标：
  - ❌ 非一次性黑盒 Text-to-SQL
  - ✅ 有状态 / 可追问 / 可解释

### 前后端关系
- 前端项目：`sql-copilot-ui`
- 通信方式：
  - POST `/api/chat`
  - 协议 **严格对齐**（前后端共享模型语义）

---

## 二、开发环境

### 本地环境（已验证）

- OS：macOS / Windows
- Python：
  - macOS：3.9.6
  - Windows：3.13.x
- 虚拟环境：`.venv`
- Backend Port：`8000`
- Frontend Port：`5173`

### 虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 三、Backend 当前完成状态（可联调）

### ✅ 已完成能力

#### 1️⃣ FastAPI 基础
- 服务可在 macOS / Windows 启动
- `/health`、`/docs` 可访问
- 已配置 CORS（支持 OPTIONS 预检）

#### 2️⃣ 强类型交互协议（Pydantic v2）
- `models/interaction.py` 是前后端协议真相源
- 定义：
  - `ChatRequest`
  - `ChatResponse`（discriminated union）：
    - `clarify`
    - `sql`
    - `blocked`

#### 3️⃣ `/api/chat` v0.1（Demo）
- 行为：
  - 无 answers → 返回 `type=clarify`
  - 有 `answers.metric` → 返回 `type=sql`
- 当前示例：
  - 销售额口径（订单金额 vs 实付金额）

#### 4️⃣ Session 记忆（可关闭）
- `InMemorySessionStore`
- 支持：
  - session_id 自动生成 / 复用
  - last_user_message / answers / pending_clarify
  - pending clarify 状态机（防止乱写 answers）
- 环境变量控制：
  - `SESSION_MEMORY_ENABLED=true|false`
- `/health` 会返回当前 memory 状态

#### 5️⃣ SQL Response Explanation
- `SqlResponse` 已包含结构化 explanation：
  - summary
  - tables
  - joins
  - select
  - filters
  - group_by / order_by / limit
- explanation 设计目标：
  - 直接支持前端 SqlPanel 渲染
  - 明确 join 与口径来源

---

## 四、数据库 Schema & Seed 设计（已完成）

### 设计目标
为 Text-to-SQL + Clarify 提供：
- 真实业务分布
- 明确业务语义
- **可被程序与 LLM 理解的 Schema**

### 核心决策（已定）

#### 1️⃣ 不使用物理外键（FOREIGN KEY）
- 关联关系 **不通过数据库约束**
- 全部通过字段 COMMENT 表达
- 原因：
  - BI / 分析型查询不依赖 FK
  - FK 会限制脏数据 / 多 join 路径测试
  - LLM 需要“解释语义”，不是“强约束”

#### 2️⃣ 关联关系统一写入 COMMENT

```text
<描述> | ref=table.column | join=N:1 | role=fact|dimension|bridge
```
- 扩展标签：
  - `metric=`：指标口径
  - `semantic=`：业务语义（gmv / sales 等）
  - `time=event`：事件时间字段

#### 3️⃣ 数据库即元数据源

- schema + column COMMENT 是 唯一权威

- schema_cards 完全由数据库自动生成

- 不依赖 LLM 猜 join / 口径

### schema测试数据

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


## 五、Schema Cards（元数据地基，已完成）

### 目标
在引入 LLM 前，彻底解决：
- Schema 是否可解释
- 注释是否自洽
- Join 是否真实可达

### 设计原则
- **现阶段不工程化**
- 全部使用单文件脚本（`tools/`）
- 所有能力必须能通过 `tests/` 触发

---

### 已完成能力

#### 1️⃣ Schema Cards 导出
- `tools/export_schema_cards.py`
- 从 information_schema 自动生成 `schema_cards.json`
- 内容：
  - 表 / 字段 / 索引
  - COMMENT → description + tags
  - relations（由 ref 聚合）
- 支持 profiling（可关）：
  - null_ratio / distinct_count
  - min / max / avg
  - top values

#### 2️⃣ Schema Cards 结构校验
- `tools/validate_schema_cards.py`
- 校验：
  - ref 指向存在性
  - join / role 合法性
  - ref 必须配 join
- 表级 role 缺失给 warning
- CLI + pytest 双入口

#### 3️⃣ Join Path 可达性校验
- `tools/validate_join_paths.py`
- 从 root fact（默认 `fact_order`）出发：
  - 构建 join 图
  - BFS 校验所有 dimension 是否可达
- 支持 env 指定 root fact（`ROOT_FACT_TABLE`）
- 提供：
  - CLI（exit code）
  - `run()` 方法供 tests 调用（不 `sys.exit`）

#### 4️⃣ Tests 覆盖
- `tests/test_export_schema_cards.py`
- `tests/test_validate_schema_cards.py`
- `tests/test_validate_join_paths.py`
- tests 内通过 `sys.path` 注入 root（避免工程化）

---

## 六、当前状态总结

- ✅ schema → 可解释（COMMENT + tags）
- ✅ schema → 可验证（结构 / join / role）
- ✅ schema → 可连通（join path reachability）
- ❌ 尚未进入 LLM / Embedding / SQL 生成阶段（刻意延后）

**结论：**
> LLM 不需要猜 join、不需要猜口径，只负责“编排”

---

## 七、下一阶段入口（未开始）

### 严格执行顺序
1. 生成 `schema_cards_for_llm.json`
   - 精简视图
   - 去掉 profiling 噪音
   - 保留描述 / tags / relations / 少量示例值
2. 基于 schema_cards 做 SQL 编排（非直接生成）
3. 再引入 Embedding / Qdrant
4. 最后接 LLM Adapter



