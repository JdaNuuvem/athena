# Bling — Situações (CRUD) (Plano 3/N) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar CRUD completo de Situações (status customizados de pedido/NF/etc do
Bling) — criar, editar, excluir situações direto pelo Athena, propagando pro Bling, com cache
local (`bling_situacoes`) usado como referência/filtro em outras telas.

**Architecture:** Segue o padrão já estabelecido em `criar_produto`/`atualizar_produto`/
`deletar_produto` (`bling_erp.py:554-566`) para as chamadas HTTP CRUD à API Bling v3, e o
padrão de `bling_categorias` (`routes/integrations.py`, criação de tabela sob demanda) para o
cache local. Rotas em `bling_bp` (`routes/integrations.py`).

**Tech Stack:** Flask (Python), pytest, requests.

**Spec:** `docs/superpowers/specs/2026-08-20-modulo-bling-design.md` (seção "Situações (novo,
CRUD)")

## Global Constraints

- TDD: escrever teste, confirmar falha, implementar, confirmar passa, para cada função nova.
- Rodar a suíte completa (`cd hermes_agents && python -m pytest tests/ -q`) ao final de cada
  task antes de commitar. Baseline conhecido: 8 falhas pré-existentes alheias a Bling (RH
  endpoints, compras segurança, RBAC lojas) — não bloqueiam, mas nenhuma NOVA falha é
  aceitável.
- O endpoint exato da API Bling v3 pra situações (`situacoes`) segue a convenção REST já usada
  no resto de `bling_erp.py` (recurso no singular/plural direto, ex: `produtos`, `contatos`),
  mas não foi confirmado contra uma conta Bling real ao vivo — igual ao caveat já documentado
  em `bling_erp.py:196-201` sobre `buscar_pedido_por_numero_loja`. Se o formato de payload
  real divergir quando testado contra a API de verdade, ajustar `_mapear_situacao` (Task 2)
  é o único ponto de mudança necessário.

---

### Task 1: Corrigir bug de PUT sem corpo em `_request` + wrappers CRUD de Situações

`hermes_agents/bling_erp.py:116` só envia `json=params` quando `method == "POST"` — para
`method == "PUT"`, o corpo da requisição é sempre `None`, mesmo quando `params` tem dados.
Isso quebra silenciosamente `atualizar_produto()` (`bling_erp.py:559-561`) hoje: ela chama
`_request(f"produtos/{id_produto}", dados, method="PUT")`, mas `dados` nunca é enviado — a
API Bling recebe um PUT vazio. Como o CRUD de Situações desta task depende de PUT funcionando
de verdade, corrigir isso é pré-requisito.

**Files:**
- Modify: `hermes_agents/bling_erp.py` (`_request`, linha 109-127; adicionar wrappers CRUD de
  situações logo após a seção `# ── Categorias de Produtos ──`)
- Test: `hermes_agents/tests/test_bling_erp.py`

**Interfaces:**
- Produces:
  - `bling_erp._request(endpoint, params=None, method="GET") -> dict` (corrigido, mesma
    assinatura)
  - `bling_erp.listar_situacoes(pagina: int = 1, limite: int = 100) -> dict`
  - `bling_erp.criar_situacao(dados: dict) -> dict`
  - `bling_erp.atualizar_situacao(id_situacao: int, dados: dict) -> dict`
  - `bling_erp.deletar_situacao(id_situacao: int) -> dict`

- [ ] **Step 1: Escrever o teste do bug do PUT (RED)**

Adicionar a `hermes_agents/tests/test_bling_erp.py`, na classe de teste que já cobre
`_request` (ou crie o teste direto contra `bling_erp._request` mockando `requests.request` —
confirme o padrão de mock já usado pra `_request` no arquivo, procure por
`patch("bling_erp.requests.request"` ou equivalente):

```python
    def test_request_envia_corpo_em_put(self):
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"data": {}}
        with patch("bling_erp.get_access_token", return_value="tok"), \
             patch("bling_erp.requests.request", return_value=fake_response) as mock_request:
            bling_erp._request("produtos/1", {"nome": "X"}, method="PUT")
            _, kwargs = mock_request.call_args
            self.assertEqual(kwargs["json"], {"nome": "X"})
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py -k test_request_envia_corpo_em_put -v`
Expected: FAIL — `kwargs["json"]` é `None`, não `{"nome": "X"}`.

- [ ] **Step 3: Corrigir `_request`**

