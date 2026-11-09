# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:/Industrial Box Plot Analyzer/app.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('samples', 'samples'), ('assets', '.')],
    hiddenimports=['pyodbc', 'openpyxl', 'reportlab', 'matplotlib.backends.backend_agg', 'scipy.stats', 'pandas'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['IPython', 'altair', 'boto3', 'botocore', 'celery', 'cv2', 'dash', 'dask', 'django', 'fastapi', 'flask', 'google', 'gradio', 'jupyter', 'keras', 'kivy', 'kivymd', 'mysql', 'nltk', 'notebook', 'onnxruntime', 'opentelemetry', 'playwright', 'plotly', 'psycopg', 'psycopg2', 'pydub', 'pymysql', 'ray', 'sklearn', 'spacy', 'tensorflow', 'tkinter', 'torch', 'torchvision', 'transformers', 'uvicorn'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='IndustrialSPCAnalyzer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['D:/Industrial Box Plot Analyzer/assets/app.ico'],
)
