import os
import sys
from pathlib import Path

# 让 tests 能 import tools（仅测试层）
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.validate_join_paths import run, SCHEMA_CARDS_PATH, ROOT_FACT


def test_join_paths_reachable_from_root_fact():
    assert os.path.exists(SCHEMA_CARDS_PATH), f"schema_cards not found: {SCHEMA_CARDS_PATH}"

    # 允许在 CI 或本地用 env 覆盖 root
    root_fact = os.getenv("ROOT_FACT_TABLE", ROOT_FACT)

    result = run(SCHEMA_CARDS_PATH, root_fact)

    # 输出调试信息（pytest -s 可见）
    print(
        f"[test] root={result['root_fact']} "
        f"tables_total={result['tables_total']} "
        f"relations_total={result['relations_total']} "
        f"dims_total={result['dims_total']} "
        f"unreachable_dims={len(result['unreachable_dims'])}"
    )
    if result["unreachable_dims"]:
        print("[test] unreachable dims:")
        for t in result["unreachable_dims"]:
            print(" -", t)

    assert len(result["unreachable_dims"]) == 0, "some dimension tables are not reachable from root fact table"