Em `hermes_agents/bling_erp.py`, substituir as duas ocorrências (linhas 116-117 e 122-123,
idênticas — a segunda é o retry após refresh de token):

```python
        r = requests.request(method, url, headers=headers, json=params if method == "POST" else None,
                             params=params if method == "GET" else None, timeout=30)
```

por:

```python
        r = requests.request(method, url, headers=headers, json=params if method in ("POST", "PUT") else None,
                             params=params if method == "GET" else None, timeout=30)
```

(repita a mesma troca nas duas ocorrências — a de dentro do bloco de retry de token expirado
também precisa da correção, senão o bug volta silenciosamente só nesse caminho).

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py -k test_request_envia_corpo_em_put -v`
Expected: PASS

- [ ] **Step 5: Escrever os testes dos wrappers CRUD de situações (RED)**

```python
    def test_listar_situacoes_chama_endpoint_correto(self):
        with patch("bling_erp._request", return_value={"data": []}) as mock_request:
            bling_erp.listar_situacoes(pagina=1, limite=100)
            mock_request.assert_called_once_with("situacoes", {"pagina": 1, "limite": 100})

    def test_criar_situacao_chama_endpoint_correto(self):
        with patch("bling_erp._request", return_value={"data": {"id": 1}}) as mock_request:
            bling_erp.criar_situacao({"nome": "Aguardando Pagamento", "cor": "FFA500"})
            mock_request.assert_called_once_with("situacoes", {"nome": "Aguardando Pagamento", "cor": "FFA500"}, method="POST")

    def test_atualizar_situacao_chama_endpoint_correto(self):
        with patch("bling_erp._request", return_value={"data": {}}) as mock_request:
            bling_erp.atualizar_situacao(42, {"nome": "Pago"})
            mock_request.assert_called_once_with("situacoes/42", {"nome": "Pago"}, method="PUT")

    def test_deletar_situacao_chama_endpoint_correto(self):
        with patch("bling_erp._request", return_value={}) as mock_request:
            bling_erp.deletar_situacao(42)
            mock_request.assert_called_once_with("situacoes/42", method="DELETE")
```

- [ ] **Step 6: Rodar e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py -k "situacao" -v`
Expected: FAIL — `AttributeError` (funções ainda não existem).

- [ ] **Step 7: Implementar os wrappers**

Em `hermes_agents/bling_erp.py`, logo após `get_categoria` (fim da seção
`# ── Categorias de Produtos ──`), adicionar:

```python
# ── Situações (status customizados de pedido/NF) ──

def listar_situacoes(pagina: int = 1, limite: int = 100) -> dict:
    return _request("situacoes", {"pagina": pagina, "limite": limite})

def criar_situacao(dados: dict) -> dict:
    """Cria situacao customizada no Bling via POST /situacoes. dados deve conter nome, cor, etc."""
    return _request("situacoes", dados, method="POST")

def atualizar_situacao(id_situacao: int, dados: dict) -> dict:
    """Atualiza situacao existente via PUT /situacoes/{id}."""
    return _request(f"situacoes/{id_situacao}", dados, method="PUT")

def deletar_situacao(id_situacao: int) -> dict:
    """Deleta situacao via DELETE /situacoes/{id}."""
    return _request(f"situacoes/{id_situacao}", method="DELETE")
```

- [ ] **Step 8: Rodar e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py -k "situacao or test_request_envia_corpo_em_put" -v`
Expected: PASS

- [ ] **Step 9: Rodar a suíte completa de testes Bling**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py tests/test_bling_routes.py -v`
Expected: todos PASS (o fix do PUT não pode quebrar nada que já usa `atualizar_produto`).

- [ ] **Step 10: Commit**

```bash
git add hermes_agents/bling_erp.py hermes_agents/tests/test_bling_erp.py
git commit -m "fix: _request envia corpo em PUT (bug pre-existente); feat: wrappers CRUD de situacoes Bling"
```

---

### Task 2: Cache local de Situações (`bling_situacoes`) + sync de leitura

Cria a tabela `bling_situacoes` e uma função de sync que faz upsert por `bling_id` a partir de
`listar_situacoes()` — mesmo padrão de `sincronizar_canais_bling` (`bling_erp.py`, já
implementado no plano anterior). Essa tabela serve de cache pras rotas de leitura/filtro
usadas por outras telas (Pedidos de Venda, Pedidos de Compra, Notas Fiscais).

**Files:**
- Modify: `hermes_agents/bling_erp.py` (adicionar `sincronizar_situacoes_bling`)
- Test: `hermes_agents/tests/test_bling_erp.py`

