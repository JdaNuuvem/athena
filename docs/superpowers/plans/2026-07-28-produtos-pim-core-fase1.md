# Produtos PIM Core — Fase 1 (Identificação e Organização) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evoluir `catalogo_produtos` (SSOT já existente e usada por 17 arquivos) com campos de identificação
faltantes e taxonomias normalizadas de marca/fabricante/categoria/tag, sem quebrar nenhum consumidor existente.

**Architecture:** Extensão in-place, 100% aditiva. Novas colunas em `catalogo_produtos` via `ALTER TABLE ...
ADD COLUMN IF NOT EXISTS` (mesmo padrão já usado no arquivo). Quatro tabelas novas de apoio
(`catalogo_marcas`, `catalogo_fabricantes`, `catalogo_categorias`, `catalogo_tags` +
`catalogo_produto_tags`). RBAC e auditoria reaproveitam infraestrutura existente
(`core/rbac.py::requer_permissao`, `core/seguranca.py::auditar_alteracao`) — nenhuma tabela nova para isso.

**Tech Stack:** Python/Flask, asyncpg (via `core.get_db()`/`core.run_async()`), Postgres, pytest, Next.js/React/TypeScript, Tailwind.

## Global Constraints

- Nenhuma coluna ou tabela existente é removida ou renomeada nesta fase (spec: "Compatibilidade").
- `buscar_por_sku_ou_criar()` mantém assinatura atual — usada pelo sync do Bling.
- Toda escrita (criar/editar/excluir produto) passa a chamar `auditar_alteracao`/`auditar_exclusao` de
  `core/seguranca.py` e exigir a permissão RBAC correspondente via `requer_permissao` de `core/rbac.py`.
- Migração de dados (`marca`/`categoria` texto → tabelas normalizadas) roda dentro do `_ensure_tables()`
  existente, guardada por `SELECT COUNT(*)` — mesmo padrão de seed condicional já usado no arquivo.
- Coluna `nome` **não é criada** — a spec original pedia um campo `nome`, mas o campo `descricao` já cumpre
  esse papel na UI (`CadastroTab.tsx` linha 169, rotulado "Nome") e em todos os 17 consumidores. Criar `nome`
  duplicaria o conceito e confundiria quem edita. Ajuste feito durante o planejamento — ver nota no spec.

---

### Task 1: Colunas de identificação em `catalogo_produtos`

**Files:**
- Modify: `hermes_agents/core/catalogo.py` (dentro de `_ensure_tables()`, após o bloco de `ALTER TABLE` existente, linha ~80)
- Test: `hermes_agents/tests/test_catalogo_identificacao.py` (novo)

**Interfaces:**
- Consumes: nada de tasks anteriores (primeira task).
- Produces: colunas `classificacao`, `nome_reduzido`, `nome_impressao`, `codigo_interno`, `codigo_erp`,
  `ex_tipi`, `modelo`, `linha`, `colecao` em `catalogo_produtos`. Tasks seguintes (3, 4, 5) leem/escrevem essas
  colunas pelo nome.

- [ ] **Step 1: Escrever o teste que falha**

```python
# hermes_agents/tests/test_catalogo_identificacao.py
"""Fase 1 do PIM Core: novas colunas de identificacao em catalogo_produtos
devem ser criadas via ALTER TABLE ... IF NOT EXISTS, sem tocar nas colunas
existentes (compatibilidade com os 17 consumidores atuais)."""
import sys, os, unittest, importlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock, MagicMock

NOVAS_COLUNAS = [
    "classificacao", "nome_reduzido", "nome_impressao", "codigo_interno",
    "codigo_erp", "ex_tipi", "modelo", "linha", "colecao",
]


class TestColunasIdentificacao(unittest.TestCase):
    def test_ensure_tables_cria_novas_colunas(self):
        fake_db = MagicMock()
        fake_db.execute = AsyncMock(return_value="OK")
        fake_db.fetchval = AsyncMock(return_value=1)  # >0 => nao roda migracao de dedup
        fake_db.fetch = AsyncMock(return_value=[])
        fake_db.fetchrow = AsyncMock(return_value=None)

        with patch("core.get_db", new=AsyncMock(return_value=fake_db)):
            import core.catalogo as catalogo
            importlib.reload(catalogo)

        sql_executado = " ".join(str(c.args[0]) for c in fake_db.execute.call_args_list if c.args)
        for coluna in NOVAS_COLUNAS:
            self.assertIn(f"ADD COLUMN IF NOT EXISTS {coluna}", sql_executado,
                          f"coluna {coluna} nao foi criada")
        # nenhuma coluna existente pode ser removida ou renomeada
        self.assertNotIn("DROP COLUMN", sql_executado)
        self.assertNotIn("RENAME COLUMN", sql_executado)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `python -m pytest hermes_agents/tests/test_catalogo_identificacao.py -v`
Expected: FAIL — `AssertionError: 'ADD COLUMN IF NOT EXISTS classificacao' not found in ...`

- [ ] **Step 3: Adicionar as colunas em `core/catalogo.py`**

Inserir logo após a linha `await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS grupo VARCHAR(50)")` (linha 80):

```python
        # ── Fase 1 PIM Core: campos de identificacao (2026-07-28) ──
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS classificacao VARCHAR(20) DEFAULT 'simples'")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS nome_reduzido VARCHAR(100)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS nome_impressao VARCHAR(100)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS codigo_interno VARCHAR(50)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS codigo_erp VARCHAR(50)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS ex_tipi VARCHAR(10)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS modelo VARCHAR(100)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS linha VARCHAR(100)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS colecao VARCHAR(100)")
```

- [ ] **Step 4: Rodar o teste e confirmar que passa**

Run: `python -m pytest hermes_agents/tests/test_catalogo_identificacao.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/catalogo.py hermes_agents/tests/test_catalogo_identificacao.py
git commit -m "feat: adiciona colunas de identificacao PIM Core em catalogo_produtos"
```

---

### Task 2: Tabelas de organização (marcas, fabricantes, categorias, tags) + migração de dedup

**Files:**
- Modify: `hermes_agents/core/catalogo.py` (novas tabelas em `_ensure_tables()`, novas funções de CRUD no final do arquivo)
- Test: `hermes_agents/tests/test_catalogo_organizacao.py` (novo)

