from __future__ import annotations

from fastapi import APIRouter, Request
from typing import Any, Dict, Optional

from sql_orchestrator.models.interaction import ChatRequest, ChatResponse

router = APIRouter()


def _new_session_id() -> str:
    import uuid
    return f"sess_{uuid.uuid4().hex[:16]}"


def _get_metric_from_answers(answers: Optional[Dict[str, Any]]) -> Optional[str]:
    if not answers:
        return None
    metric = answers.get("metric")
    if metric is None:
        return None
    return str(metric)


def _build_clarify(session_id: str) -> Dict[str, Any]:
    return {
        "type": "clarify",
        "clarify_type": "METRIC_DEFINITION_AMBIGUOUS",
        "question": "你说的“销售额”是指哪个口径？",
        "context_hint": "不同口径会影响结果，请选择一种用于生成 SQL。",
        "fields": [
            {
                "key": "metric",
                "ui": "single_select",
                "options": [
                    {"value": "SUM(o.order_amount)", "label": "订单金额（未扣退款）"},
                    {"value": "SUM(o.paid_amount)", "label": "实付金额（已扣优惠/退款）"},
                ],
                "default": "SUM(o.paid_amount)",
            }
        ],
        "session_id": session_id,
    }


def _build_sql(session_id: str, metric: str) -> Dict[str, Any]:
    sql = f"""
SELECT
  c.customer_name AS customer_name,
  {metric} AS total_sales
FROM orders o
INNER JOIN customers c ON o.customer_id = c.id
WHERE o.province = '广东'
  AND o.paid_at >= '2024-01-01' AND o.paid_at < '2025-01-01'
GROUP BY c.customer_name
ORDER BY total_sales DESC
LIMIT 10;
""".strip()

    # ===== explanation（结构化）=====
    explanation: Dict[str, Any] = {
        "summary": "按客户汇总2024年广东省销售额，取前10名。",
        "tables": [
            {"name": "orders", "alias": "o", "role": "fact", "description": "订单事实表（示例）"},
            {"name": "customers", "alias": "c", "role": "dimension", "description": "客户维表（示例）"},
        ],
        "joins": [
            {
                "type": "INNER",
                "left": {"table": "orders", "alias": "o", "column": "customer_id"},
                "right": {"table": "customers", "alias": "c", "column": "id"},
                "cardinality": "N:1",
                "reason": "通过 customer_id 关联客户名称，并按客户聚合订单",
                "source": "relation_card",
            }
        ],
        "select": [
            {
                "expr": "c.customer_name",
                "alias": "customer_name",
                "semantic_type": "dimension",
                "data_type": {"db_type": "varchar(128)", "logical_type": "string"},
                "definition": "客户名称",
            },
            {
                "expr": metric,
                "alias": "total_sales",
                "semantic_type": "metric",
                "data_type": {"db_type": "decimal(18,2)", "logical_type": "number", "unit": "CNY"},
                "definition": "实付金额汇总" if "paid_amount" in metric else "订单金额汇总",
            },
        ],
        "filters": [
            {
                "expr": "o.province = '广东'",
                "field": {"table": "orders", "alias": "o", "column": "province"},
                "op": "=",
                "value": {"type": "string", "raw": "'广东'"},
                "source": "user",
            },
            {
                "expr": "o.paid_at >= '2024-01-01' AND o.paid_at < '2025-01-01'",
                "field": {"table": "orders", "alias": "o", "column": "paid_at"},
                "op": "between",
                "value": {
                    "type": "date_range",
                    "start": "2024-01-01",
                    "end": "2025-01-01",
                    "inclusive_start": True,
                    "exclusive_end": True,
                },
                "source": "default",
            },
        ],
        "group_by": [
            {"table": "customers", "alias": "c", "column": "customer_name"}
        ],
        "order_by": [
            {"expr": "total_sales", "direction": "DESC"}
        ],
        "limit": {"value": 10, "source": "default"},
    }

    # ===== validation（先给 warn，后续接 validator 可替换）=====
    validation: Dict[str, Any] = {
        "status": "warn",
        "warnings": [
            {"code": "HARDCODED_DEMO", "message": "当前为 hardcode 演示 SQL（尚未接入真实元数据/模型）"}
        ],
    }

    return {
        "type": "sql",
        "sql": sql,
        "dialect": "mysql",
        "explanation": explanation,
        "validation": validation,
        "session_id": session_id,
    }


@router.post("/chat", response_model=ChatResponse)
def chat(req: Request, payload: ChatRequest) -> ChatResponse:
    store = getattr(req.app.state, "session_store", None)

    # ===== Memory OFF：stateless =====
    if store is None:
        session_id = payload.session_id or _new_session_id()
        metric_from_req = _get_metric_from_answers(payload.answers)

        if metric_from_req:
            return _build_sql(session_id, metric_from_req)

        return _build_clarify(session_id)

    # 1) session_id：无则生成
    session_id = payload.session_id or _new_session_id()

    # 2) 取/建 session，并记录用户消息
    store.get_or_create(session_id)
    store.set_last_user_message(session_id, payload.message)

    # 3) 如果本次提交带 answers.metric，写入 session
    metric_from_req = _get_metric_from_answers(payload.answers)
    if metric_from_req:
        store.update_answers(session_id, {"metric": metric_from_req})
        return _build_sql(session_id, metric_from_req)

    # 4) 如果 session 已经记住 metric，就不要反复追问
    s = store.get(session_id)
    metric_from_session = None
    if s and s.answers:
        metric_from_session = _get_metric_from_answers(s.answers)

    if metric_from_session:
        return _build_sql(session_id, metric_from_session)

    # 5) 否则返回 clarify，并把 clarify 记住（可用于回放/调试）
    clarify = _build_clarify(session_id)
    store.set_last_clarify(session_id, clarify)
    return clarify
