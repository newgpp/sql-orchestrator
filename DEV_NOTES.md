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


### 提示词

```
# 2025-01-07
按 sql-orchestrator 的 DEV_NOTES.md 继续
```