import sys
from pathlib import Path

# === 关键：把项目根目录加入 sys.path ===
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.export_schema_cards import export_schema_cards, OUT_PATH


def test_export_schema_cards():
    cards = export_schema_cards()
    assert len(cards["tables"]) > 0
    assert Path(OUT_PATH).exists()
    print(
        f"[test] ok: tables={len(cards['tables'])}, "
        f"relations={len(cards['relations'])}, out={OUT_PATH}"
    )
