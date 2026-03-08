from __future__ import annotations

import sys
from pathlib import Path

# Ensure `import sb` works when running `pytest StatiBaker/tests` from repo root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
