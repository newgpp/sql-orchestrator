from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sql_orchestrator.api.chat import router as chat_router
from sql_orchestrator.services.session import InMemorySessionStore
from sql_orchestrator.config.settings import settings

app = FastAPI(
    title="sql-orchestrator",
    description="Natural language to SQL orchestration service",
    version="0.1.0",
)

# ===== CORS (for local dev) =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 开关控制：是否启用 session 记忆
if settings.session_memory_enabled:
    app.state.session_store = InMemorySessionStore(ttl_seconds=3600)
else:
    app.state.session_store = None

app.include_router(chat_router, prefix="/api")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "session_memory_enabled": settings.session_memory_enabled,
    }
