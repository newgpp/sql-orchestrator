from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import pymysql

# =========================
# ENV CONFIG
# =========================
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "123456")
DB_NAME = os.getenv("DB_NAME", "demo_bi")

# profiling 开关：抽样例值/分布（对 ~1000 单非常轻量）
PROFILE = os.getenv("SCHEMA_PROFILE", "1") == "1"
MAX_EXAMPLES = int(os.getenv("SCHEMA_MAX_EXAMPLES", "8"))

# 输出文件
OUT_PATH = os.getenv("SCHEMA_CARDS_OUT", "schema_cards.json")


# =========================
# COMMENT PARSER
# =========================
TAG_RE = re.compile(r"(?P<key>[a-zA-Z_]+)\s*=\s*(?P<val>[^|]+)")

def parse_comment(raw: Optional[str]) -> Tuple[str, Dict[str, str], str]:
    """
    输入：'客户ID | ref=dim_customer.customer_id | join=N:1 | role=dimension'
    输出：(desc, tags, raw)
    """
    raw = (raw or "").strip()
    if not raw:
        return "", {}, ""

    parts = [p.strip() for p in raw.split("|")]
    desc = parts[0].strip() if parts else raw
    tags: Dict[str, str] = {}

    for p in parts[1:]:
        m = TAG_RE.search(p)
        if m:
            tags[m.group("key").strip()] = m.group("val").strip()

    return desc, tags, raw

def parse_ref(ref: str) -> Optional[Tuple[str, str]]:
    if not ref or "." not in ref:
        return None
    t, c = ref.split(".", 1)
    t, c = t.strip(), c.strip()
    return (t, c) if t and c else None


# =========================
# HELPERS
# =========================
NUMERIC_TYPES = {"int", "bigint", "smallint", "mediumint", "tinyint", "decimal", "numeric", "float", "double"}
TIME_TYPES = {"date", "datetime", "timestamp", "time", "year"}

def q_ident(name: str) -> str:
    return f"`{name.replace('`', '')}`"

def connect():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

def fetch_tables(cur) -> List[Dict[str, Any]]:
    cur.execute(
        """
        SELECT table_name, table_comment
        FROM information_schema.tables
        WHERE table_schema=%s AND table_type='BASE TABLE'
        ORDER BY table_name
        """,
        (DB_NAME,),
    )
    return list(cur.fetchall())

def fetch_columns(cur, table: str) -> List[Dict[str, Any]]:
    cur.execute(
        """
        SELECT
          column_name, ordinal_position,
          data_type, column_type,
          is_nullable, column_default,
          column_comment
        FROM information_schema.columns
        WHERE table_schema=%s AND table_name=%s
        ORDER BY ordinal_position
        """,
        (DB_NAME, table),
    )
    return list(cur.fetchall())

def fetch_indexes(cur, table: str) -> List[Dict[str, Any]]:
    cur.execute(
        """
        SELECT
          index_name, non_unique, seq_in_index, column_name, index_type
        FROM information_schema.statistics
        WHERE table_schema=%s AND table_name=%s
        ORDER BY index_name, seq_in_index
        """,
        (DB_NAME, table),
    )
    rows = list(cur.fetchall())

    by: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        name = r["index_name"]
        if name not in by:
            by[name] = {
                "name": name,
                "unique": (r["non_unique"] == 0),
                "type": r["index_type"],
                "columns": [],
            }
        by[name]["columns"].append(r["column_name"])

    res = list(by.values())
    res.sort(key=lambda x: (0 if x["name"] == "PRIMARY" else 1, x["name"]))
    return res

def table_row_count(cur, table: str) -> int:
    cur.execute(f"SELECT COUNT(*) AS c FROM {q_ident(table)}")
    return int(cur.fetchone()["c"])


