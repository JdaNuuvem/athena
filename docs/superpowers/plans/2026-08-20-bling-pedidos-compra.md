# Bling — Pedidos de Compra (Plano 4a/N) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sincronizar Pedidos de Compra do Bling pro módulo de Compras já existente do Athena
(`core/compras.py` — `compras_pedidos`/`compras_itens`), com upsert idempotente por `bling_id`
e resolução automática de fornecedor por documento.

**Architecture:** Achado importante durante o levantamento: `compras_pedidos` e `compras_itens`
já existem em produção, parte de um módulo de Compras completo (fornecedores, solicitações,
cotações, recebimentos, notas de entrada — `core/compras.py`). O spec original do módulo Bling
previa "tabelas novas" — isso está desatualizado; a integração correta é sincronizar PRA DENTRO
dessas tabelas já existentes, adicionando só a coluna `bling_id` que falta, seguindo o mesmo
padrão de `vendas_pedidos.bling_id` (módulo de Vendas) e o padrão de resolução de fornecedor por
documento já usado em `core/entidades.migrar_fornecedores_compras`. A ação de "marcar como
recebido" no Bling fica desacoplada do fluxo de recebimento próprio do Athena
(`compras_recebimentos`/`confirmar_recebimento`) — só aciona o lado Bling, sem redesenhar o
fluxo local de conferência.

**Tech Stack:** Flask (Python), pytest, requests.

**Spec:** `docs/superpowers/specs/2026-08-20-modulo-bling-design.md` (seção "Pedidos de compra
(novo)" — nota: a seção do spec que fala em "tabelas novas compras_pedidos/compras_itens" está
desatualizada, ver Architecture acima; este plano é a versão corrigida)

## Global Constraints

- `compras_pedidos`/`compras_itens` são tabelas de produção já em uso pelo módulo de Compras
  manual do Athena — nenhuma coluna ou linha existente pode ser alterada de forma destrutiva.
  Toda migração usa `ADD COLUMN IF NOT EXISTS`.
- Upsert por `bling_id` idempotente (rodar o sync duas vezes não duplica pedido).
- TDD: escrever teste, confirmar falha, implementar, confirmar passa, para cada função nova.
- Rodar a suíte completa (`cd hermes_agents && python -m pytest tests/ -q`) ao final de cada
  task antes de commitar. Baseline conhecido: 8 falhas pré-existentes alheias a Bling (RH
  endpoints, compras segurança, RBAC lojas) — não bloqueiam, mas nenhuma NOVA falha é aceitável
  (atenção especial aqui: este plano toca justamente o módulo de Compras, então rodar
  `tests/test_compras_seguranca.py` inteiro a cada task é obrigatório, não só a suíte Bling).

---

### Task 1: Wrappers de API Bling para Pedidos de Compra

Adiciona em `bling_erp.py` os wrappers HTTP: listar, detalhar, e marcar como recebido.

**Files:**
- Modify: `hermes_agents/bling_erp.py` (adicionar 3 funções novas, logo após a seção
  `# ── Detalhe do Pedido (com itens, frete, parcelas) ──`, que cobre pedidos de VENDA — a
  seção nova de compra fica logo depois, separada)
- Test: `hermes_agents/tests/test_bling_erp.py`

**Interfaces:**
- Produces:
  - `bling_erp.listar_pedidos_compra(pagina: int = 1, limite: int = 100) -> dict`
  - `bling_erp.get_pedido_compra_detalhe(id_pedido: int) -> dict`
  - `bling_erp.marcar_pedido_compra_recebido(id_pedido: int) -> dict`

- [ ] **Step 1: Escrever os testes**

Adicionar a `hermes_agents/tests/test_bling_erp.py`:

```python
    def test_listar_pedidos_compra_chama_endpoint_correto(self):
        with patch("bling_erp._request", return_value={"data": []}) as mock_request:
            bling_erp.listar_pedidos_compra(pagina=2, limite=50)
            mock_request.assert_called_once_with("pedidos/compras", {"pagina": 2, "limite": 50})

    def test_get_pedido_compra_detalhe_chama_endpoint_correto(self):
        with patch("bling_erp._request", return_value={"data": {}}) as mock_request:
            bling_erp.get_pedido_compra_detalhe(123)
            mock_request.assert_called_once_with("pedidos/compras/123")

    def test_marcar_pedido_compra_recebido_chama_endpoint_correto(self):
        with patch("bling_erp._request", return_value={"data": {}}) as mock_request:
            bling_erp.marcar_pedido_compra_recebido(123)
            mock_request.assert_called_once_with("pedidos/compras/123/receber", {}, method="POST")
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py -k "pedido_compra" -v`
Expected: FAIL — `AttributeError`.

