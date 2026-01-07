from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union, Annotated

from pydantic import BaseModel, Field


# =========================
# Request
# =========================

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    answers: Optional[Dict[str, Any]] = None


# =========================
# Clarify
# =========================

ClarifyUI = Literal[
    "single_select",
    "multi_select",
    "text",
    "number",
    "date",
    "date_range",
]

ClarifyType = Literal[
    "TIME_RANGE_MISSING",
    "TIME_FIELD_AMBIGUOUS",
    "METRIC_DEFINITION_AMBIGUOUS",
    "ENTITY_MAPPING_AMBIGUOUS",
    "FILTER_VALUE_UNKNOWN",
    "JOIN_PATH_AMBIGUOUS",
    "GROUPING_LEVEL_AMBIGUOUS",
    "LIMIT_OR_TOPN_AMBIGUOUS",
]


class ClarifyFieldOption(BaseModel):
    value: Any
    label: str


class ClarifyField(BaseModel):
    key: str
    ui: ClarifyUI
    options: Optional[List[ClarifyFieldOption]] = None
    default: Optional[Any] = None
    min: Optional[float] = None
    max: Optional[float] = None
    hint: Optional[str] = None


class ClarifyResponse(BaseModel):
    type: Literal["clarify"] = "clarify"
    clarify_type: ClarifyType
    question: str
    fields: List[ClarifyField]
    session_id: str
    context_hint: Optional[str] = None


# =========================
# SQL
# =========================

SqlDialect = Literal["mysql", "postgres", "sqlite", "unknown"]

LogicalType = Literal[
    "string",
    "number",
    "boolean",
    "date",
    "datetime",
    "timestamp",
    "enum",
    "json",
]


class DataType(BaseModel):
    db_type: str
    logical_type: LogicalType
    timezone: Optional[str] = None
    unit: Optional[str] = None
    format: Optional[str] = None


class ExplainTable(BaseModel):
    name: str
    alias: Optional[str] = None
    role: Optional[Literal["fact", "dimension", "bridge", "unknown"]] = None
    description: Optional[str] = None


class ExplainJoinSide(BaseModel):
    table: str
    alias: Optional[str] = None
    column: str


class ExplainJoin(BaseModel):
    type: Literal["INNER", "LEFT", "RIGHT", "FULL"]
    left: ExplainJoinSide
    right: ExplainJoinSide
    cardinality: Optional[Literal["1:1", "1:N", "N:1", "N:N"]] = None
    reason: Optional[str] = None
    source: Optional[Literal["fk", "relation_card", "inferred"]] = None


class ExplainSelectItem(BaseModel):
    expr: str
    alias: Optional[str] = None
    semantic_type: Optional[Literal["dimension", "metric", "unknown"]] = None
    data_type: Optional[DataType] = None
    definition: Optional[str] = None


class ExplainFilterValue(BaseModel):
    # 对齐前端：value.type 允许 string/number/date/date_range/enum/json/raw
    type: Literal["string", "number", "date", "date_range", "enum", "json", "raw"]
    raw: Optional[str] = None

    # 允许扩展字段，例如 date_range 的 start/end 等
    # Pydantic v2: extra 默认禁止；这里显式允许扩展键更灵活
    model_config = {"extra": "allow"}


class ExplainFilterField(BaseModel):
    table: str
    alias: Optional[str] = None
    column: str


class ExplainFilter(BaseModel):
    expr: str
    field: Optional[ExplainFilterField] = None
    op: Optional[str] = None
    value: Optional[ExplainFilterValue] = None
    source: Optional[Literal["user", "clarified", "default", "inferred"]] = None


class ExplainGroupBy(BaseModel):
    table: str
    alias: Optional[str] = None
    column: str


class ExplainOrderBy(BaseModel):
    expr: str
    direction: Literal["ASC", "DESC"]


class ExplainLimit(BaseModel):
    value: int
    source: Optional[Literal["user", "clarified", "default", "inferred"]] = None


class Explanation(BaseModel):
    summary: Optional[str] = None
    tables: Optional[List[ExplainTable]] = None
    joins: Optional[List[ExplainJoin]] = None
    select: Optional[List[ExplainSelectItem]] = None
    filters: Optional[List[ExplainFilter]] = None
    group_by: Optional[List[ExplainGroupBy]] = None
    order_by: Optional[List[ExplainOrderBy]] = None
    limit: Optional[ExplainLimit] = None


class ValidationWarning(BaseModel):
    code: str
    message: str


class ValidationResult(BaseModel):
    status: Literal["pass", "warn", "fail"]
    warnings: Optional[List[ValidationWarning]] = None


class SqlResponse(BaseModel):
    type: Literal["sql"] = "sql"
    sql: str
    dialect: SqlDialect
    explanation: Optional[Explanation] = None
    validation: Optional[ValidationResult] = None
    session_id: str


# =========================
# Blocked
# =========================

class BlockedResponse(BaseModel):
    type: Literal["blocked"] = "blocked"
    reason: str
    suggested_questions: Optional[List[str]] = None
    session_id: str


# =========================
# Union (discriminated)
# =========================

ChatResponse = Annotated[
    Union[ClarifyResponse, SqlResponse, BlockedResponse],
    Field(discriminator="type"),
]