**Interfaces:**
- Consumes: nenhuma (independente de Task 1, mas convive no mesmo `_ensure_tables()`).
- Produces (funções públicas em `core/catalogo.py`, usadas pela Task 3):
  - `listar_marcas() -> list[dict]`
  - `criar_marca(nome: str) -> dict` (retorna `{"id": int, "nome": str}` ou `{"error": str}`)
  - `listar_fabricantes() -> list[dict]`
  - `criar_fabricante(nome: str) -> dict`
  - `listar_categorias() -> list[dict]` (cada item: `{id, nome, categoria_pai_id}`)
  - `criar_categoria(nome: str, categoria_pai_id: int = None) -> dict`
  - `listar_tags() -> list[dict]`
  - `criar_tag(nome: str) -> dict`
  - `tags_do_produto(produto_id: int) -> list[dict]`
  - `vincular_tag(produto_id: int, tag_id: int) -> dict`
  - `desvincular_tag(produto_id: int, tag_id: int) -> dict`

- [ ] **Step 1: Escrever o teste que falha**

```python
# hermes_agents/tests/test_catalogo_organizacao.py
"""Tabelas normalizadas de marca/fabricante/categoria/tag (Fase 1 PIM Core) e
o CRUD basico sobre elas."""
import sys, os, unittest, importlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock, MagicMock


def _fake_db(fetchval_return=1):
    db = MagicMock()
    db.execute = AsyncMock(return_value="OK")
    db.fetchval = AsyncMock(return_value=fetchval_return)
    db.fetch = AsyncMock(return_value=[])
    db.fetchrow = AsyncMock(return_value=None)
    return db


class TestTabelasOrganizacao(unittest.TestCase):
    def test_ensure_tables_cria_tabelas_normalizadas(self):
        fake_db = _fake_db(fetchval_return=1)  # >0 => pula migracao de dedup
        with patch("core.get_db", new=AsyncMock(return_value=fake_db)):
            import core.catalogo as catalogo
            importlib.reload(catalogo)
        sql_executado = " ".join(str(c.args[0]) for c in fake_db.execute.call_args_list if c.args)
        for tabela in ("catalogo_marcas", "catalogo_fabricantes", "catalogo_categorias",
                       "catalogo_tags", "catalogo_produto_tags"):
            self.assertIn(tabela, sql_executado, f"tabela {tabela} nao foi criada")


class TestCrudMarcas(unittest.TestCase):
    def test_criar_marca_retorna_id_e_nome(self):
        fake_db = _fake_db()
        fake_db.fetchrow = AsyncMock(return_value={"id": 1, "nome": "Nike"})
        with patch("core.catalogo.get_db", new=AsyncMock(return_value=fake_db)):
            import core.catalogo as catalogo
            resultado = catalogo.criar_marca("Nike")
        self.assertEqual(resultado, {"id": 1, "nome": "Nike"})

    def test_listar_marcas_retorna_lista(self):
        fake_db = _fake_db()
        fake_db.fetch = AsyncMock(return_value=[{"id": 1, "nome": "Nike"}, {"id": 2, "nome": "Adidas"}])
        with patch("core.catalogo.get_db", new=AsyncMock(return_value=fake_db)):
            import core.catalogo as catalogo
            resultado = catalogo.listar_marcas()
        self.assertEqual(len(resultado), 2)


class TestVinculoTags(unittest.TestCase):
    def test_vincular_tag_produto(self):
        fake_db = _fake_db()
        fake_db.execute = AsyncMock(return_value="INSERT 0 1")
        with patch("core.catalogo.get_db", new=AsyncMock(return_value=fake_db)):
            import core.catalogo as catalogo
            resultado = catalogo.vincular_tag(10, 3)
        self.assertEqual(resultado, {"success": True})
        fake_db.execute.assert_called_once()
        self.assertIn("catalogo_produto_tags", str(fake_db.execute.call_args.args[0]))


class TestMigracaoDedupMarca(unittest.TestCase):
    def test_migracao_so_roda_quando_tabela_vazia(self):
        """Se catalogo_marcas ja tem registros, a migracao de dedup nao deve
        rodar de novo (evita duplicar em todo boot)."""
        fake_db = _fake_db(fetchval_return=5)  # tabela ja populada
        with patch("core.get_db", new=AsyncMock(return_value=fake_db)):
            import core.catalogo as catalogo
            importlib.reload(catalogo)
        sql_executado = " ".join(str(c.args[0]) for c in fake_db.execute.call_args_list if c.args)
        self.assertNotIn("INSERT INTO catalogo_marcas (nome) SELECT DISTINCT marca", sql_executado)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `python -m pytest hermes_agents/tests/test_catalogo_organizacao.py -v`
Expected: FAIL — tabelas/funções não existem ainda (`AttributeError: module 'core.catalogo' has no attribute 'criar_marca'` e falhas de asserção nas tabelas).

- [ ] **Step 3: Adicionar tabelas e migração em `_ensure_tables()`**

Inserir logo após o bloco do Task 1 (dentro do mesmo `_ensure_tables()`, antes do bloco `# ── Full-text search indexes`):

