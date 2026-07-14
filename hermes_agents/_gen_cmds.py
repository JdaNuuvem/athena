import os, base64, sys

BASE = r"D:\JORGE CHARME E LEON\SISTEMAS\N8N AUTOMACOES\hermes_agents"
W = "/home/hermes/.hermes/workspace/hermes_agents"

files = [
    "core/__init__.py",
    "__init__.py",
    "ag_01_cacador/__init__.py",
    "ag_02_lucratividade/__init__.py",
    "ag_03_marketplaces/__init__.py",
    "ag_04_planejador/__init__.py",
    "ag_05_industrial/__init__.py",
    "ag_06_telegram/__init__.py",
    "ag_07_laboratorio/__init__.py",
    "ag_08_lojas/__init__.py",
    "ag_09_memoria/__init__.py",
    "ag_10_diretor/__init__.py",
    "profiles/profiles.yaml",
    "sql/schema.sql",
]

for path in files:
    full = os.path.join(BASE, path)
    with open(full, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    # Use single-quoted python3 -c, escape single quotes in b64
    # b64 contains no single quotes, so it's safe
    cmd = f'python3 -c "import base64;open(\'{W}/{path}\',\'wb\').write(base64.b64decode(\'{b64}\'));print(\'OK {path}\')"'
    print(f"=== {path} ({len(data)} bytes, b64:{len(b64)} chars) ===")
    print(cmd)
    print()
