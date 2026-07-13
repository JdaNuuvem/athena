# Fase 0 + Fase 1 — Fundação de Acesso e Núcleo Multiloja Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir o bug de autorização (`/api/me` sempre devolve "Admin"), introduzir papéis reais (admin, financeiro, operador_loja) com menu filtrado por papel, e criar as abas **Lojas** e **Vendas** que hoje não existem no frontend apesar de parte dos dados já existir no backend.

**Architecture:** Backend Flask (blueprints em `hermes_agents/routes/`) ganha autenticação JWT por usuário e dois endpoints novos em `catalog.py` reaproveitando a tabela `vendas` e o endpoint `/api/lojas` já existentes. Frontend Next.js (`web/src/app/`) ganha um mecanismo de menu filtrado por papel em `layout.tsx` e duas páginas novas que seguem exatamente os padrões visuais já usados em `dashboard/page.tsx` e `produtos/page.tsx`.

**Tech Stack:** Flask + psycopg2 (backend), PyJWT (novo, já instalado no ambiente), Next.js/React/TypeScript + Tailwind (frontend). Sem framework de testes automatizados no frontend (pré-existente); backend usa scripts de teste com `assert` no padrão já usado em `hermes_agents/test_fase3.py`, aqui executados via `pytest`.

## Global Constraints

- Especificação de origem: `docs/superpowers/specs/2026-07-13-fase0-fase1-multiloja-design.md`.
- Exatamente 3 papéis nesta fase: `admin`, `financeiro`, `operador_loja` — não inventar papéis extras.
- Rotas de API pré-existentes (exceto `/api/me`) permanecem sem checagem de autorização — fora de escopo endurecê-las agora.
- Todo import cruzado entre módulos de `hermes_agents/routes/` usa import relativo (`from .auth import ...`), igual ao padrão já usado em `hermes_agents/routes/__init__.py`.
- Erros de API sempre devolvem JSON com chave `erro` (backend) — nunca 500 cru — igual ao padrão já usado em `hermes_agents/routes/catalog.py`.
- Erros de UI sempre aparecem em banner vermelho (`text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3`) — mesmo padrão de `web/src/app/dashboard/page.tsx`.
- Paleta e densidade seguem `web/PRODUCT.md`: dark mode operacional (`bg-neutral-900`/`border-neutral-800`), cor só carrega significado de estado, sem gradiente/glassmorphism, ícones geométricos (não emoji) na navegação lateral.
- Testes de backend que tocam o Postgres exigem o banco acessível — mesma pré-condição já assumida por `hermes_agents/test_fase2.py` e `test_fase3.py`. Rodar sempre a partir do diretório `hermes_agents/` (para que `from core import ...` resolva).
- Frontend não tem framework de teste configurado (decisão já validada no spec): o gate de verificação de cada tarefa de frontend é `npm run build` (dentro de `web/`) devolvendo exit code 0.
- Em produção (Coolify), definir a env `ATHENA_JWT_SECRET` — sem ela, cada worker gera um segredo aleatório próprio no boot e tokens emitidos por um worker não validam nos outros. Isso já é uma limitação pré-existente do `API_TOKEN` atual; o plano não resolve isso, só documenta.
- **Addendum de segurança (aprovado pelo usuário durante a execução):** hash de senha usa `werkzeug.security` (não SHA-256 puro), não há credencial `admin/admin` hardcoded (senha temporária aleatória é gerada no boot quando `ATHENA_USERS` não está configurada), e a comparação do `api_key` usa `hmac.compare_digest`. Isso substitui o comportamento do `auth.py` original nesses três pontos — todo o resto do arquivo permanece como descrito no Task 1.

---

### Task 1: Autenticação JWT por usuário e papéis no backend

**Files:**
- Modify: `hermes_agents/routes/auth.py`
- Modify: `hermes_agents/requirements.txt`
- Create: `hermes_agents/test_fase_multiloja.py`

**Interfaces:**
- Produces: `require_role(*roles: str)` — decorator Flask importável como `from .auth import require_role` a partir de módulos dentro de `hermes_agents/routes/`. Sem token válido → 401 `{"error": "Unauthorized"}`. Token válido mas papel fora de `roles` → 403 `{"error": "Forbidden"}`. `roles` vazio = qualquer usuário autenticado.
- Produces: `ROLE_PERMISSIONS: dict[str, list[str]]` com chaves `admin`, `financeiro`, `operador_loja`.
- Produces: `GET /api/me` devolvendo `{"name": str, "role": str, "permissoes": list[str]}` a partir do JWT real (não mais hardcoded).
- Produces: `hermes_agents/test_fase_multiloja.py` com `run_all_tests()` e bloco `if __name__ == "__main__":`, seguindo o padrão de `test_fase3.py`.

- [ ] **Step 1: Escrever o teste que falha**

Criar `hermes_agents/test_fase_multiloja.py`:

