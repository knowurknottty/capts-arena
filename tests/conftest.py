from __future__ import annotations

import os
from pathlib import Path

# Add src to path so imports work
_src = Path(__file__).parent.parent / "src"
os.environ.setdefault("PYTHONPATH", str(_src))