```python
        # ── Fase 1 PIM Core: taxonomias normalizadas (2026-07-28) ──
        await db.execute("""CREATE TABLE IF NOT EXISTS catalogo_marcas (
            id SERIAL PRIMARY KEY, nome VARCHAR(150) NOT NULL UNIQUE, created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS catalogo_fabricantes (
            id SERIAL PRIMARY KEY, nome VARCHAR(150) NOT NULL UNIQUE, created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS catalogo_categorias (
            id SERIAL PRIMARY KEY, nome VARCHAR(150) NOT NULL,
            categoria_pai_id INT REFERENCES catalogo_categorias(id),
            created_at TIMESTAMP DEFAULT NOW()
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS catalogo_tags (
            id SERIAL PRIMARY KEY, nome VARCHAR(60) NOT NULL UNIQUE
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS catalogo_produto_tags (
            produto_id INT REFERENCES catalogo_produtos(id) ON DELETE CASCADE,
            tag_id INT REFERENCES catalogo_tags(id) ON DELETE CASCADE,
            PRIMARY KEY (produto_id, tag_id)
        )""")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS marca_id INT REFERENCES catalogo_marcas(id)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS fabricante_id INT REFERENCES catalogo_fabricantes(id)")
        await db.execute("ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS categoria_id_norm INT REFERENCES catalogo_categorias(id)")

        # ── Migracao: dedup de marca/categoria texto livre -> tabelas normalizadas ──
        # So' roda uma vez (guardada por catalogo_marcas vazia) para nao duplicar em todo boot.
        count_marcas = await db.fetchval("SELECT COUNT(*) FROM catalogo_marcas")
        if count_marcas == 0:
            await db.execute("""
                INSERT INTO catalogo_marcas (nome)
                SELECT DISTINCT TRIM(marca) FROM catalogo_produtos
                WHERE marca IS NOT NULL AND TRIM(marca) != ''
                ON CONFLICT (nome) DO NOTHING
            """)
            await db.execute("""
                UPDATE catalogo_produtos SET marca_id = m.id
                FROM catalogo_marcas m WHERE TRIM(catalogo_produtos.marca) = m.nome
            """)
            await db.execute("""
                INSERT INTO catalogo_categorias (nome)
                SELECT DISTINCT TRIM(categoria) FROM catalogo_produtos
                WHERE categoria IS NOT NULL AND TRIM(categoria) != ''
                ON CONFLICT DO NOTHING
            """)
            await db.execute("""
                UPDATE catalogo_produtos SET categoria_id_norm = c.id
                FROM catalogo_categorias c
                WHERE TRIM(catalogo_produtos.categoria) = c.nome AND c.categoria_pai_id IS NULL
            """)
            log(AGENT, "Migracao dedup marca/categoria concluida")
```

Nota: `catalogo_categorias.nome` não tem `UNIQUE` (categorias com mesmo nome podem existir em ramos
diferentes da hierarquia), por isso o `ON CONFLICT DO NOTHING` do INSERT de categorias não tem alvo — usa a
forma sem coluna, que no Postgres exige que não haja `UNIQUE`/`PRIMARY KEY` conflitante (não há, é seguro).

Adicionar as funções de CRUD no final do arquivo (após `fornecedor_resumo`... na verdade após `ficha_tecnica_por_sku`, que é a última função do arquivo):

```python
# ── Fase 1 PIM Core: organizacao (marcas, fabricantes, categorias, tags) ──

def listar_marcas() -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM catalogo_marcas ORDER BY nome")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: return []

def criar_marca(nome: str) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "INSERT INTO catalogo_marcas (nome) VALUES ($1) ON CONFLICT (nome) DO UPDATE SET nome = EXCLUDED.nome RETURNING *",
            nome.strip())
        return dict(row) if row else {"error": "insert failed"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def listar_fabricantes() -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM catalogo_fabricantes ORDER BY nome")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: return []

def criar_fabricante(nome: str) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "INSERT INTO catalogo_fabricantes (nome) VALUES ($1) ON CONFLICT (nome) DO UPDATE SET nome = EXCLUDED.nome RETURNING *",
            nome.strip())
        return dict(row) if row else {"error": "insert failed"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def listar_categorias() -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM catalogo_categorias ORDER BY nome")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: return []

def criar_categoria(nome: str, categoria_pai_id: int = None) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "INSERT INTO catalogo_categorias (nome, categoria_pai_id) VALUES ($1, $2) RETURNING *",
            nome.strip(), categoria_pai_id)
        return dict(row) if row else {"error": "insert failed"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def listar_tags() -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM catalogo_tags ORDER BY nome")
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: return []

def criar_tag(nome: str) -> dict:
    async def _go():
        db = await get_db()
        row = await db.fetchrow(
            "INSERT INTO catalogo_tags (nome) VALUES ($1) ON CONFLICT (nome) DO UPDATE SET nome = EXCLUDED.nome RETURNING *",
            nome.strip())
        return dict(row) if row else {"error": "insert failed"}
    try: return run_async(_go())
    except Exception as e: return {"error": str(e)}

def tags_do_produto(produto_id: int) -> list:
    async def _go():
        db = await get_db()
        rows = await db.fetch("""SELECT t.id, t.nome FROM catalogo_tags t
            JOIN catalogo_produto_tags pt ON pt.tag_id = t.id
            WHERE pt.produto_id = $1 ORDER BY t.nome""", produto_id)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: return []

def vincular_tag(produto_id: int, tag_id: int) -> dict:
    async def _go():
        db = await get_db()
        await db.execute(
            "INSERT INTO catalogo_produto_tags (produto_id, tag_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            produto_id, tag_id)
    try: run_async(_go()); return {"success": True}
    except Exception as e: return {"error": str(e)}

def desvincular_tag(produto_id: int, tag_id: int) -> dict:
    async def _go():
        db = await get_db()
        await db.execute(
            "DELETE FROM catalogo_produto_tags WHERE produto_id = $1 AND tag_id = $2",
            produto_id, tag_id)
    try: run_async(_go()); return {"success": True}
    except Exception as e: return {"error": str(e)}
```

- [ ] **Step 4: Rodar o teste e confirmar que passa**

Run: `python -m pytest hermes_agents/tests/test_catalogo_organizacao.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/catalogo.py hermes_agents/tests/test_catalogo_organizacao.py
git commit -m "feat: tabelas normalizadas de marca/fabricante/categoria/tag + migracao de dedup"
```

---

### Task 3: Blueprint `routes/produtos.py` — CRUD de marcas/fabricantes/categorias/tags

**Files:**
- Create: `hermes_agents/routes/produtos.py`
- Modify: `hermes_agents/athena_bridge.py` (registrar o blueprint)
- Test: `hermes_agents/tests/test_produtos_organizacao_rotas.py` (novo)

**Interfaces:**
- Consumes: `core.catalogo.listar_marcas/criar_marca/listar_fabricantes/criar_fabricante/listar_categorias/criar_categoria/listar_tags/criar_tag/vincular_tag/desvincular_tag` (Task 2). `core.rbac.requer_permissao` (já existe — usa os códigos `produtos.ver`/`produtos.editar`, que já são seedados automaticamente porque `"produtos"` já está em `core.rbac.MODULOS`, com ações `ver`/`criar`/`editar`/`excluir`/`aprovar`/`exportar` — **nenhuma permissão nova precisa ser cadastrada**). `core.seguranca.auditar_alteracao`.
- Produces: blueprint `produtos_bp`, endpoints `GET/POST /api/produtos/marcas`, `GET/POST /api/produtos/fabricantes`, `GET/POST /api/produtos/categorias`, `GET/POST /api/produtos/tags`, `POST /api/produtos/<int:produto_id>/tags`, `DELETE /api/produtos/<int:produto_id>/tags/<int:tag_id>`.

