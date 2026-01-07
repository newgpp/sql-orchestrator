import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.validate_schema_cards import run_validate, SCHEMA_CARDS_PATH


# 注释 ref 写错、表名/字段名拼错，立即爆出来
# join 写成 n:1 或 N-1 这种不规范，直接报错
# role 缺失给 warning（不影响导出，但提醒你补）
def test_validate_schema_cards():
    assert os.path.exists(SCHEMA_CARDS_PATH), f"schema_cards not found: {SCHEMA_CARDS_PATH}"
    errs = run_validate(SCHEMA_CARDS_PATH)
    hard = [e for e in errs if not e.code.startswith("WARN_")]
    # 先严格：不允许硬错误
    assert len(hard) == 0, "schema_cards validation has errors"
