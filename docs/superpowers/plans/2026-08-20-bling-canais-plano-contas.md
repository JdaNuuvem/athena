# Bling — Canais e Contas Contábeis (Plano 2/N) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar os dois recursos "de leitura simples" do módulo Bling ainda não
cobertos: sync de Lojas/Canais de venda do Bling (conceito novo, tabela própria) e sync de
Contas Contábeis / plano de contas (upsert na tabela `fin_plano_contas` já existente no
módulo financeiro).

**Architecture:** Segue exatamente os padrões já estabelecidos no código: wrappers de API em
`bling_erp.py` (como `listar_categorias`), função de sync fazendo upsert por `bling_id` (como
`sincronizar_contas_receber_bling` em `core/fiscal.py`), rotas em `bling_bp`
(`routes/integrations.py`, prefixo `/api/bling`). Canais ganha tabela nova `bling_canais`
(conceito Bling-específico, sem equivalente no Athena). Contas contábeis faz upsert direto em
`fin_plano_contas`, adicionando coluna `bling_id` a ela.

**Tech Stack:** Flask (Python), pytest, requests (já usado em `bling_erp.py` pra chamar a API
Bling v3).

**Spec:** `docs/superpowers/specs/2026-08-20-modulo-bling-design.md` (seções "Lojas/Canais
Bling (novo)" e "Contas contábeis / plano de contas (novo)")

## Global Constraints

- Todo upsert por `bling_id` deve ser idempotente (rodar o sync duas vezes não duplica
  registros) — seguir exatamente o padrão de `sincronizar_contas_receber_bling`
  (`core/fiscal.py:635-675`): `SELECT id FROM tabela WHERE bling_id = $1`, `UPDATE` se existe,
  `INSERT` se não.
- Nenhuma tabela existente perde dado: a coluna nova em `fin_plano_contas` (`bling_id`) usa
  `ADD COLUMN IF NOT EXISTS`, preservando as 11 linhas de seed já existentes
  (`core/financeiro.py:150-153`).
- TDD: escrever teste, confirmar falha, implementar, confirmar passa, para cada função nova.
- Rodar a suíte completa (`cd hermes_agents && python -m pytest tests/ -q`) ao final de cada
  task antes de commitar. Baseline conhecido nesta branch: 8 falhas pré-existentes alheias a
  Bling (RH endpoints, compras segurança, RBAC lojas) — não bloqueiam, mas nenhuma NOVA falha
  é aceitável.

---

### Task 1: Wrappers de API Bling — Lojas/Canais e Contas Contábeis

Adiciona em `bling_erp.py` os wrappers HTTP pros dois recursos novos, seguindo exatamente o
padrão de `listar_categorias` (linha 168): uma função fina que chama `_request(endpoint,
params)`.

**Files:**
- Modify: `hermes_agents/bling_erp.py` (adicionar 2 funções novas, logo após a seção
  `# ── Categorias de Produtos ──`, linha ~172)
- Test: `hermes_agents/tests/test_bling_erp.py`

**Interfaces:**
- Consumes: `bling_erp._request(endpoint: str, params: dict = None, method: str = "GET") -> dict`
  (já existe, `bling_erp.py:109`, sem mudanças)
- Produces:
  - `bling_erp.listar_lojas(pagina: int = 1, limite: int = 100) -> dict`
  - `bling_erp.listar_contas_contabeis(pagina: int = 1, limite: int = 100) -> dict`

- [ ] **Step 1: Escrever os testes**

Adicionar a `hermes_agents/tests/test_bling_erp.py` (na classe de teste existente que cobre
funções de listagem simples — procure por `def test_listar_categorias` ou equivalente pra usar
o mesmo padrão de mock de `_request`):

```python
    def test_listar_lojas_chama_endpoint_correto(self):
        with patch("bling_erp._request", return_value={"data": []}) as mock_request:
            bling_erp.listar_lojas(pagina=2, limite=50)
            mock_request.assert_called_once_with("lojas", {"pagina": 2, "limite": 50})

    def test_listar_contas_contabeis_chama_endpoint_correto(self):
        with patch("bling_erp._request", return_value={"data": []}) as mock_request:
            bling_erp.listar_contas_contabeis(pagina=1, limite=100)
            mock_request.assert_called_once_with("contas/contabeis", {"pagina": 1, "limite": 100})
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py -k "test_listar_lojas_chama_endpoint_correto or test_listar_contas_contabeis_chama_endpoint_correto" -v`
Expected: FAIL — `AttributeError: module 'bling_erp' has no attribute 'listar_lojas'`.

- [ ] **Step 3: Implementar as funções**

Em `hermes_agents/bling_erp.py`, logo após `get_categoria` (linha 172), adicionar:

```python
# ── Lojas / Canais de Venda ──

def listar_lojas(pagina: int = 1, limite: int = 100) -> dict:
    return _request("lojas", {"pagina": pagina, "limite": limite})

# ── Contas Contábeis (Plano de Contas) ──

def listar_contas_contabeis(pagina: int = 1, limite: int = 100) -> dict:
    return _request("contas/contabeis", {"pagina": pagina, "limite": limite})
```

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py -k "test_listar_lojas_chama_endpoint_correto or test_listar_contas_contabeis_chama_endpoint_correto" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/bling_erp.py hermes_agents/tests/test_bling_erp.py
git commit -m "feat: wrappers de API Bling para lojas/canais e contas contabeis"
```

---

### Task 2: Sync de Canais Bling (tabela nova `bling_canais`)

Cria a tabela `bling_canais` e a função de sync que faz upsert por `bling_id`, seguindo o
padrão de `sincronizar_contas_receber_bling` (`core/fiscal.py:635`). Coloca a função em
`bling_erp.py`, junto de `sincronizar_produtos` (linha ~376), já que canal é um conceito
Bling-específico sem equivalente no Athena — não pertence a nenhum módulo `core/*` existente.

**Files:**
- Modify: `hermes_agents/bling_erp.py` (adicionar `sincronizar_canais_bling`)
- Test: `hermes_agents/tests/test_bling_erp.py`

**Interfaces:**
- Consumes: `bling_erp.listar_lojas(pagina, limite) -> dict` (Task 1),
  `bling_erp.get_access_token() -> str`, `bling_erp.get_auth_url() -> str` (já existem)
- Produces: `bling_erp.sincronizar_canais_bling(pagina: int = 1, limite: int = 100) -> dict`
  — retorna `{"sync": int, "message": str}` em caso de sucesso vazio, `{"error": str,
  "auth_url": str}` se não autenticado, ou `{"sync": int}` com o total de canais
  sincronizados.

- [ ] **Step 1: Escrever o teste (RED)**

Adicionar a `hermes_agents/tests/test_bling_erp.py`:

```python
    def test_sincronizar_canais_bling_cria_tabela_e_faz_upsert(self):
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = None  # nenhum canal existente ainda
        with patch("bling_erp.get_access_token", return_value="tok"), \
             patch("bling_erp.get_db", new=AsyncMock(return_value=fake_db)), \
             patch("bling_erp.listar_lojas", return_value={"data": [
                 {"id": 111, "descricao": "Loja Virtual", "situacao": "A"},
             ]}):
            resultado = bling_erp.sincronizar_canais_bling()
        self.assertEqual(resultado["sync"], 1)
        # confirma que criou a tabela e fez INSERT (nao UPDATE, ja que fetchval retornou None)
        sqls_executados = [c.args[0] for c in fake_db.execute.call_args_list]
        self.assertTrue(any("CREATE TABLE IF NOT EXISTS bling_canais" in s for s in sqls_executados))
        self.assertTrue(any("INSERT INTO bling_canais" in s for s in sqls_executados))
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py::TestBlingErp::test_sincronizar_canais_bling_cria_tabela_e_faz_upsert -v`
(troque `TestBlingErp` pelo nome real da classe de teste se for diferente, confirme no arquivo)
Expected: FAIL — `AttributeError: module 'bling_erp' has no attribute 'sincronizar_canais_bling'`.

- [ ] **Step 3: Implementar a função**

Em `hermes_agents/bling_erp.py`, adicionar logo após `sincronizar_produtos` (procure o fim da
função, marcado por `return {"sincronizados": 0, "erro": str(e)}` dentro de um `except`):

```python
def sincronizar_canais_bling(pagina: int = 1, limite: int = 100) -> dict:
    """Sync de lojas/canais de venda cadastrados dentro do Bling (conceito interno
    do Bling — ex. 'Loja Virtual', 'Balcão' — distinto da tabela `lojas` do Athena,
    que ja' mapeia depositos fisicos via lojas.bling_id)."""
    token = get_access_token()
    if not token:
        return {"error": "Bling nao autenticado", "auth_url": get_auth_url()}
    r = listar_lojas(pagina, limite)
    if r.get("error"):
        return r
    dados = r.get("data", [])
    if not dados:
        return {"sync": 0, "message": "sem dados"}

    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS bling_canais (
            id SERIAL PRIMARY KEY, bling_id BIGINT UNIQUE, nome VARCHAR(200),
            situacao VARCHAR(20), created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW())""")
        total = 0
        for canal in dados:
            try:
                bling_id = canal.get("id")
                if not bling_id:
                    continue
                nome = canal.get("descricao", "")
                situacao = str(canal.get("situacao", ""))
                existing = await db.fetchval("SELECT id FROM bling_canais WHERE bling_id = $1", bling_id)
                if existing:
                    await db.execute(
                        "UPDATE bling_canais SET nome=$1, situacao=$2, updated_at=NOW() WHERE bling_id=$3",
                        nome, situacao, bling_id)
                else:
                    await db.execute(
                        "INSERT INTO bling_canais (bling_id, nome, situacao) VALUES ($1,$2,$3)",
                        bling_id, nome, situacao)
                total += 1
            except Exception as e:
                log(AGENT, f"Erro ao sincronizar canal {canal.get('id')}: {e}")
        return total

    try:
        total = run_async(_go())
        return {"sync": total}
    except Exception as e:
        return {"error": str(e)}
```

Confirme que `get_db`, `run_async` e `log` já estão importados no topo de `bling_erp.py` (o
arquivo já os usa em outras funções — se algum não estiver, adicione ao bloco de import
existente em vez de importar localmente dentro da função, seguindo o estilo do resto do
arquivo).

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py::TestBlingErp::test_sincronizar_canais_bling_cria_tabela_e_faz_upsert -v`
Expected: PASS

- [ ] **Step 5: Rodar a suíte completa de testes Bling**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py tests/test_bling_routes.py -v`
Expected: todos PASS.

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/bling_erp.py hermes_agents/tests/test_bling_erp.py
git commit -m "feat: sync de canais Bling (tabela bling_canais nova)"
```

---

### Task 3: Rota HTTP para Canais em `bling_bp`

Expõe o sync e a listagem local de canais como rota HTTP, seguindo o padrão de
`/categorias`/`/produtos/sincronizar` já existentes em `bling_bp`.

**Files:**
- Modify: `hermes_agents/routes/integrations.py` (bloco `bling_bp`, logo após a rota
  `/categorias`, linha ~650)
- Test: `hermes_agents/tests/test_bling_routes.py`

**Interfaces:**
- Consumes: `bling_erp.sincronizar_canais_bling(pagina, limite) -> dict` (Task 2)
- Produces: `GET /api/bling/canais` (lista local, lida de `bling_canais`),
  `POST /api/bling/canais/sincronizar` (dispara o sync)

- [ ] **Step 1: Escrever os testes**

Adicionar a `hermes_agents/tests/test_bling_routes.py`:

```python
    def test_canais_sincronizar_route(self):
        with patch("routes.integrations.sincronizar_canais_bling", return_value={"sync": 2}) as mock_sync:
            rv = self.client.post("/api/bling/canais/sincronizar")
            self.assertEqual(rv.status_code, 200)
            data = json.loads(rv.data)
            self.assertEqual(data["sync"], 2)
            mock_sync.assert_called_once()

    def test_canais_listar_route(self):
        rv = self.client.get("/api/bling/canais")
        self.assertIn(rv.status_code, [200, 500])
```

(o segundo teste aceita 500 porque a app de teste desta classe não tem banco real conectado —
o mesmo padrão já usado em `test_produtos_route`/`test_depositos_route` no mesmo arquivo;
confirme lendo essas duas funções antes de escrever, pra manter consistência.)

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py -k "test_canais_sincronizar_route or test_canais_listar_route" -v`
Expected: FAIL — 404 (rota não existe ainda).

- [ ] **Step 3: Adicionar o import e as rotas**

Em `hermes_agents/routes/integrations.py`, no bloco de import de `bling_erp` do `bling_bp`
(procure a linha que já foi editada no plano anterior, algo como `from bling_erp import (...
sincronizar_produtos, ...)`), adicionar `sincronizar_canais_bling` à lista de nomes
importados.

Depois, logo após a rota `/categorias` (a que tem `def api_categorias():`), adicionar:

```python
@bling_bp.route("/canais")
def api_canais():
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT id, bling_id, nome, situacao FROM bling_canais ORDER BY nome")
        return [dict(r) for r in rows]
    try:
        return jsonify(run_async(_go()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bling_bp.route("/canais/sincronizar", methods=["POST"])
def api_sincronizar_canais():
    return jsonify(sincronizar_canais_bling())
```

Confirme que `get_db` e `run_async` já estão importados no topo de
`hermes_agents/routes/integrations.py` (o arquivo já os usa em outras rotas locais — se não
estiverem, adicione ao import existente de `core`).

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py -k "test_canais_sincronizar_route or test_canais_listar_route" -v`
Expected: PASS

- [ ] **Step 5: Rodar a suíte completa**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes (RH, compras, RBAC lojas), nenhuma nova.

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/routes/integrations.py hermes_agents/tests/test_bling_routes.py
git commit -m "feat: rotas GET/POST /api/bling/canais"
```

---

### Task 4: Sync de Contas Contábeis → `fin_plano_contas`

Adiciona a coluna `bling_id` em `fin_plano_contas` e a função de sync que faz upsert nela,
seguindo o mesmo padrão de `sincronizar_contas_receber_bling`. Coloca a função em
`core/financeiro.py`, já que é esse módulo que possui `fin_plano_contas`.

**Files:**
- Modify: `hermes_agents/core/financeiro.py` (migração da coluna em `_ensure_tables` +
  função de sync nova)
- Test: `hermes_agents/tests/test_bling_erp.py` (ou um novo `tests/test_financeiro.py` se esse
  arquivo já existir com testes de `core/financeiro.py` — confirme antes de escolher)

**Interfaces:**
- Consumes: `bling_erp.listar_contas_contabeis(pagina, limite) -> dict` (Task 1)
- Produces: `core.financeiro.sincronizar_plano_contas_bling(pagina: int = 1, limite: int = 100) -> dict`

- [ ] **Step 1: Escrever o teste da migração de coluna**

Primeiro, confirme se existe `hermes_agents/tests/test_financeiro.py`. Rode:

Run: `cd hermes_agents && python -c "import os; print(os.path.exists('tests/test_financeiro.py'))"`

Se `True`, adicione os testes deste task nesse arquivo, seguindo o padrão de setup que ele já
usa. Se `False`, crie `hermes_agents/tests/test_financeiro.py` seguindo o padrão de mock de
`get_db`/`run_async` já usado em `tests/test_bling_erp.py` (importe `unittest`,
`unittest.mock.patch/AsyncMock`, e o módulo `core.financeiro`).

Teste a escrever:

```python
    def test_sincronizar_plano_contas_bling_faz_upsert_por_bling_id(self):
        fake_db = AsyncMock()
        fake_db.fetchval.side_effect = [None, None]  # 1a chamada: checa coluna; 2a: checa conta existente
        with patch("core.financeiro.get_access_token", return_value="tok"), \
             patch("core.financeiro.get_db", new=AsyncMock(return_value=fake_db)), \
             patch("core.financeiro.listar_contas_contabeis", return_value={"data": [
                 {"id": 999, "descricao": "Receita de Vendas Online", "tipo": "R"},
             ]}):
            resultado = core_financeiro.sincronizar_plano_contas_bling()
        self.assertEqual(resultado["sync"], 1)
        sqls_executados = [c.args[0] for c in fake_db.execute.call_args_list]
        self.assertTrue(any("ALTER TABLE fin_plano_contas ADD COLUMN" in s for s in sqls_executados))
        self.assertTrue(any("INSERT INTO fin_plano_contas" in s for s in sqls_executados))
```

Ajuste os imports/mocks (`patch("core.financeiro....")`) para o caminho real de import usado
no arquivo de teste que você escolheu ou criou no passo anterior — confirme lendo o topo de
`core/financeiro.py` pra saber se `get_access_token`/`listar_contas_contabeis` precisam ser
importados de `bling_erp` dentro da própria função nova (siga o padrão de
`sincronizar_contas_receber_bling` em `core/fiscal.py:637`, que importa `bling_erp` localmente
dentro da função) — ajuste os `patch(...)` do teste pra baterem com esse import local
(`patch("bling_erp.get_access_token", ...)` em vez de `patch("core.financeiro....")`, se for
esse o caso).

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_financeiro.py -k test_sincronizar_plano_contas_bling_faz_upsert_por_bling_id -v`
Expected: FAIL — `AttributeError` (função ainda não existe).

- [ ] **Step 3: Implementar a função**

Em `hermes_agents/core/financeiro.py`, adicionar (posição sugerida: final do arquivo, ou perto
de outras funções de sync se o arquivo já tiver alguma — confirme lendo o arquivo inteiro
antes de decidir onde encaixar, mantendo o restante do arquivo coeso):

```python
def sincronizar_plano_contas_bling(pagina: int = 1, limite: int = 100) -> dict:
    """Sync de contas contabeis do Bling -> fin_plano_contas (upsert por bling_id,
    preserva o plano de contas seed ja existente)."""
    from bling_erp import listar_contas_contabeis, get_access_token, get_auth_url
    token = get_access_token()
    if not token:
        return {"error": "Bling nao autenticado", "auth_url": get_auth_url()}
    r = listar_contas_contabeis(pagina, limite)
    if r.get("error"):
        return r
    dados = r.get("data", [])
    if not dados:
        return {"sync": 0, "message": "sem dados"}

    async def _go():
        db = await get_db()
        exists = await db.fetchval(
            "SELECT column_name FROM information_schema.columns WHERE table_name='fin_plano_contas' AND column_name='bling_id'")
        if not exists:
            await db.execute("ALTER TABLE fin_plano_contas ADD COLUMN IF NOT EXISTS bling_id BIGINT")
        total = 0
        for conta in dados:
            try:
                bling_id = conta.get("id")
                if not bling_id:
                    continue
                nome = conta.get("descricao", "")
                tipo_raw = conta.get("tipo", "")
                natureza = "devedora" if tipo_raw == "D" else "credora"
                existing = await db.fetchval("SELECT id FROM fin_plano_contas WHERE bling_id = $1", bling_id)
                if existing:
                    await db.execute(
                        "UPDATE fin_plano_contas SET nome=$1, natureza=$2 WHERE bling_id=$3",
                        nome, natureza, bling_id)
                else:
                    await db.execute(
                        "INSERT INTO fin_plano_contas (codigo, nome, tipo, natureza, bling_id) VALUES ($1,$2,$3,$4,$5)",
                        f"bling-{bling_id}", nome, "analitica", natureza, bling_id)
                total += 1
            except Exception as e:
                log("Financeiro", f"Erro ao sincronizar conta contabil {conta.get('id')}: {e}")
        return total

    try:
        total = run_async(_go())
        return {"sync": total}
    except Exception as e:
        return {"error": str(e)}
```

Confirme que `get_db`, `run_async` e `log` já estão importados no topo de
`core/financeiro.py` (o arquivo já os usa nas funções `_ensure_tables`/`_list`/etc — se algum
não estiver disponível no escopo do módulo, adicione ao import existente).

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_financeiro.py -k test_sincronizar_plano_contas_bling_faz_upsert_por_bling_id -v`
Expected: PASS

- [ ] **Step 5: Rodar a suíte completa**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes, nenhuma nova.

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/core/financeiro.py hermes_agents/tests/test_financeiro.py
git commit -m "feat: sync de contas contabeis Bling em fin_plano_contas (coluna bling_id nova)"
```

---

### Task 5: Rota HTTP para Contas Contábeis em `bling_bp`

**Files:**
- Modify: `hermes_agents/routes/integrations.py` (bloco `bling_bp`)
- Test: `hermes_agents/tests/test_bling_routes.py`

**Interfaces:**
- Consumes: `core.financeiro.sincronizar_plano_contas_bling(pagina, limite) -> dict` (Task 4)
- Produces: `GET /api/bling/plano-contas` (lista local de `fin_plano_contas`),
  `POST /api/bling/plano-contas/sincronizar`

- [ ] **Step 1: Escrever os testes**

Adicionar a `hermes_agents/tests/test_bling_routes.py`:

```python
    def test_plano_contas_sincronizar_route(self):
        with patch("routes.integrations.sincronizar_plano_contas_bling", return_value={"sync": 5}) as mock_sync:
            rv = self.client.post("/api/bling/plano-contas/sincronizar")
            self.assertEqual(rv.status_code, 200)
            data = json.loads(rv.data)
            self.assertEqual(data["sync"], 5)
            mock_sync.assert_called_once()

    def test_plano_contas_listar_route(self):
        rv = self.client.get("/api/bling/plano-contas")
        self.assertIn(rv.status_code, [200, 500])
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py -k "test_plano_contas_sincronizar_route or test_plano_contas_listar_route" -v`
Expected: FAIL — 404.

- [ ] **Step 3: Adicionar o import e as rotas**

Em `hermes_agents/routes/integrations.py`, adicionar `from core.financeiro import
sincronizar_plano_contas_bling` (import local dedicado, seguindo o padrão já usado em outras
rotas que consomem `core.vendas`/`core.fiscal` no mesmo arquivo — procure por `from
core.fiscal import` como referência de estilo).

Logo após as rotas de canais (Task 3), adicionar:

```python
@bling_bp.route("/plano-contas")
def api_plano_contas():
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT id, codigo, nome, tipo, natureza, conta_pai_id, bling_id FROM fin_plano_contas ORDER BY codigo")
        return [dict(r) for r in rows]
    try:
        return jsonify(run_async(_go()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bling_bp.route("/plano-contas/sincronizar", methods=["POST"])
def api_sincronizar_plano_contas():
    return jsonify(sincronizar_plano_contas_bling())
```

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py -k "test_plano_contas_sincronizar_route or test_plano_contas_listar_route" -v`
Expected: PASS

- [ ] **Step 5: Rodar a suíte completa**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes, nenhuma nova.

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/routes/integrations.py hermes_agents/tests/test_bling_routes.py
git commit -m "feat: rotas GET/POST /api/bling/plano-contas"
```

---

### Task 6: Regressão final

**Files:**
- Test: `hermes_agents/tests/test_bling_routes.py`, `hermes_agents/tests/test_bling_erp.py`,
  `hermes_agents/tests/test_financeiro.py`

- [ ] **Step 1: Rodar toda a suíte Bling + financeiro**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py tests/test_bling_erp.py tests/test_financeiro.py -v`
Expected: todos PASS.

- [ ] **Step 2: Rodar a suíte inteira do projeto**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes documentadas (RH endpoints, compras segurança, RBAC
lojas), nenhuma nova — confirme os nomes exatos das 8 falhas e compare com essa lista antes de
seguir.

- [ ] **Step 3: Smoke test de import da app completa**

Run: `cd hermes_agents && python -c "import athena_bridge"`
Expected: importa sem erro.

- [ ] **Step 4: Commit (se houver qualquer ajuste feito nesta task)**

```bash
git add -A
git commit -m "test: regressao final canais/plano de contas Bling" --allow-empty
```
