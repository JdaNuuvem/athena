# Minimal deploy script that creates all agent directories and init files
import os, json

W = "/home/hermes/.hermes/workspace/hermes_agents"
dirs = ["core","ag_09_memoria","ag_01_cacador","ag_02_lucratividade","ag_03_marketplaces","ag_04_planejador","ag_05_industrial","ag_06_telegram","ag_07_laboratorio","ag_08_lojas","ag_10_diretor","profiles","sql"]
for d in dirs: os.makedirs(W+"/"+d, exist_ok=True)

# Create __init__.py stubs
for d in dirs:
    with open(W+"/"+d+"/__init__.py","w") as f:
        f.write(f"# {d} agent module\n")

# Core __init__.py
with open(W+"/__init__.py","w") as f:
    f.write("""#!/usr/bin/env python3
\"\"\"Hermes Agent Swarm - 10 agents\"\"\"
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
print("Hermes Agent Swarm loaded. 10 agents ready.")
""")

print("Deployed:", sorted(os.listdir(W)))
for root, d, files in os.walk(W):
    for f in files:
        print(os.path.join(root, f))
