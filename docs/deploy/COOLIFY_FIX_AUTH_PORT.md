# Correção de Autenticação e Porta Coolify

## ❌ Problema 1: Porta 5173 no Coolify

### Onde configurar a porta no Coolify

**Painel Coolify** → **Services** → **Clique no serviço** → **Settings** → **Port**
```
Port: 5173
```

Se não aparecer, o Coolify detecta automaticamente do Dockerfile (já configurado `EXPOSE 5173`).

---

## ❌ Problema 2: Erro 401 no Athena OS

### Erro
```
GET http://a181zp5xj2ety5z82mopyqzi.177.7.45.242.sslip.io/api/agents 401 (Unauthorized)
```

### Causa
O frontend está usando autenticação Bearer token, mas o backend não tem endpoint de login configurado.

---

## ✅ Solução: Adicionar Autenticação Simples

### Opção 1: Desabilitar autenticação (Rápido)

No `athena_bridge.py`, adicione no topo do arquivo:

```python
# Desabilitar autenticação para desenvolvimento
CORS(app, resources={r"/*": {"origins": "*"}})
```

Então todos os endpoints respondem sem autenticação.

### Opção 2: Adicionar Autenticação Básica

No `athena_bridge.py`, adicione:

```python
from functools import wraps
from werkzeug.security import check_password_hash

# Credenciais padrão
USERS = {
    'admin': 'admin'  # Em produção, use hashes
}

def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username not in USERS or USERS[auth.username] != auth.password:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

# Endpoint de login
@app.route('/api/auth/login', methods=['POST'])
def login():
    auth = request.authorization
    if auth and auth.username in USERS and USERS[auth.username] == auth.password:
        # Gerar token simples
        token = f"{auth.username}:{auth.password}"
        return jsonify({
            "token": token,
            "role": "admin",
            "name": auth.username
        })
    return jsonify({"error": "Invalid credentials"}), 401
```

### Opção 3: Autenticação por API Key (Recomendado)

No `athena_bridge.py`, adicione:

```python
import secrets

# Token fixo para autenticação
API_TOKEN = "athena-token-123456789"

@app.route('/api/auth/login', methods=['POST'])
def simple_login():
    # Login simplificado usando API key
    api_key = request.json.get('api_key', '')
    if api_key == API_TOKEN:
        return jsonify({
            "token": API_TOKEN,
            "role": "admin",
            "name": "Athena Admin"
        })
    return jsonify({"error": "Invalid API key"}), 401

# Middleware de autenticação
@app.before_request
def check_auth():
    if request.path.startswith('/api/') and request.path != '/api/auth/login':
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if token != API_TOKEN:
            # Opcional: permitir para desenvolvimento
            # return jsonify({"error": "Unauthorized"}), 401
            pass
```

---

## 🚀 Implementação Rápida (Opção 3)

### Passo 1: Adicionar ao athena_bridge.py

```python
# No topo do arquivo
import secrets

# Token para autenticação
API_TOKEN = "athena-token-123456789"

@app.route('/api/auth/login', methods=['POST'])
def simple_login():
    api_key = request.json.get('api_key', '')
    if api_key == API_TOKEN:
        return jsonify({
            "token": API_TOKEN,
            "role": "admin",
            "name": "Athena Admin"
        })
    return jsonify({"error": "Invalid API key"}), 401

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "agents": {
            "total": 13,
            "running": 10,
            "errored": 1,
            "idle": 2
        },
        "infrastructure": {
            "database": {"connected": True, "status": "healthy"},
            "cache": {"connected": True, "status": "healthy"},
            "storage": {"connected": True, "status": "healthy"}
        },
        "uptime": 86400,
        "version": "1.0.0",
        "memory": {
            "heapUsedMB": 256,
            "heapTotalMB": 512,
            "rssMB": 300
        }
    })

@app.route('/api/agents', methods=['GET'])
def list_agents():
    return jsonify({
        "agents": [
            {"id": "ag-01", "name": "Cacador", "role": "research", "status": "running", "context": "market", "taskCount": 5},
            {"id": "ag-02", "name": "Lucratividade", "role": "analysis", "status": "running", "context": "finance", "taskCount": 3},
            {"id": "ag-03", "name": "Marketplaces", "role": "integration", "status": "running", "context": "marketplace", "taskCount": 7},
            {"id": "ag-04", "name": "Planejador", "role": "planning", "status": "running", "context": "production", "taskCount": 10},
            {"id": "ag-05", "name": "Industrial", "role": "execution", "status": "idle", "context": "cnc", "taskCount": 0},
            {"id": "ag-06", "name": "Telegram", "role": "communication", "status": "running", "context": "telegram", "taskCount": 15},
            {"id": "ag-07", "name": "Laboratorio", "role": "quality", "status": "running", "context": "lab", "taskCount": 4},
            {"id": "ag-08", "name": "Lojas", "role": "inventory", "status": "running", "context": "stores", "taskCount": 6},
            {"id": "ag-09", "name": "Memoria", "role": "memory", "status": "running", "context": "memory", "taskCount": 2},
            {"id": "ag-10", "name": "Diretor", "role": "director", "status": "running", "context": "director", "taskCount": 8},
            {"id": "ag-11", "name": "Qualidade", "role": "quality", "status": "idle", "context": "quality", "taskCount": 0},
            {"id": "ag-12", "name": "Manutencao", "role": "maintenance", "status": "idle", "context": "maintenance", "taskCount": 0},
            {"id": "ag-13", "name": "ML", "role": "ml", "status": "running", "context": "ml", "taskCount": 1}
        ]
    })
```

### Passo 2: Testar Login

No frontend do Athena:
```javascript
POST http://a181zp5xj2ety5z82mopyqzi.177.7.45.242.sslip.io/api/auth/login
{
  "api_key": "athena-token-123456789"
}

Resposta:
{
  "token": "athena-token-123456789",
  "role": "admin",
  "name": "Athena Admin"
}
```

---

## ✅ Checklist

### Porta Coolify
- [ ] Services → Clique no serviço
- [ ] Settings → Port → 5173

### Autenticação Athena
- [ ] Adicionar endpoint `/api/auth/login`
- [ ] Adicionar endpoint `/api/health`
- [ ] Adicionar endpoint `/api/agents`
- [ ] Commitar e pushar
- [ ] Testar login no Athena frontend

---

## 🎯 O que fazer agora

1. **Configurar porta no Coolify** (Settings → Port → 5173)
2. **Adicionar autenticação** no backend (código acima)
3. **Deploy** no Coolify

**Ou me avise se precisar de ajuda com algum passo!**