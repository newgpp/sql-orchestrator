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


## 