**Interfaces:**
- Consumes: `bling_erp.listar_situacoes(pagina, limite) -> dict` (Task 1)
- Produces: `bling_erp.sincronizar_situacoes_bling(pagina: int = 1, limite: int = 100) -> dict`

- [ ] **Step 1: Escrever o teste (RED)**

```python
    def test_sincronizar_situacoes_bling_cria_tabela_e_faz_upsert(self):
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = None
        with patch("bling_erp.get_access_token", return_value="tok"), \
             patch("bling_erp.get_db", new=AsyncMock(return_value=fake_db)), \
             patch("bling_erp.listar_situacoes", return_value={"data": [
                 {"id": 777, "nome": "Aguardando Pagamento", "cor": "FFA500", "modulo": "pedidos"},
             ]}):
            resultado = bling_erp.sincronizar_situacoes_bling()
        self.assertEqual(resultado["sync"], 1)
        sqls_executados = [c.args[0] for c in fake_db.execute.call_args_list]
        self.assertTrue(any("CREATE TABLE IF NOT EXISTS bling_situacoes" in s for s in sqls_executados))
        self.assertTrue(any("INSERT INTO bling_situacoes" in s for s in sqls_executados))
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py -k test_sincronizar_situacoes_bling_cria_tabela_e_faz_upsert -v`
Expected: FAIL.

- [ ] **Step 3: Implementar a função**

Em `hermes_agents/bling_erp.py`, logo após `sincronizar_canais_bling` (implementada no plano
anterior — procure a assinatura `def sincronizar_canais_bling`), adicionar:

```python
def sincronizar_situacoes_bling(pagina: int = 1, limite: int = 100) -> dict:
    """Sync de situacoes (status customizados) cadastradas no Bling, usadas como
    filtro/referencia nas telas de Pedidos de Venda, Pedidos de Compra e Notas Fiscais."""
    token = get_access_token()
    if not token:
        return {"error": "Bling nao autenticado", "auth_url": get_auth_url()}
    r = listar_situacoes(pagina, limite)
    if r.get("error"):
        return r
    dados = r.get("data", [])
    if not dados:
        return {"sync": 0, "message": "sem dados"}

    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS bling_situacoes (
            id SERIAL PRIMARY KEY, bling_id BIGINT UNIQUE, nome VARCHAR(200),
            cor VARCHAR(20), modulo VARCHAR(50), created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW())""")
        total = 0
        for situacao in dados:
            try:
                bling_id = situacao.get("id")
                if not bling_id:
                    continue
                nome = situacao.get("nome", "")
                cor = situacao.get("cor", "")
                modulo = situacao.get("modulo", "")
                existing = await db.fetchval("SELECT id FROM bling_situacoes WHERE bling_id = $1", bling_id)
                if existing:
                    await db.execute(
                        "UPDATE bling_situacoes SET nome=$1, cor=$2, modulo=$3, updated_at=NOW() WHERE bling_id=$4",
                        nome, cor, modulo, bling_id)
                else:
                    await db.execute(
                        "INSERT INTO bling_situacoes (bling_id, nome, cor, modulo) VALUES ($1,$2,$3,$4)",
                        bling_id, nome, cor, modulo)
                total += 1
            except Exception as e:
                log(AGENT, f"Erro ao sincronizar situacao {situacao.get('id')}: {e}")
        return total

    try:
        total = run_async(_go())
        return {"sync": total}
    except Exception as e:
        return {"error": str(e)}
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py -k test_sincronizar_situacoes_bling_cria_tabela_e_faz_upsert -v`
Expected: PASS

- [ ] **Step 5: Rodar a suíte completa de testes Bling**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py tests/test_bling_routes.py -v`
Expected: todos PASS.

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/bling_erp.py hermes_agents/tests/test_bling_erp.py
git commit -m "feat: sync de situacoes Bling (tabela bling_situacoes nova)"
```

---

### Task 3: Rotas HTTP CRUD de Situações em `bling_bp`

Expõe leitura (local, cache), sync, e as 3 operações de escrita (criar/atualizar/excluir) que
propagam pro Bling. Segue o padrão de `/produtos` (POST/PUT/DELETE) já existente no mesmo
arquivo — leia essas rotas como referência de estilo antes de escrever
(`routes/integrations.py`, procure `def api_criar_produto`).