- [ ] **Step 3: Implementar os wrappers**

Em `hermes_agents/bling_erp.py`, adicionar (posição sugerida: logo após `get_pedido_detalhe`,
mantendo a seção de vendas intacta):

```python
# ── Pedidos de Compra ──

def listar_pedidos_compra(pagina: int = 1, limite: int = 100) -> dict:
    return _request("pedidos/compras", {"pagina": pagina, "limite": limite})

def get_pedido_compra_detalhe(id_pedido: int) -> dict:
    """Retorna detalhes completos do pedido de compra: itens, fornecedor, condicoes."""
    return _request(f"pedidos/compras/{id_pedido}")

def marcar_pedido_compra_recebido(id_pedido: int) -> dict:
    """Marca o pedido de compra como recebido no Bling via POST /pedidos/compras/{id}/receber."""
    return _request(f"pedidos/compras/{id_pedido}/receber", {}, method="POST")
```

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py -k "pedido_compra" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/bling_erp.py hermes_agents/tests/test_bling_erp.py
git commit -m "feat: wrappers de API Bling para pedidos de compra"
```

---

### Task 2: Coluna `bling_id` em `compras_pedidos`/`compras_itens` + sync com resolução de fornecedor

Adiciona a coluna `bling_id` (idempotente, `ADD COLUMN IF NOT EXISTS`) em `compras_pedidos` e
`compras_itens`, e implementa `sincronizar_pedidos_compra_bling()` em `core/compras.py`. A
função resolve o fornecedor do pedido Bling contra `cad_fornecedores` por documento (mesmo
padrão de `core/entidades.migrar_fornecedores_compras`) — cria o fornecedor em
`cad_fornecedores` se ele ainda não existir, em vez de deixar `fornecedor_id` nulo.

**Files:**
- Modify: `hermes_agents/core/compras.py` (`_ensure_tables` ganha as colunas novas; nova
  função `sincronizar_pedidos_compra_bling`)
- Test: `hermes_agents/tests/test_compras_seguranca.py` ou um novo
  `hermes_agents/tests/test_compras_bling.py` (confirme se já existe um arquivo de teste mais
  apropriado pra `core/compras.py` rodando `python -c "import os; print(os.path.exists('tests/test_compras.py'))"`
  antes de decidir onde colocar — se não existir nenhum, crie
  `hermes_agents/tests/test_compras_bling.py` dedicado)

**Interfaces:**
- Consumes: `bling_erp.listar_pedidos_compra`, `bling_erp.get_pedido_compra_detalhe`,
  `bling_erp.get_access_token`, `bling_erp.get_auth_url` (Task 1 + já existentes)
- Produces: `core.compras.sincronizar_pedidos_compra_bling(pagina: int = 1, limite: int = 100) -> dict`

- [ ] **Step 1: Escrever o teste (RED)**

Criar/adicionar no arquivo de teste escolhido no Step anterior:

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unittest
from unittest.mock import patch, AsyncMock

from core import compras as core_compras


class TestSincronizarPedidosCompraBling(unittest.TestCase):
    def test_resolve_fornecedor_existente_por_documento_e_faz_upsert(self):
        fake_db = AsyncMock()
        # 1a chamada: checa se coluna bling_id existe em compras_pedidos -> None (nao existe, sera criada)
        # 2a chamada: busca fornecedor por documento -> encontra id 7
        # 3a chamada: busca pedido existente por bling_id -> None (novo)
        fake_db.fetchval.side_effect = [None, 7, None]
        fake_db.fetchrow.return_value = None
        with patch("core.compras.get_access_token", return_value="tok"), \
             patch("core.compras.get_db", new=AsyncMock(return_value=fake_db)), \
             patch("core.compras.get_pedido_compra_detalhe", return_value={"data": {
                 "id": 555, "numero": "PC-001", "total": 1200.50,
                 "situacao": {"valor": 6, "nome": "Em andamento"},
                 "data": "2026-08-20", "dataPrevista": "2026-08-27",
                 "fornecedor": {"nome": "Fornecedor XYZ", "numeroDocumento": "12.345.678/0001-99"},
                 "itens": [{"codigo": "SKU-1", "descricao": "Produto 1", "quantidade": 10, "valor": 100.0}],
             }}), \
             patch("core.compras.listar_pedidos_compra", return_value={"data": [{"id": 555}]}):
            resultado = core_compras.sincronizar_pedidos_compra_bling()
        self.assertEqual(resultado["sync"], 1)
        sqls_executados = [c.args[0] for c in fake_db.execute.call_args_list]
        self.assertTrue(any("ALTER TABLE compras_pedidos ADD COLUMN" in s for s in sqls_executados))
        self.assertTrue(any("INSERT INTO compras_pedidos" in s for s in sqls_executados))
        self.assertTrue(any("INSERT INTO compras_itens" in s for s in sqls_executados))
```