```python
#!/usr/bin/env python3
"""
Testes de integração para Fase 0 + Fase 1 - Fundação de Acesso e Núcleo Multiloja.
"""
import os
from werkzeug.security import generate_password_hash

TEST_PASSWORD = "senha-teste-123"
os.environ["ATHENA_USERS"] = f"admin:{generate_password_hash(TEST_PASSWORD)}:admin:Admin"

import sys
from core import log


def test_auth_jwt_login_and_me():
    """Testa que o login emite um JWT por usuário e /api/me devolve o papel real."""
    log("TEST", "Testando login JWT e /api/me...")
    from athena_bridge import app
    client = app.test_client()

    resp = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
    assert resp.status_code == 200, f"Login deve retornar 200: {resp.get_json()}"
    body = resp.get_json()
    assert body["role"] == "admin", f"Role deve ser admin: {body}"
    token = body["token"]
    log("TEST", f"✅ Login emitiu token para role={body['role']}")

    resp_me = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert resp_me.status_code == 200, f"/api/me deve retornar 200: {resp_me.get_json()}"
    me = resp_me.get_json()
    assert me["role"] == "admin", f"/api/me deve refletir role do token: {me}"
    assert "ver_lojas" in me["permissoes"], f"Admin deve ter ver_lojas: {me}"
    log("TEST", f"✅ /api/me devolveu permissoes: {me['permissoes']}")

    resp_no_token = client.get("/api/me")
    assert resp_no_token.status_code == 401, "Sem token deve retornar 401"
    log("TEST", "✅ /api/me sem token retorna 401")

    return True


def run_all_tests():
    """Executa todos os testes."""
    log("TEST", "=" * 50)
    log("TEST", "Iniciando testes Fase 0 + Fase 1")
    log("TEST", "=" * 50)

    tests = [
        ("Auth JWT + /api/me", test_auth_jwt_login_and_me),
    ]

    resultados = []
    for nome, test_func in tests:
        try:
            sucesso = test_func()
            resultados.append((nome, "PASSOU" if sucesso else "FALHOU"))
        except Exception as e:
            log("TEST", f"❌ {nome} falhou: {e}")
            resultados.append((nome, f"ERRO: {str(e)}"))

    log("TEST", "=" * 50)
    log("TEST", "Resultados:")
    for nome, resultado in resultados:
        log("TEST", f"  {nome}: {resultado}")
    log("TEST", "=" * 50)

    return all(r[1] == "PASSOU" for r in resultados)


if __name__ == "__main__":
    sucesso = run_all_tests()
    sys.exit(0 if sucesso else 1)
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `cd hermes_agents && python -m pytest test_fase_multiloja.py -v`
Expected: FAIL — `/api/me` ainda devolve sempre `"role": "admin"` mas `body["token"]` do login atual é o `API_TOKEN` estático (não um JWT), então o assert de `permissoes` pode até passar por acaso hoje, mas o teste de fluxo real (login com token único por usuário) não está implementado ainda. Confirme que o teste roda (sem erro de import) e falhe ao menos em algum assert antes de prosseguir — se todos passarem já sem a mudança, ajuste os asserts para cobrir o comportamento real esperado antes de implementar.

- [ ] **Step 3: Implementar `hermes_agents/routes/auth.py`**

Substituir o conteúdo inteiro do arquivo por:

**Nota de segurança (adicionada após revisão automática no fluxo de execução):** o `auth.py` original usava SHA-256 sem salt para senha e um usuário padrão `admin/admin` hardcoded. Essas duas práticas foram substituídas abaixo por `werkzeug.security` (hash com salt, já é dependência do Flask) e por uma senha temporária aleatória gerada no boot quando `ATHENA_USERS` não está configurada — em vez de preservar o padrão antigo verbatim como este documento originalmente descrevia.

```python
import os
import hmac
import secrets
import functools
from datetime import datetime, timedelta

import jwt
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

auth_bp = Blueprint("auth", __name__)

API_TOKEN = os.environ.get("ATHENA_TOKEN", "")
if not API_TOKEN:
    API_TOKEN = secrets.token_hex(16)

JWT_SECRET = os.environ.get("ATHENA_JWT_SECRET", "")
if not JWT_SECRET:
    JWT_SECRET = secrets.token_hex(32)


# ponytail: users from env vars ATHENA_USERS="admin:hash:role:nome,joao:hash:role:nome"
# hash gerado com werkzeug.security.generate_password_hash
raw = os.environ.get("ATHENA_USERS", "")
USUARIOS = {}
if raw:
    for entry in raw.split(","):
        parts = entry.strip().split(":")
        if len(parts) >= 4:
            USUARIOS[parts[0]] = {"hash": parts[1], "role": parts[2], "name": parts[3]}

if "admin" not in USUARIOS:
    _senha_temporaria = secrets.token_urlsafe(12)
    USUARIOS["admin"] = {
        "hash": generate_password_hash(_senha_temporaria),
        "role": "admin",
        "name": "Admin",
    }
    print(f"[auth] ATHENA_USERS não configurada — senha temporária do admin gerada: {_senha_temporaria}")


ROLE_PERMISSIONS = {
    "admin": [
        "ver_produtos", "ver_estoque", "ver_lojas", "ver_vendas", "ver_financeiro",
        "ver_tributario", "ver_perdas", "ver_marketplaces", "ver_integracoes",
        "exportar", "gerenciar_usuarios",
    ],
    "financeiro": ["ver_financeiro", "ver_tributario", "ver_perdas", "ver_vendas", "exportar"],
    "operador_loja": ["ver_lojas", "ver_estoque", "ver_vendas", "ver_perdas", "ver_produtos"],
}