- [ ] **Step 1: Escrever o teste que falha**

```python
# hermes_agents/tests/test_produtos_organizacao_rotas.py
"""CRUD de marcas/fabricantes/categorias/tags exige RBAC (produtos.ver para
listar, produtos.editar para criar) e audita toda criacao."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

_TEST_TOKEN = "test-master-token-32-bytes-long!!"

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=1), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

from flask import Flask
from routes.produtos import produtos_bp
import core.rbac as rbac


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(produtos_bp)
    return app.test_client()


class TestMarcasCRUD(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env.start()
        self.client = _app()

    def tearDown(self):
        self._env.stop()

    def test_listar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(1, "op@x.com", "Operador")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]):
            r = self.client.get("/api/produtos/marcas", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_criar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(1, "op@x.com", "Operador")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["produtos.ver"]), \
             patch("core.catalogo.criar_marca") as mock_criar:
            r = self.client.post("/api/produtos/marcas", json={"nome": "Nike"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_criar.assert_not_called()

    def test_criar_com_permissao_libera_e_audita(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.catalogo.criar_marca", return_value={"id": 1, "nome": "Nike"}) as mock_criar, \
             patch("core.seguranca.auditar_alteracao") as mock_audit:
            r = self.client.post("/api/produtos/marcas", json={"nome": "Nike"}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_criar.assert_called_once_with("Nike")
        mock_audit.assert_called_once()

    def test_criar_sem_nome_retorna_400(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.post("/api/produtos/marcas", json={}, headers=headers)
        self.assertEqual(r.status_code, 400)


class TestVincularTag(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env.start()
        self.client = _app()

    def tearDown(self):
        self._env.stop()

    def test_vincular_tag_com_permissao(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.catalogo.vincular_tag", return_value={"success": True}) as mock_vinc:
            r = self.client.post("/api/produtos/10/tags", json={"tag_id": 3}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_vinc.assert_called_once_with(10, 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `python -m pytest hermes_agents/tests/test_produtos_organizacao_rotas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'routes.produtos'`

- [ ] **Step 3: Criar `hermes_agents/routes/produtos.py`**

```python
from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao

produtos_bp = Blueprint("produtos_organizacao", __name__, url_prefix="/api/produtos")


@produtos_bp.route("/marcas", methods=["GET"])
@requer_permissao("produtos.ver")
def listar_marcas_route():
    from core.catalogo import listar_marcas
    return jsonify({"data": listar_marcas()})


@produtos_bp.route("/marcas", methods=["POST"])
@requer_permissao("produtos.editar")
def criar_marca_route():
    from core.catalogo import criar_marca
    from core.seguranca import auditar_alteracao
    nome = (request.json or {}).get("nome", "").strip()
    if not nome:
        return jsonify({"error": "nome e obrigatorio"}), 400
    resultado = criar_marca(nome)
    if not resultado.get("error"):
        auditar_alteracao("criar", "produtos", "catalogo_marcas", resultado.get("id"), dados_depois=resultado)
    return jsonify(resultado)


@produtos_bp.route("/fabricantes", methods=["GET"])
@requer_permissao("produtos.ver")
def listar_fabricantes_route():
    from core.catalogo import listar_fabricantes
    return jsonify({"data": listar_fabricantes()})


@produtos_bp.route("/fabricantes", methods=["POST"])
@requer_permissao("produtos.editar")
def criar_fabricante_route():
    from core.catalogo import criar_fabricante
    from core.seguranca import auditar_alteracao
    nome = (request.json or {}).get("nome", "").strip()
    if not nome:
        return jsonify({"error": "nome e obrigatorio"}), 400
    resultado = criar_fabricante(nome)
    if not resultado.get("error"):
        auditar_alteracao("criar", "produtos", "catalogo_fabricantes", resultado.get("id"), dados_depois=resultado)
    return jsonify(resultado)


@produtos_bp.route("/categorias", methods=["GET"])
@requer_permissao("produtos.ver")
def listar_categorias_route():
    from core.catalogo import listar_categorias
    return jsonify({"data": listar_categorias()})


@produtos_bp.route("/categorias", methods=["POST"])
@requer_permissao("produtos.editar")
def criar_categoria_route():
    from core.catalogo import criar_categoria
    from core.seguranca import auditar_alteracao
    data = request.json or {}
    nome = data.get("nome", "").strip()
    if not nome:
        return jsonify({"error": "nome e obrigatorio"}), 400
    categoria_pai_id = data.get("categoria_pai_id")
    resultado = criar_categoria(nome, categoria_pai_id)
    if not resultado.get("error"):
        auditar_alteracao("criar", "produtos", "catalogo_categorias", resultado.get("id"), dados_depois=resultado)
    return jsonify(resultado)


@produtos_bp.route("/tags", methods=["GET"])
@requer_permissao("produtos.ver")
def listar_tags_route():
    from core.catalogo import listar_tags
    return jsonify({"data": listar_tags()})


@produtos_bp.route("/tags", methods=["POST"])
@requer_permissao("produtos.editar")
def criar_tag_route():
    from core.catalogo import criar_tag
    from core.seguranca import auditar_alteracao
    nome = (request.json or {}).get("nome", "").strip()
    if not nome:
        return jsonify({"error": "nome e obrigatorio"}), 400
    resultado = criar_tag(nome)
    if not resultado.get("error"):
        auditar_alteracao("criar", "produtos", "catalogo_tags", resultado.get("id"), dados_depois=resultado)
    return jsonify(resultado)


@produtos_bp.route("/<int:produto_id>/tags", methods=["POST"])
@requer_permissao("produtos.editar")
def vincular_tag_route(produto_id):
    from core.catalogo import vincular_tag
    tag_id = (request.json or {}).get("tag_id")
    if not tag_id:
        return jsonify({"error": "tag_id e obrigatorio"}), 400
    return jsonify(vincular_tag(produto_id, int(tag_id)))


@produtos_bp.route("/<int:produto_id>/tags/<int:tag_id>", methods=["DELETE"])
@requer_permissao("produtos.editar")
def desvincular_tag_route(produto_id, tag_id):
    from core.catalogo import desvincular_tag
    return jsonify(desvincular_tag(produto_id, tag_id))