Ajuste os `side_effect`/mocks conforme a ordem real das chamadas `fetchval`/`fetchrow` que sua
implementação usar no Step 3 — o teste acima é o esqueleto do comportamento esperado, não uma
receita rígida de mock; rode e ajuste a ordem dos `side_effect` até bater com a implementação
real (é normal precisar de 1-2 iterações aqui, isso ainda é a fase RED do TDD).

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_compras_bling.py -v` (ou o caminho do
arquivo escolhido)
Expected: FAIL — `AttributeError: module 'core.compras' has no attribute 'sincronizar_pedidos_compra_bling'`.

- [ ] **Step 3: Implementar a função**

Em `hermes_agents/core/compras.py`, adicionar as colunas novas dentro de `_ensure_tables`,
logo após o bloco que já adiciona `loja_id` em `compras_pedidos` (linhas ~41-48):

```python
        try: await db.execute("ALTER TABLE compras_pedidos ADD COLUMN IF NOT EXISTS bling_id BIGINT")
        except Exception: pass
        try: await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_compras_pedidos_bling_id ON compras_pedidos (bling_id) WHERE bling_id IS NOT NULL")
        except Exception: pass
        try: await db.execute("ALTER TABLE compras_itens ADD COLUMN IF NOT EXISTS bling_item_id BIGINT")
        except Exception: pass
