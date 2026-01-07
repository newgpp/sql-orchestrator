from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter()

@router.post("/chat")
def chat(payload: Dict[str, Any]):
    """
    临时 hardcode 版本：
    - 永远返回一个 clarify
    - 用于打通前后端
    """
    session_id = payload.get("session_id") or "backend_session_001"

    return {
        "type": "clarify",
        "clarify_type": "METRIC_DEFINITION_AMBIGUOUS",
        "question": "你说的“销售额”是指哪个口径？",
        "fields": [
            {
                "key": "metric",
                "ui": "single_select",
                "options": [
                    {
                        "value": "SUM(o.order_amount)",
                        "label": "订单金额（未扣退款）"
                    },
                    {
                        "value": "SUM(o.paid_amount)",
                        "label": "实付金额（已扣优惠/退款）"
                    }
                ],
                "default": "SUM(o.paid_amount)"
            }
        ],
        "session_id": session_id
    }