```

- [ ] **Step 4: Registrar o blueprint em `athena_bridge.py`**

Adicionar junto aos outros imports de blueprint (perto da linha 221, onde `from routes.cadastros import cadastros_bp` está):

```python
from routes.produtos import produtos_bp
```

Adicionar junto aos outros `register_blueprint` (perto da linha 251, `app.register_blueprint(cadastros_bp)`):

```python
app.register_blueprint(produtos_bp)
```

- [ ] **Step 5: Rodar o teste e confirmar que passa**

Run: `python -m pytest hermes_agents/tests/test_produtos_organizacao_rotas.py -v`
Expected: PASS

- [ ] **Step 6: Rodar a suíte completa pra checar que nada quebrou**

Run: `python -m pytest hermes_agents/tests/ -v`
Expected: todos os testes existentes continuam passando (nenhuma rota `/api/produtos/marcas` etc. colide com
`/api/produtos/<sku>` já existente — Flask/Werkzeug resolve rotas estáticas antes de rotas com parâmetro,
então isso é seguro, mas a suíte completa confirma).

- [ ] **Step 7: Commit**

```bash
git add hermes_agents/routes/produtos.py hermes_agents/athena_bridge.py hermes_agents/tests/test_produtos_organizacao_rotas.py
git commit -m "feat: rotas CRUD de marcas/fabricantes/categorias/tags de produtos"
```

---

### Task 4: Estender `POST`/`PUT /api/produtos` com os novos campos + RBAC granular + auditoria com usuário real

**Files:**
- Modify: `hermes_agents/athena_bridge.py:1684-1759` (`criar_produto_local` e `editar_produto`)
- Test: `hermes_agents/tests/test_produtos_campos_identificacao.py` (novo)

**Interfaces:**
- Consumes: `core.rbac.requer_permissao` (códigos `produtos.criar`, `produtos.editar` — já existentes),
  `core.seguranca.auditar_alteracao` (Task 2 do spec original, já existe em `core/seguranca.py`).
- Produces: nada consumido por outras tasks deste plano — é o fim da cadeia backend desta fase.

**Contexto do problema encontrado:** hoje essas duas rotas só checam `_autenticado()` (login válido, sem
granularidade de permissão) e chamam `auditar(...)` diretamente sem `user_id`/`email`/`ip` — a auditoria fica
sem registrar **quem** criou/editou o produto. Corrigido nesta task junto com a extensão de campos, porque é a
mesma mudança de código (trocar a chamada de auditoria já está na função que estamos editando).

- [ ] **Step 1: Escrever o teste que falha**

```python
# hermes_agents/tests/test_produtos_campos_identificacao.py
"""POST/PUT /api/produtos aceitam os novos campos de identificacao da Fase 1
do PIM Core, exigem permissao granular (produtos.criar/produtos.editar) em
vez de so' 'esta logado', e a auditoria passa a registrar o usuario real."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

_TEST_TOKEN = "test-master-token-32-bytes-long!!"

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=1), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import athena_bridge
import core.rbac as rbac


def _app():
    athena_bridge.app.config["TESTING"] = True
    return athena_bridge.app.test_client()


class TestCriarProdutoComNovosCampos(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env.start()
        self.client = _app()

    def tearDown(self):
        self._env.stop()

    def test_criar_sem_permissao_produtos_criar_nega(self):
        token = rbac.gerar_token_sessao(1, "op@x.com", "Estoquista")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["produtos.ver"]), \
             patch("core.catalogo.criar") as mock_criar:
            r = self.client.post("/api/produtos", json={"sku": "X1", "descricao": "Produto X"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_criar.assert_not_called()

    def test_criar_com_novos_campos_passa_pro_catalogo(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        payload = {
            "sku": "X1", "descricao": "Produto X",
            "classificacao": "variavel", "nome_reduzido": "Prod X",
            "nome_impressao": "PRODUTO X", "codigo_interno": "INT-001",
            "codigo_erp": "ERP-001", "ex_tipi": "01", "modelo": "M1",
            "linha": "Linha A", "colecao": "Verao 2026",
            "marca_id": 5, "fabricante_id": 7, "categoria_id_norm": 2,
        }
        with patch("core.catalogo.criar", return_value={"id": 1, **payload}) as mock_criar, \
             patch("core.seguranca.auditar_alteracao") as mock_audit:
            r = self.client.post("/api/produtos", json=payload, headers=headers)
        self.assertEqual(r.status_code, 201)
        campos_enviados = mock_criar.call_args.args[0]
        for campo in ("classificacao", "nome_reduzido", "nome_impressao", "codigo_interno",
                      "codigo_erp", "ex_tipi", "modelo", "linha", "colecao",
                      "marca_id", "fabricante_id", "categoria_id_norm"):
            self.assertIn(campo, campos_enviados, f"campo {campo} nao foi repassado pro catalogo")
        mock_audit.assert_called_once()
        self.assertEqual(mock_audit.call_args.args[0], "criar")
        self.assertEqual(mock_audit.call_args.args[1], "produtos")


class TestEditarProdutoComNovosCampos(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env.start()
        self.client = _app()

    def tearDown(self):
        self._env.stop()

    def test_editar_sem_permissao_produtos_editar_nega(self):
        token = rbac.gerar_token_sessao(1, "op@x.com", "Estoquista")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["produtos.ver"]):
            r = self.client.put("/api/produtos/X1", json={"classificacao": "kit"}, headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_editar_classificacao_e_auditado_com_dados_antes_depois(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.seguranca.auditar_alteracao") as mock_audit:
            r = self.client.put("/api/produtos/X1", json={"classificacao": "kit", "marca_id": 5}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_audit.assert_called_once()
        self.assertEqual(mock_audit.call_args.args[0], "editar")
        dados_depois = mock_audit.call_args.kwargs.get("dados_depois")
        self.assertEqual(dados_depois.get("classificacao"), "kit")


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `python -m pytest hermes_agents/tests/test_produtos_campos_identificacao.py -v`
Expected: FAIL — 403 esperado não acontece (rota ainda só checa `_autenticado()`), e os novos campos não
aparecem em `campos_enviados`.

- [ ] **Step 3: Editar `criar_produto_local` em `athena_bridge.py` (linhas 1684-1720)**

Substituir a função inteira por:

```python
@app.route('/api/produtos', methods=['POST'])
def criar_produto_local():
    """Cria produto 100% local em catalogo_produtos, sem depender de sync do Bling."""
    from core.rbac import requer_permissao

    @requer_permissao("produtos.criar")
    def _handler():
        data = request.json or {}
        sku = (data.get("sku") or "").strip()
        descricao = (data.get("descricao") or "").strip()
        if not sku or not descricao:
            return jsonify({"error": "sku e descricao sao obrigatorios"}), 400

        campos = {"sku": sku, "descricao": descricao}
        for campo in ("categoria", "marca", "codigo_barras", "fornecedor_codigo",
                      "unidade_padrao", "tipo", "estoque_localizacao",
                      "classificacao", "nome_reduzido", "nome_impressao",
                      "codigo_interno", "codigo_erp", "ex_tipi",
                      "modelo", "linha", "colecao"):
            if data.get(campo):
                campos[campo] = data[campo]
        for campo in ("preco_custo", "custo_transporte", "preco_venda",
                      "estoque_minimo", "estoque_maximo"):
            if data.get(campo) not in (None, ""):
                try: campos[campo] = float(data[campo])
                except (TypeError, ValueError): pass
        for campo in ("fornecedor_id", "marca_id", "fabricante_id", "categoria_id_norm"):
            if data.get(campo) not in (None, ""):
                try: campos[campo] = int(data[campo])
                except (TypeError, ValueError): pass

        from core.catalogo import criar
        resultado = criar(campos)
        if resultado.get("error"):
            msg = resultado["error"]
            status = 409 if "unique" in msg.lower() or "duplicate" in msg.lower() else 500
            return jsonify({"error": "SKU ja existe" if status == 409 else msg}), status
        try:
            from core.seguranca import auditar_alteracao
            auditar_alteracao("criar", "produtos", "catalogo_produtos", resultado.get("id"), dados_depois=campos)
        except Exception:
            pass
        return jsonify({"success": True, "produto": resultado}), 201

    return _handler()
```

- [ ] **Step 4: Editar `editar_produto` em `athena_bridge.py` (linhas 1722-1759)**

Substituir a função inteira por:

```python
@app.route('/api/produtos/<sku>', methods=['PUT'])
def editar_produto(sku):
    from core.rbac import requer_permissao

    @requer_permissao("produtos.editar")
    def _handler():
        try:
            data = request.json or {}
            conn = _db_sync(); cur = conn.cursor()
            updates = []
            values = []
            campos = ["descricao","ncm","cest","categoria","marca","unidade_padrao","tipo",
                      "peso_bruto","sku_pai","atributo",
                      "codigo_barras","gtin_embalagem","descricao_curta","descricao_complementar",
                      "peso_liquido","largura","altura","profundidade","unidade_medida_dimensao",
                      "volumes","itens_por_caixa","cfop_padrao","observacoes","link_externo",
                      "fornecedor_nome","fornecedor_codigo","fornecedor_id","preco_custo",
                      "custo_transporte","preco_venda",
                      "estoque_minimo","estoque_maximo","estoque_localizacao",
                      "classificacao","nome_reduzido","nome_impressao","codigo_interno",
                      "codigo_erp","ex_tipi","modelo","linha","colecao",
                      "marca_id","fabricante_id","categoria_id_norm"]
            for campo in campos:
                if campo in data and data[campo] is not None:
                    updates.append(f"{campo} = %s")
                    values.append(data[campo])
            if not updates:
                return jsonify({"error": "Nenhum campo para atualizar"}), 400
            updates.append("updated_at = NOW()")
            values.append(sku)
            sql = f"UPDATE catalogo_produtos SET {', '.join(updates)} WHERE sku = %s"
            cur.execute(sql, values)
            if "descricao" in data:
                cur.execute("UPDATE fichas_tecnicas SET descricao = %s WHERE sku = %s", (data["descricao"], sku))
            cur.close(); conn.close()
            try:
                from core.seguranca import auditar_alteracao
                auditar_alteracao("editar", "produtos", "catalogo_produtos", None, dados_depois=data)
            except Exception:
                pass
            return jsonify({"success": True, "sku": sku})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return _handler()
```

Nota: `entidade_id` fica `None` no `auditar_alteracao` de edição porque a rota identifica o produto por `sku`,
não por `id` numérico — `auditar_alteracao` aceita `entidade_id: int = None` (assinatura já existente em
`core/seguranca.py`), então isso não quebra a chamada; o `sku` continua rastreável dentro de `dados_depois`
(a rota já recebe `sku` na URL e `data` no corpo, mas se quiser o sku explícito no log, adicionar
`dados_depois={**data, "sku": sku}` — usar essa forma).

- [ ] **Step 5: Rodar o teste e confirmar que passa**

Run: `python -m pytest hermes_agents/tests/test_produtos_campos_identificacao.py -v`
Expected: PASS

- [ ] **Step 6: Rodar a suíte completa**

Run: `python -m pytest hermes_agents/tests/ -v`
Expected: PASS — nenhum teste existente de estoque/PDV/BI quebra (essas rotas não usam
`criar_produto_local`/`editar_produto` diretamente, só leem `catalogo_produtos` por SQL próprio).

- [ ] **Step 7: Commit**

```bash
git add hermes_agents/athena_bridge.py hermes_agents/tests/test_produtos_campos_identificacao.py
git commit -m "feat: novos campos de identificacao em POST/PUT produtos + RBAC granular + auditoria com usuario real"
```

---

### Task 5: Componente compartilhado "select com criação inline"

**Files:**
- Create: `web/src/app/produtos/[sku]/_components/SelectComCriacao.tsx`

**Interfaces:**
- Consumes: nada (componente puro de UI).
- Produces: `export default function SelectComCriacao(props: SelectComCriacaoProps)` — usado pela Task 6.

```typescript
interface SelectComCriacaoProps {
  label: string;
  value: string;              // id selecionado, como string (ou "" se nenhum)
  options: { id: number; nome: string }[];
  onChange: (id: string) => void;
  onCriar: (nome: string) => Promise<{ id: number; nome: string } | { error: string }>;
  onCriado: (novo: { id: number; nome: string }) => void;  // avisa o pai pra atualizar a lista de options
  disabled?: boolean;
}
```

- [ ] **Step 1: Criar o componente**

```tsx
// web/src/app/produtos/[sku]/_components/SelectComCriacao.tsx
"use client";

import { useState } from "react";

interface Opcao { id: number; nome: string; }

export default function SelectComCriacao({
  label, value, options, onChange, onCriar, onCriado, disabled,
}: {
  label: string;
  value: string;
  options: Opcao[];
  onChange: (id: string) => void;
  onCriar: (nome: string) => Promise<Opcao | { error: string }>;
  onCriado: (novo: Opcao) => void;
  disabled?: boolean;
}) {
  const [criando, setCriando] = useState(false);
  const [novoNome, setNovoNome] = useState("");
  const [erro, setErro] = useState("");

  const confirmarCriacao = async () => {
    const nome = novoNome.trim();
    if (!nome) return;
    const resultado = await onCriar(nome);
    if ("error" in resultado) {
      setErro(resultado.error);
      return;
    }
    onCriado(resultado);
    onChange(String(resultado.id));
    setCriando(false);
    setNovoNome("");
    setErro("");
  };

  if (criando) {
    return (
      <div className="space-y-1">
        <label className="text-[10px] text-neutral-500 uppercase tracking-wider">{label}</label>
        <div className="flex gap-1">
          <input
            type="text" autoFocus value={novoNome}
            onChange={e => setNovoNome(e.target.value)}
            onKeyDown={e => e.key === "Enter" && confirmarCriacao()}
            placeholder="Nome novo..."
            className="flex-1 bg-neutral-900 border border-indigo-600 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none"
          />
          <button onClick={confirmarCriacao} className="px-2 bg-indigo-600 text-white text-xs rounded-lg">OK</button>
          <button onClick={() => { setCriando(false); setErro(""); }} className="px-2 text-neutral-400 text-xs">✕</button>
        </div>
        {erro && <p className="text-[10px] text-red-400">{erro}</p>}
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <label className="text-[10px] text-neutral-500 uppercase tracking-wider">{label}</label>
      <select
        value={value}
        disabled={disabled}
        onChange={e => {
          if (e.target.value === "__novo__") { setCriando(true); return; }
          onChange(e.target.value);
        }}
        className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500"
      >
        <option value="">— Nenhum —</option>
        {options.map(o => <option key={o.id} value={o.id}>{o.nome}</option>)}
        <option value="__novo__">+ Criar novo...</option>
      </select>
    </div>
  );
}
```

- [ ] **Step 2: Verificar tipos**

Run: `cd web && npx tsc --noEmit -p .`
Expected: sem erros novos relacionados a `SelectComCriacao.tsx`.

- [ ] **Step 3: Commit**

```bash
git add "web/src/app/produtos/[sku]/_components/SelectComCriacao.tsx"
git commit -m "feat: componente select com criacao inline (marca/fabricante/categoria)"
```

---

### Task 6: `CadastroTab.tsx` ganha os novos campos de identificação

**Files:**
- Modify: `web/src/app/produtos/[sku]/_components/CadastroTab.tsx`
- Modify: `web/src/lib/api.ts` (novas funções de API)

**Interfaces:**
- Consumes: `SelectComCriacao` (Task 5); endpoints de `routes/produtos.py` (Task 3):
  `GET/POST /api/produtos/marcas`, `/fabricantes`, `/categorias`.
- Produces: nada consumido por outra task (fim da cadeia).

- [ ] **Step 1: Adicionar funções em `web/src/lib/api.ts`**

Adicionar próximo às demais funções de produtos (perto da linha 289, após `criarProduto`):

```typescript
  listarMarcas: () => request<{ data: { id: number; nome: string }[] }>("/api/produtos/marcas"),
  criarMarca: (nome: string) =>
    request<{ id: number; nome: string; error?: string }>("/api/produtos/marcas", {
      method: "POST", body: JSON.stringify({ nome }),
    }),
  listarFabricantes: () => request<{ data: { id: number; nome: string }[] }>("/api/produtos/fabricantes"),
  criarFabricante: (nome: string) =>
    request<{ id: number; nome: string; error?: string }>("/api/produtos/fabricantes", {
      method: "POST", body: JSON.stringify({ nome }),
    }),
  listarCategoriasProduto: () => request<{ data: { id: number; nome: string; categoria_pai_id: number | null }[] }>("/api/produtos/categorias"),
  criarCategoriaProduto: (nome: string) =>
    request<{ id: number; nome: string; error?: string }>("/api/produtos/categorias", {
      method: "POST", body: JSON.stringify({ nome }),
    }),
```

- [ ] **Step 2: Editar `CadastroTab.tsx`**

Adicionar os imports e estado (após a linha `const [fornecedores, setFornecedores] = useState<Fornecedor[]>([]);`):

```tsx
import SelectComCriacao from "./SelectComCriacao";

// ...dentro do componente, junto aos outros useState:
  const [marcas, setMarcas] = useState<{ id: number; nome: string }[]>([]);
  const [fabricantes, setFabricantes] = useState<{ id: number; nome: string }[]>([]);
  const [categorias, setCategorias] = useState<{ id: number; nome: string }[]>([]);
```

Estender o `useEffect` de carga inicial:

```tsx
  useEffect(() => {
    api.cadList("fornecedores").then(r => setFornecedores((r.data ?? []) as Fornecedor[])).catch(() => {});
    api.listarMarcas().then(r => setMarcas(r.data ?? [])).catch(() => {});
    api.listarFabricantes().then(r => setFabricantes(r.data ?? [])).catch(() => {});
    api.listarCategoriasProduto().then(r => setCategorias(r.data ?? [])).catch(() => {});
  }, []);
```

Estender `CAMPOS_EDITAVEIS`:

```tsx
  const CAMPOS_EDITAVEIS = [
    "descricao", "categoria", "marca", "ncm", "tipo",
    "codigo_barras", "gtin_embalagem", "descricao_curta", "descricao_complementar",
    "peso_bruto", "peso_liquido", "largura", "altura", "profundidade", "unidade_medida_dimensao",
    "volumes", "itens_por_caixa", "cfop_padrao", "observacoes", "link_externo",
    "fornecedor_nome", "fornecedor_codigo", "fornecedor_id", "preco_custo",
    "custo_transporte", "preco_venda",
    "estoque_minimo", "estoque_maximo", "estoque_localizacao",
    "classificacao", "nome_reduzido", "nome_impressao", "codigo_interno",
    "codigo_erp", "ex_tipi", "modelo", "linha", "colecao",
    "marca_id", "fabricante_id", "categoria_id_norm",
  ];
```

Adicionar a seção nova de campos, logo após a `<Section title="Identificacao">` existente (depois da tag de
fechamento `</Section>` dela, linha 177):

```tsx
      <Section title="Classificação e Organização">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          <InputGroup label="Classificação">
            {editando ? (
              <select
                value={form.classificacao || "simples"}
                onChange={e => setForm({ ...form, classificacao: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500"
              >
                <option value="simples">Simples</option>
                <option value="variavel">Variável</option>
                <option value="kit">Kit</option>
                <option value="combo">Combo</option>
              </select>
            ) : (
              <div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 capitalize">
                {String(p?.classificacao || "simples")}
              </div>
            )}
          </InputGroup>
          <InputGroup label="Nome Reduzido">{field("nome_reduzido")}</InputGroup>
          <InputGroup label="Nome para Impressão">{field("nome_impressao")}</InputGroup>
          <InputGroup label="Código Interno">{field("codigo_interno")}</InputGroup>
          <InputGroup label="Código ERP">{field("codigo_erp")}</InputGroup>
          <InputGroup label="EX TIPI">{field("ex_tipi")}</InputGroup>
          <InputGroup label="Modelo">{field("modelo")}</InputGroup>
          <InputGroup label="Linha">{field("linha")}</InputGroup>
          <InputGroup label="Coleção">{field("colecao")}</InputGroup>
          {editando ? (
            <SelectComCriacao
              label="Marca"
              value={form.marca_id || ""}
              options={marcas}
              onChange={id => setForm({ ...form, marca_id: id })}
              onCriar={api.criarMarca}
              onCriado={nova => setMarcas(prev => [...prev, nova])}
            />
          ) : (
            <InputGroup label="Marca">
              <div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200">
                {marcas.find(m => m.id === Number(p?.marca_id))?.nome || "—"}
              </div>
            </InputGroup>
          )}
          {editando ? (
            <SelectComCriacao
              label="Fabricante"
              value={form.fabricante_id || ""}
              options={fabricantes}
              onChange={id => setForm({ ...form, fabricante_id: id })}
              onCriar={api.criarFabricante}
              onCriado={novo => setFabricantes(prev => [...prev, novo])}
            />
          ) : (
            <InputGroup label="Fabricante">
              <div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200">
                {fabricantes.find(f => f.id === Number(p?.fabricante_id))?.nome || "—"}
              </div>
            </InputGroup>
          )}
          {editando ? (
            <SelectComCriacao
              label="Categoria (normalizada)"
              value={form.categoria_id_norm || ""}
              options={categorias}
              onChange={id => setForm({ ...form, categoria_id_norm: id })}
              onCriar={api.criarCategoriaProduto}
              onCriado={nova => setCategorias(prev => [...prev, nova])}
            />
          ) : (
            <InputGroup label="Categoria (normalizada)">
              <div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200">
                {categorias.find(c => c.id === Number(p?.categoria_id_norm))?.nome || "—"}
              </div>
            </InputGroup>
          )}
        </div>
      </Section>
```

Nota: `criarMarca`/`criarFabricante`/`criarCategoriaProduto` em `api.ts` retornam `{id, nome, error?}` —
compatível com o tipo `Opcao | {error: string}` esperado por `SelectComCriacao.onCriar` (TypeScript infere a
união corretamente porque `error` é opcional no tipo de retorno de `request<...>`).

- [ ] **Step 3: Verificar tipos**

Run: `cd web && npx tsc --noEmit -p .`
Expected: sem erros.

- [ ] **Step 4: Testar manualmente no navegador**

Rodar `cd web && npm run dev`, abrir `/produtos/<algum-sku-existente>`, clicar em "Editar", confirmar:
- Os 9 campos de texto novos aparecem e salvam.
- Os 3 selects (Marca/Fabricante/Categoria) carregam as opções vindas da API.
- Escolher "+ Criar novo..." em qualquer um dos três abre o campo de texto inline, cria e seleciona
  automaticamente o novo item.
- Salvar não quebra o fluxo existente de sincronização com Bling (campos `descricao`/`preco` continuam
  sendo empurrados pro Bling quando `id_bling` existe).

- [ ] **Step 5: Commit**

```bash
git add "web/src/app/produtos/[sku]/_components/CadastroTab.tsx" "web/src/lib/api.ts"
git commit -m "feat: campos de identificacao e organizacao (marca/fabricante/categoria) no cadastro de produto"
```

---

## Self-Review

**Cobertura do spec:** classificação ✅ (Task 1+6), nome_reduzido/nome_impressao/codigo_interno/codigo_erp/
ex_tipi/modelo/linha/colecao ✅ (Task 1+4+6), marcas/fabricantes/categorias normalizados ✅ (Task 2+3+6), tags
✅ (Task 2+3, sem UI nesta fase — ver nota abaixo), auditoria com usuário real ✅ (Task 4), RBAC granular ✅
(Task 3+4, reaproveitando permissões já seedadas), migração de dedup sem duplicar em reboots ✅ (Task 2),
compatibilidade com os 17 consumidores ✅ (nenhuma coluna/tabela removida, nenhuma assinatura de função
pública alterada).

**Gap encontrado e assumido conscientemente:** a UI de tags (Task 5/6) ficou de fora — o backend (Task 2+3)
está completo (`listar_tags`, `criar_tag`, `vincular_tag`, `desvincular_tag`, rotas), mas `CadastroTab.tsx`
não ganhou um multi-select de tags nesta fase. Motivo: é um componente de interação diferente (multi-seleção
+ criação, não um select simples) do `SelectComCriacao` da Task 5, e o objeto do spec original ("tags: sim/
não existiam") já foi atendido pela camada de dados. Adicionar a UI de tags fica como item imediato da
próxima sessão, não requer nova spec.

**Consistência de tipos:** `criar_marca`/`criar_fabricante`/`criar_tag` (Task 2) retornam `dict` com `id`/`nome`
ou `{"error": str}` — usado identicamente em Task 3 (rotas) e Task 6 (`onCriar` do frontend). `classificacao`
usa os mesmos 4 valores (`simples`/`variavel`/`kit`/`combo`) no `DEFAULT` do banco (Task 1) e no `<select>` do
frontend (Task 6).
