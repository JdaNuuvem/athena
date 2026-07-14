import os, base64

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

batch_num = 0
batch = []
total_chars = 0

for path in files:
    full = os.path.join(BASE, path)
    with open(full, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    line = f'w("{path}",__b64.decode("{b64}"))'
    batch.append(line)
    total_chars += len(b64)
    
    if total_chars > 15000 or len(batch) >= 3:
        batch_num += 1
        deploy_script = f'import os,base64 as __b64\nW="{W}"\ndef w(p,c):\n    fp=os.path.join(W,p);os.makedirs(os.path.dirname(fp),exist_ok=True);open(fp,"wb").write(c);print("OK",p)\n'
        deploy_script += "\n".join(batch)
        deploy_script += f'\nprint("BATCH{batch_num} DONE")'
        b64script = base64.b64encode(deploy_script.encode()).decode()
        out = os.path.join(BASE, f"_bb{batch_num}.txt")
        with open(out, "w") as f:
            f.write(b64script)
        print(f"Batch {batch_num}: {len(batch)} files, total_b64 {total_chars}, b64script {len(b64script)} -> {out}")
        batch = []
        total_chars = 0

if batch:
    batch_num += 1
    deploy_script = f'import os,base64 as __b64\nW="{W}"\ndef w(p,c):\n    fp=os.path.join(W,p);os.makedirs(os.path.dirname(fp),exist_ok=True);open(fp,"wb").write(c);print("OK",p)\n'
    deploy_script += "\n".join(batch)
    deploy_script += f'\nprint("BATCH{batch_num} DONE")'
    b64script = base64.b64encode(deploy_script.encode()).decode()
    out = os.path.join(BASE, f"_bb{batch_num}.txt")
    with open(out, "w") as f:
        f.write(b64script)
    print(f"Batch {batch_num}: {len(batch)} files, total_b64 {total_chars}, b64script {len(b64script)} -> {out}")
