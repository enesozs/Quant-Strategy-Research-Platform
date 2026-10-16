"""FastAPI backend for the strategy backtester (see api/CONTRACT.md).

The core research modules are flat modules at the repository root, so the
root is put on sys.path here. That keeps ``fastapi dev api/main.py``,
``uvicorn api.main:app`` and pytest working from any working directory.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