def profile_column(cur, table: str, col: str, data_type: str, row_count: int) -> Dict[str, Any]:
    """
    轻量 profiling（适合 1k 级数据）
    """
    t = q_ident(table)
    c = q_ident(col)
    dt = (data_type or "").lower()

    cur.execute(
        f"""
        SELECT
          SUM(CASE WHEN {c} IS NULL THEN 1 ELSE 0 END) AS null_cnt,
          COUNT(DISTINCT {c}) AS distinct_cnt
        FROM {t}
        """
    )
    r = cur.fetchone()
    null_cnt = int(r["null_cnt"] or 0)
    distinct_cnt = int(r["distinct_cnt"] or 0)
    null_ratio = (null_cnt / row_count) if row_count > 0 else 0.0

    stats: Dict[str, Any] = {
        "row_count": row_count,
        "null_count": null_cnt,
        "null_ratio": round(null_ratio, 4),
        "distinct_count": distinct_cnt,
    }

    if dt in NUMERIC_TYPES:
        cur.execute(f"SELECT MIN({c}) mn, MAX({c}) mx, AVG({c}) av FROM {t} WHERE {c} IS NOT NULL")
        s = cur.fetchone()
        stats.update({
            "min": float(s["mn"]) if s["mn"] is not None else None,
            "max": float(s["mx"]) if s["mx"] is not None else None,
            "avg": float(s["av"]) if s["av"] is not None else None,
        })

    if dt in TIME_TYPES:
        cur.execute(f"SELECT MIN({c}) mn, MAX({c}) mx FROM {t} WHERE {c} IS NOT NULL")
        s = cur.fetchone()
        stats.update({
            "min": str(s["mn"]) if s["mn"] is not None else None,
            "max": str(s["mx"]) if s["mx"] is not None else None,
        })

    cur.execute(
        f"""
        SELECT {c} AS v, COUNT(*) AS cnt
        FROM {t}
        WHERE {c} IS NOT NULL
        GROUP BY {c}
        ORDER BY cnt DESC
        LIMIT {int(MAX_EXAMPLES)}
        """
    )
    top = [{"value": str(x["v"]), "count": int(x["cnt"])} for x in cur.fetchall()]

    return {"stats": stats, "examples": {"top_values": top}}


# =========================
# MAIN EXPORT
# =========================
def export_schema_cards() -> Dict[str, Any]:
    """
    单文件版本：
    - 全部配置来自 env
    - 导出 schema_cards.json
    - 返回 dict（方便测试断言）
    """
    conn = connect()
    try:
        with conn.cursor() as cur:
            tables = fetch_tables(cur)
            relations: List[Dict[str, Any]] = []
            table_cards: List[Dict[str, Any]] = []

            for t in tables:
                table = t["table_name"]
                t_desc, t_tags, t_raw = parse_comment(t.get("table_comment"))

                cols = fetch_columns(cur, table)
                idxs = fetch_indexes(cur, table)

                rc = table_row_count(cur, table) if PROFILE else None

                col_cards: List[Dict[str, Any]] = []
                for c in cols:
                    desc, tags, raw = parse_comment(c.get("column_comment"))
                    item: Dict[str, Any] = {
                        "name": c["column_name"],
                        "data_type": c["data_type"],
                        "column_type": c["column_type"],
                        "nullable": (c["is_nullable"] == "YES"),
                        "default": c["column_default"],
                        "description": desc,
                        "comment_raw": raw,
                        "tags": tags,
                    }

                    if "ref" in tags:
                        ref = parse_ref(tags["ref"])
                        if ref:
                            item["ref"] = {"table": ref[0], "column": ref[1]}
                            relations.append({
                                "from_table": table,
                                "from_column": c["column_name"],
                                "to_table": ref[0],
                                "to_column": ref[1],
                                "join": tags.get("join"),
                                "role": tags.get("role"),
                                "note": desc,
                                "source": "comment",
                            })

                    if PROFILE and rc is not None:
                        item.update(profile_column(cur, table, c["column_name"], c["data_type"], rc))

                    col_cards.append(item)

                table_cards.append({
                    "table": table,
                    "row_count": rc,
                    "description": t_desc,
                    "comment_raw": t_raw,
                    "tags": t_tags,
                    "columns": col_cards,
                    "indexes": idxs,
                })

            # 去重 relations
            seen = set()
            dedup: List[Dict[str, Any]] = []
            for r in relations:
                k = (r["from_table"], r["from_column"], r["to_table"], r["to_column"])
                if k in seen:
                    continue
                seen.add(k)
                dedup.append(r)

            out = {
                "version": "0.3",
                "db": {"engine": "mariadb", "schema": DB_NAME},
                "profiling": {"enabled": PROFILE, "max_examples": MAX_EXAMPLES},
                "tables": table_cards,
                "relations": dedup,
            }

            # write file
            os.makedirs(os.path.dirname(OUT_PATH) or ".", exist_ok=True)
            with open(OUT_PATH, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)

            return out
    finally:
        conn.close()


if __name__ == "__main__":
    cards = export_schema_cards()
    print(f"[ok] exported -> {OUT_PATH}")
    print(f"[ok] tables={len(cards['tables'])}, relations={len(cards['relations'])}, profile={PROFILE}")
