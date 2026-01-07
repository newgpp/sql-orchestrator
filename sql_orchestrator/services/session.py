from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from time import time
from typing import Any, Dict, Optional, List

# 让 session 记忆“有边界”，避免你后面接 LLM/Schema 后出现把旧答案错用到新问题的灾难
# 只有在“明确处于追问中（pending）”时，才把 answers 写入 session
#
# 一旦收到答案并生成 SQL，就清掉 pending
# 如果用户在 pending 状态下又问了新问题（没带 answers），我们可以：
# 继续追问（默认）
# 或判定为新意图并重置（后续做 intent 决策；现在先保守：继续追问）
@dataclass
class SessionState:
    session_id: str
    created_at: float = field(default_factory=time)
    updated_at: float = field(default_factory=time)

    last_user_message: Optional[str] = None
    answers: Dict[str, Any] = field(default_factory=dict)
    last_clarify: Optional[Dict[str, Any]] = None

    # ===== pending clarify state =====
    pending_clarify_type: Optional[str] = None
    pending_fields: List[str] = field(default_factory=list)


class InMemorySessionStore:
    def __init__(self, ttl_seconds: int = 3600):
        self._ttl = ttl_seconds
        self._lock = RLock()
        self._data: Dict[str, SessionState] = {}

    def get_or_create(self, session_id: str) -> SessionState:
        with self._lock:
            s = self._data.get(session_id)
            if s is None:
                s = SessionState(session_id=session_id)
                self._data[session_id] = s
            s.updated_at = time()
            return s

    def get(self, session_id: str) -> Optional[SessionState]:
        with self._lock:
            s = self._data.get(session_id)
            if s is None:
                return None
            s.updated_at = time()
            return s

    def set_last_user_message(self, session_id: str, msg: str) -> SessionState:
        with self._lock:
            s = self.get_or_create(session_id)
            s.last_user_message = msg
            s.updated_at = time()
            return s

    def update_answers(self, session_id: str, answers: Dict[str, Any]) -> SessionState:
        with self._lock:
            s = self.get_or_create(session_id)
            s.answers.update(answers or {})
            s.updated_at = time()
            return s

    def set_last_clarify(self, session_id: str, clarify_payload: Dict[str, Any]) -> SessionState:
        with self._lock:
            s = self.get_or_create(session_id)
            s.last_clarify = clarify_payload
            s.updated_at = time()
            return s

    # ===== pending clarify helpers =====
    def set_pending(self, session_id: str, clarify_type: str, fields: List[str]) -> SessionState:
        with self._lock:
            s = self.get_or_create(session_id)
            s.pending_clarify_type = clarify_type
            s.pending_fields = list(fields or [])
            s.updated_at = time()
            return s

    def clear_pending(self, session_id: str) -> SessionState:
        with self._lock:
            s = self.get_or_create(session_id)
            s.pending_clarify_type = None
            s.pending_fields = []
            s.updated_at = time()
            return s

    def is_pending(self, session_id: str) -> bool:
        s = self.get(session_id)
        return bool(s and s.pending_clarify_type and s.pending_fields)

    def cleanup_expired(self) -> int:
        now = time()
        with self._lock:
            expired = [sid for sid, s in self._data.items() if (now - s.updated_at) > self._ttl]
            for sid in expired:
                self._data.pop(sid, None)
            return len(expired)
