# Estoque Rápido (Shopee) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar uma aba "Estoque Rápido" que mostra um grid único (SKU × loja Shopee) e permite editar quantidade de estoque inline, com sync síncrono e feedback visual por célula direto na API oficial da Shopee — sem Playwright/navegador.

**Architecture:** Reusa 100% do motor de estoque/sync já existente (`core.estoque.ajustar_absoluto`, `shopee.stock.sincronizar_estoque_shopee`, `core.lojas.listar_lojas_shopee`/`_loja_efetiva_async`). Só adiciona: 1 módulo backend novo (`shopee/estoque_rapido.py`) com 2 funções (montar o grid, salvar 1 célula), 2 rotas Flask que os expõem, e 1 página frontend nova que consome essas rotas.

**Tech Stack:** Python 3.13 / Flask / asyncpg (backend `hermes_agents/`), Next.js / React / TypeScript (frontend `web/`), pytest + unittest.mock (testes backend, sem DB real — todo `asyncpg.create_pool` é mockado).

**Spec:** [docs/superpowers/specs/2026-08-06-estoque-rapido-shopee-design.md](../specs/2026-08-06-estoque-rapido-shopee-design.md)

## Global Constraints

- Só Shopee (nenhum outro marketplace nesta feature).
- Nenhuma tabela nova — só `anuncios`, `estoque_lojas`, `lojas`, `catalogo_produtos` (já existentes).
- Sync com a Shopee é **síncrono** por célula (não thread solta) — usuário precisa ver sucesso/erro na hora.
- Falha ao salvar localmente **nunca** dispara a chamada à Shopee.
- Escopo é só quantidade — sem preço/outros campos de `produtos_loja`.
- Rodar testes backend a partir da raiz do repo: `python -m pytest hermes_agents/tests/<arquivo>.py -v` (confirmado funcionando nesta máquina).

---

### Task 1: Backend — montar o grid (`listar_grid_estoque_rapido`)

**Files:**
- Create: `hermes_agents/shopee/estoque_rapido.py`
- Test: `hermes_agents/tests/test_shopee_estoque_rapido.py`

**Interfaces:**
- Consumes: `core.lojas.listar_lojas_shopee() -> list[dict]` (chaves `id, nome, shopee_shop_id, shopee_shop_name, shopee_token_expira_em, tem_token`), `core.lojas._loja_efetiva_async(loja: str) -> str` (async), `core.get_db()`/`core.run_async()`.
- Produces: `listar_grid_estoque_rapido(busca: str = "", pagina: int = 1, por_pagina: int = 50, skus: list = None) -> dict` retornando `{"lojas": [{"id": int, "nome": str, "shopee_shop_name": str}], "produtos": [{"sku": str, "nome": str, "estoque": {<loja_id int>: float|None}}], "total": int}`. Usado pela Task 2 (via `skus=[sku]` para re-buscar 1 linha) e pela Task 3 (rota GET).

- [ ] **Step 1: Escrever o teste que falha — grid resolve ausência de anúncio e loja vinculada**

Criar `hermes_agents/tests/test_shopee_estoque_rapido.py`:

```python
"""Testes de shopee/estoque_rapido.py — grid SKU x loja Shopee (aba Estoque
Rapido) e salvamento de 1 celula com sync sincrono pra Shopee."""
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

_db_table_patcher = patch("core.config._ensure_db_table", return_value=False)
_db_table_patcher.start()

import shopee.estoque_rapido as estoque_rapido


class TestListarGridEstoqueRapido(unittest.TestCase):

    @patch("shopee.estoque_rapido._loja_efetiva_async", new_callable=AsyncMock)
    @patch("shopee.estoque_rapido.listar_lojas_shopee")
    @patch("shopee.estoque_rapido.get_db")
    def test_grid_resolve_anuncio_ausente_e_loja_vinculada(self, mock_get_db, mock_lojas, mock_efetiva):
        mock_lojas.return_value = [
            {"id": 1, "nome": "Loja A", "shopee_shop_id": "111", "shopee_shop_name": "Shop A"},
            {"id": 2, "nome": "Loja Virtual B", "shopee_shop_id": "222", "shopee_shop_name": "Shop B"},
        ]
        # Loja A nao tem vinculo (efetiva = ela mesma). Loja Virtual B e' vinculada
        # a "Loja Fisica X" — o saldo mora la', nao sob o proprio nome dela.
        mock_efetiva.side_effect = lambda nome: {"Loja A": "Loja A", "Loja Virtual B": "Loja Fisica X"}[nome]

        fake_db = AsyncMock()
        fake_db.fetch.side_effect = [
            [{"sku": "SKU1", "nome": "Produto 1"}],                      # sku_rows
            [{"sku": "SKU1", "shop_id": "222"}],                         # pares (so' tem anuncio na loja 2)
            [{"sku": "SKU1", "loja": "Loja Fisica X", "quantidade": 25}],  # saldos
        ]
        mock_get_db.return_value = fake_db

        r = estoque_rapido.listar_grid_estoque_rapido(skus=["SKU1"])

        self.assertEqual(r["produtos"], [
            {"sku": "SKU1", "nome": "Produto 1", "estoque": {1: None, 2: 25.0}}
        ])
        self.assertEqual(r["total"], 1)
        fake_db.fetchval.assert_not_called()  # skus= bypassa contagem/paginacao

    @patch("shopee.estoque_rapido.listar_lojas_shopee")
    @patch("shopee.estoque_rapido.get_db")
    def test_sem_lojas_shopee_retorna_vazio(self, mock_get_db, mock_lojas):
        mock_lojas.return_value = []
        fake_db = AsyncMock()
        mock_get_db.return_value = fake_db

        r = estoque_rapido.listar_grid_estoque_rapido(busca="qualquer")

        self.assertEqual(r, {"lojas": [], "produtos": [], "total": 0})
        fake_db.fetch.assert_not_called()

    @patch("shopee.estoque_rapido._loja_efetiva_async", new_callable=AsyncMock)
    @patch("shopee.estoque_rapido.listar_lojas_shopee")
    @patch("shopee.estoque_rapido.get_db")
    def test_busca_com_paginacao_usa_fetchval_para_total(self, mock_get_db, mock_lojas, mock_efetiva):
        mock_lojas.return_value = [{"id": 1, "nome": "Loja A", "shopee_shop_id": "111", "shopee_shop_name": "Shop A"}]
        mock_efetiva.side_effect = lambda nome: nome

        fake_db = AsyncMock()
        fake_db.fetchval.return_value = 1
        fake_db.fetch.side_effect = [
            [{"sku": "SKU1", "nome": "Produto 1"}],                # sku_rows (pagina)
            [{"sku": "SKU1", "shop_id": "111"}],                   # pares
            [{"sku": "SKU1", "loja": "Loja A", "quantidade": 5}],  # saldos
        ]
        mock_get_db.return_value = fake_db

        r = estoque_rapido.listar_grid_estoque_rapido(busca="SKU1", pagina=1, por_pagina=50)

        self.assertEqual(r["total"], 1)
        self.assertEqual(r["produtos"][0]["estoque"], {1: 5.0})
        fake_db.fetchval.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar o teste e confirmar que falha (módulo não existe)**

Run: `python -m pytest hermes_agents/tests/test_shopee_estoque_rapido.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'shopee.estoque_rapido'`

- [ ] **Step 3: Implementar `hermes_agents/shopee/estoque_rapido.py`**

```python
"""Shopee Estoque Rapido — grid SKU x loja para edicao em lote de estoque,
substituindo o fluxo Playwright do sistema ESTOQUE RAPIDO externo por
chamadas diretas a API oficial da Shopee.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core import get_db, run_async
from core.lojas import listar_lojas_shopee, _loja_efetiva_async, obter
from core.estoque import ajustar_absoluto
from .stock import sincronizar_estoque_shopee

AGENT = "AG-03 | Shopee Estoque Rapido"


def listar_grid_estoque_rapido(busca: str = "", pagina: int = 1, por_pagina: int = 50,
                                skus: list = None) -> dict:
    """Monta o grid SKU x loja Shopee. Com `skus` informado, ignora busca/
    paginacao e retorna exatamente aquelas linhas (usado por
    atualizar_celula_estoque_rapido pra reler 1 linha apos salvar)."""
    async def _go():
        db = await get_db()
        lojas = listar_lojas_shopee()
        if not lojas:
            return {"lojas": [], "produtos": [], "total": 0}
        shop_ids = [l["shopee_shop_id"] for l in lojas]

        if skus:
            sku_rows = await db.fetch(
                "SELECT DISTINCT a.sku, c.descricao AS nome FROM anuncios a "
                "LEFT JOIN catalogo_produtos c ON c.sku = a.sku "
                "WHERE a.marketplace = 'shopee' AND a.shop_id = ANY($1) AND a.sku = ANY($2) "
                "ORDER BY a.sku", shop_ids, skus)
            total = len(sku_rows)
        else:
            where = ["a.marketplace = 'shopee'", "a.shop_id = ANY($1)"]
            params = [shop_ids]
            if busca:
                n = len(params) + 1
                where.append(f"(a.sku ILIKE ${n} OR c.descricao ILIKE ${n})")
                params.append(f"%{busca}%")
            sql_where = " AND ".join(where)
            total = await db.fetchval(
                f"SELECT COUNT(DISTINCT a.sku) FROM anuncios a "
                f"LEFT JOIN catalogo_produtos c ON c.sku = a.sku WHERE {sql_where}", *params)
            offset = (pagina - 1) * por_pagina
            n = len(params) + 1
            sku_rows = await db.fetch(
                f"SELECT DISTINCT a.sku, c.descricao AS nome FROM anuncios a "
                f"LEFT JOIN catalogo_produtos c ON c.sku = a.sku WHERE {sql_where} "
                f"ORDER BY a.sku LIMIT ${n} OFFSET ${n + 1}", *params, por_pagina, offset)

        lojas_out = [{"id": l["id"], "nome": l["nome"], "shopee_shop_name": l["shopee_shop_name"]} for l in lojas]
        skus_pagina = [r["sku"] for r in sku_rows]
        if not skus_pagina:
            return {"lojas": lojas_out, "produtos": [], "total": total}

        pares = await db.fetch(
            "SELECT sku, shop_id FROM anuncios WHERE marketplace = 'shopee' "
            "AND sku = ANY($1) AND shop_id = ANY($2)", skus_pagina, shop_ids)
        pares_set = {(p["sku"], p["shop_id"]) for p in pares}

        nomes_efetivos = {l["id"]: await _loja_efetiva_async(l["nome"]) for l in lojas}
        nomes_unicos = list(set(nomes_efetivos.values()))

        saldos = await db.fetch(
            "SELECT sku, loja, quantidade FROM estoque_lojas WHERE sku = ANY($1) AND loja = ANY($2)",
            skus_pagina, nomes_unicos)
        saldo_map = {(s["sku"], s["loja"]): float(s["quantidade"]) for s in saldos}

        produtos = []
        for r in sku_rows:
            estoque = {}
            for l in lojas:
                tem_anuncio = (r["sku"], l["shopee_shop_id"]) in pares_set
                if not tem_anuncio:
                    estoque[l["id"]] = None
                else:
                    nome_efetivo = nomes_efetivos[l["id"]]
                    estoque[l["id"]] = saldo_map.get((r["sku"], nome_efetivo), 0.0)
            produtos.append({"sku": r["sku"], "nome": r["nome"] or r["sku"], "estoque": estoque})

        return {"lojas": lojas_out, "produtos": produtos, "total": total}
    return run_async(_go())
```

- [ ] **Step 4: Rodar o teste e confirmar que passa**

Run: `python -m pytest hermes_agents/tests/test_shopee_estoque_rapido.py -v`
Expected: PASS (3 testes)

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/shopee/estoque_rapido.py hermes_agents/tests/test_shopee_estoque_rapido.py
git commit -m "feat: monta grid SKU x loja Shopee pro Estoque Rapido"
```

---

### Task 2: Backend — salvar 1 célula (`atualizar_celula_estoque_rapido`)

**Files:**
- Modify: `hermes_agents/shopee/estoque_rapido.py`
- Test: `hermes_agents/tests/test_shopee_estoque_rapido.py`

**Interfaces:**
- Consumes: `core.lojas.obter(id_loja: int) -> dict|None`, `core.estoque.ajustar_absoluto(sku, loja, quantidade_absoluta, motivo, usuario_id, usuario_nome, ip, dispositivo) -> dict` (retorna `{"erro": str}` em falha), `shopee.stock.sincronizar_estoque_shopee(sku, quantidade, loja_id) -> dict` (retorna `{"error": str}` em falha), `listar_grid_estoque_rapido(skus=[sku])` (Task 1).
- Produces: `atualizar_celula_estoque_rapido(sku: str, loja_id: int, quantidade: float, usuario: dict, ip: str = None, dispositivo: str = None) -> dict` retornando `{"ok": bool, "salvo_local": bool, "erro_shopee": str|None, "erro_local": str (só quando ok=False e salvo_local ausente/False), "linha": dict|None}`. Usado pela Task 3 (rota PUT).

- [ ] **Step 1: Adicionar os testes que falham**

Adicionar ao final de `hermes_agents/tests/test_shopee_estoque_rapido.py` (antes do `if __name__ == "__main__":`):

```python
class TestAtualizarCelulaEstoqueRapido(unittest.TestCase):

    @patch("shopee.estoque_rapido.listar_grid_estoque_rapido")
    @patch("shopee.estoque_rapido.sincronizar_estoque_shopee")
    @patch("shopee.estoque_rapido.ajustar_absoluto")
    @patch("shopee.estoque_rapido.obter")
    def test_sucesso_local_e_shopee(self, mock_obter, mock_ajustar, mock_sync, mock_grid):
        mock_obter.return_value = {"id": 1, "nome": "Loja A"}
        mock_ajustar.return_value = {"ok": True, "sku": "SKU1", "loja": "Loja A", "quantidade": 10, "anterior": 5, "atual": 10}
        mock_sync.return_value = {"success": True}
        mock_grid.return_value = {"produtos": [{"sku": "SKU1", "nome": "Produto 1", "estoque": {1: 10.0}}], "lojas": [], "total": 1}

        r = estoque_rapido.atualizar_celula_estoque_rapido(
            "SKU1", 1, 10, {"user_id": 9, "nome": "Ana"}, "127.0.0.1", "pytest")

        mock_ajustar.assert_called_once_with("SKU1", "Loja A", 10, "estoque_rapido", 9, "Ana", "127.0.0.1", "pytest")
        mock_sync.assert_called_once_with("SKU1", 10, loja_id=1)
        mock_grid.assert_called_once_with(skus=["SKU1"])
        self.assertEqual(r, {
            "ok": True, "salvo_local": True, "erro_shopee": None,
            "linha": {"sku": "SKU1", "nome": "Produto 1", "estoque": {1: 10.0}},
        })

    @patch("shopee.estoque_rapido.ajustar_absoluto")
    @patch("shopee.estoque_rapido.obter")
    def test_loja_nao_encontrada_nao_chama_ajustar(self, mock_obter, mock_ajustar):
        mock_obter.return_value = None

        r = estoque_rapido.atualizar_celula_estoque_rapido(
            "SKU1", 999, 10, {"user_id": 9, "nome": "Ana"})

        self.assertEqual(r, {"ok": False, "erro_local": "Loja 999 nao encontrada"})
        mock_ajustar.assert_not_called()

    @patch("shopee.estoque_rapido.sincronizar_estoque_shopee")
    @patch("shopee.estoque_rapido.ajustar_absoluto")
    @patch("shopee.estoque_rapido.obter")
    def test_falha_local_nao_chama_shopee(self, mock_obter, mock_ajustar, mock_sync):
        mock_obter.return_value = {"id": 1, "nome": "Loja A"}
        mock_ajustar.return_value = {"erro": "saldo negativo nao permitido"}

        r = estoque_rapido.atualizar_celula_estoque_rapido(
            "SKU1", 1, -5, {"user_id": 9, "nome": "Ana"})

        self.assertEqual(r, {"ok": False, "erro_local": "saldo negativo nao permitido"})
        mock_sync.assert_not_called()

    @patch("shopee.estoque_rapido.listar_grid_estoque_rapido")
    @patch("shopee.estoque_rapido.sincronizar_estoque_shopee")
    @patch("shopee.estoque_rapido.ajustar_absoluto")
    @patch("shopee.estoque_rapido.obter")
    def test_sucesso_local_falha_shopee(self, mock_obter, mock_ajustar, mock_sync, mock_grid):
        mock_obter.return_value = {"id": 1, "nome": "Loja A"}
        mock_ajustar.return_value = {"ok": True}
        mock_sync.return_value = {"error": "token expirado"}
        mock_grid.return_value = {"produtos": [{"sku": "SKU1", "nome": "Produto 1", "estoque": {1: 10.0}}]}

        r = estoque_rapido.atualizar_celula_estoque_rapido(
            "SKU1", 1, 10, {"user_id": 9, "nome": "Ana"})

        self.assertEqual(r["ok"], False)
        self.assertEqual(r["salvo_local"], True)
        self.assertEqual(r["erro_shopee"], "token expirado")
```

- [ ] **Step 2: Rodar os testes e confirmar que falham**

Run: `python -m pytest hermes_agents/tests/test_shopee_estoque_rapido.py -v`
Expected: FAIL — `AttributeError: module 'shopee.estoque_rapido' has no attribute 'atualizar_celula_estoque_rapido'`

- [ ] **Step 3: Implementar `atualizar_celula_estoque_rapido`**

Adicionar ao final de `hermes_agents/shopee/estoque_rapido.py`:

```python
def atualizar_celula_estoque_rapido(sku: str, loja_id: int, quantidade: float, usuario: dict,
                                     ip: str = None, dispositivo: str = None) -> dict:
    """Salva 1 celula do grid: grava saldo local e sincroniza com a Shopee de
    forma SINCRONA (nao dispara thread solta) — o usuario precisa ver na hora
    se a Shopee aceitou. Falha ao gravar local nunca chama a Shopee."""
    loja = obter(loja_id)
    if not loja:
        return {"ok": False, "erro_local": f"Loja {loja_id} nao encontrada"}

    resultado_local = ajustar_absoluto(sku, loja["nome"], quantidade, "estoque_rapido",
                                        usuario.get("user_id"), usuario.get("nome", ""), ip, dispositivo)
    if resultado_local.get("erro"):
        return {"ok": False, "erro_local": resultado_local["erro"]}

    resultado_shopee = sincronizar_estoque_shopee(sku, int(quantidade), loja_id=loja_id)
    grid = listar_grid_estoque_rapido(skus=[sku])
    linha = grid["produtos"][0] if grid["produtos"] else None

    return {
        "ok": "error" not in resultado_shopee,
        "salvo_local": True,
        "erro_shopee": resultado_shopee.get("error"),
        "linha": linha,
    }
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `python -m pytest hermes_agents/tests/test_shopee_estoque_rapido.py -v`
Expected: PASS (7 testes no total)

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/shopee/estoque_rapido.py hermes_agents/tests/test_shopee_estoque_rapido.py
git commit -m "feat: salva 1 celula do Estoque Rapido com sync sincrono pra Shopee"
```

---

### Task 3: Backend — rotas Flask + export do módulo

**Files:**
- Modify: `hermes_agents/shopee/__init__.py`
- Modify: `hermes_agents/routes/shopee.py`
- Test: `hermes_agents/tests/test_shopee_estoque_rapido_rotas.py`

**Interfaces:**
- Consumes: `listar_grid_estoque_rapido`, `atualizar_celula_estoque_rapido` (Tasks 1-2), `core.rbac.usuario_atual_da_request()`, `core.rbac._origem_requisicao` (não existe em `core.rbac` — replicar a mesma lógica inline, ver Step 3), `core.rbac.requer_permissao`.
- Produces: `GET /api/shopee/estoque-rapido?busca=&pagina=&por_pagina=`, `PUT /api/shopee/estoque-rapido/celula` — consumidos pela Task 4 (frontend).

- [ ] **Step 1: Exportar as novas funções em `hermes_agents/shopee/__init__.py`**

```python
# hermes_agents/shopee/__init__.py:32-35 (logo apos o import de .stock)
from .stock import (
    sincronizar_estoque_shopee, sincronizar_estoque_todas_lojas,
    sincronizar_estoque_todas_lojas_automatico,
)
from .estoque_rapido import listar_grid_estoque_rapido, atualizar_celula_estoque_rapido
```

- [ ] **Step 2: Escrever o teste de rota que falha**

Criar `hermes_agents/tests/test_shopee_estoque_rapido_rotas.py` (mesmo padrão de `test_shopee_fulfillment_rotas.py`):

```python
"""Testes de integracao — rotas GET/PUT /api/shopee/estoque-rapido em
routes/shopee.py (aba Estoque Rapido)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

