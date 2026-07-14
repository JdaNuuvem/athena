import os, base64

BASE = r"D:\JORGE CHARME E LEON\SISTEMAS\N8N AUTOMACOES\hermes_agents"
W = "/home/hermes/.hermes/workspace/hermes_agents"

all_files = [
    "core/__init__.py",
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
    "__init__.py",
    "profiles/profiles.yaml",
    "sql/schema.sql",
]

def make_batch(files, batch_id):
    lines = [
        "import os, base64 as __b64",
        f'W="{W}"',
        "def w(p,c):fp=os.path.join(W,p);os.makedirs(os.path.dirname(fp),exist_ok=True);open(fp,'wb').write(c);print('OK',p)"
    ]
    for relpath in files:
        full = os.path.join(BASE, relpath)
        with open(full, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode()
        lines.append(f'w("{relpath}",__b64.b64decode("{b64}"))')
    lines.append(f'print("BATCH{batch_id} DONE")')
    script = "\n".join(lines)
    b64script = base64.b64encode(script.encode()).decode()
    out = os.path.join(BASE, f"_b{batch_id}.txt")
    with open(out, "w") as f:
        f.write(b64script)
    print(f"Batch {batch_id}: {len(files)} files, script {len(script)} chars, b64 {len(b64script)} chars -> {out}")

# Split into 3 batches
mid = len(all_files) // 3
make_batch(all_files[:5], 1)
make_batch(all_files[5:10], 2)
make_batch(all_files[10:], 3)