Importante: como a rota `GET /api/bling/situacoes` lê de uma tabela que só é criada dentro do
sync (mesmo padrão do plano anterior, Fase 2), esta task já nasce evitando o bug de 500
encontrado e corrigido naquele plano — a rota GET deve garantir a tabela existe antes do
SELECT, chamando uma função exportada de `bling_erp.py` (siga o padrão de
`ensure_bling_canais_table`, já implementado — procure essa função em `bling_erp.py` como
referência e crie uma equivalente `ensure_bling_situacoes_table` reaproveitada tanto pelo sync
quanto pela rota GET).

**Files:**
- Modify: `hermes_agents/bling_erp.py` (extrair `ensure_bling_situacoes_table` de dentro de
  `sincronizar_situacoes_bling`, mesma refatoração já feita pra canais)
- Modify: `hermes_agents/routes/integrations.py` (bloco `bling_bp`, logo após as rotas de
  categorias/canais)
- Test: `hermes_agents/tests/test_bling_routes.py`

**Interfaces:**
- Consumes: `bling_erp.sincronizar_situacoes_bling`, `bling_erp.criar_situacao`,
  `bling_erp.atualizar_situacao`, `bling_erp.deletar_situacao` (Tasks 1-2)
- Produces:
  - `GET /api/bling/situacoes` (lista local)
  - `POST /api/bling/situacoes/sincronizar` (sync de leitura)
  - `POST /api/bling/situacoes` (cria — propaga pro Bling, depois insere local)
  - `PUT /api/bling/situacoes/<int:id_situacao>` (atualiza — propaga pro Bling, depois
    atualiza local)
  - `DELETE /api/bling/situacoes/<int:id_situacao>` (exclui — propaga pro Bling, depois
    remove local)

- [ ] **Step 1: Refatorar `sincronizar_situacoes_bling` pra extrair `ensure_bling_situacoes_table`**

Em `hermes_agents/bling_erp.py`, extraia o `CREATE TABLE IF NOT EXISTS bling_situacoes (...)`
de dentro de `sincronizar_situacoes_bling` para uma função própria:

```python
async def ensure_bling_situacoes_table(db):
    await db.execute("""CREATE TABLE IF NOT EXISTS bling_situacoes (
        id SERIAL PRIMARY KEY, bling_id BIGINT UNIQUE, nome VARCHAR(200),
        cor VARCHAR(20), modulo VARCHAR(50), created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW())""")
```

E, dentro de `sincronizar_situacoes_bling`, troque a chamada inline `CREATE TABLE` por
`await ensure_bling_situacoes_table(db)`.

Rode os testes da Task 2 de novo pra confirmar que a refatoração não quebrou nada:

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py -k situacao -v`
Expected: PASS (mesmo comportamento, só reorganizado).

- [ ] **Step 2: Escrever os testes das rotas (RED)**

Adicionar a `hermes_agents/tests/test_bling_routes.py`:

```python
    def test_situacoes_listar_route(self):
        rv = self.client.get("/api/bling/situacoes")
        self.assertEqual(rv.status_code, 200)

    def test_situacoes_sincronizar_route(self):
        with patch("routes.integrations.sincronizar_situacoes_bling", return_value={"sync": 3}) as mock_sync:
            rv = self.client.post("/api/bling/situacoes/sincronizar")
            self.assertEqual(rv.status_code, 200)
            mock_sync.assert_called_once()

    def test_situacoes_criar_route(self):
        with patch("routes.integrations.criar_situacao", return_value={"data": {"id": 99}}) as mock_criar:
            rv = self.client.post("/api/bling/situacoes", json={"nome": "Em Análise", "cor": "0000FF"})
            self.assertEqual(rv.status_code, 200)
            mock_criar.assert_called_once_with({"nome": "Em Análise", "cor": "0000FF"})

    def test_situacoes_atualizar_route(self):
        with patch("routes.integrations.atualizar_situacao", return_value={"data": {}}) as mock_atualizar:
            rv = self.client.put("/api/bling/situacoes/42", json={"nome": "Pago"})
            self.assertEqual(rv.status_code, 200)
            mock_atualizar.assert_called_once_with(42, {"nome": "Pago"})

    def test_situacoes_deletar_route(self):
        with patch("routes.integrations.deletar_situacao", return_value={}) as mock_deletar:
            rv = self.client.delete("/api/bling/situacoes/42")
            self.assertEqual(rv.status_code, 200)
            mock_deletar.assert_called_once_with(42)
