# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Incognito — onedir macOS arm64 bundle."""
from __future__ import annotations

from PyInstaller.utils.hooks import collect_dynamic_libs

pymupdf_binaries = collect_dynamic_libs("pymupdf")

a = Analysis(
    ["../src/incognito/main.py"],
    pathex=["../src"],
    binaries=pymupdf_binaries,
    datas=[
        ("../src/incognito/static", "incognito/static"),
        ("hf-cache", "hf-cache"),
    ],
    hiddenimports=[
        # --- uvicorn submodules (string-based imports) ---
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        # --- web framework ---
        "multipart",
        "multipart.multipart",
        "fastapi",
        # --- incognito package (uvicorn factory string import) ---
        "incognito",
        "incognito.app",
        "incognito.models",
        "incognito.api",
        "incognito.api.routes",
        "incognito.api.events",
        "incognito.core",
        "incognito.core.config",
        "incognito.core.exceptions",
        "incognito.core.sessions",
        "incognito.core.tempfiles",
        "incognito.gliner",
        "incognito.gliner.loader",
        "incognito.ollama",
        "incognito.ollama.manager",
        "incognito.pipeline",
        "incognito.pipeline.detector",
        "incognito.pipeline.detect_ner",
        "incognito.pipeline.detect_regex",
        "incognito.pipeline.extractor",
        "incognito.pipeline.validator",
        "incognito.pipeline.redactor",
        "incognito.pipeline.keyfile",
        "incognito.pipeline.recovery",
        # --- gliner / torch / transformers ---
        "gliner",
        "torch",
        "transformers",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["rthook_hf.py"],
    excludes=[
        "IPython",
        "jupyter",
        "notebook",
        "tkinter",
        "matplotlib",
        "scipy",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Incognito",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Incognito",
)

app = BUNDLE(
    coll,
    name="Incognito.app",
    icon=None,
    bundle_identifier="ai.incognito.app",
    info_plist={
        "CFBundleExecutable": "Incognito",
        "CFBundleName": "Incognito",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
    },
)
