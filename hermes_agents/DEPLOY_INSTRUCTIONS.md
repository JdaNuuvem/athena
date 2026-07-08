# Hermes Agent Swarm — Fase 1
# ===========================================================================
# Para implantar, cole os comandos abaixo NO TERMINAL DO COOLIFY
# (http://177.7.45.242:8000/project/ms4tg7zfr6chjyg4nnku9u1o/environment/rx4y3uxy042an81bjjsi5sbr/service/w9hn3qezdgivens9g1o7r3of/terminal)
# 
# PASSO 1: Selecione o container "hermes-agent-w9hn3qezdgivens9g1o7r3of"
# PASSO 2: Cole o comando do PASSO 1 abaixo
# PASSO 3: Cole o comando do PASSO 2 abaixo
# PASSO 4: Cole o comando do PASSO 3 abaixo
# ===========================================================================

# PASSO 1: Criar estrutura de diretórios (já feito)
for d in core ag_09_memoria ag_01_cacador ag_02_lucratividade ag_03_marketplaces profiles sql; do mkdir -p /workspace/hermes_agents/$d; done

# PASSO 2: Baixar o deploy script do Gist (cole a URL raw do seu arquivo)
# Ou cole o conteúdo do deploy_to_hermes.py diretamente via:
python3 /workspace/hermes_agents/deploy_to_hermes.py

# PASSO 3: Verificar
find /workspace/hermes_agents -type f | sort

# PASSO 4: Testar
python3 -c "import sys; sys.path.insert(0,'/workspace'); from hermes_agents.ag_09_memoria import stats; print(stats())"
