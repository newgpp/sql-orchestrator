from __future__ import annotations

import json
import os
import sys
from collections import defaultdict, deque
from typing import Dict, List, Set, Tuple

SCHEMA_CARDS_PATH = os.getenv("SCHEMA_CARDS_IN", os.getenv("SCHEMA_CARDS_OUT", "schema_cards.json"))
ROOT_FACT = os.getenv("ROOT_FACT_TABLE", "fact_order")


def load_cards(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_graph(relations: List[Dict]) -> Dict[str, Set[str]]:
    """
    构建无向图（join 可双向走）
    table -> set(connected tables)
    """
    g: Dict[str, Set[str]] = defaultdict(set)
    for r in relations:
        a = r.get("from_table")
        b = r.get("to_table")
        if a and b:
            g[a].add(b)
            g[b].add(a)
    return g


def bfs_reachable(graph: Dict[str, Set[str]], start: str) -> Set[str]:
    visited: Set[str] = set()
    q = deque([start])
    visited.add(start)
    while q:
        cur = q.popleft()
        for nxt in graph.get(cur, []):
            if nxt not in visited:
                visited.add(nxt)
                q.append(nxt)
    return visited


def classify_tables(cards: Dict) -> Tuple[Set[str], Set[str]]:
    facts = set()
    dims = set()
    for t in cards.get("tables", []):
        table = t.get("table")
        for c in t.get("columns", []):
            role = (c.get("tags") or {}).get("role")
            if role == "fact":
                facts.add(table)
            elif role == "dimension":
                dims.add(table)
    return facts, dims

def run(path: str, root_fact: str) -> dict:
    """
    给 tests 调用：不 sys.exit，返回结构化结果
    """
    cards = load_cards(path)
    relations = cards.get("relations", [])

    graph = build_graph(relations)
    reachable = bfs_reachable(graph, root_fact)

    facts, dims = classify_tables(cards)

    all_tables = {t.get("table") for t in cards.get("tables", []) if t.get("table")}
    unreachable_dims = sorted(dims - reachable)
    unreachable_tables = sorted(all_tables - reachable)

    return {
        "root_fact": root_fact,
        "tables_total": len(all_tables),
        "relations_total": len(relations),
        "reachable_tables": sorted(reachable),
        "unreachable_dims": unreachable_dims,
        "unreachable_tables": unreachable_tables,
        "dims_total": len(dims),
        "facts_total": len(facts),
    }



def main():
    if not os.path.exists(SCHEMA_CARDS_PATH):
        print(f"[error] schema_cards not found: {SCHEMA_CARDS_PATH}")
        sys.exit(2)

    result = run(SCHEMA_CARDS_PATH, ROOT_FACT)

    print(f"[ok] join-path validation from root: {result['root_fact']}")
    print(f"[ok] reachable tables: {len(result['reachable_tables'])}")
    if result["unreachable_dims"]:
        print("[warn] unreachable dimension tables:")
        for t in result["unreachable_dims"]:
            print(f"  - {t}")
        print("[result] ❌ some dimensions are not reachable from root fact")
        sys.exit(1)

    print("[result] ✅ all dimension tables are reachable from root fact")
    sys.exit(0)




if __name__ == "__main__":
    main()