```

Igual à Task 1 do plano anterior (Fase 2): o `test_situacoes_listar_route` já usa
`assertEqual(200)` direto — não `assertIn([200,500])` — porque a rota GET vai garantir a
tabela via `ensure_bling_situacoes_table` antes do SELECT, exatamente a lição aprendida na
revisão final do plano anterior.

- [ ] **Step 3: Rodar e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py -k "situacoes" -v`
Expected: FAIL — 404 (rotas não existem ainda).

- [ ] **Step 4: Adicionar os imports e as rotas**

Em `hermes_agents/routes/integrations.py`, adicionar ao bloco de import de `bling_erp` do
`bling_bp`: `sincronizar_situacoes_bling, ensure_bling_situacoes_table, criar_situacao,
atualizar_situacao, deletar_situacao`.

Logo após as rotas de canais (procure `def api_sincronizar_canais`), adicionar:

```python
@bling_bp.route("/situacoes")
def api_situacoes():
    async def _go():
        db = await get_db()
        await ensure_bling_situacoes_table(db)
        rows = await db.fetch("SELECT id, bling_id, nome, cor, modulo FROM bling_situacoes ORDER BY nome")
        return [dict(r) for r in rows]
    try:
        return jsonify(run_async(_go()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bling_bp.route("/situacoes/sincronizar", methods=["POST"])
def api_sincronizar_situacoes():
    return jsonify(sincronizar_situacoes_bling())


@bling_bp.route("/situacoes", methods=["POST"])
def api_criar_situacao():
    dados = request.get_json(silent=True) or {}
    return jsonify(criar_situacao(dados))


@bling_bp.route("/situacoes/<int:id_situacao>", methods=["PUT"])
def api_atualizar_situacao(id_situacao):
    dados = request.get_json(silent=True) or {}
    return jsonify(atualizar_situacao(id_situacao, dados))


@bling_bp.route("/situacoes/<int:id_situacao>", methods=["DELETE"])
def api_deletar_situacao(id_situacao):
    return jsonify(deletar_situacao(id_situacao))
```

Nota: as rotas de escrita (POST/PUT/DELETE) propagam pro Bling mas não atualizam o cache local
`bling_situacoes` nesta task — o próximo `POST /situacoes/sincronizar` (manual ou futuro job)
reflete a mudança no cache. Isso é intencional pra manter esta task pequena e symmetric ao
padrão já usado em `criar_produto`/`atualizar_produto`/`deletar_produto`, que também não
atualizam nenhum cache local. Se o usuário quiser sync automático pós-escrita depois, é uma
task separada.

- [ ] **Step 5: Rodar e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py -k "situacoes" -v`
Expected: PASS

- [ ] **Step 6: Rodar a suíte completa**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes (RH, compras, RBAC lojas), nenhuma nova.

- [ ] **Step 7: Commit**

```bash
git add hermes_agents/bling_erp.py hermes_agents/routes/integrations.py hermes_agents/tests/test_bling_routes.py
git commit -m "feat: CRUD de situacoes Bling via HTTP (GET/POST/PUT/DELETE /api/bling/situacoes)"
```

---

### Task 4: Regressão final

**Files:**
- Test: `hermes_agents/tests/test_bling_routes.py`, `hermes_agents/tests/test_bling_erp.py`

- [ ] **Step 1: Rodar toda a suíte Bling**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py tests/test_bling_erp.py -v`
Expected: todos PASS.

- [ ] **Step 2: Rodar a suíte inteira do projeto**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes documentadas (RH endpoints, compras segurança, RBAC
lojas), nenhuma nova — confirme os nomes exatos e compare com essa lista antes de seguir.

- [ ] **Step 3: Smoke test de import da app completa**

Run: `cd hermes_agents && python -c "import athena_bridge"`
Expected: importa sem erro.

- [ ] **Step 4: Confirmar que `atualizar_produto` (não tocado por este plano, mas afetado pelo
  fix da Task 1) continua funcionando corretamente**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py -k "produto" -v`
Expected: todos PASS — o fix do bug de PUT sem corpo não pode ter quebrado nenhum teste
existente de produto.

- [ ] **Step 5: Commit (se houver qualquer ajuste feito nesta task)**

```bash
git add -A -- ':!hermes_agents/storage' ':!hermes_agents/uploads'
git commit -m "test: regressao final CRUD de situacoes Bling" --allow-empty
```

(o `-- ':!hermes_agents/storage' ':!hermes_agents/uploads'` evita repetir o erro já corrigido
no plano anterior, de acidentalmente versionar artefatos de teste gerados em disco — confirme
com `git status --porcelain` antes do commit que nada além de código-fonte real está staged).
