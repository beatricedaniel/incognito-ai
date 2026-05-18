"""PyInstaller runtime hook: point HuggingFace at the bundled model cache."""

from __future__ import annotations

import os
import sys

if getattr(sys, "frozen", False):
    os.environ["HF_HOME"] = os.path.join(sys._MEIPASS, "hf-cache")  # type: ignore[attr-defined]
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
