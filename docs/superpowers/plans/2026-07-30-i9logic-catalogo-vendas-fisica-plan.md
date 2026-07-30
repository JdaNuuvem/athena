# Catálogo e Vendas PDV (i9Logic → Athena) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Importar o catálogo de produtos (uma vez) e sincronizar continuamente as vendas do PDV das lojas físicas, puxando da API real do i9Logic pro Athena.

**Architecture:** Dois módulos novos (`core/i9logic_catalogo.py`, `core/i9logic_vendas.py`) reusando o client HTTP/rate-limit/de-para já construídos em `core/i9logic.py` (Fase 1 — reconciliação de saldo). O paginador vira genérico com retry por página. Catálogo é disparo manual (endpoint HTTP); vendas roda no `core/scheduler.py` a cada 10min com janela rolante por data (autocura, sem checkpoint persistido).

**Tech Stack:** Python 3.13, Flask, asyncpg, `requests`, unittest (mock de `asyncpg.create_pool` — sem banco real nos testes).

## Global Constraints

- Auth real da API i9Logic exige `X-Client-Id` + `Authorization: Bearer` (já corrigido em `core/i9logic.py`, commit `68c6c53`) — toda chamada nova usa `_client_id()`/`_api_key()`.
- Rate limit ~30 req/min — `RATE_LIMIT_SLEEP_SEGUNDOS = 2.5` já existe em `core/i9logic.py`, reusar.
- `GET /v1/produtos` é global (sem filtro de filial) — 22.105 produtos confirmados testando a API real.
- `GET /v1/pedidos` exige pelo menos 1 filtro (`id`/`data`/`cliente`/`status_id`/`origem`); `data_de`+`data_ate` funciona e traz todas as filiais numa chamada só (confirmado, não precisa loop por filial).
- `GET /v1/pedidos_produtos?idpedido=X` e `GET /v1/pedidos_pagamentos?pedido=X` são endpoints separados (não aninhados em `/pedidos`), 1 chamada por pedido cada, sem suporte a lista de ids por vírgula (testado, retorna vazio).
- **Desvio do spec, anotado aqui**: o spec descreve "janela rolante de 3h"; a API só filtra `data_de`/`data_ate` por **dia inteiro** (campo `data` é DATE, sem hora no filtro — confirmado testando a API real). A implementação usa janela por **data** (`hoje - 1 dia` até `hoje`) em vez de por hora. O princípio (autocura sem checkpoint persistido) é o mesmo, só a granularidade muda.
- `categoria`/`marca`/`fabricante` do catálogo e `formadepagamento` das vendas **não são resolvidos pra texto** — API não oferece endpoint de lookup (`GET /v1/categorias` e `GET /v1/marcas` retornam 404, confirmado).
- Catálogo é importação **única** (upsert idempotente, sem fila de revisão); vendas é **recorrente** a cada 600s via `core/scheduler.py`.
- Testes: unittest + `unittest.mock` (`patch`/`AsyncMock`/`MagicMock`), `asyncpg.create_pool` mockado a nível de módulo — nenhum teste toca banco real. Rodar com `python -m pytest hermes_agents/tests/ -q` da raiz do repo (`hermes_agents/`).

---

### Task 1: Paginador genérico com retry + refactor de `_paginar_estoques`

**Files:**
- Modify: `hermes_agents/core/i9logic.py`
- Test: `hermes_agents/tests/test_i9logic.py` (adicionar classe nova, não remover as existentes)

**Interfaces:**
- Consumes: nada de outras tasks (é a base de todas as seguintes).
- Produces: `_paginar(endpoint: str, params: dict, on_pagina: callable = None) -> list`; `class I9LogicPaginaError(Exception)` com atributos `.pagina` (int) e `.causa` (Exception); constantes `MAX_TENTATIVAS_PAGINA = 3`, `BACKOFF_SEGUNDOS = [2.5, 5, 10]`. `_paginar_estoques` continua existindo com a mesma assinatura/comportamento (agora delegando pra `_paginar`).

- [ ] **Step 1: Escrever os testes que falham**

Adicionar em `hermes_agents/tests/test_i9logic.py`, logo após a classe `TestPaginarEstoques` existente:

```python
class TestPaginarGenerico(unittest.TestCase):
    def _resposta(self, pagina, total, por_pagina=200):
        inicio = (pagina - 1) * por_pagina
        fim = min(inicio + por_pagina, total)
        dados = [{"id": i} for i in range(inicio, fim)]
        resp = MagicMock()
        resp.json.return_value = {"data": dados, "total": total}
        resp.raise_for_status.return_value = None
        return resp

    def test_retry_recupera_apos_falha_temporaria(self):
        chamadas = {"n": 0}
        def _get(url, params=None, headers=None, timeout=None):
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                raise Exception("timeout")
            return self._resposta(params["page"], 10)
        with patch("core.i9logic.requests.get", side_effect=_get), \
             patch("core.i9logic.time.sleep") as mock_sleep:
            resultado = i9logic._paginar("produtos", {})
        self.assertEqual(len(resultado), 10)
        self.assertEqual(chamadas["n"], 2)

    def test_esgotou_retries_levanta_erro_com_numero_da_pagina(self):
        def _get(url, params=None, headers=None, timeout=None):
            raise Exception("erro persistente")
        with patch("core.i9logic.requests.get", side_effect=_get), \
             patch("core.i9logic.time.sleep"):
            with self.assertRaises(i9logic.I9LogicPaginaError) as ctx:
                i9logic._paginar("produtos", {})
        self.assertEqual(ctx.exception.pagina, 1)

    def test_on_pagina_chamado_a_cada_pagina_com_registros_certos(self):
        total = 450
        paginas_recebidas = []
        def _get(url, params=None, headers=None, timeout=None):
            return self._resposta(params["page"], total)
        with patch("core.i9logic.requests.get", side_effect=_get), \
             patch("core.i9logic.time.sleep"):
            resultado = i9logic._paginar("produtos", {}, on_pagina=lambda regs: paginas_recebidas.append(len(regs)))
        self.assertEqual(paginas_recebidas, [200, 200, 50])
        self.assertEqual(len(resultado), total)

    def test_sem_on_pagina_nao_quebra(self):
        def _get(url, params=None, headers=None, timeout=None):
            return self._resposta(params["page"], 5)
        with patch("core.i9logic.requests.get", side_effect=_get), \
             patch("core.i9logic.time.sleep"):
            resultado = i9logic._paginar("produtos", {})
        self.assertEqual(len(resultado), 5)
```

