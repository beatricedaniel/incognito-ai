"""PyInstaller runtime hook: redirect HuggingFace cache outside the frozen bundle."""

from __future__ import annotations

import os
import sys

if getattr(sys, "frozen", False):
    _cache = os.path.join(os.path.expanduser("~"), ".cache", "incognito", "huggingface")
    os.makedirs(_cache, exist_ok=True)
    os.environ.setdefault("HF_HOME", _cache)
    os.environ.setdefault("TRANSFORMERS_CACHE", os.path.join(_cache, "hub"))