```

Depois, adicionar a função de sync (posição sugerida: após `confirmar_recebimento`, antes de
`dashboard`):

```python
def sincronizar_pedidos_compra_bling(pagina: int = 1, limite: int = 100) -> dict:
    """Sync de pedidos de compra do Bling -> compras_pedidos/compras_itens (upsert por
    bling_id). Resolve fornecedor por documento em cad_fornecedores, criando se nao existir —
    mesmo padrao de core.entidades.migrar_fornecedores_compras."""
    from bling_erp import listar_pedidos_compra, get_pedido_compra_detalhe, get_access_token, get_auth_url
    token = get_access_token()
    if not token:
        return {"error": "Bling nao autenticado", "auth_url": get_auth_url()}
    r = listar_pedidos_compra(pagina, limite)
    if r.get("error"):
        return r
    resumos = r.get("data", [])
    if not resumos:
        return {"sync": 0, "message": "sem dados"}

    async def _go():
        db = await get_db()
        total = 0
        erros = []
        for resumo in resumos:
            bling_id = resumo.get("id")
            if not bling_id:
                continue
            r_detalhe = get_pedido_compra_detalhe(bling_id)
            if r_detalhe.get("error"):
                erros.append(f"pedido {bling_id}: {r_detalhe['error']}")
                continue
            detalhe = r_detalhe.get("data", {})
            try:
                fornecedor = detalhe.get("fornecedor", {}) or {}
                doc = (fornecedor.get("numeroDocumento") or "").replace(".", "").replace("/", "").replace("-", "").strip()
                fornecedor_id = None
                if doc:
                    fornecedor_id = await db.fetchval(
                        "SELECT id FROM cad_fornecedores WHERE REPLACE(REPLACE(REPLACE(documento,'.',''),'/',''),'-','') = $1 LIMIT 1", doc)
                    if not fornecedor_id:
                        fornecedor_id = await db.fetchval(
                            "INSERT INTO cad_fornecedores (nome, tipo, documento, status) VALUES ($1,'PJ',$2,'ativo') RETURNING id",
                            fornecedor.get("nome", ""), doc)

                numero = str(detalhe.get("numero", ""))
                valor_total = float(detalhe.get("total", 0) or 0)
                situacao = (detalhe.get("situacao") or {}).get("nome", "")
                data_emissao = (detalhe.get("data") or "")[:10] or None
                data_prevista = (detalhe.get("dataPrevista") or "")[:10] or None

                pedido_id = await db.fetchval("SELECT id FROM compras_pedidos WHERE bling_id = $1", bling_id)
                if pedido_id:
                    await db.execute("""UPDATE compras_pedidos SET
                        numero=$1, fornecedor_id=$2, valor_total=$3, status=$4,
                        data_emissao=$5::date, data_entrega_prevista=$6::date, updated_at=NOW()
                        WHERE bling_id=$7""",
                        numero, fornecedor_id, valor_total, situacao,
                        data_emissao, data_prevista, bling_id)
                else:
                    pedido_id = await db.fetchval("""INSERT INTO compras_pedidos
                        (numero, fornecedor_id, valor_total, status, data_emissao,
                         data_entrega_prevista, bling_id)
                        VALUES ($1,$2,$3,$4,$5::date,$6::date,$7) RETURNING id""",
                        numero, fornecedor_id, valor_total, situacao,
                        data_emissao, data_prevista, bling_id)

                await db.execute("DELETE FROM compras_itens WHERE pedido_id = $1", pedido_id)
                for item in detalhe.get("itens", []) or []:
                    await db.execute("""INSERT INTO compras_itens
                        (pedido_id, produto_codigo, descricao, quantidade, valor_unitario, valor_total)
                        VALUES ($1,$2,$3,$4,$5,$6)""",
                        pedido_id, item.get("codigo", ""), item.get("descricao", ""),
                        float(item.get("quantidade", 0) or 0), float(item.get("valor", 0) or 0),
                        float(item.get("quantidade", 0) or 0) * float(item.get("valor", 0) or 0))
                total += 1
            except Exception as e:
                erros.append(f"pedido {bling_id}: {e}")
                log(AGENT, f"Erro ao sincronizar pedido de compra {bling_id}: {e}")
        return {"sync": total, "erros": erros}

    try:
        return run_async(_go())
    except Exception as e:
        return {"error": str(e)}
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_compras_bling.py -v` (ou o caminho
escolhido)
Expected: PASS

- [ ] **Step 5: Rodar a suíte de Compras inteira (não só o teste novo)**

Run: `cd hermes_agents && python -m pytest tests/test_compras_seguranca.py -v`
Expected: mesmo resultado da baseline documentada (as 5 falhas pré-existentes desse arquivo
continuam, nenhuma NOVA falha — a migração de coluna não pode ter quebrado nada do CRUD manual
de compras).

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/core/compras.py hermes_agents/tests/test_compras_bling.py
git commit -m "feat: sync de pedidos de compra Bling em compras_pedidos/compras_itens (resolve fornecedor por documento)"
```

(ajuste o nome do arquivo de teste no `git add` conforme o caminho real escolhido no Step 1 da
task anterior)

---

### Task 3: Rotas HTTP para Pedidos de Compra em `bling_bp`

**Files:**
- Modify: `hermes_agents/routes/integrations.py` (bloco `bling_bp`, logo após as rotas de
  situações da fase anterior)
- Test: `hermes_agents/tests/test_bling_routes.py`

**Interfaces:**
- Consumes: `core.compras.sincronizar_pedidos_compra_bling(pagina, limite) -> dict`,
  `bling_erp.marcar_pedido_compra_recebido(id) -> dict` (Tasks 1-2)
- Produces:
  - `GET /api/bling/pedidos-compra` (lista local, lê de `compras_pedidos WHERE bling_id IS NOT NULL`)
  - `POST /api/bling/pedidos-compra/sincronizar`
  - `POST /api/bling/pedidos-compra/<int:id_pedido>/receber` (aciona o lado Bling — recebe
    `id_pedido` como o `bling_id`, não o `id` interno do Athena, já que quem chama essa rota
    está olhando pro pedido do lado do Bling)

- [ ] **Step 1: Escrever os testes**

Adicionar a `hermes_agents/tests/test_bling_routes.py`:

```python
    def test_pedidos_compra_listar_route(self):
        rv = self.client.get("/api/bling/pedidos-compra")
        self.assertEqual(rv.status_code, 200)

    def test_pedidos_compra_sincronizar_route(self):
        with patch("routes.integrations.sincronizar_pedidos_compra_bling", return_value={"sync": 2}) as mock_sync:
            rv = self.client.post("/api/bling/pedidos-compra/sincronizar")
            self.assertEqual(rv.status_code, 200)
            mock_sync.assert_called_once()

    def test_pedidos_compra_receber_route(self):
        with patch("routes.integrations.marcar_pedido_compra_recebido", return_value={"data": {}}) as mock_receber:
            rv = self.client.post("/api/bling/pedidos-compra/555/receber")
            self.assertEqual(rv.status_code, 200)
            mock_receber.assert_called_once_with(555)
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py -k "pedidos_compra" -v`
Expected: FAIL — 404.

- [ ] **Step 3: Adicionar os imports e as rotas**

Em `hermes_agents/routes/integrations.py`, adicionar ao bloco de import de `bling_erp` do
`bling_bp`: `marcar_pedido_compra_recebido`. Adicionar import dedicado:
`from core.compras import sincronizar_pedidos_compra_bling`.

Logo após as rotas de situações (procure `def api_deletar_situacao`), adicionar:

```python
@bling_bp.route("/pedidos-compra")
def api_pedidos_compra():
    async def _go():
        db = await get_db()
        rows = await db.fetch("""SELECT id, numero, fornecedor_id, valor_total, status,
            data_emissao, data_entrega_prevista, bling_id
            FROM compras_pedidos WHERE bling_id IS NOT NULL ORDER BY data_emissao DESC""")
        return [dict(r) for r in rows]
    try:
        return jsonify(run_async(_go()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bling_bp.route("/pedidos-compra/sincronizar", methods=["POST"])
def api_sincronizar_pedidos_compra():
    return jsonify(sincronizar_pedidos_compra_bling())


@bling_bp.route("/pedidos-compra/<int:id_pedido>/receber", methods=["POST"])
def api_receber_pedido_compra(id_pedido):
    return jsonify(marcar_pedido_compra_recebido(id_pedido))
```

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py -k "pedidos_compra" -v`
Expected: PASS

- [ ] **Step 5: Rodar a suíte completa**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes (RH, compras, RBAC lojas), nenhuma nova.

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/routes/integrations.py hermes_agents/tests/test_bling_routes.py
git commit -m "feat: rotas GET/POST /api/bling/pedidos-compra"
```

---

### Task 4: Regressão final

**Files:**
- Test: `hermes_agents/tests/test_bling_routes.py`, `hermes_agents/tests/test_bling_erp.py`,
  arquivo de teste de `core/compras.py` escolhido na Task 2,
  `hermes_agents/tests/test_compras_seguranca.py`

- [ ] **Step 1: Rodar toda a suíte Bling + Compras**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py tests/test_bling_erp.py tests/test_compras_seguranca.py -v`
(adicione o arquivo de teste novo de `core/compras.py` a esse comando também)
Expected: todos PASS, exceto as 5 falhas pré-existentes já documentadas em
`test_compras_seguranca.py`.

- [ ] **Step 2: Rodar a suíte inteira do projeto**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes documentadas (RH endpoints, compras segurança, RBAC
lojas), nenhuma nova.

- [ ] **Step 3: Smoke test de import da app completa**

Run: `cd hermes_agents && python -c "import athena_bridge"`
Expected: importa sem erro.

- [ ] **Step 4: Confirmar que o CRUD manual de Compras (não tocado por este plano, mas na
  mesma tabela) continua funcionando**

Run: `cd hermes_agents && python -m pytest tests/test_compras_seguranca.py -v`
Expected: mesmo resultado exato da baseline (nenhuma regressão introduzida pela coluna
`bling_id` nova ou pelas mudanças em `_ensure_tables`).

- [ ] **Step 5: Commit (se houver qualquer ajuste feito nesta task)**

```bash
git status --porcelain
```

Confirme que nada de `hermes_agents/storage/`/`hermes_agents/uploads/` aparece staged antes de
commitar (lição já aprendida em fases anteriores deste módulo). Se não houver mudança de
código real:

```bash
git commit -m "test: regressao final pedidos de compra Bling" --allow-empty
```