- [ ] **Step 2: Rodar os testes novos e confirmar que falham**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -v -k TestPaginarGenerico`
Expected: FAIL — `AttributeError: module 'core.i9logic' has no attribute '_paginar'` (ou `I9LogicPaginaError`).

- [ ] **Step 3: Rodar a suíte inteira de `test_i9logic.py` antes de mexer, pra ter a baseline**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -q`
Expected: 68 passed (baseline atual, sem o `_paginar` novo ainda).

- [ ] **Step 4: Implementar `_paginar` genérico e refatorar `_paginar_estoques`**

Em `hermes_agents/core/i9logic.py`, logo após a definição de `TOLERANCIA_ZERO` (linha ~21), adicionar:

```python
MAX_TENTATIVAS_PAGINA = 3
BACKOFF_SEGUNDOS = [2.5, 5, 10]


class I9LogicPaginaError(Exception):
    def __init__(self, pagina: int, causa):
        self.pagina = pagina
        self.causa = causa
        super().__init__(f"falha ao buscar pagina {pagina} apos {MAX_TENTATIVAS_PAGINA} tentativas: {causa}")
```

Substituir o corpo de `_paginar_estoques` (bloco `def _paginar_estoques(...): ...` inteiro, linhas ~140-164) por:

```python
def _paginar(endpoint: str, params: dict, on_pagina=None) -> list:
    """Pagina qualquer endpoint do i9Logic respeitando o rate limit (sleep de
    RATE_LIMIT_SLEEP_SEGUNDOS entre paginas, nunca apos a ultima). Falha de
    rede/API numa pagina tenta de novo ate MAX_TENTATIVAS_PAGINA vezes com
    backoff (BACKOFF_SEGUNDOS); esgotou, levanta I9LogicPaginaError (carrega
    o numero da pagina que falhou, pro chamador reportar progresso parcial).
    on_pagina, se passado, e' chamado com a lista de registros de cada
    pagina assim que ela chega — permite processamento/gravacao incremental
    em cargas grandes (import de catalogo) sem perder o progresso se uma
    pagina posterior falhar."""
    registros = []
    pagina = 1
    while True:
        dados = None
        ultimo_erro = None
        for tentativa in range(MAX_TENTATIVAS_PAGINA):
            try:
                resp = requests.get(
                    f"{BASE_URL}/v1/{endpoint}",
                    params={**params, "page": pagina, "per_page": PER_PAGE_PADRAO},
                    headers={"X-Client-Id": _client_id(), "Authorization": f"Bearer {_api_key()}"},
                    timeout=30,
                )
                resp.raise_for_status()
                dados = resp.json()
                break
            except Exception as e:
                ultimo_erro = e
                if tentativa < MAX_TENTATIVAS_PAGINA - 1:
                    time.sleep(BACKOFF_SEGUNDOS[tentativa])
        if dados is None:
            raise I9LogicPaginaError(pagina, ultimo_erro)
        pagina_registros = dados.get("data", [])
        registros.extend(pagina_registros)
        if on_pagina:
            on_pagina(pagina_registros)
        total = dados.get("total", len(registros))
        if pagina * PER_PAGE_PADRAO >= total or not pagina_registros:
            break
        pagina += 1
        time.sleep(RATE_LIMIT_SLEEP_SEGUNDOS)
    return registros


def _paginar_estoques(filial_id_i9logic: int, tipoestoque: int) -> list:
    return _paginar("produtos_estoques", {"filial": filial_id_i9logic, "tipoestoque": tipoestoque})
```

- [ ] **Step 5: Rodar a suíte inteira de novo e confirmar 100% verde (novos + antigos)**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -q`
Expected: 72 passed (68 antigos + 4 novos), 0 failures. Os testes antigos de `TestPaginarEstoques` (`test_pagina_completa_sem_duplicar_mais_de_200_registros`, `test_pagina_unica_nao_dorme`, `test_paginacao_passa_tipoestoque_e_filial_corretos`) devem continuar passando sem alteração — o refactor é transparente pro caminho feliz (retry só ativa em falha real).

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/core/i9logic.py hermes_agents/tests/test_i9logic.py
git commit -m "feat: paginador generico com retry em core/i9logic.py

_paginar(endpoint, params, on_pagina) reusavel por catalogo/vendas/saldo.
Retry com backoff por pagina (I9LogicPaginaError se esgotar). _paginar_estoques
vira wrapper fino, comportamento identico (68 testes antigos continuam verdes)."
```

---

### Task 2: Import de catálogo i9Logic → `catalogo_produtos`

**Files:**
- Modify: `hermes_agents/core/catalogo.py` (colunas novas `ean`, `id_i9logic`)
- Create: `hermes_agents/core/i9logic_catalogo.py`
- Test: `hermes_agents/tests/test_i9logic_catalogo.py`

**Interfaces:**
- Consumes: `core.i9logic._paginar`, `core.i9logic.I9LogicPaginaError`, `core.i9logic.BASE_URL` (Task 1); `core.get_db`, `core.run_async`, `core.log`.
- Produces: `sincronizar_catalogo_i9logic() -> dict` — sucesso: `{"ok": True, "importados": int, "erros_registro": [{"codproduto":..., "erro":...}, ...]}`; falha de página: `{"erro": str, "pagina_falhou": int, "importados_ate_agora": int, "erros_registro": [...]}`. Também `_upsert_produto(produto: dict) -> dict`.

- [ ] **Step 1: Adicionar as colunas novas em `core/catalogo.py`**

Em `hermes_agents/core/catalogo.py`, logo após a linha `await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS atributo VARCHAR(200)")` (linha ~36), adicionar:

```python
await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS ean VARCHAR(20)")
await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS id_i9logic BIGINT")
```

- [ ] **Step 2: Escrever os testes que falham**

Criar `hermes_agents/tests/test_i9logic_catalogo.py`:

```python
"""Testes de integracao — import de catalogo i9Logic -> catalogo_produtos."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock, MagicMock

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.i9logic_catalogo as catalogo_i9logic
from core.i9logic import I9LogicPaginaError


class TestUpsertProduto(unittest.TestCase):
    def test_codproduto_vazio_retorna_erro(self):
        resultado = catalogo_i9logic._upsert_produto({"id": 1, "codproduto": "  "})
        self.assertIn("erro", resultado)

    def test_grava_de_para_automatico_junto_com_upsert(self):
        chamadas_execute = []
        async def _fetchrow(query, *args):
            return {"sku": args[0]}
        async def _execute(query, *args):
            chamadas_execute.append((query, args))
            return "OK"
        with patch("core.i9logic_catalogo.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow, execute=_execute)
            resultado = catalogo_i9logic._upsert_produto(
                {"id": 99, "codproduto": "SKU-99", "descricao": "Teste", "ean": "123",
                 "ncm": "0000", "unidademedida": "UN", "peso": 1})
        self.assertEqual(resultado["sku"], "SKU-99")
        self.assertTrue(any("de_para_i9logic" in q for q, _ in chamadas_execute))
        query_depara, args_depara = next((q, a) for q, a in chamadas_execute if "de_para_i9logic" in q)
        self.assertEqual(args_depara, ("99", "SKU-99"))


class TestSincronizarCatalogo(unittest.TestCase):
    def test_sem_base_url_retorna_erro(self):
        with patch("core.i9logic_catalogo.BASE_URL", ""):
            resultado = catalogo_i9logic.sincronizar_catalogo_i9logic()
        self.assertIn("erro", resultado)

    def test_filtra_apenas_ativo_e_emlinha(self):
        produtos_upsertados = []
        def _fake_upsert(produto):
            produtos_upsertados.append(produto["codproduto"])
            return {"sku": produto["codproduto"]}
        def _fake_paginar(endpoint, params, on_pagina=None):
            pagina = [
                {"id": 1, "codproduto": "ATIVO1", "ativo": "1", "emlinha": "1"},
                {"id": 2, "codproduto": "INATIVO", "ativo": "0", "emlinha": "1"},
                {"id": 3, "codproduto": "FORADELINHA", "ativo": "1", "emlinha": "0"},
            ]
            if on_pagina: on_pagina(pagina)
            return pagina
        with patch("core.i9logic_catalogo.BASE_URL", "https://fake"), \
             patch("core.i9logic_catalogo._paginar", side_effect=_fake_paginar), \
             patch("core.i9logic_catalogo._upsert_produto", side_effect=_fake_upsert):
            resultado = catalogo_i9logic.sincronizar_catalogo_i9logic()
        self.assertEqual(produtos_upsertados, ["ATIVO1"])
        self.assertEqual(resultado["importados"], 1)

    def test_produto_malformado_e_pulado_sem_abortar_lote(self):
        def _fake_paginar(endpoint, params, on_pagina=None):
            pagina = [
                {"id": 1, "codproduto": "", "ativo": "1", "emlinha": "1"},
                {"id": 2, "codproduto": "OK", "ativo": "1", "emlinha": "1"},
            ]
            if on_pagina: on_pagina(pagina)
            return pagina
        def _fake_upsert(produto):
            if not produto.get("codproduto"):
                return {"erro": "codproduto vazio"}
            return {"sku": produto["codproduto"]}
        with patch("core.i9logic_catalogo.BASE_URL", "https://fake"), \
             patch("core.i9logic_catalogo._paginar", side_effect=_fake_paginar), \
             patch("core.i9logic_catalogo._upsert_produto", side_effect=_fake_upsert):
            resultado = catalogo_i9logic.sincronizar_catalogo_i9logic()
        self.assertEqual(resultado["importados"], 1)
        self.assertEqual(len(resultado["erros_registro"]), 1)

    def test_falha_de_pagina_retorna_progresso_parcial(self):
        def _fake_paginar(endpoint, params, on_pagina=None):
            if on_pagina:
                on_pagina([{"id": 1, "codproduto": "P1", "ativo": "1", "emlinha": "1"}])
            raise I9LogicPaginaError(2, Exception("timeout"))
        with patch("core.i9logic_catalogo.BASE_URL", "https://fake"), \
             patch("core.i9logic_catalogo._paginar", side_effect=_fake_paginar), \
             patch("core.i9logic_catalogo._upsert_produto", return_value={"sku": "P1"}):
            resultado = catalogo_i9logic.sincronizar_catalogo_i9logic()
        self.assertIn("erro", resultado)
        self.assertEqual(resultado["pagina_falhou"], 2)
        self.assertEqual(resultado["importados_ate_agora"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 3: Rodar e confirmar que falha**

Run: `python -m pytest hermes_agents/tests/test_i9logic_catalogo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.i9logic_catalogo'`.

- [ ] **Step 4: Implementar `core/i9logic_catalogo.py`**

```python
"""Import de catalogo — i9Logic -> Athena (importacao unica, disparo manual).

Puxa o catalogo inteiro (/produtos, global, sem filial — 22.105 produtos
confirmados na API real) e faz upsert direto em catalogo_produtos por
sku=codproduto, sem fila de revisao. So' campos com significado direto
entram (sku, descricao, ean, ncm, unidade, peso) — categoria/marca/
fabricante ficam de fora porque sao so' codigos numericos internos do
i9Logic sem endpoint de resolucao (GET /categorias e /marcas retornam 404,
confirmado). Grava o de-para (tipo='produto') automaticamente no mesmo
upsert, deixando a Fase 1 (reconciliacao de saldo) pronta pra usar esses
produtos sem matching manual."""
from core import get_db, run_async, log
from core.i9logic import _paginar, I9LogicPaginaError, BASE_URL

AGENT = "I9Logic Catalogo"


def _upsert_produto(produto: dict) -> dict:
    sku = str(produto.get("codproduto", "")).strip()
    if not sku:
        return {"erro": "codproduto vazio"}
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            INSERT INTO catalogo_produtos (sku, descricao, ean, ncm, unidade_padrao, peso_bruto, id_i9logic)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            ON CONFLICT (sku) DO UPDATE SET
                descricao=$2, ean=$3, ncm=$4, unidade_padrao=$5, peso_bruto=$6, id_i9logic=$7,
                updated_at=NOW()
            RETURNING *
        """, sku, produto.get("descricao") or "", produto.get("ean") or None,
            produto.get("ncm") or None, produto.get("unidademedida") or "UN",
            produto.get("peso") or 0, produto.get("id"))
        await db.execute("""
            INSERT INTO de_para_i9logic (tipo, id_i9logic, codigo_athena) VALUES ('produto',$1,$2)
            ON CONFLICT (tipo, id_i9logic) DO UPDATE SET codigo_athena=$2
        """, str(produto.get("id")), sku)
        return dict(row)
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}


def sincronizar_catalogo_i9logic() -> dict:
    """Importacao unica do catalogo inteiro — disparo manual (nao entra no
    scheduler). Idempotente: rodar de novo do zero so' reprocessa (upsert por
    sku), nao duplica."""
    if not BASE_URL:
        return {"erro": "I9LOGIC_BASE_URL nao configurado - configure antes de importar"}
    importados = {"count": 0}
    erros_registro = []

    def _on_pagina(pagina_registros):
        for produto in pagina_registros:
            if str(produto.get("ativo", "")) != "1" or str(produto.get("emlinha", "")) != "1":
                continue
            r = _upsert_produto(produto)
            if r.get("erro"):
                erros_registro.append({"codproduto": produto.get("codproduto"), "erro": r["erro"]})
            else:
                importados["count"] += 1

    try:
        _paginar("produtos", {}, on_pagina=_on_pagina)
    except I9LogicPaginaError as e:
        return {"erro": str(e), "pagina_falhou": e.pagina,
                "importados_ate_agora": importados["count"], "erros_registro": erros_registro}
    return {"ok": True, "importados": importados["count"], "erros_registro": erros_registro}
```

