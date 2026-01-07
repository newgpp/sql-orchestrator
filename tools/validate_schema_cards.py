from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

# 默认读取导出的 schema_cards.json
SCHEMA_CARDS_PATH = os.getenv("SCHEMA_CARDS_IN", os.getenv("SCHEMA_CARDS_OUT", "schema_cards.json"))

# 允许的 join / role 值（你后面可以扩展）
ALLOWED_JOIN = {"N:1", "1:N", "1:1", "N:N"}
ALLOWED_ROLE = {"fact", "dimension", "bridge"}

JOIN_RE = re.compile(r"^\s*(N:1|1:N|1:1|N:N)\s*$")


@dataclass
class ValidationError:
    code: str
    message: str
    where: str
    detail: Dict[str, Any]


def load_cards(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def index_schema(cards: Dict[str, Any]) -> Tuple[Set[str], Set[Tuple[str, str]]]:
    """
    返回：
      tables: {table}
      columns: {(table, column)}
    """
    tables: Set[str] = set()
    columns: Set[Tuple[str, str]] = set()

    for t in cards.get("tables", []):
        table = t.get("table")
        if not table:
            continue
        tables.add(table)
        for c in t.get("columns", []):
            col = c.get("name")
            if col:
                columns.add((table, col))

    return tables, columns


def validate_refs(cards: Dict[str, Any], tables: Set[str], columns: Set[Tuple[str, str]]) -> List[ValidationError]:
    errors: List[ValidationError] = []

    # 1) 基于 relations 校验
    for r in cards.get("relations", []):
        ft, fc = r.get("from_table"), r.get("from_column")
        tt, tc = r.get("to_table"), r.get("to_column")
        where = f"relation {ft}.{fc} -> {tt}.{tc}"

        if ft not in tables:
            errors.append(ValidationError(
                code="REF_FROM_TABLE_NOT_FOUND",
                message="from_table 不存在于 schema_cards.tables",
                where=where,
                detail=r
            ))
        if (ft, fc) not in columns:
            errors.append(ValidationError(
                code="REF_FROM_COLUMN_NOT_FOUND",
                message="from_column 不存在于 schema_cards.tables.columns",
                where=where,
                detail=r
            ))
        if tt not in tables:
            errors.append(ValidationError(
                code="REF_TO_TABLE_NOT_FOUND",
                message="to_table 不存在于 schema_cards.tables",
                where=where,
                detail=r
            ))
        if (tt, tc) not in columns:
            errors.append(ValidationError(
                code="REF_TO_COLUMN_NOT_FOUND",
                message="to_column 不存在于 schema_cards.tables.columns",
                where=where,
                detail=r
            ))

        # join 规范
        j = r.get("join")
        if j and not JOIN_RE.match(j):
            errors.append(ValidationError(
                code="JOIN_INVALID",
                message=f"join 值不合法（允许：{sorted(ALLOWED_JOIN)}）",
                where=where,
                detail={"join": j, **r}
            ))

        # role 规范（relation 里的 role 目前可选，但如果填了就校验）
        role = r.get("role")
        if role and role not in ALLOWED_ROLE:
            errors.append(ValidationError(
                code="ROLE_INVALID",
                message=f"role 值不合法（允许：{sorted(ALLOWED_ROLE)}）",
                where=where,
                detail={"role": role, **r}
            ))

    return errors


def validate_column_tags(cards: Dict[str, Any]) -> List[ValidationError]:
    """
    校验列级 tags：
    - 有 ref 就必须有 join
    - 有 ref 就建议有 role（且合法）
    - metric/semantic/time 等不强制，但做基本类型校验（字符串即可）
    """
    errors: List[ValidationError] = []

    for t in cards.get("tables", []):
        table = t.get("table")
        for c in t.get("columns", []):
            col = c.get("name")
            tags: Dict[str, Any] = c.get("tags", {}) or {}
            where = f"{table}.{col}"

            ref = tags.get("ref")
            join = tags.get("join")
            role = tags.get("role")

            if ref:
                if not join:
                    errors.append(ValidationError(
                        code="REF_MISSING_JOIN",
                        message="列 tags 有 ref 但没有 join（建议写 join=N:1 等）",
                        where=where,
                        detail={"tags": tags}
                    ))
                elif not JOIN_RE.match(str(join)):
                    errors.append(ValidationError(
                        code="JOIN_INVALID",
                        message=f"列 tags 的 join 值不合法（允许：{sorted(ALLOWED_JOIN)}）",
                        where=where,
                        detail={"tags": tags}
                    ))

                if role and role not in ALLOWED_ROLE:
                    errors.append(ValidationError(
                        code="ROLE_INVALID",
                        message=f"列 tags 的 role 值不合法（允许：{sorted(ALLOWED_ROLE)}）",
                        where=where,
                        detail={"tags": tags}
                    ))

            # 如果有 time/metric/semantic，确保是字符串
            for k in ("time", "metric", "semantic"):
                if k in tags and not isinstance(tags[k], str):
                    errors.append(ValidationError(
                        code="TAG_TYPE_INVALID",
                        message=f"tags.{k} 必须是字符串",
                        where=where,
                        detail={"tags": tags}
                    ))

    return errors


def validate_table_role_hint(cards: Dict[str, Any]) -> List[ValidationError]:
    """
    非强制，但给提示：建议在表 comment 或关键列上能推断 role
    - 如果表里任何列 tag.role=... 都没有，给 warning（作为 error 输出但 code=WARN）
    """
    errors: List[ValidationError] = []
    for t in cards.get("tables", []):
        table = t.get("table")
        cols = t.get("columns", [])
        any_role = any(((c.get("tags") or {}).get("role") in ALLOWED_ROLE) for c in cols)
        if not any_role:
            errors.append(ValidationError(
                code="WARN_TABLE_ROLE_MISSING",
                message="该表未发现任何列 tags.role（建议在主键/关键列标注 role=fact|dimension|bridge）",
                where=str(table),
                detail={}
            ))
    return errors


def run_validate(path: str) -> List[ValidationError]:
    cards = load_cards(path)
    tables, columns = index_schema(cards)

    errors: List[ValidationError] = []
    errors.extend(validate_refs(cards, tables, columns))
    errors.extend(validate_column_tags(cards))
    errors.extend(validate_table_role_hint(cards))

    return errors


def main():
    if not os.path.exists(SCHEMA_CARDS_PATH):
        print(f"[error] schema_cards not found: {SCHEMA_CARDS_PATH}")
        print("hint: run export first, or set env SCHEMA_CARDS_IN")
        sys.exit(2)

    errs = run_validate(SCHEMA_CARDS_PATH)

    hard = [e for e in errs if not e.code.startswith("WARN_")]
    warns = [e for e in errs if e.code.startswith("WARN_")]

    print(f"[ok] validate schema_cards: {SCHEMA_CARDS_PATH}")
    print(f"[ok] errors={len(hard)} warnings={len(warns)}")

    # 打印细节（最多 50 条，避免刷屏）
    for e in errs[:50]:
        print(f"- [{e.code}] {e.where}: {e.message}")
        # 需要时打开：print(e.detail)

    if hard:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