def _issue_token(username: str, role: str, name: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "name": name,
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _decode_token(auth_header: str):
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1]
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def require_role(*roles: str):
    """Decorator Flask: exige JWT válido; se `roles` não vazio, exige que o papel do token esteja nele."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            payload = _decode_token(request.headers.get("Authorization", ""))
            if payload is None:
                return jsonify({"error": "Unauthorized"}), 401
            if roles and payload.get("role") not in roles:
                return jsonify({"error": "Forbidden"}), 403
            request.user = payload
            return fn(*args, **kwargs)
        return wrapper
    return decorator


@auth_bp.route("/api/auth/login", methods=["POST"])
def simple_login():
    data = request.json or {}
    username = data.get("username", "").lower()
    password = data.get("password", "")
    api_key = data.get("api_key", "")

    user = USUARIOS.get(username, {})
    if user and check_password_hash(user.get("hash", ""), password):
        token = _issue_token(username, user["role"], user["name"])
        return jsonify({"token": token, "role": user["role"], "name": user["name"]})
    if api_key and hmac.compare_digest(api_key, API_TOKEN):
        token = _issue_token("admin", "admin", "Admin")
        return jsonify({"token": token, "role": "admin", "name": "Admin"})
    return jsonify({"error": "Invalid credentials"}), 401


@auth_bp.route("/api/me", methods=["GET"])
def current_user():
    payload = _decode_token(request.headers.get("Authorization", ""))
    if payload is None:
        return jsonify({"error": "Unauthorized"}), 401
    role = payload.get("role", "")
    return jsonify({
        "name": payload.get("name", ""),
        "role": role,
        "permissoes": ROLE_PERMISSIONS.get(role, []),
    })
```

- [ ] **Step 4: Adicionar PyJWT às dependências**

Em `hermes_agents/requirements.txt`, adicionar a linha (já instalado no ambiente, só faltava fixar para deploy):

```
pyjwt>=2.8.0
```

- [ ] **Step 5: Rodar o teste e confirmar que passa**

Run: `cd hermes_agents && python -m pytest test_fase_multiloja.py -v`
Expected: PASS — `1 passed`

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/routes/auth.py hermes_agents/requirements.txt hermes_agents/test_fase_multiloja.py
git commit -m "feat: autenticação JWT por usuário com papéis reais (admin/financeiro/operador_loja)"
```

---

### Task 2: Endpoint de detalhe de loja

**Files:**
- Modify: `hermes_agents/routes/catalog.py:107-151`
- Modify: `hermes_agents/test_fase_multiloja.py`

**Interfaces:**
- Consumes: `require_role(*roles)` de `hermes_agents/routes/auth.py` (Task 1), importado como `from .auth import require_role`.
- Produces: `GET /api/lojas/<int:loja_id>` devolvendo `{id, nome, tipo, receita, pedidos, ticket_medio, vendas_por_dia, top_produtos, estoque_local}`; 404 `{"erro": "loja nao encontrada"}` se `loja_id` não existir no catálogo.
- Produces: helper `_obter_catalogo_lojas(cur)` reaproveitado por `listar_lojas` (refatoração interna, sem mudança de contrato do endpoint já existente).

- [ ] **Step 1: Escrever o teste que falha**

Adicionar em `hermes_agents/test_fase_multiloja.py`, antes de `def run_all_tests():`:

```python
def test_loja_detalhe_requer_role():
    """Testa que /api/lojas/<id> exige token válido e devolve detalhe completo."""
    log("TEST", "Testando GET /api/lojas/<id>...")
    from athena_bridge import app
    client = app.test_client()

    resp_sem_token = client.get("/api/lojas/1")
    assert resp_sem_token.status_code == 401, "Sem token deve retornar 401"
    log("TEST", "✅ /api/lojas/1 sem token retorna 401")

    login = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
    token = login.get_json()["token"]

    resp = client.get("/api/lojas/1", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, f"Detalhe de loja deve retornar 200: {resp.get_json()}"
    body = resp.get_json()
    assert "vendas_por_dia" in body, f"Detalhe deve ter vendas_por_dia: {body}"
    assert "top_produtos" in body, f"Detalhe deve ter top_produtos: {body}"
    assert "estoque_local" in body, f"Detalhe deve ter estoque_local: {body}"
    log("TEST", f"✅ Detalhe da loja 1: {len(body['vendas_por_dia'])} dias de venda")

    resp_404 = client.get("/api/lojas/9999", headers={"Authorization": f"Bearer {token}"})
    assert resp_404.status_code == 404, f"Loja inexistente deve retornar 404: {resp_404.get_json()}"
    log("TEST", "✅ /api/lojas/9999 retorna 404")

    return True
```

E atualizar a lista `tests` dentro de `run_all_tests()` para:

```python
    tests = [
        ("Auth JWT + /api/me", test_auth_jwt_login_and_me),
        ("Detalhe de loja", test_loja_detalhe_requer_role),
    ]
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `cd hermes_agents && python -m pytest test_fase_multiloja.py::test_loja_detalhe_requer_role -v`
Expected: FAIL — rota `GET /api/lojas/<int:loja_id>` ainda não existe (404 genérico do Flask, não o 401/200/404 esperado pelos asserts).

- [ ] **Step 3: Implementar o endpoint em `hermes_agents/routes/catalog.py`**

No topo do arquivo, adicionar o import do decorator (junto aos imports existentes):

```python
from .auth import require_role
```

Substituir a função `listar_lojas` (linhas 107-151 do arquivo atual) por:

```python
def _obter_catalogo_lojas(cur) -> list:
    fisicas = [{"id": i, "nome": n, "tipo": "fisica"}
               for i, n in enumerate(["Loja Centro", "Loja Shopping", "Loja Norte", "Loja Sul", "Loja Leste"], 1)]
    mps = []
    try:
        cur.execute("SELECT DISTINCT marketplace FROM vendas WHERE marketplace IS NOT NULL")
        mps = [{"id": 10 + i, "nome": r["marketplace"], "tipo": "digital"}
               for i, r in enumerate(cur.fetchall())]
    except Exception:
        pass
    if not mps:
        mps = [{"id": 10, "nome": "shopee", "tipo": "digital"},
               {"id": 11, "nome": "mercado_livre", "tipo": "digital"}]
    return fisicas + mps


@catalog_bp.route("/api/lojas", methods=["GET"])
def listar_lojas():
    try:
        conn = _db_sync()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        periodo = request.args.get("periodo", 30, type=int)
        catalogo = _obter_catalogo_lojas(cur)
        resultado = []
        for loja in catalogo:
            try:
                if loja["tipo"] == "fisica":
                    cur.execute(
                        "SELECT COALESCE(SUM(receita_bruta),0) AS r,COALESCE(SUM(quantidade),0) AS p FROM vendas WHERE loja_id=%s AND data>=CURRENT_DATE-%s",
                        (loja["id"], periodo))
                else:
                    cur.execute(
                        "SELECT COALESCE(SUM(receita_bruta),0) AS r,COALESCE(SUM(quantidade),0) AS p FROM vendas WHERE marketplace=%s AND data>=CURRENT_DATE-%s",
                        (loja["nome"], periodo))
                v = cur.fetchone()
                receita, pedidos = float(v["r"]), v["p"]
            except Exception:
                receita, pedidos = 0, 0
            resultado.append({**loja, "receita": receita, "pedidos": pedidos,
                              "ticket_medio": round(receita / max(pedidos, 1), 2)})
        tr = sum(r["receita"] for r in resultado)
        resultado.insert(0, {"id": 0, "nome": "Consolidado", "tipo": "consolidado",
                             "receita": tr, "pedidos": sum(r["pedidos"] for r in resultado),
                             "ticket_medio": round(tr / max(sum(r["pedidos"] for r in resultado), 1), 2)})
        cur.close()
        conn.close()
        return jsonify(resultado)
    except Exception as e:
        return jsonify([{"id": 0, "nome": "Consolidado", "tipo": "consolidado",
                        "receita": 0, "pedidos": 0, "ticket_medio": 0, "erro": str(e)}])


@catalog_bp.route("/api/lojas/<int:loja_id>", methods=["GET"])
@require_role("admin", "operador_loja")
def detalhe_loja(loja_id):
    try:
        conn = _db_sync()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        catalogo = _obter_catalogo_lojas(cur)
        loja = next((l for l in catalogo if l["id"] == loja_id), None)
        if not loja:
            cur.close()
            conn.close()
            return jsonify({"erro": "loja nao encontrada"}), 404

        filtro_col = "loja_id" if loja["tipo"] == "fisica" else "marketplace"
        filtro_val = loja_id if loja["tipo"] == "fisica" else loja["nome"]

        cur.execute(f"""
            SELECT data, COALESCE(SUM(quantidade),0) AS qtd, COALESCE(SUM(receita_bruta),0) AS receita
            FROM vendas WHERE {filtro_col}=%s AND data>=CURRENT_DATE-30
            GROUP BY data ORDER BY data ASC
        """, (filtro_val,))
        vendas_por_dia = [{"data": str(r["data"]), "quantidade": r["qtd"], "receita": float(r["receita"])}
                           for r in cur.fetchall()]

        cur.execute(f"""
            SELECT v.sku, f.descricao AS nome, SUM(v.quantidade) AS qtd, SUM(v.receita_bruta) AS receita
            FROM vendas v JOIN fichas_tecnicas f ON f.sku=v.sku
            WHERE v.{filtro_col}=%s AND v.data>=CURRENT_DATE-30
            GROUP BY v.sku, f.descricao ORDER BY SUM(v.receita_bruta) DESC LIMIT 10
        """, (filtro_val,))
        top_produtos = [{"sku": r["sku"], "nome": r["nome"], "qtd": r["qtd"], "receita": float(r["receita"])}
                         for r in cur.fetchall()]

        estoque_local = []
        if loja["tipo"] == "digital":
            cur.execute("SELECT sku, preco, status FROM anuncios WHERE marketplace=%s", (loja["nome"],))
            estoque_local = [{"sku": r["sku"], "preco": float(r["preco"]) if r["preco"] else 0, "status": r["status"]}
                              for r in cur.fetchall()]

        cur.close()
        conn.close()

        receita_total = sum(v["receita"] for v in vendas_por_dia)
        pedidos_total = sum(v["quantidade"] for v in vendas_por_dia)
        return jsonify({
            **loja,
            "receita": receita_total,
            "pedidos": pedidos_total,
            "ticket_medio": round(receita_total / max(pedidos_total, 1), 2),
            "vendas_por_dia": vendas_por_dia,
            "top_produtos": top_produtos,
            "estoque_local": estoque_local,
        })
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
```

- [ ] **Step 4: Rodar o teste e confirmar que passa**

Run: `cd hermes_agents && python -m pytest test_fase_multiloja.py -v`
Expected: PASS — `2 passed`

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/routes/catalog.py hermes_agents/test_fase_multiloja.py
git commit -m "feat: endpoint de detalhe de loja (vendas por dia, top produtos, estoque local)"
```

---

### Task 3: Endpoint de vendas agregadas

**Files:**
- Modify: `hermes_agents/routes/catalog.py`
- Modify: `hermes_agents/test_fase_multiloja.py`

**Interfaces:**
- Consumes: `require_role(*roles)` de `hermes_agents/routes/auth.py` (Task 1).
- Produces: `GET /api/vendas?loja=&periodo=&agrupado_por=dia|loja|canal` devolvendo `{agrupado_por, periodo, linhas: [{chave, quantidade, receita}]}`.

- [ ] **Step 1: Escrever o teste que falha**

Adicionar em `hermes_agents/test_fase_multiloja.py`, antes de `def run_all_tests():`:

```python
def test_vendas_agregadas():
    """Testa GET /api/vendas com agregação por dia."""
    log("TEST", "Testando GET /api/vendas...")
    from athena_bridge import app
    client = app.test_client()

    resp_sem_token = client.get("/api/vendas")
    assert resp_sem_token.status_code == 401, "Sem token deve retornar 401"

    login = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
    token = login.get_json()["token"]

    resp = client.get("/api/vendas?periodo=30&agrupado_por=dia", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, f"Vendas deve retornar 200: {resp.get_json()}"
    body = resp.get_json()
    assert body["agrupado_por"] == "dia", f"agrupado_por deve ecoar o parâmetro: {body}"
    assert isinstance(body["linhas"], list), f"linhas deve ser lista: {body}"
    log("TEST", f"✅ Vendas agregadas por dia: {len(body['linhas'])} linhas")

    return True
```

E atualizar `tests` em `run_all_tests()`:

```python
    tests = [
        ("Auth JWT + /api/me", test_auth_jwt_login_and_me),
        ("Detalhe de loja", test_loja_detalhe_requer_role),
        ("Vendas agregadas", test_vendas_agregadas),
    ]
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `cd hermes_agents && python -m pytest test_fase_multiloja.py::test_vendas_agregadas -v`
Expected: FAIL — rota `GET /api/vendas` ainda não existe.

- [ ] **Step 3: Implementar o endpoint em `hermes_agents/routes/catalog.py`**

Adicionar ao final do arquivo:

```python
@catalog_bp.route("/api/vendas", methods=["GET"])
@require_role("admin", "operador_loja", "financeiro")
def listar_vendas():
    try:
        loja = request.args.get("loja", "")
        periodo = request.args.get("periodo", 30, type=int)
        agrupado_por = request.args.get("agrupado_por", "dia")
        colunas_validas = {"dia": "data", "loja": "loja_id", "canal": "marketplace"}
        coluna = colunas_validas.get(agrupado_por, "data")

        conn = _db_sync()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        where = ["data >= CURRENT_DATE - %s"]
        params = [periodo]
        if loja:
            where.append("(loja_id::text = %s OR marketplace = %s)")
            params.extend([loja, loja])
        sql_where = " AND ".join(where)

        cur.execute(f"""
            SELECT {coluna} AS chave, COALESCE(SUM(quantidade),0) AS quantidade, COALESCE(SUM(receita_bruta),0) AS receita
            FROM vendas WHERE {sql_where}
            GROUP BY {coluna} ORDER BY {coluna}
        """, params)
        linhas = [{"chave": str(r["chave"]), "quantidade": r["quantidade"], "receita": float(r["receita"])}
                  for r in cur.fetchall()]
        cur.close()
        conn.close()
        return jsonify({"agrupado_por": agrupado_por, "periodo": periodo, "linhas": linhas})
    except Exception as e:
        return jsonify({"erro": str(e), "agrupado_por": "dia", "periodo": 30, "linhas": []})
```

- [ ] **Step 4: Rodar o teste e confirmar que passa**

Run: `cd hermes_agents && python -m pytest test_fase_multiloja.py -v`
Expected: PASS — `3 passed`

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/routes/catalog.py hermes_agents/test_fase_multiloja.py
git commit -m "feat: endpoint de vendas agregadas por dia/loja/canal"
```

---

### Task 4: Menu filtrado por papel no frontend

**Files:**
- Modify: `web/src/app/layout.tsx`

**Interfaces:**
- Produces: `type Role = "admin" | "financeiro" | "operador_loja"` e `NAV_ITEMS: Array<{href, label, icon, roles: Role[]}>`, exportados apenas internamente ao arquivo (não é módulo compartilhado — Tasks 6 e 7 replicam o array ao adicionar itens no mesmo arquivo).
- Produces: guard client-side que redireciona para `/dashboard` quando a rota atual não está entre os itens permitidos para o papel do usuário logado.

- [ ] **Step 1: Implementar a mudança**

Em `web/src/app/layout.tsx`, substituir o bloco `NAV_ITEMS` (linhas 8-16 do arquivo atual) por:

```tsx
type Role = "admin" | "financeiro" | "operador_loja";

const NAV_ITEMS: Array<{ href: string; label: string; icon: string; roles: Role[] }> = [
  { href: "/dashboard", label: "Dashboard", icon: "⊞", roles: ["admin", "financeiro", "operador_loja"] },
  { href: "/agents", label: "Agentes", icon: "◈", roles: ["admin"] },
  { href: "/produtos", label: "Produtos", icon: "◇", roles: ["admin", "operador_loja"] },
  { href: "/workflows", label: "Workflows", icon: "⇄", roles: ["admin"] },
  { href: "/metrics", label: "Métricas", icon: "▤", roles: ["admin"] },
  { href: "/business", label: "Operações", icon: "⚙", roles: ["admin"] },
  { href: "/integracoes", label: "Integrações", icon: "↔", roles: ["admin"] },
];
```

Substituir o `useEffect` de carregamento de usuário (linhas 24-35 do arquivo atual) por:

```tsx
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token && pathname !== "/login") {
      router.push("/login");
      return;
    }
    if (token) {
      api.me()
        .then((d) => {
          setUser(d);
          const role = d.role as Role;
          const allowed = NAV_ITEMS.filter((item) => item.roles.includes(role));
          const hasAccess = allowed.some((item) => pathname?.startsWith(item.href));
          if (!hasAccess && pathname !== "/dashboard") {
            router.push("/dashboard");
          }
        })
        .catch(() => { localStorage.removeItem("token"); router.push("/login"); });
    }
  }, [pathname]);
```

Substituir a linha `{NAV_ITEMS.map((item) => {` (dentro do `<nav>`, linha 107 do arquivo atual) por:

```tsx
            {NAV_ITEMS.filter((item) => !user || item.roles.includes(user.role as Role)).map((item) => {
```

- [ ] **Step 2: Rodar o build e confirmar que passa**

Run: `cd web && npm run build`
Expected: exit code 0, sem erros de TypeScript.

- [ ] **Step 3: Verificação manual**

Com o backend da Task 1 rodando, logar com o usuário `admin`/`admin` e confirmar visualmente que todos os 7 itens de menu aparecem (nenhum item novo ainda, já que Lojas/Vendas entram nas Tasks 6 e 7).

- [ ] **Step 4: Commit**

```bash
git add web/src/app/layout.tsx
git commit -m "feat: menu lateral filtrado por papel do usuário"
```

---

### Task 5: Cliente de API para lojas e vendas

**Files:**
- Modify: `web/src/lib/api.ts`

**Interfaces:**
- Produces: `api.lojaDetalhe(id: number): Promise<LojaDetalhe>`, `api.vendas(params?: {loja?: string; periodo?: number; agrupadoPor?: "dia"|"loja"|"canal"}): Promise<VendasResponse>`.
- Produces: tipos `Loja`, `LojaDetalhe`, `VendasResponse` exportados de `@/lib/api`.
- Modifies: `api.lojas()` passa a devolver `Promise<Loja[]>` (era `Promise<unknown[]>`).

- [ ] **Step 1: Implementar a mudança**

Em `web/src/lib/api.ts`, substituir a linha do endpoint `lojas` (linhas 111-112 do arquivo atual):

```ts
  lojas: (periodo?: number) =>
    request<unknown[]>(`/api/lojas${periodo ? `?periodo=${periodo}` : ""}`),
```

por:

```ts
  lojas: (periodo?: number) =>
    request<Loja[]>(`/api/lojas${periodo ? `?periodo=${periodo}` : ""}`),

  lojaDetalhe: (id: number) => request<LojaDetalhe>(`/api/lojas/${id}`),

  vendas: (params?: { loja?: string; periodo?: number; agrupadoPor?: "dia" | "loja" | "canal" }) => {
    const q = new URLSearchParams();
    if (params?.loja) q.set("loja", params.loja);
    if (params?.periodo) q.set("periodo", String(params.periodo));
    if (params?.agrupadoPor) q.set("agrupado_por", params.agrupadoPor);
    return request<VendasResponse>(`/api/vendas?${q}`);
  },
```

Adicionar ao final do arquivo, junto aos outros `export interface`:

```ts
export interface Loja {
  id: number;
  nome: string;
  tipo: "fisica" | "digital" | "consolidado";
  receita: number;
  pedidos: number;
  ticket_medio: number;
}

export interface LojaDetalhe extends Loja {
  vendas_por_dia: Array<{ data: string; quantidade: number; receita: number }>;
  top_produtos: Array<{ sku: string; nome: string; qtd: number; receita: number }>;
  estoque_local: Array<{ sku: string; preco: number; status: string }>;
}

export interface VendasResponse {
  agrupado_por: string;
  periodo: number;
  linhas: Array<{ chave: string; quantidade: number; receita: number }>;
}
```

- [ ] **Step 2: Rodar o build e confirmar que passa**

Run: `cd web && npm run build`
Expected: exit code 0.

- [ ] **Step 3: Commit**

```bash
git add web/src/lib/api.ts
git commit -m "feat: cliente de API para detalhe de loja e vendas agregadas"
```

---

### Task 6: Páginas `/lojas` e `/lojas/[id]`

**Files:**
- Create: `web/src/app/lojas/page.tsx`
- Create: `web/src/app/lojas/[id]/page.tsx`
- Modify: `web/src/app/layout.tsx`

**Interfaces:**
- Consumes: `api.lojas`, `api.lojaDetalhe`, tipos `Loja`/`LojaDetalhe` (Task 5); `NAV_ITEMS`/`Role` (Task 4).

- [ ] **Step 1: Criar `web/src/app/lojas/page.tsx`**

```tsx
"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api, type Loja } from "@/lib/api";

const PERIODOS = [7, 30, 90];

export default function LojasPage() {
  const [lojas, setLojas] = useState<Loja[]>([]);
  const [periodo, setPeriodo] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.lojas(periodo)
      .then((r) => setLojas(r))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Erro ao carregar lojas"))
      .finally(() => setLoading(false));
  }, [periodo]);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-lg font-light text-neutral-300">Lojas</h1>
        <div className="flex gap-1">
          {PERIODOS.map((p) => (
            <button
              key={p}
              onClick={() => setPeriodo(p)}
              className={`px-3 py-1.5 rounded-lg text-xs transition-colors ${
                periodo === p
                  ? "bg-indigo-600/20 text-indigo-300"
                  : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800"
              }`}
            >
              {p}d
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-neutral-500 text-sm">Carregando...</div>
      ) : (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
          <table className="w-full text-sm min-w-[640px]">
            <thead>
              <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
                <th className="text-left p-3 font-medium">Loja</th>
                <th className="text-left p-3 font-medium">Tipo</th>
                <th className="text-right p-3 font-medium">Receita</th>
                <th className="text-right p-3 font-medium">Pedidos</th>
                <th className="text-right p-3 font-medium">Ticket Médio</th>
              </tr>
            </thead>
            <tbody>
              {lojas.map((l) => (
                <tr
                  key={l.id}
                  onClick={() => l.tipo !== "consolidado" && router.push(`/lojas/${l.id}`)}
                  className={`border-b border-neutral-800/50 last:border-0 ${
                    l.tipo !== "consolidado" ? "hover:bg-neutral-800/30 cursor-pointer" : "bg-neutral-900/60"
                  }`}
                >
                  <td className="p-3 text-neutral-200">{l.nome}</td>
                  <td className="p-3 text-neutral-500 text-xs uppercase">{l.tipo}</td>
                  <td className="p-3 text-right text-neutral-300 numeric">
                    R$ {l.receita.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="p-3 text-right text-neutral-400 numeric">{l.pedidos}</td>
                  <td className="p-3 text-right text-neutral-400 numeric">R$ {l.ticket_medio.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Criar `web/src/app/lojas/[id]/page.tsx`**

```tsx
"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, type LojaDetalhe } from "@/lib/api";

export default function LojaDetalhePage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);
  const [loja, setLoja] = useState<LojaDetalhe | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isFinite(id)) return;
    api.lojaDetalhe(id)
      .then(setLoja)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Erro ao carregar loja"))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="p-6 text-neutral-500">Carregando...</div>;

  return (
    <div className="p-6 space-y-6">
      <button onClick={() => router.push("/lojas")} className="text-neutral-500 hover:text-neutral-300 text-sm">
        ← Voltar
      </button>

      {error && (
        <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {loja && (
        <>
          <h1 className="text-lg font-light text-neutral-300">{loja.nome}</h1>

          <div className="grid grid-cols-3 gap-4">
            <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
              <div className="text-[10px] text-neutral-500 uppercase tracking-wider mb-1">Receita</div>
              <div className="text-xl font-light text-neutral-100 numeric">
                R$ {loja.receita.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
              </div>
            </div>
            <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
              <div className="text-[10px] text-neutral-500 uppercase tracking-wider mb-1">Pedidos</div>
              <div className="text-xl font-light text-neutral-100 numeric">{loja.pedidos}</div>
            </div>
            <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
              <div className="text-[10px] text-neutral-500 uppercase tracking-wider mb-1">Ticket Médio</div>
              <div className="text-xl font-light text-neutral-100 numeric">R$ {loja.ticket_medio.toFixed(2)}</div>
            </div>
          </div>

          <section>
            <h2 className="text-sm font-medium text-neutral-400 mb-3">Top Produtos</h2>
            <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
              <table className="w-full text-sm min-w-[480px]">
                <thead>
                  <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
                    <th className="text-left p-3 font-medium">SKU</th>
                    <th className="text-left p-3 font-medium">Nome</th>
                    <th className="text-right p-3 font-medium">Qtd</th>
                    <th className="text-right p-3 font-medium">Receita</th>
                  </tr>
                </thead>
                <tbody>
                  {loja.top_produtos.map((p) => (
                    <tr key={p.sku} className="border-b border-neutral-800/50 last:border-0">
                      <td className="p-3 text-indigo-400 font-mono text-xs numeric">{p.sku}</td>
                      <td className="p-3 text-neutral-300">{p.nome}</td>
                      <td className="p-3 text-right text-neutral-400 numeric">{p.qtd}</td>
                      <td className="p-3 text-right text-neutral-300 numeric">
                        R$ {p.receita.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {loja.estoque_local.length > 0 && (
            <section>
              <h2 className="text-sm font-medium text-neutral-400 mb-3">Estoque Local</h2>
              <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
                <table className="w-full text-sm min-w-[420px]">
                  <thead>
                    <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
                      <th className="text-left p-3 font-medium">SKU</th>
                      <th className="text-right p-3 font-medium">Preço</th>
                      <th className="text-left p-3 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {loja.estoque_local.map((e, i) => (
                      <tr key={`${e.sku}-${i}`} className="border-b border-neutral-800/50 last:border-0">
                        <td className="p-3 text-indigo-400 font-mono text-xs numeric">{e.sku}</td>
                        <td className="p-3 text-right text-neutral-300 numeric">R$ {e.preco.toFixed(2)}</td>
                        <td className="p-3 text-neutral-400">{e.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Adicionar o item de menu**

Em `web/src/app/layout.tsx`, no array `NAV_ITEMS` (criado na Task 4), inserir logo após o item `/produtos`:

```tsx
  { href: "/lojas", label: "Lojas", icon: "▦", roles: ["admin", "operador_loja"] },
```

- [ ] **Step 4: Rodar o build e confirmar que passa**

Run: `cd web && npm run build`
Expected: exit code 0.

- [ ] **Step 5: Verificação manual**

Com backend e frontend rodando, logar como `admin`, abrir `/lojas` e confirmar que a tabela comparativa carrega com dados reais (não mock) e que clicar numa loja abre `/lojas/<id>` com vendas por dia, top produtos e (se digital) estoque local.

- [ ] **Step 6: Commit**

```bash
git add web/src/app/lojas web/src/app/layout.tsx
git commit -m "feat: aba Lojas com comparativo e detalhe por loja/canal"
```

---

### Task 7: Página `/vendas`

**Files:**
- Create: `web/src/app/vendas/page.tsx`
- Modify: `web/src/app/layout.tsx`

**Interfaces:**
- Consumes: `api.vendas`, tipo `VendasResponse` (Task 5); `NAV_ITEMS`/`Role` (Task 4).

- [ ] **Step 1: Criar `web/src/app/vendas/page.tsx`**

```tsx
"use client";

import { useState, useEffect } from "react";
import { api, type VendasResponse } from "@/lib/api";

const PERIODOS = [7, 30, 90];
const AGRUPAMENTOS: Array<{ value: "dia" | "loja" | "canal"; label: string }> = [
  { value: "dia", label: "Por Dia" },
  { value: "loja", label: "Por Loja" },
  { value: "canal", label: "Por Canal" },
];

export default function VendasPage() {
  const [dados, setDados] = useState<VendasResponse | null>(null);
  const [periodo, setPeriodo] = useState(30);
  const [agrupadoPor, setAgrupadoPor] = useState<"dia" | "loja" | "canal">("dia");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.vendas({ periodo, agrupadoPor })
      .then(setDados)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Erro ao carregar vendas"))
      .finally(() => setLoading(false));
  }, [periodo, agrupadoPor]);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-lg font-light text-neutral-300">Vendas</h1>
        <div className="flex gap-4 flex-wrap">
          <div className="flex gap-1">
            {AGRUPAMENTOS.map((a) => (
              <button
                key={a.value}
                onClick={() => setAgrupadoPor(a.value)}
                className={`px-3 py-1.5 rounded-lg text-xs transition-colors ${
                  agrupadoPor === a.value
                    ? "bg-indigo-600/20 text-indigo-300"
                    : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800"
                }`}
              >
                {a.label}
              </button>
            ))}
          </div>
          <div className="flex gap-1">
            {PERIODOS.map((p) => (
              <button
                key={p}
                onClick={() => setPeriodo(p)}
                className={`px-3 py-1.5 rounded-lg text-xs transition-colors ${
                  periodo === p
                    ? "bg-indigo-600/20 text-indigo-300"
                    : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800"
                }`}
              >
                {p}d
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-neutral-500 text-sm">Carregando...</div>
      ) : (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
          <table className="w-full text-sm min-w-[480px]">
            <thead>
              <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
                <th className="text-left p-3 font-medium">
                  {agrupadoPor === "dia" ? "Data" : agrupadoPor === "loja" ? "Loja" : "Canal"}
                </th>
                <th className="text-right p-3 font-medium">Quantidade</th>
                <th className="text-right p-3 font-medium">Receita</th>
              </tr>
            </thead>
            <tbody>
              {(dados?.linhas ?? []).map((l, i) => (
                <tr key={`${l.chave}-${i}`} className="border-b border-neutral-800/50 last:border-0">
                  <td className="p-3 text-neutral-300">{l.chave}</td>
                  <td className="p-3 text-right text-neutral-400 numeric">{l.quantidade}</td>
                  <td className="p-3 text-right text-neutral-300 numeric">
                    R$ {l.receita.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Adicionar o item de menu**

Em `web/src/app/layout.tsx`, no array `NAV_ITEMS`, inserir logo após o item `/lojas` (adicionado na Task 6):

```tsx
  { href: "/vendas", label: "Vendas", icon: "⇌", roles: ["admin", "operador_loja", "financeiro"] },
```

- [ ] **Step 3: Rodar o build e confirmar que passa**

Run: `cd web && npm run build`
Expected: exit code 0.

- [ ] **Step 4: Verificação manual**

Logar como cada um dos 3 papéis e confirmar: `admin` vê os 9 itens de menu (7 originais + Lojas + Vendas); `financeiro` vê só Dashboard e Vendas; `operador_loja` vê Dashboard, Produtos, Lojas e Vendas. Abrir `/vendas`, trocar agrupamento e período, confirmar que os números batem com os mesmos períodos vistos em `/lojas`.

- [ ] **Step 5: Commit**

```bash
git add web/src/app/vendas web/src/app/layout.tsx
git commit -m "feat: aba Vendas com agregação por dia/loja/canal"
```