- [ ] **Step 5: Rodar e confirmar que passa**

Run: `python -m pytest hermes_agents/tests/test_i9logic_catalogo.py -v`
Expected: 6 passed.

- [ ] **Step 6: Rodar a suíte inteira pra garantir que nada quebrou**

Run: `python -m pytest hermes_agents/tests/ -q`
Expected: todos os testes existentes + os novos passando (nenhuma regressão em `test_i9logic.py`, `test_fase4_fase1.py`, etc).

- [ ] **Step 7: Commit**

```bash
git add hermes_agents/core/catalogo.py hermes_agents/core/i9logic_catalogo.py hermes_agents/tests/test_i9logic_catalogo.py
git commit -m "feat: import de catalogo i9Logic -> catalogo_produtos

Importacao unica (disparo manual), upsert por sku=codproduto, filtro
ativo+emlinha, de-para produto gravado automatico junto. categoria/marca/
fabricante ficam de fora (sem endpoint de resolucao na API real)."
```

---

### Task 3: Rota `POST /produtos/importar`

**Files:**
- Modify: `hermes_agents/routes/i9logic.py`
- Modify: `hermes_agents/tests/test_i9logic.py` (adicionar à classe `TestRotasI9Logic`)

**Interfaces:**
- Consumes: `core.i9logic_catalogo.sincronizar_catalogo_i9logic` (Task 2).
- Produces: rota `POST /api/integrations/i9logic/produtos/importar`, protegida por `estoque.editar`.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar em `hermes_agents/tests/test_i9logic.py`, dentro da classe `TestRotasI9Logic` (após o último teste existente):

```python
    def test_importar_produtos_exige_estoque_editar(self):
        headers = self._headers_com_permissao([])
        with patch("core.rbac.usuario_tem_permissao", return_value=False):
            r = self.client.post("/api/integrations/i9logic/produtos/importar", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_importar_produtos_com_permissao_libera(self):
        headers = self._headers_com_permissao(["estoque.editar"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.sincronizar_catalogo_i9logic",
                   return_value={"ok": True, "importados": 5, "erros_registro": []}) as mock_sync:
            r = self.client.post("/api/integrations/i9logic/produtos/importar", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["importados"], 5)
        mock_sync.assert_called_once()
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -v -k importar_produtos`
Expected: FAIL — 404 (rota não existe ainda).

- [ ] **Step 3: Implementar a rota**

Em `hermes_agents/routes/i9logic.py`, adicionar ao bloco de imports do topo:

```python
from core.i9logic_catalogo import sincronizar_catalogo_i9logic
```

E ao final do arquivo:

```python
@i9logic_bp.route("/produtos/importar", methods=["POST"])
def i9logic_importar_produtos():
    """Importacao unica do catalogo inteiro (22k+ produtos) - disparo manual,
    nao entra no job recorrente do scheduler."""
    @requer_permissao("estoque.editar")
    def _go():
        return jsonify(sincronizar_catalogo_i9logic())
    return _go()
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -v -k importar_produtos`
Expected: 2 passed.

- [ ] **Step 5: Rodar a suíte inteira do arquivo**

Run: `python -m pytest hermes_agents/tests/test_i9logic.py -q`
Expected: todos passando, 0 failures.

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/routes/i9logic.py hermes_agents/tests/test_i9logic.py
git commit -m "feat: rota POST /api/integrations/i9logic/produtos/importar"
```

---

### Task 4: Busca e montagem de um pedido i9Logic (`_buscar_dados_pedido`)

**Files:**
- Create: `hermes_agents/core/i9logic_vendas.py`
- Test: `hermes_agents/tests/test_i9logic_vendas.py`

**Interfaces:**
- Consumes: `core.i9logic._paginar`, `core.i9logic.buscar_codigo_athena` (de-para de filial, já existente da Fase 1).
- Produces: `_buscar_dados_pedido(pedido_id_i9logic: int) -> dict` — retorna `{"pedido": dict, "loja_athena": str, "itens": list, "pagamentos": list}`, ou `None` se a filial do pedido não tiver de-para mapeado (sem gastar chamadas de itens/pagamentos nesse caso). Levanta exceção se a API falhar — o chamador (Task 5) decide como tratar.

- [ ] **Step 1: Escrever os testes que falham**

Criar `hermes_agents/tests/test_i9logic_vendas.py`:

```python
"""Testes de integracao — sync de vendas PDV i9Logic -> Athena."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock, MagicMock

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.i9logic_vendas as vendas_i9logic


class TestBuscarDadosPedido(unittest.TestCase):
    def test_filial_sem_depara_retorna_none_sem_buscar_itens_pagamentos(self):
        chamadas = []
        def _fake_paginar(endpoint, params, on_pagina=None):
            chamadas.append(endpoint)
            if endpoint == "pedidos":
                return [{"id": 322643, "filial_venda": 999, "valor_total": 25.97,
                         "cancelado": "0", "data": "2026-07-29"}]
            return []
        with patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar), \
             patch("core.i9logic_vendas.buscar_codigo_athena", return_value=None):
            resultado = vendas_i9logic._buscar_dados_pedido(322643)
        self.assertIsNone(resultado)
        self.assertEqual(chamadas, ["pedidos"])

    def test_filial_mapeada_monta_pedido_completo(self):
        def _fake_paginar(endpoint, params, on_pagina=None):
            if endpoint == "pedidos":
                return [{"id": 322643, "filial_venda": 1, "valor_total": 25.97,
                         "cancelado": "0", "data": "2026-07-29"}]
            if endpoint == "pedidos_produtos":
                return [{"codproduto": "012810", "qtd": 1, "valorvenda": 1.99, "descricao": "Pinca"}]
            if endpoint == "pedidos_pagamentos":
                return [{"formadepagamento": 335, "valor": 25.97, "codautorizacao": ""}]
            return []
        with patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar), \
             patch("core.i9logic_vendas.buscar_codigo_athena", return_value="Loja Matriz"):
            resultado = vendas_i9logic._buscar_dados_pedido(322643)
        self.assertEqual(resultado["loja_athena"], "Loja Matriz")
        self.assertEqual(resultado["pedido"]["id"], 322643)
        self.assertEqual(len(resultado["itens"]), 1)
        self.assertEqual(len(resultado["pagamentos"]), 1)

    def test_pedido_nao_encontrado_levanta_erro(self):
        def _fake_paginar(endpoint, params, on_pagina=None):
            return []
        with patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar):
            with self.assertRaises(Exception):
                vendas_i9logic._buscar_dados_pedido(999999)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python -m pytest hermes_agents/tests/test_i9logic_vendas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.i9logic_vendas'`.

- [ ] **Step 3: Implementar `core/i9logic_vendas.py`**

```python
"""Sync de vendas do PDV — i9Logic -> Athena (lojas fisicas).

