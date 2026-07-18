"""Generate OpenAPI JSON from the FastAPI app (no server needed).

Usage:
    python backend/scripts/generate_openapi.py

Output:
    backend/openapi.json — the OpenAPI 3.x spec for this application.
"""
import json
from pathlib import Path
import sys

_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

try:
    from app.main import app  # noqa: E402
except ImportError as exc:
    sys.exit(
        f"无法导入 FastAPI app。请确保已安装后端依赖：\n"
        f"  pip install -r {_BACKEND_DIR / 'requirements.txt'}\n"
        f"原始错误: {exc}"
    )

_OUTPUT = _BACKEND_DIR / "openapi.json"
spec = app.openapi()
spec["info"]["title"] = "After-Sales Work Order Review API"
spec["info"]["version"] = "1.0.0"

_OUTPUT.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"OpenAPI spec written to {_OUTPUT}")