from flask import Flask
from routes.shopee import shopee_bp

_TEST_TOKEN = "test-master-token-32-bytes-long!!"


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(shopee_bp)
    return app.test_client()


class TestEstoqueRapidoGet(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_lista_grid_chama_core_com_params(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("shopee.listar_grid_estoque_rapido",
                    return_value={"lojas": [], "produtos": [], "total": 0}) as mock_listar:
            r = self.client.get("/api/shopee/estoque-rapido?busca=SKU1&pagina=2&por_pagina=25", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_listar.assert_called_once_with(busca="SKU1", pagina=2, por_pagina=25)


class TestEstoqueRapidoCelula(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_sem_campos_obrigatorios_retorna_400(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.put("/api/shopee/estoque-rapido/celula", json={"sku": "SKU1"}, headers=headers)
        self.assertEqual(r.status_code, 400)

    def test_sem_token_retorna_403(self):
        r = self.client.put("/api/shopee/estoque-rapido/celula",
                             json={"sku": "SKU1", "loja_id": 1, "quantidade": 10})
        self.assertEqual(r.status_code, 403)

    def test_com_token_master_chama_core(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("shopee.atualizar_celula_estoque_rapido",
                    return_value={"ok": True, "salvo_local": True, "erro_shopee": None, "linha": {}}) as mock_at:
            r = self.client.put("/api/shopee/estoque-rapido/celula",
                                 json={"sku": "SKU1", "loja_id": 1, "quantidade": 10}, headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["ok"], True)
        mock_at.assert_called_once()
        args, kwargs = mock_at.call_args
        self.assertEqual(args[0], "SKU1")
        self.assertEqual(args[1], 1)
        self.assertEqual(args[2], 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 3: Rodar os testes e confirmar que falham**

Run: `python -m pytest hermes_agents/tests/test_shopee_estoque_rapido_rotas.py -v`
Expected: FAIL — `404 NOT FOUND` (rotas não existem ainda)

- [ ] **Step 4: Implementar as rotas em `hermes_agents/routes/shopee.py`**

Adicionar logo após a rota `shopee_atualizar_estoque_produto` (linha 609-624, ver Task interfaces):

```python
@shopee_bp.route('/estoque-rapido', methods=['GET'])
def shopee_estoque_rapido_listar():
    from shopee import listar_grid_estoque_rapido
    busca = request.args.get("busca", "")
    pagina = request.args.get("pagina", 1, type=int)
    por_pagina = request.args.get("por_pagina", 50, type=int)
    try:
        return jsonify(listar_grid_estoque_rapido(busca=busca, pagina=pagina, por_pagina=por_pagina))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@shopee_bp.route('/estoque-rapido/celula', methods=['PUT'])
def shopee_estoque_rapido_atualizar_celula():
    from core.rbac import requer_permissao, usuario_atual_da_request

    @requer_permissao("produtos.editar")
    def _handler():
        from shopee import atualizar_celula_estoque_rapido
        data = request.json or {}
        sku = data.get("sku")
        loja_id = data.get("loja_id")
        quantidade = data.get("quantidade")
        if not sku or loja_id is None or quantidade is None:
            return jsonify({"error": "sku, loja_id e quantidade sao obrigatorios"}), 400
        usuario = usuario_atual_da_request()
        ip = request.remote_addr
        dispositivo = request.headers.get("User-Agent", "")[:300]
        try:
            return jsonify(atualizar_celula_estoque_rapido(sku, int(loja_id), float(quantidade), usuario, ip, dispositivo))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return _handler()
```

- [ ] **Step 5: Rodar os testes e confirmar que passam**

Run: `python -m pytest hermes_agents/tests/test_shopee_estoque_rapido_rotas.py -v`
Expected: PASS (4 testes)

- [ ] **Step 6: Rodar a suíte inteira de testes Shopee pra garantir que nada quebrou**

Run: `python -m pytest hermes_agents/tests/test_shopee_stock.py hermes_agents/tests/test_shopee_estoque_rapido.py hermes_agents/tests/test_shopee_estoque_rapido_rotas.py hermes_agents/tests/test_shopee_fulfillment_rotas.py -v`
Expected: PASS (todos)

- [ ] **Step 7: Commit**

```bash
git add hermes_agents/shopee/__init__.py hermes_agents/routes/shopee.py hermes_agents/tests/test_shopee_estoque_rapido_rotas.py
git commit -m "feat: expoe rotas GET/PUT do Estoque Rapido em /api/shopee/estoque-rapido"
```

---

### Task 4: Frontend — funções de API (`web/src/lib/api.ts`)

**Files:**
- Modify: `web/src/lib/api.ts`

**Interfaces:**
- Consumes: `request<T>(path, options)` helper já existente no topo do arquivo (`web/src/lib/api.ts:30-46`).
- Produces: `api.shopeeEstoqueRapidoListar(params)` e `api.shopeeEstoqueRapidoAtualizarCelula(sku, lojaId, quantidade)`, tipos `EstoqueRapidoLoja` e `EstoqueRapidoProduto` — consumidos pela Task 5.

- [ ] **Step 1: Adicionar os tipos e as duas funções, logo após `shopeeEstoqueTodasLojas` (`web/src/lib/api.ts:206-210`)**

```typescript
export interface EstoqueRapidoLoja {
  id: number;
  nome: string;
  shopee_shop_name: string;
}

export interface EstoqueRapidoProduto {
  sku: string;
  nome: string;
  estoque: Record<number, number | null>;
}
```
(adicionar essas duas interfaces no topo do arquivo, junto às outras `interface`/`type` exportadas — ex.: logo acima de `ShopeeProdutoSincronizado`, se existir nesse bloco; caso contrário, imediatamente antes de `export const api = {`)

Dentro do objeto `api = { ... }`, logo após `shopeeEstoqueTodasLojas`:

```typescript
  shopeeEstoqueRapidoListar: (params: { busca?: string; pagina?: number; por_pagina?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.busca) q.set("busca", params.busca);
    if (params.pagina) q.set("pagina", String(params.pagina));
    if (params.por_pagina) q.set("por_pagina", String(params.por_pagina));
    return request<{ lojas: EstoqueRapidoLoja[]; produtos: EstoqueRapidoProduto[]; total: number }>(
      `/api/shopee/estoque-rapido?${q}`);
  },
  shopeeEstoqueRapidoAtualizarCelula: (sku: string, lojaId: number, quantidade: number) =>
    request<{ ok: boolean; salvo_local?: boolean; erro_shopee?: string | null; erro_local?: string; linha?: EstoqueRapidoProduto }>(
      "/api/shopee/estoque-rapido/celula", {
        method: "PUT",
        body: JSON.stringify({ sku, loja_id: lojaId, quantidade }),
      }),
```

- [ ] **Step 2: Verificar que o projeto compila (typecheck)**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros novos relacionados a `api.ts` (erros pré-existentes no projeto, se houver, não são desta task)

- [ ] **Step 3: Commit**

```bash
git add web/src/lib/api.ts
git commit -m "feat: adiciona funcoes de API do Estoque Rapido no frontend"
```

---

### Task 5: Frontend — página da grid (`web/src/app/estoque/rapido/page.tsx`)

**Files:**
- Create: `web/src/app/estoque/rapido/page.tsx`

**Interfaces:**
- Consumes: `api.shopeeEstoqueRapidoListar`, `api.shopeeEstoqueRapidoAtualizarCelula`, `EstoqueRapidoLoja`, `EstoqueRapidoProduto` (Task 4); `Can` de `@/lib/auth`; `Icon` de `@/app/_components/Icon`.
- Produces: rota `/estoque/rapido` — consumida pela Task 6 (link de menu).

- [ ] **Step 1: Criar a página**

```tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { api, type EstoqueRapidoLoja, type EstoqueRapidoProduto } from "@/lib/api";
import { Can } from "@/lib/auth";

type CellStatus = "idle" | "salvando" | "ok" | "erro";

export default function EstoqueRapidoPage() {
  const [lojas, setLojas] = useState<EstoqueRapidoLoja[]>([]);
  const [produtos, setProdutos] = useState<EstoqueRapidoProduto[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState(1);
  const POR_PAGINA = 50;

  const [valores, setValores] = useState<Record<string, string>>({});
  const [status, setStatus] = useState<Record<string, CellStatus>>({});
  const [mensagemErro, setMensagemErro] = useState<Record<string, string>>({});

  const chave = (sku: string, lojaId: number) => `${sku}:${lojaId}`;

  const load = useCallback(async (buscaAtual: string, pg: number) => {
    setLoading(true);
    setErro(null);
    try {
      const r = await api.shopeeEstoqueRapidoListar({ busca: buscaAtual, pagina: pg, por_pagina: POR_PAGINA });
      setLojas(r.lojas);
      setProdutos(r.produtos);
      setTotal(r.total);
      const iniciais: Record<string, string> = {};
      r.produtos.forEach((p) => {
        r.lojas.forEach((l) => {
          const q = p.estoque[l.id];
          if (q !== null && q !== undefined) iniciais[chave(p.sku, l.id)] = String(q);
        });
      });
      setValores(iniciais);
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar grid de estoque");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(busca, 1); }, [load]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPagina(1);
    load(busca, 1);
  };

  const salvarCelula = async (sku: string, lojaId: number) => {
    const k = chave(sku, lojaId);
    const quantidade = Number(valores[k]);
    if (!Number.isFinite(quantidade) || quantidade < 0) return;
    setStatus((s) => ({ ...s, [k]: "salvando" }));
    try {
      const r = await api.shopeeEstoqueRapidoAtualizarCelula(sku, lojaId, quantidade);
      if (!r.ok) {
        setStatus((s) => ({ ...s, [k]: "erro" }));
        setMensagemErro((m) => ({ ...m, [k]: r.erro_shopee || r.erro_local || "Falha ao salvar" }));
      } else {
        setStatus((s) => ({ ...s, [k]: "ok" }));
        setMensagemErro((m) => ({ ...m, [k]: "" }));
      }
      if (r.linha) {
        setProdutos((prev) => prev.map((p) => (p.sku === r.linha!.sku ? r.linha! : p)));
        const novosValores: Record<string, string> = {};
        lojas.forEach((l) => {
          const q = r.linha!.estoque[l.id];
          if (q !== null && q !== undefined) novosValores[chave(r.linha!.sku, l.id)] = String(q);
        });
        setValores((v) => ({ ...v, ...novosValores }));
      }
    } catch (e: unknown) {
      setStatus((s) => ({ ...s, [k]: "erro" }));
      setMensagemErro((m) => ({ ...m, [k]: e instanceof Error ? e.message : "Erro ao salvar" }));
    }
  };

  const totalPaginas = Math.max(1, Math.ceil(total / POR_PAGINA));

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-lg font-light text-neutral-300">Estoque Rápido</h1>
        <p className="text-xs text-neutral-500 mt-0.5">{total} SKU{total !== 1 ? "s" : ""} com anúncio em alguma loja Shopee</p>
      </div>

      {erro && (
        <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">{erro}</div>
      )}

      <form onSubmit={handleSearch} className="flex gap-2 max-w-md">
        <label htmlFor="buscaRapido" className="sr-only">Buscar SKU</label>
        <input
          id="buscaRapido"
          type="text"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          placeholder="Buscar por SKU ou nome..."
          className="flex-1 bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-transparent"
        />
        <button type="submit" className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 rounded-lg text-sm transition-colors">
          Buscar
        </button>
      </form>

      {loading ? (
        <div className="text-neutral-500 text-sm">Carregando...</div>
      ) : lojas.length === 0 ? (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-8 text-center text-neutral-500 text-xs">
          Nenhuma loja Shopee conectada. Conecte uma loja em{" "}
          <a href="/integracoes/shopee" className="text-indigo-400 underline">Integrações &gt; Shopee</a>.
        </div>
      ) : produtos.length === 0 ? (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-8 text-center text-neutral-500 text-xs">
          Nenhum SKU encontrado com anúncio Shopee.
        </div>
      ) : (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-800 text-neutral-500 text-xs uppercase">
                  <th className="text-left px-4 py-3 font-medium">SKU</th>
                  {lojas.map((l) => (
                    <th key={l.id} className="text-right px-4 py-3 font-medium w-32">{l.nome}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {produtos.map((p) => (
                  <tr key={p.sku} className="border-b border-neutral-800/50 hover:bg-neutral-800/20">
                    <td className="px-4 py-2.5">
                      <div className="font-mono text-xs text-neutral-500">{p.sku}</div>
                      <div className="text-neutral-300 text-xs max-w-64 truncate">{p.nome}</div>
                    </td>
                    {lojas.map((l) => {
                      const temAnuncio = p.estoque[l.id] !== null && p.estoque[l.id] !== undefined;
                      const k = chave(p.sku, l.id);
                      const st = status[k] ?? "idle";
                      if (!temAnuncio) {
                        return <td key={l.id} className="px-4 py-2.5 text-right text-neutral-600 text-xs">—</td>;
                      }
                      return (
                        <td key={l.id} className="px-4 py-2.5 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <Can permission="produtos.editar">
                              <input
                                type="number"
                                min="0"
                                step="1"
                                value={valores[k] ?? ""}
                                onChange={(e) => setValores((v) => ({ ...v, [k]: e.target.value }))}
                                onBlur={() => salvarCelula(p.sku, l.id)}
                                onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
                                disabled={st === "salvando"}
                                title={st === "erro" ? mensagemErro[k] : undefined}
                                className={`w-20 bg-neutral-800 border rounded px-2 py-1 text-xs text-right text-neutral-200 numeric focus:outline-none disabled:opacity-60 ${
                                  st === "erro" ? "border-red-600" : st === "ok" ? "border-emerald-700" : "border-neutral-700"
                                }`}
                              />
                            </Can>
                            {st === "salvando" && <span className="text-neutral-500 text-[10px]">...</span>}
                            {st === "ok" && <span className="text-emerald-400 text-xs">✓</span>}
                            {st === "erro" && <span className="text-red-400 text-xs" title={mensagemErro[k]}>✗</span>}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {totalPaginas > 1 && (
        <div className="flex items-center justify-center gap-1">
          <button disabled={pagina <= 1} onClick={() => { setPagina(pagina - 1); load(busca, pagina - 1); }}
            className="px-2 py-1 text-xs rounded bg-neutral-800 text-neutral-400 hover:bg-neutral-700 disabled:opacity-30">Anterior</button>
          <span className="text-xs text-neutral-500 px-2">{pagina} / {totalPaginas}</span>
          <button disabled={pagina >= totalPaginas} onClick={() => { setPagina(pagina + 1); load(busca, pagina + 1); }}
            className="px-2 py-1 text-xs rounded bg-neutral-800 text-neutral-400 hover:bg-neutral-700 disabled:opacity-30">Próxima</button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verificar que o projeto compila (typecheck)**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros novos relacionados a `estoque/rapido/page.tsx`

- [ ] **Step 3: Commit**

```bash
git add web/src/app/estoque/rapido/page.tsx
git commit -m "feat: pagina da grid Estoque Rapido com autosave e feedback por celula"
```

---

### Task 6: Frontend — link no menu lateral

**Files:**
- Modify: `web/src/app/layout.tsx`

**Interfaces:**
- Consumes: `NavChild` type já existente (`web/src/app/layout.tsx` — `type NavChild = { href: string; label: string; store?: "fisica" | "virtual" }`).
- Produces: item de menu visível em `/estoque` apontando para `/estoque/rapido` (Task 5).

- [ ] **Step 1: Adicionar o item no array `children` do grupo "Estoque"**

Em `web/src/app/layout.tsx`, dentro do item `estoque` (por volta da linha 102-111), adicionar `{ href: "/estoque/rapido", label: "Estoque Rápido", store: "virtual" }` como primeira entrada de `children` (destaque — é o atalho mais usado no dia a dia de lojas virtuais):

```typescript
      {
        href: "/estoque", label: "Estoque", icon: "estoque",
        children: [
          { href: "/estoque", label: "Visão Geral" },
          { href: "/estoque/rapido", label: "Estoque Rápido", store: "virtual" },
          { href: "/estoque/entrada", label: "Entrada (Scanner)", store: "fisica" },
          { href: "/estoque/saida", label: "Saída", store: "fisica" },
          { href: "/estoque/transferencias", label: "Transferências", store: "fisica" },
          { href: "/estoque/aprovacoes", label: "Aprovações", store: "fisica" },
          { href: "/estoque/contagem", label: "Contagem Cíclica", store: "fisica" },
          { href: "/estoque/discrepancias", label: "Discrepâncias" },
          { href: "/estoque/rotacao", label: "Rotação", store: "fisica" },
        ],
      },
```

- [ ] **Step 2: Verificar que o projeto compila (typecheck)**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros novos

- [ ] **Step 3: Commit**

```bash
git add web/src/app/layout.tsx
git commit -m "feat: adiciona Estoque Rapido ao menu lateral"
```

---

### Task 7: Verificação manual end-to-end

**Files:** nenhum (só verificação)

- [ ] **Step 1: Subir o backend**

Run: `cd hermes_agents && python athena_bridge.py` (entrypoint real — `app = Flask(__name__)` em `athena_bridge.py:196`, registra `shopee_bp` em `athena_bridge.py:255`, sobe com `app.run(...)` em `athena_bridge.py:2059`)
Expected: servidor sobe sem erro

- [ ] **Step 2: Subir o frontend**

Run: `cd web && npm run dev`
Expected: Next.js sobe em `http://localhost:3000` sem erro de build

- [ ] **Step 3: Testar o fluxo na UI**

1. Logar no Hermes, abrir menu Estoque → Estoque Rápido (`/estoque/rapido`).
2. Confirmar que a grid carrega com colunas = lojas Shopee conectadas e linhas = SKUs com anúncio.
3. Editar a quantidade de 1 célula, sair do campo (blur) ou apertar Enter.
4. Confirmar feedback: "..." durante o salvamento, depois ✓ verde (ou ✗ vermelho com tooltip, se a loja Shopee estiver com token expirado).
5. Recarregar a página e confirmar que o valor persistiu.
6. Buscar por um SKU específico e confirmar que a paginação/filtro funciona.

Expected: fluxo completo funciona sem erro de console/rede.

- [ ] **Step 4: Reportar quaisquer problemas encontrados antes de considerar a task concluída**

Se algo falhar, voltar à task backend/frontend correspondente, corrigir, e repetir a partir do Step 1 desta task.