_buscar_dados_pedido busca e monta um pedido completo (cabecalho + itens +
pagamentos) SEM gravar nada no banco — a gravacao so' acontece se as 3
chamadas de API tiverem sucesso (ver sincronizar_pedidos_i9logic, Task 5),
pra nunca deixar um pedido meio gravado (cabecalho sem itens) que a janela
rolante nao conseguiria mais detectar como pendente. Verifica o de-para de
filial ANTES de buscar itens/pagamentos - pedido de filial nao mapeada nao
gasta chamada nenhuma com isso, economiza rate limit."""
from core.i9logic import _paginar, buscar_codigo_athena


def _buscar_dados_pedido(pedido_id_i9logic: int) -> dict:
    pedidos = _paginar("pedidos", {"id": pedido_id_i9logic})
    if not pedidos:
        raise RuntimeError(f"pedido {pedido_id_i9logic} nao encontrado na API i9Logic")
    pedido = pedidos[0]
    loja_athena = buscar_codigo_athena("filial", pedido.get("filial_venda"))
    if not loja_athena:
        return None
    itens = _paginar("pedidos_produtos", {"idpedido": pedido_id_i9logic})
    pagamentos = _paginar("pedidos_pagamentos", {"pedido": pedido_id_i9logic})
    return {"pedido": pedido, "loja_athena": loja_athena, "itens": itens, "pagamentos": pagamentos}
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python -m pytest hermes_agents/tests/test_i9logic_vendas.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/i9logic_vendas.py hermes_agents/tests/test_i9logic_vendas.py
git commit -m "feat: busca e montagem de pedido i9Logic (_buscar_dados_pedido)

Resolve filial->loja via de-para ANTES de buscar itens/pagamentos - pedido
de filial nao mapeada nao gasta chamada de API com isso."
```

---

### Task 5: Ciclo de sincronização de vendas (janela rolante + gravação + schema)

**Files:**
- Modify: `hermes_agents/core/vendas.py` (coluna `id_i9logic` + índice único)
- Modify: `hermes_agents/core/i9logic_vendas.py` (continua o arquivo da Task 4)
- Modify: `hermes_agents/tests/test_i9logic_vendas.py`

**Interfaces:**
- Consumes: `_buscar_dados_pedido` (Task 4), `core.get_db`, `core.run_async`, `core.log`, `core.i9logic._paginar`, `core.i9logic.BASE_URL`.
- Produces: `sincronizar_pedidos_i9logic(data_de: str = None, data_ate: str = None) -> dict`; `_janela_padrao() -> tuple`; `_ja_sincronizados(ids: list) -> set`; `_gravar_pedido(dados: dict) -> dict`; constantes `JANELA_ROLANTE_DIAS = 1`, `MAX_PEDIDOS_NOVOS_POR_CICLO = 100`.

- [ ] **Step 1: Adicionar a coluna e o índice em `core/vendas.py`**

Em `hermes_agents/core/vendas.py`, logo após a linha `except Exception as e: pass` que segue `CREATE UNIQUE INDEX IF NOT EXISTS idx_vendas_pedidos_shopee_order_sn` (linha ~27), adicionar:

```python
        try: await db.execute("ALTER TABLE vendas_pedidos ADD COLUMN IF NOT EXISTS id_i9logic BIGINT")
        except Exception as e: pass
        try: await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_vendas_pedidos_id_i9logic ON vendas_pedidos (id_i9logic) WHERE id_i9logic IS NOT NULL")
        except Exception as e: pass
```

- [ ] **Step 2: Escrever os testes que falham**

Adicionar em `hermes_agents/tests/test_i9logic_vendas.py` (após `TestBuscarDadosPedido`, antes do `if __name__`):

```python
class TestJanelaPadrao(unittest.TestCase):
    def test_janela_padrao_e_data_string_com_inicio_antes_do_fim(self):
        data_de, data_ate = vendas_i9logic._janela_padrao()
        self.assertRegex(data_de, r"^\d{4}-\d{2}-\d{2}$")
        self.assertRegex(data_ate, r"^\d{4}-\d{2}-\d{2}$")
        self.assertLessEqual(data_de, data_ate)


class TestSincronizarPedidos(unittest.TestCase):
    def test_sem_base_url_retorna_erro(self):
        with patch("core.i9logic_vendas.BASE_URL", ""):
            resultado = vendas_i9logic.sincronizar_pedidos_i9logic()
        self.assertIn("erro", resultado)

    def test_pedido_ja_sincronizado_nao_gasta_chamada_de_busca(self):
        def _fake_paginar_pedidos(endpoint, params, on_pagina=None):
            self.assertEqual(endpoint, "pedidos")
            return [{"id": 1}, {"id": 2}]
        chamou_buscar_dados = []
        def _fake_buscar_dados(pid):
            chamou_buscar_dados.append(pid)
            return None
        with patch("core.i9logic_vendas.BASE_URL", "https://fake"), \
             patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar_pedidos), \
             patch("core.i9logic_vendas._ja_sincronizados", return_value={1}), \
             patch("core.i9logic_vendas._buscar_dados_pedido", side_effect=_fake_buscar_dados):
            vendas_i9logic.sincronizar_pedidos_i9logic()
        self.assertEqual(chamou_buscar_dados, [2])

    def test_falha_isolada_em_um_pedido_nao_impede_os_demais(self):
        def _fake_paginar_pedidos(endpoint, params, on_pagina=None):
            return [{"id": 1}, {"id": 2}]
        def _fake_buscar_dados(pid):
            if pid == 1:
                raise Exception("erro de rede")
            return {"pedido": {"id": 2, "cancelado": "0", "valor_total": 10, "data": "2026-07-29"},
                    "loja_athena": "Loja X", "itens": [], "pagamentos": []}
        gravados = []
        def _fake_gravar(dados):
            gravados.append(dados["pedido"]["id"])
            return {"ok": True}
        with patch("core.i9logic_vendas.BASE_URL", "https://fake"), \
             patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar_pedidos), \
             patch("core.i9logic_vendas._ja_sincronizados", return_value=set()), \
             patch("core.i9logic_vendas._buscar_dados_pedido", side_effect=_fake_buscar_dados), \
             patch("core.i9logic_vendas._gravar_pedido", side_effect=_fake_gravar):
            resultado = vendas_i9logic.sincronizar_pedidos_i9logic()
        self.assertEqual(gravados, [2])
        self.assertEqual(len(resultado["erros"]), 1)
        self.assertEqual(resultado["sincronizados"], 1)

    def test_teto_max_pedidos_novos_por_ciclo_e_respeitado(self):
        muitos_pedidos = [{"id": i} for i in range(1, 150)]
        def _fake_paginar_pedidos(endpoint, params, on_pagina=None):
            return muitos_pedidos
        processados = []
        def _fake_buscar_dados(pid):
            processados.append(pid)
            return None
        with patch("core.i9logic_vendas.BASE_URL", "https://fake"), \
             patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar_pedidos), \
             patch("core.i9logic_vendas._ja_sincronizados", return_value=set()), \
             patch("core.i9logic_vendas._buscar_dados_pedido", side_effect=_fake_buscar_dados):
            resultado = vendas_i9logic.sincronizar_pedidos_i9logic()
        self.assertEqual(len(processados), vendas_i9logic.MAX_PEDIDOS_NOVOS_POR_CICLO)
        self.assertTrue(resultado["truncado"])

    def test_backfill_com_datas_explicitas_repassa_para_paginar(self):
        params_capturados = {}
        def _fake_paginar(endpoint, params, on_pagina=None):
            params_capturados.update(params)
            return []
        with patch("core.i9logic_vendas.BASE_URL", "https://fake"), \
             patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar), \
             patch("core.i9logic_vendas._ja_sincronizados", return_value=set()):
            vendas_i9logic.sincronizar_pedidos_i9logic(data_de="2026-01-01", data_ate="2026-01-31")
        self.assertEqual(params_capturados["data_de"], "2026-01-01")
        self.assertEqual(params_capturados["data_ate"], "2026-01-31")


class TestGravarPedido(unittest.TestCase):
    def test_grava_pedido_novo_itens_e_pagamentos(self):
        execucoes = []
        dados = {
            "pedido": {"id": 322643, "cancelado": "0", "valor_total": 25.97, "data": "2026-07-29"},
            "loja_athena": "Loja Matriz",
            "itens": [{"codproduto": "012810", "descricao": "Pinca", "qtd": 1, "valorvenda": 1.99}],
            "pagamentos": [{"formadepagamento": 335, "valor": 25.97, "codautorizacao": ""}],
        }
        # fetchval do conn cobre: loja_id (lojas), checagem de pedido existente (None = novo),
        # e o INSERT em vendas_pedidos retornando o id novo
        async def _fetchval(query, *args):
            if "lojas" in query:
                return 7
            if "SELECT id FROM vendas_pedidos WHERE id_i9logic" in query:
                return None
            if "INSERT INTO vendas_pedidos" in query:
                return 55
            return None
        async def _execute(query, *args):
            execucoes.append(query)
            return "OK"
        # db (a pool) so' expoe acquire() - se o codigo voltar a chamar
        # db.transaction()/db.fetchval() direto por engano, o teste quebra
        # com AttributeError em vez de passar batido (mesmo bug que ja
        # aconteceu no import de catalogo, corrigido la).
        conn = AsyncMock()
        conn.fetchval = _fetchval
        conn.execute = _execute
        conn.transaction.return_value = AsyncMock(
            __aenter__=AsyncMock(return_value=None), __aexit__=AsyncMock(return_value=None))
        db = MagicMock(spec=["acquire"])
        db.acquire.return_value = AsyncMock(
            __aenter__=AsyncMock(return_value=conn), __aexit__=AsyncMock(return_value=None))
        with patch("core.i9logic_vendas.get_db") as mock_get_db:
            mock_get_db.return_value = db
            resultado = vendas_i9logic._gravar_pedido(dados)
        self.assertTrue(resultado["ok"])
        self.assertTrue(any("vendas_itens" in q for q in execucoes))
        self.assertTrue(any("vendas_pagamentos" in q for q in execucoes))
```

- [ ] **Step 3: Rodar e confirmar que falha**

Run: `python -m pytest hermes_agents/tests/test_i9logic_vendas.py -v`
Expected: FAIL — `AttributeError` (`_janela_padrao`, `sincronizar_pedidos_i9logic` etc. ainda não existem).

- [ ] **Step 4: Implementar a Task 5 em `core/i9logic_vendas.py`**

Adicionar no topo do arquivo (substituindo o import único existente):

```python
from datetime import datetime, timedelta
from core import get_db, run_async, log
from core.i9logic import _paginar, buscar_codigo_athena, BASE_URL

AGENT = "I9Logic Vendas"

JANELA_ROLANTE_DIAS = 1
MAX_PEDIDOS_NOVOS_POR_CICLO = 100
```

E ao final do arquivo (após `_buscar_dados_pedido`):

```python
def _janela_padrao() -> tuple:
    agora = datetime.now()
    inicio = agora - timedelta(days=JANELA_ROLANTE_DIAS)
    return inicio.strftime("%Y-%m-%d"), agora.strftime("%Y-%m-%d")


def _ja_sincronizados(ids_i9logic: list) -> set:
    async def _go():
        db = await get_db()
        rows = await db.fetch(
            "SELECT id_i9logic FROM vendas_pedidos WHERE id_i9logic = ANY($1::bigint[])", ids_i9logic)
        return {r["id_i9logic"] for r in rows}
    try:
        return run_async(_go())
    except Exception:
        return set()


def _gravar_pedido(dados: dict) -> dict:
    """Grava pedido+itens+pagamentos numa UNICA conexao/transacao (nunca
    db.execute/db.fetchval direto na pool - asyncpg.Pool nao tem .transaction(),
    so' asyncpg.Connection tem, obtida via db.acquire()). Tudo-ou-nada: se
    qualquer INSERT falhar no meio, nada deste pedido fica gravado, e ele
    continua elegivel pra retry no proximo ciclo (a janela rolante so' pula
    pedido cujo id_i9logic ja existe em vendas_pedidos - uma gravacao parcial
    quebraria essa premissa)."""
    pedido = dados["pedido"]
    async def _go():
        db = await get_db()
        async with db.acquire() as conn:
            async with conn.transaction():
                loja_id = await conn.fetchval("SELECT id FROM lojas WHERE nome=$1", dados["loja_athena"])
                status = "cancelado" if str(pedido.get("cancelado")) == "1" else "concluido"
                existente = await conn.fetchval("SELECT id FROM vendas_pedidos WHERE id_i9logic=$1", pedido["id"])
                if existente:
                    await conn.execute(
                        "UPDATE vendas_pedidos SET status=$1, total=$2, updated_at=NOW() WHERE id_i9logic=$3",
                        status, pedido.get("valor_total", 0), pedido["id"])
                    pedido_id = existente
                    await conn.execute("DELETE FROM vendas_itens WHERE pedido_id=$1", pedido_id)
                    await conn.execute("DELETE FROM vendas_pagamentos WHERE pedido_id=$1", pedido_id)
                else:
                    pedido_id = await conn.fetchval("""
                        INSERT INTO vendas_pedidos (numero, status, total, data, origem, loja_id, id_i9logic)
                        VALUES ($1,$2,$3,$4,'i9logic_pdv',$5,$6) RETURNING id
                    """, str(pedido["id"]), status, pedido.get("valor_total", 0), pedido.get("data"),
                        loja_id, pedido["id"])
                for item in dados["itens"]:
                    qtd = float(item.get("qtd", 0) or 0)
                    valor_unitario = float(item.get("valorvenda", 0) or 0)
                    await conn.execute("""
                        INSERT INTO vendas_itens (pedido_id, sku, descricao, quantidade, valor_unitario, valor_total)
                        VALUES ($1,$2,$3,$4,$5,$6)
                    """, pedido_id, item.get("codproduto", ""), item.get("descricao", ""),
                        qtd, valor_unitario, qtd * valor_unitario)
                for pagamento in dados["pagamentos"]:
                    await conn.execute("""
                        INSERT INTO vendas_pagamentos (pedido_id, forma, valor, autorizacao)
                        VALUES ($1,$2,$3,$4)
                    """, pedido_id, str(pagamento.get("formadepagamento", "")),
                        pagamento.get("valor", 0), pagamento.get("codautorizacao") or None)
        return {"ok": True, "pedido_id": pedido_id}
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}


def sincronizar_pedidos_i9logic(data_de: str = None, data_ate: str = None) -> dict:
    """Ciclo de sync de vendas PDV. Sem data_de/data_ate, usa a janela rolante
    padrao (JANELA_ROLANTE_DIAS) - autocura sozinha: pedido que falhou num
    ciclo reaparece na janela do ciclo seguinte, sem checkpoint persistido.
    Com data_de/data_ate explicitos, serve de backfill manual (historico)."""
    if not BASE_URL:
        return {"erro": "I9LOGIC_BASE_URL nao configurado - configure antes de sincronizar"}
    if not data_de or not data_ate:
        data_de, data_ate = _janela_padrao()
    try:
        pedidos = _paginar("pedidos", {"data_de": data_de, "data_ate": data_ate})
    except Exception as e:
        return {"erro": f"falha ao listar pedidos: {e}"}
    ids_i9logic = [p["id"] for p in pedidos]
    ja_sincronizados = _ja_sincronizados(ids_i9logic)
    novos = [pid for pid in ids_i9logic if pid not in ja_sincronizados]
    truncado = len(novos) > MAX_PEDIDOS_NOVOS_POR_CICLO
    if truncado:
        log(AGENT, f"MAX_PEDIDOS_NOVOS_POR_CICLO ({MAX_PEDIDOS_NOVOS_POR_CICLO}) atingido - resto entra no proximo ciclo")
        novos = novos[:MAX_PEDIDOS_NOVOS_POR_CICLO]
    sincronizados, pulados, erros = 0, 0, []
    for pid in novos:
        try:
            dados = _buscar_dados_pedido(pid)
        except Exception as e:
            erros.append({"pedido": pid, "erro": str(e)})
            continue
        if dados is None:
            pulados += 1
            continue
        r = _gravar_pedido(dados)
        if r.get("erro"):
            erros.append({"pedido": pid, "erro": r["erro"]})
        else:
            sincronizados += 1
    return {"ok": True, "pedidos_na_janela": len(pedidos), "sincronizados": sincronizados,
            "pulados_filial_nao_mapeada": pulados, "erros": erros, "truncado": truncado}
```

- [ ] **Step 5: Rodar e confirmar que passa**

Run: `python -m pytest hermes_agents/tests/test_i9logic_vendas.py -v`
Expected: 9 passed (3 da Task 4 + 6 novos).

- [ ] **Step 6: Rodar a suíte inteira**

Run: `python -m pytest hermes_agents/tests/ -q`
Expected: tudo passando, 0 failures (checar em particular que `test_scheduler_pedidos_shopee.py`, `test_i9logic.py`, `test_fase4_fase1.py` continuam verdes — nenhum deles toca as tabelas/colunas alteradas aqui).

- [ ] **Step 7: Commit**

```bash
git add hermes_agents/core/vendas.py hermes_agents/core/i9logic_vendas.py hermes_agents/tests/test_i9logic_vendas.py
git commit -m "feat: ciclo de sincronizacao de vendas PDV i9Logic

Janela rolante por data (autocura sem checkpoint persistido), pula pedido
ja sincronizado antes de gastar rate limit, teto MAX_PEDIDOS_NOVOS_POR_CICLO,
aceita data_de/data_ate explicitos pra backfill historico."
```

---

### Task 6: Rota `POST /vendas/sincronizar` + job recorrente no scheduler

**Files:**
- Modify: `hermes_agents/routes/i9logic.py`
- Modify: `hermes_agents/core/scheduler.py`
- Modify: `hermes_agents/tests/test_i9logic.py` (rota)
- Create: `hermes_agents/tests/test_scheduler_i9logic.py` (job)

**Interfaces:**
- Consumes: `core.i9logic_vendas.sincronizar_pedidos_i9logic` (Task 5).
- Produces: rota `POST /api/integrations/i9logic/vendas/sincronizar`; `core.scheduler._sync_pedidos_i9logic` registrado via `add_job(..., "i9logic-pedidos", 600)`.

- [ ] **Step 1: Escrever o teste do job que falha**

Criar `hermes_agents/tests/test_scheduler_i9logic.py`:

```python
"""Job de sync automatico de vendas PDV i9Logic (core/scheduler.py::_sync_pedidos_i9logic)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock
import unittest

_fake_conn = AsyncMock()
_fake_conn.fetch.return_value = []
_fake_conn.fetchrow.return_value = None
_fake_conn.fetchval.return_value = 0
_fake_conn.execute.return_value = "OK"

async def _mock_create_pool(*a, **kw):
    pool = AsyncMock()
    pool.acquire.return_value = _fake_conn
    return pool

_pool_patcher = patch("asyncpg.create_pool", side_effect=_mock_create_pool)
_pool_patcher.start()

from core.scheduler import _sync_pedidos_i9logic


class TestSyncPedidosI9Logic(unittest.TestCase):
    @patch("core.i9logic_vendas.sincronizar_pedidos_i9logic")
    def test_chama_sincronizacao(self, mock_sync):
        mock_sync.return_value = {"ok": True, "sincronizados": 3}
        _sync_pedidos_i9logic()
        mock_sync.assert_called_once_with()

    @patch("core.i9logic_vendas.sincronizar_pedidos_i9logic")
    def test_erro_nao_propaga(self, mock_sync):
        mock_sync.side_effect = Exception("API fora do ar")
        try:
            _sync_pedidos_i9logic()
        except Exception as e:
            self.fail(f"_sync_pedidos_i9logic nao deveria propagar excecao: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

E adicionar em `hermes_agents/tests/test_i9logic.py`, dentro de `TestRotasI9Logic`:

```python
    def test_sincronizar_vendas_exige_estoque_editar(self):
        headers = self._headers_com_permissao([])
        with patch("core.rbac.usuario_tem_permissao", return_value=False):
            r = self.client.post("/api/integrations/i9logic/vendas/sincronizar", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_sincronizar_vendas_com_permissao_libera(self):
        headers = self._headers_com_permissao(["estoque.editar"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.sincronizar_pedidos_i9logic",
                   return_value={"ok": True, "sincronizados": 2}) as mock_sync:
            r = self.client.post("/api/integrations/i9logic/vendas/sincronizar", headers=headers, json={})
        self.assertEqual(r.status_code, 200)
        mock_sync.assert_called_once_with(data_de=None, data_ate=None)
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `python -m pytest hermes_agents/tests/test_scheduler_i9logic.py hermes_agents/tests/test_i9logic.py -v -k "i9logic and (sincronizar_vendas or SyncPedidosI9Logic)"`
Expected: FAIL — rota 404 e `ImportError: cannot import name '_sync_pedidos_i9logic'`.

- [ ] **Step 3: Implementar a rota**

Em `hermes_agents/routes/i9logic.py`, adicionar ao bloco de imports:

```python
from core.i9logic_vendas import sincronizar_pedidos_i9logic
```

E ao final do arquivo:

```python
@i9logic_bp.route("/vendas/sincronizar", methods=["POST"])
def i9logic_sincronizar_vendas():
    """Dispara um ciclo de sync de vendas PDV. Sem data_de/data_ate no corpo,
    usa a janela rolante padrao (mesma que o job recorrente do scheduler);
    com data_de/data_ate, serve de backfill manual de historico."""
    @requer_permissao("estoque.editar")
    def _go():
        dados = request.get_json(silent=True) or {}
        return jsonify(sincronizar_pedidos_i9logic(
            data_de=dados.get("data_de"), data_ate=dados.get("data_ate")))
    return _go()
```

- [ ] **Step 4: Implementar o job no scheduler**

Em `hermes_agents/core/scheduler.py`, adicionar (após `_renovar_tokens_shopee`, antes de `_sync_categorias`):

```python
def _sync_pedidos_i9logic():
    try:
        from core.i9logic_vendas import sincronizar_pedidos_i9logic
        r = sincronizar_pedidos_i9logic()
        if r.get("sincronizados", 0) > 0:
            log(AGENT, f"Pedidos i9Logic sync: {r['sincronizados']}")
    except Exception as e:
        log(AGENT, f"Erro sync pedidos i9Logic: {e}")
```

E na lista de `add_job(...)` no final do arquivo, adicionar:

```python
add_job(_sync_pedidos_i9logic, "i9logic-pedidos", 600)  # 10 min
```

- [ ] **Step 5: Rodar e confirmar que passam**

Run: `python -m pytest hermes_agents/tests/test_scheduler_i9logic.py hermes_agents/tests/test_i9logic.py -v`
Expected: todos passando (2 do job + 2 da rota + os já existentes de `test_i9logic.py`).

- [ ] **Step 6: Rodar a suíte inteira do projeto**

Run: `python -m pytest hermes_agents/tests/ -q`
Expected: 100% verde, nenhuma regressão em nenhum arquivo de teste (`test_i9logic.py`, `test_i9logic_catalogo.py`, `test_i9logic_vendas.py`, `test_scheduler_i9logic.py`, `test_scheduler_pedidos_shopee.py`, `test_fase4_fase1.py`, etc).

- [ ] **Step 7: Commit**

```bash
git add hermes_agents/routes/i9logic.py hermes_agents/core/scheduler.py hermes_agents/tests/test_i9logic.py hermes_agents/tests/test_scheduler_i9logic.py
git commit -m "feat: rota de sync manual de vendas + job recorrente no scheduler (10min)

POST /api/integrations/i9logic/vendas/sincronizar aceita data_de/data_ate
opcionais pra backfill; job do scheduler roda sem args (janela rolante padrao)."
```

---

## Depois do merge (pendência operacional do usuário, fora de escopo do código)

As 8 filiais reais do i9Logic precisam de de-para (`tipo='filial'`, via `POST /api/integrations/i9logic/depara` ou `/depara/matching`, já existentes da Fase 1) antes do sync de vendas funcionar pra elas. Sem isso, `sincronizar_pedidos_i9logic()` roda normalmente mas todo pedido cai em `pulados_filial_nao_mapeada` (comportamento esperado, não é bug).
