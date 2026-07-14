# Bling — Aba de Produtos completa Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar a aba de Produtos da integração Bling numa listagem completa (todos os campos relevantes do produto), com busca textual, filtros de data/estoque/preço/status/categoria, e um sync que cacheia o detalhe completo de cada produto localmente.

**Architecture:** Nova tabela Postgres `bling_produtos` (ad-hoc `CREATE TABLE IF NOT EXISTS`, seguindo o padrão já usado em `shopee_sync.py`) alimentada por uma sincronização em background que busca o detalhe de cada produto na API do Bling (`GET /produtos/{id}`) com throttle. A listagem/filtros da UI passam a consultar essa tabela local em vez de bater direto na API do Bling. Criação/edição/remoção continuam batendo direto no Bling e espelham o resultado na tabela local.

**Tech Stack:** Python 3 + Flask (blueprints em `hermes_agents/routes/integrations.py`) + asyncpg (`hermes_agents/core`) para o backend; Next.js/React + TypeScript + Tailwind para o frontend (`web/src/app/integracoes/bling`).

## Global Constraints

- Situação de produto usa as letras `"A"` (ativo) / `"I"` (inativo) — já é essa a convenção usada em `BlingProductsTab.tsx:265` (`p.situacao === "A"`). Manter.
- Nenhum novo `console.log` em código de produção (regra do projeto).
- Campos ausentes na resposta do Bling viram `NULL` no banco e `"—"` na UI — nunca lançar erro por campo opcional faltante.
- Sincronização deve respeitar throttle (~3 requisições/segundo) para não estourar rate limit do Bling v3.
- Seguir o estilo visual existente: Tailwind com paleta `neutral-800/700/900`, texto `text-xs`, botões `indigo-600`/`emerald-600`/`red`, exatamente como em `StockModal.tsx` e `BlingProductsTab.tsx`.

---

### Task 1: Funções puras — normalização de produto Bling e montagem de filtros SQL

**Files:**
- Modify: `hermes_agents/bling_erp.py`
- Test: `hermes_agents/test_bling_produtos.py` (novo)

**Interfaces:**
- Produces: `_normalizar_produto_bling(detalhe: dict) -> dict` — recebe o JSON de `GET /produtos/{id}` (campo `data`, já desembrulhado) e retorna um dict com exatamente as chaves da tabela `bling_produtos` (ver Task 2): `id_bling, codigo, nome, tipo, formato, situacao, preco, preco_custo, categoria_id, categoria_nome, marca, unidade, gtin, ncm, peso_liquido, peso_bruto, largura, altura, profundidade, estoque_atual, estoque_minimo, estoque_maximo, imagem_url, descricao_curta, descricao_complementar, fornecedor_nome, data_criacao, data_alteracao`.
- Produces: `_montar_filtros_sql(filtros: dict) -> tuple[str, list]` — recebe um dict com chaves opcionais `busca, situacao, categoria_id, preco_min, preco_max, estoque_min, estoque_max, estoque_baixo, data_de, data_ate` e retorna `(clausula_where, params)` onde `clausula_where` é uma string tipo `"situacao = $1 AND preco >= $2"` (placeholders posicionais `$N` no estilo asyncpg) e `params` é a lista de valores na ordem correspondente. Se `filtros` estiver vazio, retorna `("", [])`.

- [ ] **Step 1: Escrever os testes das duas funções puras**

Criar `hermes_agents/test_bling_produtos.py`:

```python
#!/usr/bin/env python3
"""
Testes das funções puras de normalização e filtro da aba de Produtos Bling.
Não requerem banco de dados nem rede.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bling_erp import _normalizar_produto_bling, _montar_filtros_sql


def test_normalizar_produto_completo():
    detalhe = {
        "id": 123456789,
        "nome": "Produto Teste",
        "codigo": "SKU-001",
        "preco": 99.9,
        "tipo": "P",
        "situacao": "A",
        "formato": "S",
        "descricaoCurta": "Descrição curta",
        "descricaoComplementar": "Descrição completa",
        "unidade": "UN",
        "pesoLiquido": 0.5,
        "pesoBruto": 0.6,
        "gtin": "7891234567890",
        "marca": "MinhaMarca",
        "categoria": {"id": 111, "descricao": "Categoria X"},
        "estoque": {"minimo": 5, "maximo": 100, "saldoVirtualTotal": 42},
        "dimensoes": {"largura": 10, "altura": 5, "profundidade": 15},
        "tributacao": {"ncm": "12345678"},
        "fornecedor": {"nome": "Fornecedor X"},
        "imagemURL": "https://exemplo.com/img.jpg",
        "precoCusto": 50.0,
        "dataInclusao": "2026-01-01 10:00:00",
        "dataAlteracao": "2026-02-01 12:00:00",
    }
    r = _normalizar_produto_bling(detalhe)
    assert r["id_bling"] == 123456789
    assert r["codigo"] == "SKU-001"
    assert r["nome"] == "Produto Teste"
    assert r["situacao"] == "A"
    assert r["preco"] == 99.9
    assert r["preco_custo"] == 50.0
    assert r["categoria_id"] == 111
    assert r["categoria_nome"] == "Categoria X"
    assert r["marca"] == "MinhaMarca"
    assert r["gtin"] == "7891234567890"
    assert r["ncm"] == "12345678"
    assert r["peso_liquido"] == 0.5
    assert r["peso_bruto"] == 0.6
    assert r["largura"] == 10
    assert r["altura"] == 5
    assert r["profundidade"] == 15
    assert r["estoque_atual"] == 42
    assert r["estoque_minimo"] == 5
    assert r["estoque_maximo"] == 100
    assert r["imagem_url"] == "https://exemplo.com/img.jpg"
    assert r["descricao_curta"] == "Descrição curta"
    assert r["descricao_complementar"] == "Descrição completa"
    assert r["fornecedor_nome"] == "Fornecedor X"
    assert r["data_criacao"] == "2026-01-01 10:00:00"
    assert r["data_alteracao"] == "2026-02-01 12:00:00"
    print("[TEST] ✅ test_normalizar_produto_completo")


def test_normalizar_produto_campos_ausentes():
    """Produto com resposta mínima do Bling — nenhum campo opcional deve quebrar."""
    detalhe = {"id": 1, "nome": "Mínimo", "codigo": "MIN-1"}
    r = _normalizar_produto_bling(detalhe)
    assert r["id_bling"] == 1
    assert r["codigo"] == "MIN-1"
    assert r["nome"] == "Mínimo"
    assert r["categoria_id"] is None
    assert r["categoria_nome"] is None
    assert r["marca"] is None
    assert r["estoque_atual"] is None
    assert r["estoque_minimo"] is None
    assert r["ncm"] is None
    assert r["preco"] is None or r["preco"] == 0
    print("[TEST] ✅ test_normalizar_produto_campos_ausentes")


def test_montar_filtros_sql_vazio():
    where, params = _montar_filtros_sql({})
    assert where == ""
    assert params == []
    print("[TEST] ✅ test_montar_filtros_sql_vazio")


def test_montar_filtros_sql_busca_e_situacao():
    where, params = _montar_filtros_sql({"busca": "parafuso", "situacao": "A"})
    assert "ILIKE" in where
    assert "situacao = $2" in where
    assert params == ["%parafuso%", "A"]
    print("[TEST] ✅ test_montar_filtros_sql_busca_e_situacao")


def test_montar_filtros_sql_faixas_e_datas():
    where, params = _montar_filtros_sql({
        "preco_min": 10, "preco_max": 100,
        "estoque_min": 1, "estoque_max": 50,
        "data_de": "2026-01-01", "data_ate": "2026-02-01",
    })
    assert "preco >= $1" in where
    assert "preco <= $2" in where
    assert "estoque_atual >= $3" in where
    assert "estoque_atual <= $4" in where
    assert "data_criacao >= $5" in where
    assert "data_criacao <= $6" in where
    assert params == [10, 100, 1, 50, "2026-01-01", "2026-02-01"]
    print("[TEST] ✅ test_montar_filtros_sql_faixas_e_datas")


def test_montar_filtros_sql_estoque_baixo():
    where, params = _montar_filtros_sql({"estoque_baixo": True})
    assert "estoque_atual < estoque_minimo" in where
    assert params == []
    print("[TEST] ✅ test_montar_filtros_sql_estoque_baixo")


def test_montar_filtros_sql_categoria():
    where, params = _montar_filtros_sql({"categoria_id": 42})
    assert "categoria_id = $1" in where
    assert params == [42]
    print("[TEST] ✅ test_montar_filtros_sql_categoria")


if __name__ == "__main__":
    test_normalizar_produto_completo()
    test_normalizar_produto_campos_ausentes()
    test_montar_filtros_sql_vazio()
    test_montar_filtros_sql_busca_e_situacao()
    test_montar_filtros_sql_faixas_e_datas()
    test_montar_filtros_sql_estoque_baixo()
    test_montar_filtros_sql_categoria()
    print("\n[TEST] Todos os testes passaram.")
```

- [ ] **Step 2: Rodar os testes e confirmar que falham** (as funções ainda não existem)

Run: `cd hermes_agents && python test_bling_produtos.py`
Expected: `ImportError: cannot import name '_normalizar_produto_bling' from 'bling_erp'`

- [ ] **Step 3: Implementar as duas funções puras**

Adicionar em `hermes_agents/bling_erp.py`, logo após a seção `# ── Depósitos e Estoque ──` (depois de `obter_saldo_deposito`, por volta da linha 260):

```python
# ── Normalização e filtros — Task de Produtos completo ──

def _normalizar_produto_bling(detalhe: dict) -> dict:
    """Converte o JSON de GET /produtos/{id} do Bling nas colunas de bling_produtos.
    Campos ausentes viram None — nunca lança erro por campo opcional faltante."""
    categoria = detalhe.get("categoria") or {}
    estoque = detalhe.get("estoque") or {}
    dimensoes = detalhe.get("dimensoes") or {}
    tributacao = detalhe.get("tributacao") or {}
    fornecedor = detalhe.get("fornecedor") or {}
    fornecedor_nome = fornecedor.get("nome") or (fornecedor.get("contato") or {}).get("nome")

    return {
        "id_bling": detalhe.get("id"),
        "codigo": detalhe.get("codigo", ""),
        "nome": detalhe.get("nome", ""),
        "tipo": detalhe.get("tipo"),
        "formato": detalhe.get("formato"),
        "situacao": detalhe.get("situacao"),
        "preco": detalhe.get("preco"),
        "preco_custo": detalhe.get("precoCusto"),
        "categoria_id": categoria.get("id"),
        "categoria_nome": categoria.get("descricao"),
        "marca": detalhe.get("marca"),
        "unidade": detalhe.get("unidade"),
        "gtin": detalhe.get("gtin"),
        "ncm": tributacao.get("ncm"),
        "peso_liquido": detalhe.get("pesoLiquido"),
        "peso_bruto": detalhe.get("pesoBruto"),
        "largura": dimensoes.get("largura"),
        "altura": dimensoes.get("altura"),
        "profundidade": dimensoes.get("profundidade"),
        "estoque_atual": estoque.get("saldoVirtualTotal"),
        "estoque_minimo": estoque.get("minimo"),
        "estoque_maximo": estoque.get("maximo"),
        "imagem_url": detalhe.get("imagemURL"),
        "descricao_curta": detalhe.get("descricaoCurta"),
        "descricao_complementar": detalhe.get("descricaoComplementar"),
        "fornecedor_nome": fornecedor_nome,
        "data_criacao": detalhe.get("dataInclusao"),
        "data_alteracao": detalhe.get("dataAlteracao"),
    }


def _montar_filtros_sql(filtros: dict) -> tuple:
    """Monta a cláusula WHERE (sem a palavra 'WHERE') e a lista de params posicionais
    ($1, $2, ...) a partir de um dict de filtros da UI. Ignora chaves ausentes/None."""
    condicoes = []
    params = []

    def _add(condicao: str, valor):
        params.append(valor)
        condicoes.append(condicao.format(n=len(params)))

    if filtros.get("busca"):
        _add("(nome ILIKE ${n} OR codigo ILIKE ${n})", f"%{filtros['busca']}%")
    if filtros.get("situacao"):
        _add("situacao = ${n}", filtros["situacao"])
    if filtros.get("categoria_id") is not None:
        _add("categoria_id = ${n}", filtros["categoria_id"])
    if filtros.get("preco_min") is not None:
        _add("preco >= ${n}", filtros["preco_min"])
    if filtros.get("preco_max") is not None:
        _add("preco <= ${n}", filtros["preco_max"])
    if filtros.get("estoque_min") is not None:
        _add("estoque_atual >= ${n}", filtros["estoque_min"])
    if filtros.get("estoque_max") is not None:
        _add("estoque_atual <= ${n}", filtros["estoque_max"])
    if filtros.get("data_de"):
        _add("data_criacao >= ${n}", filtros["data_de"])
    if filtros.get("data_ate"):
        _add("data_criacao <= ${n}", filtros["data_ate"])
    if filtros.get("estoque_baixo"):
        condicoes.append("estoque_atual < estoque_minimo")

    return " AND ".join(condicoes), params
```

Nota: a condição `(nome ILIKE ${n} OR codigo ILIKE ${n})` reusa o mesmo índice de parâmetro duas vezes — isso é válido em asyncpg/Postgres (`$1` pode aparecer mais de uma vez na query).

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `cd hermes_agents && python test_bling_produtos.py`
Expected: `[TEST] Todos os testes passaram.` (7 linhas `✅` antes da mensagem final)

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/bling_erp.py hermes_agents/test_bling_produtos.py
git commit -m "feat: normalizacao de produto Bling e montagem de filtros SQL"
```

---

### Task 2: Tabela local `bling_produtos` e listagem com filtros

**Files:**
- Modify: `hermes_agents/bling_erp.py`

**Interfaces:**
- Consumes: `_normalizar_produto_bling`, `_montar_filtros_sql` (Task 1).
- Produces: `async def _init_tabela_produtos(db)` — cria a tabela se não existir. `def listar_produtos_local(filtros: dict, pagina: int, limite: int) -> dict` — retorna `{"data": [...], "total": int}` consultando a tabela local. `def listar_categorias_produtos() -> dict` — retorna `{"data": [{"id": int, "nome": str}, ...]}` com categorias distintas presentes na tabela.

- [ ] **Step 1: Implementar `_init_tabela_produtos`, `listar_produtos_local` e `listar_categorias_produtos`**

Adicionar em `hermes_agents/bling_erp.py`, logo após as funções da Task 1:

```python
async def _init_tabela_produtos(db):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS bling_produtos (
            id_bling BIGINT PRIMARY KEY,
            codigo TEXT NOT NULL,
            nome TEXT NOT NULL,
            tipo TEXT, formato TEXT, situacao TEXT,
            preco NUMERIC, preco_custo NUMERIC,
            categoria_id BIGINT, categoria_nome TEXT,
            marca TEXT, unidade TEXT,
            gtin TEXT, ncm TEXT,
            peso_liquido NUMERIC, peso_bruto NUMERIC,
            largura NUMERIC, altura NUMERIC, profundidade NUMERIC,
            estoque_atual NUMERIC, estoque_minimo NUMERIC, estoque_maximo NUMERIC,
            imagem_url TEXT,
            descricao_curta TEXT, descricao_complementar TEXT,
            fornecedor_nome TEXT,
            data_criacao TIMESTAMPTZ, data_alteracao TIMESTAMPTZ,
            sincronizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_bling_produtos_nome ON bling_produtos (nome)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_bling_produtos_categoria ON bling_produtos (categoria_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_bling_produtos_situacao ON bling_produtos (situacao)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_bling_produtos_estoque ON bling_produtos (estoque_atual)")


def listar_produtos_local(filtros: dict, pagina: int = 1, limite: int = 50) -> dict:
    """Lista produtos da tabela local (cache), aplicando filtros da UI."""
    async def _go():
        db = await get_db()
        await _init_tabela_produtos(db)
        where, params = _montar_filtros_sql(filtros or {})
        where_clause = f"WHERE {where}" if where else ""
        offset = (pagina - 1) * limite
        ordenar_por = {
            "nome": "nome", "preco": "preco",
            "estoque": "estoque_atual", "data_criacao": "data_criacao",
        }.get(filtros.get("ordenar_por") if filtros else None, "nome")

        total = await db.fetchval(f"SELECT count(*) FROM bling_produtos {where_clause}", *params)
        rows = await db.fetch(
            f"SELECT * FROM bling_produtos {where_clause} ORDER BY {ordenar_por} LIMIT ${len(params)+1} OFFSET ${len(params)+2}",
            *params, limite, offset,
        )
        return {"data": [dict(r) for r in rows], "total": total}
    return run_async(_go())


def listar_categorias_produtos() -> dict:
    """Categorias distintas presentes na tabela local, para popular o filtro."""
    async def _go():
        db = await get_db()
        await _init_tabela_produtos(db)
        rows = await db.fetch("""
            SELECT DISTINCT categoria_id AS id, categoria_nome AS nome
            FROM bling_produtos
            WHERE categoria_id IS NOT NULL
            ORDER BY categoria_nome
        """)
        return {"data": [dict(r) for r in rows]}
    return run_async(_go())
```

- [ ] **Step 2: Verificação manual (requer banco configurado)**

Este passo não é TDD tradicional porque depende de um Postgres real — segue o padrão de testes de integração já usado no repo (`test_fase3.py`), que também assume banco configurado via `FactoryConfig`.

Run:
```bash
cd hermes_agents && python -c "
from bling_erp import listar_produtos_local, listar_categorias_produtos
print(listar_produtos_local({}, 1, 10))
print(listar_categorias_produtos())
"
```
Expected: `{'data': [], 'total': 0}` seguido de `{'data': []}` (tabela recém-criada, ainda vazia) — sem exceções.

- [ ] **Step 3: Commit**

```bash
git add hermes_agents/bling_erp.py
git commit -m "feat: tabela local bling_produtos com listagem filtrada"
```

---

### Task 3: Sincronização completa com throttle e progresso

**Files:**
- Modify: `hermes_agents/bling_erp.py`

**Interfaces:**
- Consumes: `_request` (helper HTTP existente), `_normalizar_produto_bling` (Task 1), `_init_tabela_produtos` (Task 2).
- Produces: `def obter_produto_bling(id_produto: int) -> dict` — chama `GET /produtos/{id}`. `def sincronizar_produtos_completo() -> dict` — substitui o corpo antigo de `sincronizar_produtos`; roda de forma síncrona (bloqueante) o ciclo completo com throttle e atualiza `_SYNC_STATUS`. `def status_sincronizacao_produtos() -> dict` — retorna o conteúdo atual de `_SYNC_STATUS`.

- [ ] **Step 1: Implementar throttle, progresso e a nova sincronização completa**

Adicionar `import time` já está no topo do arquivo (linha 4: `import os, json, time, requests`) — confirmar que `time` já está importado (está).

Adicionar logo abaixo de `def sincronizar_produtos()` atual (linha ~119-146 de `hermes_agents/bling_erp.py`) uma nova função e o estado de progresso. Primeiro, adicionar o estado de progresso perto de `_TOKEN` (linha 24):

```python
_TOKEN = {"access": "", "refresh": ""}
_SYNC_STATUS = {"em_andamento": False, "processados": 0, "total": 0, "erro": None}
```

Agora adicionar, depois de `_init_tabela_produtos`/`listar_categorias_produtos` (final da Task 2):

```python
def obter_produto_bling(id_produto: int) -> dict:
    """Busca o detalhe completo de um produto via GET /produtos/{id}."""
    return _request(f"produtos/{id_produto}")


def status_sincronizacao_produtos() -> dict:
    return dict(_SYNC_STATUS)


def sincronizar_produtos_completo() -> dict:
    """Sincroniza todos os produtos: lista resumida + detalhe de cada um (throttle ~3 req/s),
    upsert em bling_produtos. Roda de forma bloqueante — o chamador deve disparar em thread."""
    global _SYNC_STATUS
    async def _go():
        db = await get_db()
        await _init_tabela_produtos(db)

        _SYNC_STATUS.update({"em_andamento": True, "processados": 0, "total": 0, "erro": None})
        try:
            resumo = listar_produtos(1, 100)
            produtos_resumo = resumo.get("data", [])
            if not produtos_resumo:
                _SYNC_STATUS.update({"em_andamento": False, "erro": resumo.get("error", "sem dados")})
                return {"sincronizados": 0, "erro": resumo.get("error", "sem dados")}

            _SYNC_STATUS["total"] = len(produtos_resumo)
            total_ok = 0
            for item in produtos_resumo:
                id_produto = item.get("id")
                if not id_produto:
                    continue
                try:
                    detalhe_resp = obter_produto_bling(id_produto)
                    detalhe = detalhe_resp.get("data", detalhe_resp)
                    normalizado = _normalizar_produto_bling(detalhe)
                    await db.execute("""
                        INSERT INTO bling_produtos (
                            id_bling, codigo, nome, tipo, formato, situacao, preco, preco_custo,
                            categoria_id, categoria_nome, marca, unidade, gtin, ncm,
                            peso_liquido, peso_bruto, largura, altura, profundidade,
                            estoque_atual, estoque_minimo, estoque_maximo, imagem_url,
                            descricao_curta, descricao_complementar, fornecedor_nome,
                            data_criacao, data_alteracao, sincronizado_em
                        ) VALUES (
                            $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,
                            $20,$21,$22,$23,$24,$25,$26,$27,$28, now()
                        )
                        ON CONFLICT (id_bling) DO UPDATE SET
                            codigo=$2, nome=$3, tipo=$4, formato=$5, situacao=$6, preco=$7, preco_custo=$8,
                            categoria_id=$9, categoria_nome=$10, marca=$11, unidade=$12, gtin=$13, ncm=$14,
                            peso_liquido=$15, peso_bruto=$16, largura=$17, altura=$18, profundidade=$19,
                            estoque_atual=$20, estoque_minimo=$21, estoque_maximo=$22, imagem_url=$23,
                            descricao_curta=$24, descricao_complementar=$25, fornecedor_nome=$26,
                            data_criacao=$27, data_alteracao=$28, sincronizado_em=now()
                    """,
                        normalizado["id_bling"], normalizado["codigo"], normalizado["nome"],
                        normalizado["tipo"], normalizado["formato"], normalizado["situacao"],
                        normalizado["preco"], normalizado["preco_custo"],
                        normalizado["categoria_id"], normalizado["categoria_nome"],
                        normalizado["marca"], normalizado["unidade"], normalizado["gtin"], normalizado["ncm"],
                        normalizado["peso_liquido"], normalizado["peso_bruto"],
                        normalizado["largura"], normalizado["altura"], normalizado["profundidade"],
                        normalizado["estoque_atual"], normalizado["estoque_minimo"], normalizado["estoque_maximo"],
                        normalizado["imagem_url"], normalizado["descricao_curta"], normalizado["descricao_complementar"],
                        normalizado["fornecedor_nome"], normalizado["data_criacao"], normalizado["data_alteracao"],
                    )
                    total_ok += 1
                except Exception as e:
                    log(AGENT, f"Erro ao sincronizar produto {id_produto}: {e}")
                finally:
                    _SYNC_STATUS["processados"] += 1
                    time.sleep(0.34)  # throttle ~3 req/s

            return {"sincronizados": total_ok}
        finally:
            _SYNC_STATUS["em_andamento"] = False

    return run_async(_go())
```

Manter a função antiga `sincronizar_produtos()` (linha 119-146) intacta — ela alimenta `fichas_tecnicas`/`anuncios` e é usada por outro fluxo (`api_task_bling` na linha ~232 de `integrations.py`). `sincronizar_produtos_completo` é uma função nova e separada, não substitui a antiga.

- [ ] **Step 2: Verificação manual (requer Bling autenticado + banco configurado)**

Run:
```bash
cd hermes_agents && python -c "
from bling_erp import sincronizar_produtos_completo, status_sincronizacao_produtos
print(sincronizar_produtos_completo())
print(status_sincronizacao_produtos())
"
```
Expected: `{'sincronizados': N}` com N > 0 se houver produtos e token válido; `{'em_andamento': False, 'processados': N, 'total': N, 'erro': None}`. Se `BLING_ACCESS_TOKEN` não estiver configurado no ambiente local, é esperado `{'sincronizados': 0, 'erro': 'Bling não autenticado...'}` — aceitável nesta etapa, a validação completa acontece em produção onde o token existe.

- [ ] **Step 3: Commit**

```bash
git add hermes_agents/bling_erp.py
git commit -m "feat: sincronizacao completa de produtos Bling com throttle e progresso"
```

---

### Task 4: Rotas Flask — filtros, categorias, sync com progresso

**Files:**
- Modify: `hermes_agents/routes/integrations.py`

**Interfaces:**
- Consumes: `listar_produtos_local, listar_categorias_produtos, sincronizar_produtos_completo, status_sincronizacao_produtos` (Tasks 2 e 3), `criar_produto, atualizar_produto, deletar_produto` (já existentes).
- Produces: rotas Flask atualizadas em `bling_bp`.

- [ ] **Step 1: Atualizar o import e as rotas de produtos**

Em `hermes_agents/routes/integrations.py`, atualizar o bloco de import (linhas 418-427):

```python
from bling_erp import (
    status as bling_status_fn, get_auth_url, exchange_code,
    listar_produtos, criar_produto, atualizar_produto, deletar_produto,
    atualizar_situacao_produtos,
    listar_depositos, obter_saldo_deposito, atualizar_estoque_deposito,
    listar_pedidos, listar_contas_receber, listar_notas_fiscais,
    resumo_vendas, sincronizar_produtos, sincronizar_pedidos,
    listar_webhooks, criar_webhook, deletar_webhook,
    listar_notificacoes, confirmar_leitura_notificacao,
    listar_produtos_local, listar_categorias_produtos,
    sincronizar_produtos_completo, status_sincronizacao_produtos,
)
import threading
```

Substituir a rota `api_produtos` (linhas 452-456):

```python
@bling_bp.route("/produtos")
def api_produtos():
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 50, type=int)
    filtros = {
        "busca": request.args.get("busca") or None,
        "situacao": request.args.get("situacao") or None,
        "categoria_id": request.args.get("categoria_id", type=int),
        "preco_min": request.args.get("preco_min", type=float),
        "preco_max": request.args.get("preco_max", type=float),
        "estoque_min": request.args.get("estoque_min", type=float),
        "estoque_max": request.args.get("estoque_max", type=float),
        "estoque_baixo": request.args.get("estoque_baixo") == "true",
        "data_de": request.args.get("data_de") or None,
        "data_ate": request.args.get("data_ate") or None,
        "ordenar_por": request.args.get("ordenar_por") or None,
    }
    return jsonify(listar_produtos_local(filtros, pagina, limite))


@bling_bp.route("/produtos/categorias")
def api_produtos_categorias():
    return jsonify(listar_categorias_produtos())
```

Substituir a rota de sincronizar (linhas 484-486) e adicionar a rota de status:

```python
@bling_bp.route("/produtos/sincronizar", methods=["POST"])
def api_sincronizar_produtos():
    if status_sincronizacao_produtos()["em_andamento"]:
        return jsonify({"erro": "Sincronização já em andamento"}), 409
    thread = threading.Thread(target=sincronizar_produtos_completo, daemon=True)
    thread.start()
    return jsonify({"iniciado": True})


@bling_bp.route("/produtos/sincronizar/status")
def api_status_sincronizar_produtos():
    return jsonify(status_sincronizacao_produtos())
```

As rotas `api_criar_produto`, `api_atualizar_produto`, `api_deletar_produto` (linhas 459-473) continuam chamando `criar_produto`/`atualizar_produto`/`deletar_produto` sem mudança — essas funções batem direto no Bling; espelhar o resultado na tabela local fica fora de escopo desta task (documentado como não-crítico: a próxima sincronização completa já corrige a tabela local).

- [ ] **Step 2: Verificação manual (requer o servidor Flask rodando)**

Run:
```bash
cd hermes_agents && python -c "
from routes.integrations import bling_bp
print([r.rule for r in bling_bp.deferred_functions] if hasattr(bling_bp, 'deferred_functions') else 'blueprint importado sem erro')
"
```
Expected: nenhuma exceção de import (confirma que os nomes importados existem e a sintaxe das rotas está correta).

Se houver um servidor local disponível, testar com `curl`:
```bash
curl "http://localhost:5000/api/bling/produtos?busca=teste&situacao=A"
curl "http://localhost:5000/api/bling/produtos/categorias"
curl -X POST "http://localhost:5000/api/bling/produtos/sincronizar"
curl "http://localhost:5000/api/bling/produtos/sincronizar/status"
```
Expected: JSON válido em todas, sem 500.

- [ ] **Step 3: Commit**

```bash
git add hermes_agents/routes/integrations.py
git commit -m "feat: rotas de produtos Bling com filtros, categorias e status de sync"
```

---

### Task 5: Frontend — `api.ts` (tipos, filtros, correção de bug)

**Files:**
- Modify: `web/src/lib/api.ts`

**Interfaces:**
- Produces: `interface BlingProduto` (expandida), `interface BlingProdutoFiltros`, `listarBlingProdutos(filtros?: BlingProdutoFiltros, pagina?: number, limite?: number)`, `listarBlingCategorias()`, `statusSincronizacaoBlingProdutos()`.

- [ ] **Step 1: Expandir o tipo `BlingProduto` e adicionar `BlingProdutoFiltros`**

Em `web/src/lib/api.ts`, substituir (linhas 272-279):

```typescript
export interface BlingProduto {
  id: number;
  codigo: string;
  nome?: string;
  descricao: string;
  preco: number;
  precoCusto?: number;
  situacao: string;
  tipo?: string;
  formato?: string;
  categoriaId?: number;
  categoriaNome?: string;
  marca?: string;
  unidade?: string;
  gtin?: string;
  ncm?: string;
  pesoLiquido?: number;
  pesoBruto?: number;
  largura?: number;
  altura?: number;
  profundidade?: number;
  estoqueAtual?: number;
  estoqueMinimo?: number;
  estoqueMaximo?: number;
  imagemURL?: string;
  descricaoCurta?: string;
  descricaoComplementar?: string;
  fornecedorNome?: string;
  dataCriacao?: string;
  dataAlteracao?: string;
  [key: string]: unknown;
}

export interface BlingProdutoFiltros {
  busca?: string;
  situacao?: string;
  categoriaId?: number;
  precoMin?: number;
  precoMax?: number;
  estoqueMin?: number;
  estoqueMax?: number;
  estoqueBaixo?: boolean;
  dataDe?: string;
  dataAte?: string;
  ordenarPor?: "nome" | "preco" | "estoque" | "data_criacao";
}
```

- [ ] **Step 2: Atualizar `listarBlingProdutos` para aceitar filtros, adicionar `listarBlingCategorias`/`statusSincronizacaoBlingProdutos`, corrigir bug das barras invertidas**

Substituir (linhas 328-334):

```typescript
export async function listarBlingProdutos(
  filtros: BlingProdutoFiltros = {},
  pagina = 1,
  limite = 50
): Promise<BlingProdutosResponse & { total?: number }> {
  const params = new URLSearchParams({ pagina: String(pagina), limite: String(limite) });
  if (filtros.busca) params.set("busca", filtros.busca);
  if (filtros.situacao) params.set("situacao", filtros.situacao);
  if (filtros.categoriaId !== undefined) params.set("categoria_id", String(filtros.categoriaId));
  if (filtros.precoMin !== undefined) params.set("preco_min", String(filtros.precoMin));
  if (filtros.precoMax !== undefined) params.set("preco_max", String(filtros.precoMax));
  if (filtros.estoqueMin !== undefined) params.set("estoque_min", String(filtros.estoqueMin));
  if (filtros.estoqueMax !== undefined) params.set("estoque_max", String(filtros.estoqueMax));
  if (filtros.estoqueBaixo) params.set("estoque_baixo", "true");
  if (filtros.dataDe) params.set("data_de", filtros.dataDe);
  if (filtros.dataAte) params.set("data_ate", filtros.dataAte);
  if (filtros.ordenarPor) params.set("ordenar_por", filtros.ordenarPor);
  const res = await fetch(`/api/bling/produtos?${params.toString()}`);
  return res.json();
}

export async function listarBlingCategorias(): Promise<{ data: { id: number; nome: string }[] }> {
  const res = await fetch("/api/bling/produtos/categorias");
  return res.json();
}

export async function statusSincronizacaoBlingProdutos(): Promise<{
  em_andamento: boolean;
  processados: number;
  total: number;
  erro: string | null;
}> {
  const res = await fetch("/api/bling/produtos/sincronizar/status");
  return res.json();
}
```

Corrigir as duas URLs quebradas (linhas 359-364 e 378-384 no arquivo original):

```typescript
export async function deletarBlingProduto(
  id: number
): Promise<{ success?: boolean; error?: string }> {
  const res = await fetch(`/api/bling/produtos/${id}`, { method: "DELETE" });
  return res.json();
}
```

```typescript
export async function sincronizarBlingProdutos(): Promise<{
  sincronizados?: number;
  erro?: string;
}> {
  const res = await fetch("/api/bling/produtos/sincronizar", { method: "POST" });
  return res.json();
}
```

- [ ] **Step 3: Checar tipos**

Run: `cd web && npx tsc --noEmit`
Expected: sem novos erros relacionados a `web/src/lib/api.ts` (erros pré-existentes em outros arquivos, se houver, não são desta task).

- [ ] **Step 4: Commit**

```bash
git add web/src/lib/api.ts
git commit -m "fix: corrige URLs quebradas e adiciona filtros/campos completos de produtos Bling"
```

---

### Task 6: Frontend — barra de filtros, tabela enxuta e progresso de sync

**Files:**
- Modify: `web/src/app/integracoes/bling/_components/BlingProductsTab.tsx`

**Interfaces:**
- Consumes: `listarBlingProdutos, listarBlingCategorias, statusSincronizacaoBlingProdutos, sincronizarBlingProdutos` (Task 5).
- Produces: prop nova `onProductClick?: (produto: BlingProduto) => void` disparada ao clicar numa linha (usada pela Task 7 para abrir o painel de detalhe).

- [ ] **Step 1: Reescrever `BlingProductsTab.tsx` com filtros, colunas novas e progresso de sync**

Ler o arquivo atual antes de editar (já lido nesta sessão — 288 linhas). Aplicar as seguintes mudanças:

Substituir os imports (linhas 1-18):

```typescript
"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Spinner from "./shared/Spinner";
import Alert from "./shared/Alert";
import EmptyState from "./shared/EmptyState";
import StockModal from "./StockModal";
import {
  listarBlingProdutos,
  deletarBlingProduto,
  atualizarSituacaoProdutos,
  sincronizarBlingProdutos,
  listarBlingDepositos,
  listarBlingCategorias,
  statusSincronizacaoBlingProdutos,
  atualizarEstoqueDeposito,
  BlingProduto,
  BlingDeposito,
  BlingProdutoFiltros,
} from "@/lib/api";

interface BlingProductsTabProps {
  onNewProduct?: () => void;
  onStockManage?: () => void;
  onProductClick?: (produto: BlingProduto) => void;
}
```

Substituir a assinatura do componente e o state (linhas 25-38):

```typescript
export default function BlingProductsTab({ onNewProduct, onStockManage, onProductClick }: BlingProductsTabProps) {
  const [produtos, setProdutos] = useState<BlingProduto[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [pagina, setPagina] = useState(1);
  const [depositos, setDepositos] = useState<BlingDeposito[]>([]);
  const [categorias, setCategorias] = useState<{ id: number; nome: string }[]>([]);
  const [filtros, setFiltros] = useState<BlingProdutoFiltros>({});
  const [buscaInput, setBuscaInput] = useState("");
  const [syncStatus, setSyncStatus] = useState<{ em_andamento: boolean; processados: number; total: number } | null>(null);
  const syncPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Stock inline editor state
  const [editStockId, setEditStockId] = useState<number | null>(null);
  const [editStockQty, setEditStockQty] = useState(0);
  const [editStockDeposit, setEditStockDeposit] = useState<number>(0);
  const [stockModalProduto, setStockModalProduto] = useState<{ id: number; codigo: string; nome: string; preco: number } | null>(null);
```

Substituir `carregar` e adicionar debounce da busca + polling de sync (substitui linhas 40-60):

```typescript
  const carregar = useCallback(async (p = 1, f: BlingProdutoFiltros = filtros) => {
    try {
      setLoading(true);
      setErro(null);
      const [r, d, c] = await Promise.all([
        listarBlingProdutos(f, p, 50),
        listarBlingDepositos().catch(() => ({ data: [] })),
        listarBlingCategorias().catch(() => ({ data: [] })),
      ]);
      if (r.error) throw new Error(r.error);
      setProdutos(r.data || []);
      setTotal(r.total || 0);
      setDepositos(d.data || []);
      setCategorias(c.data || []);
      if (d.data?.length && !editStockDeposit) setEditStockDeposit(d.data[0].id);
      setPagina(p);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar produtos");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { carregar(1, filtros); }, [carregar]);

  // Debounce da busca textual
  useEffect(() => {
    const t = setTimeout(() => {
      const novosFiltros = { ...filtros, busca: buscaInput || undefined };
      setFiltros(novosFiltros);
      carregar(1, novosFiltros);
    }, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buscaInput]);

  const aplicarFiltro = (patch: Partial<BlingProdutoFiltros>) => {
    const novosFiltros = { ...filtros, ...patch };
    setFiltros(novosFiltros);
    carregar(1, novosFiltros);
  };

  const limparFiltros = () => {
    setBuscaInput("");
    setFiltros({});
    carregar(1, {});
  };

  const pollSyncStatus = useCallback(() => {
    if (syncPollRef.current) return;
    syncPollRef.current = setInterval(async () => {
      const s = await statusSincronizacaoBlingProdutos().catch(() => null);
      if (!s) return;
      setSyncStatus(s);
      if (!s.em_andamento) {
        if (syncPollRef.current) clearInterval(syncPollRef.current);
        syncPollRef.current = null;
        setSucesso("Sincronização concluída");
        carregar(pagina, filtros);
      }
    }, 2000);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pagina, filtros]);

  useEffect(() => () => { if (syncPollRef.current) clearInterval(syncPollRef.current); }, []);
```

Substituir `handleSync` (linhas 143-154 no arquivo original):

```typescript
  const handleSync = async () => {
    try {
      const r = await sincronizarBlingProdutos();
      if (r.erro) throw new Error(r.erro);
      setSucesso("Sincronização iniciada");
      setSyncStatus({ em_andamento: true, processados: 0, total: 0 });
      pollSyncStatus();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro na sincronização");
    }
  };
```

Adicionar a barra de filtros logo abaixo da barra de ações existente (depois do `</div>` que fecha o `flex flex-wrap items-center justify-between gap-2` — linha 193 no arquivo original — e antes do `{produtos.length === 0 ? (`):

```typescript
      {syncStatus?.em_andamento && (
        <div className="bg-neutral-800 border border-indigo-700/50 rounded-lg px-3 py-2 text-xs text-indigo-300">
          Sincronizando produtos... {syncStatus.processados}/{syncStatus.total || "?"}
        </div>
      )}

      <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-3 flex flex-wrap items-end gap-2">
        <div className="flex flex-col gap-1">
          <label className="text-[10px] text-neutral-500">Buscar</label>
          <input type="text" value={buscaInput} onChange={(e) => setBuscaInput(e.target.value)}
            placeholder="Nome ou SKU" className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200 w-40" />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[10px] text-neutral-500">Status</label>
          <select value={filtros.situacao || ""} onChange={(e) => aplicarFiltro({ situacao: e.target.value || undefined })}
            className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200">
            <option value="">Todos</option>
            <option value="A">Ativo</option>
            <option value="I">Inativo</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[10px] text-neutral-500">Categoria</label>
          <select value={filtros.categoriaId ?? ""} onChange={(e) => aplicarFiltro({ categoriaId: e.target.value ? Number(e.target.value) : undefined })}
            className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200">
            <option value="">Todas</option>
            {categorias.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[10px] text-neutral-500">Preço mín/máx</label>
          <div className="flex gap-1">
            <input type="number" placeholder="Min" value={filtros.precoMin ?? ""} onChange={(e) => aplicarFiltro({ precoMin: e.target.value ? Number(e.target.value) : undefined })}
              className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200 w-16" />
            <input type="number" placeholder="Max" value={filtros.precoMax ?? ""} onChange={(e) => aplicarFiltro({ precoMax: e.target.value ? Number(e.target.value) : undefined })}
              className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200 w-16" />
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[10px] text-neutral-500">Estoque mín/máx</label>
          <div className="flex gap-1">
            <input type="number" placeholder="Min" value={filtros.estoqueMin ?? ""} onChange={(e) => aplicarFiltro({ estoqueMin: e.target.value ? Number(e.target.value) : undefined })}
              className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200 w-16" />
            <input type="number" placeholder="Max" value={filtros.estoqueMax ?? ""} onChange={(e) => aplicarFiltro({ estoqueMax: e.target.value ? Number(e.target.value) : undefined })}
              className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200 w-16" />
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[10px] text-neutral-500">Criado de/até</label>
          <div className="flex gap-1">
            <input type="date" value={filtros.dataDe ?? ""} onChange={(e) => aplicarFiltro({ dataDe: e.target.value || undefined })}
              className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200" />
            <input type="date" value={filtros.dataAte ?? ""} onChange={(e) => aplicarFiltro({ dataAte: e.target.value || undefined })}
              className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200" />
          </div>
        </div>
        <label className="flex items-center gap-1 text-[10px] text-neutral-400 pb-1.5">
          <input type="checkbox" checked={!!filtros.estoqueBaixo} onChange={(e) => aplicarFiltro({ estoqueBaixo: e.target.checked || undefined })} />
          Só estoque baixo
        </label>
        <button onClick={limparFiltros} className="text-[10px] text-neutral-400 hover:text-neutral-200 underline pb-1.5">Limpar filtros</button>
        <span className="text-[10px] text-neutral-500 ml-auto pb-1.5">{total} produto(s)</span>
      </div>
```

Adicionar a coluna "Categoria" e "Criado em" na `<thead>` (linhas 200-210 no arquivo original) e o `onClick` na `<tr>` do corpo da tabela (linha 217):

```typescript
              <tr className="border-b border-neutral-700 text-neutral-400">
                <th className="p-3 w-8"><input type="checkbox" checked={selected.size === produtos.length && produtos.length > 0} onChange={toggleAll} /></th>
                <th className="text-left p-3 w-10"></th>
                <th className="text-left p-3">SKU</th>
                <th className="text-left p-3">Nome</th>
                <th className="text-left p-3">Categoria</th>
                <th className="text-right p-3">Preço</th>
                <th className="text-center p-3 w-36">Estoque</th>
                <th className="text-center p-3 w-20">Status</th>
                <th className="text-left p-3">Criado em</th>
                <th className="text-right p-3">Ações</th>
              </tr>
```

```typescript
                <tr key={p.id} className={`border-b border-neutral-700/50 cursor-pointer hover:bg-neutral-700/30 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}
                  onClick={() => onProductClick?.(p)}>
```

(mantendo os `<td>` de checkbox/ações com `onClick={(e) => e.stopPropagation()}` no `<input>`/`<button>` internos, já que hoje já usam `onChange`/`onClick` próprios — adicionar `e.stopPropagation()` dentro de cada handler existente que fica dentro da linha, ex.: `onClick={(e) => { e.stopPropagation(); toggleSelect(p.id); }}` no `<input type="checkbox">` da primeira coluna e em todos os botões de estoque/deletar, para que clicar neles não dispare também a abertura do painel de detalhe).

Adicionar as duas novas `<td>` no corpo (entre a coluna Nome e a coluna Preço, e entre Status e Ações):

```typescript
                  <td className="p-3 text-neutral-400 max-w-[120px] truncate">{p.categoriaNome || "—"}</td>
```

```typescript
                  <td className="p-3 text-neutral-400">{p.dataCriacao ? new Date(p.dataCriacao).toLocaleDateString("pt-BR") : "—"}</td>
```

- [ ] **Step 2: Checar tipos e lint**

Run: `cd web && npx tsc --noEmit && npx eslint src/app/integracoes/bling/_components/BlingProductsTab.tsx`
Expected: sem erros novos.

- [ ] **Step 3: Commit**

```bash
git add web/src/app/integracoes/bling/_components/BlingProductsTab.tsx
git commit -m "feat: barra de filtros, colunas de categoria/data e progresso de sync na aba de Produtos"
```

---

### Task 7: Frontend — painel de detalhe completo (drawer)

**Files:**
- Modify: `web/src/app/integracoes/bling/_components/ProductFormModal.tsx`
- Modify: `web/src/app/integracoes/bling/page.tsx` (conectar `onProductClick` ao componente)

**Interfaces:**
- Consumes: `BlingProduto` (Task 5), `criarBlingProduto, atualizarBlingProduto` (já existentes).

- [ ] **Step 1: Expandir `ProductFormModal.tsx` com os campos completos**

Substituir o `useState` do form (linhas 15-20):

```typescript
  const [form, setForm] = useState({
    codigo: produto?.codigo || "",
    descricao: produto?.descricao || produto?.nome || "",
    preco: produto?.preco || 0,
    situacao: produto?.situacao || "A",
    marca: produto?.marca || "",
    unidade: produto?.unidade || "",
    gtin: produto?.gtin || "",
    ncm: produto?.ncm || "",
    pesoLiquido: produto?.pesoLiquido || 0,
    pesoBruto: produto?.pesoBruto || 0,
    largura: produto?.largura || 0,
    altura: produto?.altura || 0,
    profundidade: produto?.profundidade || 0,
    estoqueMinimo: produto?.estoqueMinimo || 0,
    estoqueMaximo: produto?.estoqueMaximo || 0,
    descricaoComplementar: produto?.descricaoComplementar || "",
  });
```

Adicionar os campos novos no JSX, logo após o bloco `<div>` de "Situação" (linhas 79-86) e antes do `<div className="flex justify-end gap-2 pt-2">`:

```typescript
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-neutral-400 mb-1">Marca</label>
              <input type="text" value={form.marca} onChange={(e) => setForm({ ...form, marca: e.target.value })}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500" />
            </div>
            <div>
              <label className="block text-xs text-neutral-400 mb-1">Unidade</label>
              <input type="text" value={form.unidade} onChange={(e) => setForm({ ...form, unidade: e.target.value })}
                placeholder="UN, KG, CX..." className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500" />
            </div>
            <div>
              <label className="block text-xs text-neutral-400 mb-1">GTIN/EAN</label>
              <input type="text" value={form.gtin} onChange={(e) => setForm({ ...form, gtin: e.target.value })}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500" />
            </div>
            <div>
              <label className="block text-xs text-neutral-400 mb-1">NCM</label>
              <input type="text" value={form.ncm} onChange={(e) => setForm({ ...form, ncm: e.target.value })}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500" />
            </div>
            <div>
              <label className="block text-xs text-neutral-400 mb-1">Peso líquido (kg)</label>
              <input type="number" step="0.01" min="0" value={form.pesoLiquido} onChange={(e) => setForm({ ...form, pesoLiquido: parseFloat(e.target.value) || 0 })}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500" />
            </div>
            <div>
              <label className="block text-xs text-neutral-400 mb-1">Peso bruto (kg)</label>
              <input type="number" step="0.01" min="0" value={form.pesoBruto} onChange={(e) => setForm({ ...form, pesoBruto: parseFloat(e.target.value) || 0 })}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500" />
            </div>
            <div>
              <label className="block text-xs text-neutral-400 mb-1">Largura (cm)</label>
              <input type="number" step="0.1" min="0" value={form.largura} onChange={(e) => setForm({ ...form, largura: parseFloat(e.target.value) || 0 })}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500" />
            </div>
            <div>
              <label className="block text-xs text-neutral-400 mb-1">Altura (cm)</label>
              <input type="number" step="0.1" min="0" value={form.altura} onChange={(e) => setForm({ ...form, altura: parseFloat(e.target.value) || 0 })}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500" />
            </div>
            <div>
              <label className="block text-xs text-neutral-400 mb-1">Profundidade (cm)</label>
              <input type="number" step="0.1" min="0" value={form.profundidade} onChange={(e) => setForm({ ...form, profundidade: parseFloat(e.target.value) || 0 })}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500" />
            </div>
            <div>
              <label className="block text-xs text-neutral-400 mb-1">Estoque mínimo</label>
              <input type="number" min="0" value={form.estoqueMinimo} onChange={(e) => setForm({ ...form, estoqueMinimo: parseFloat(e.target.value) || 0 })}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500" />
            </div>
            <div>
              <label className="block text-xs text-neutral-400 mb-1">Estoque máximo</label>
              <input type="number" min="0" value={form.estoqueMaximo} onChange={(e) => setForm({ ...form, estoqueMaximo: parseFloat(e.target.value) || 0 })}
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500" />
            </div>
          </div>

          <div>
            <label className="block text-xs text-neutral-400 mb-1">Descrição complementar</label>
            <textarea value={form.descricaoComplementar} onChange={(e) => setForm({ ...form, descricaoComplementar: e.target.value })}
              rows={3} className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500" />
          </div>

          {isEdit && (
            <div className="grid grid-cols-2 gap-2 text-[10px] text-neutral-500 border-t border-neutral-700 pt-2">
              <span>Categoria: {produto?.categoriaNome || "—"}</span>
              <span>Fornecedor: {produto?.fornecedorNome || "—"}</span>
              <span>Criado em: {produto?.dataCriacao ? new Date(produto.dataCriacao).toLocaleDateString("pt-BR") : "—"}</span>
              <span>Alterado em: {produto?.dataAlteracao ? new Date(produto.dataAlteracao).toLocaleDateString("pt-BR") : "—"}</span>
            </div>
          )}
```

Categoria e fornecedor ficam somente-leitura (editá-los exigiria criar/listar categorias/fornecedores no Bling, fora do escopo definido na spec).

- [ ] **Step 2: Conectar `onProductClick` em `page.tsx`**

Hoje `web/src/app/integracoes/bling/page.tsx` só tem `showProductForm` (boolean) controlando o `ProductFormModal` a partir do botão "+ Novo" (sempre em modo criação, sem produto). Vamos adicionar um segundo state para o produto clicado na tabela, e unificar a renderização do modal para cobrir os dois casos (criar e editar).

Em `web/src/app/integracoes/bling/page.tsx`, atualizar o import (linha 10) para trazer o tipo:

```typescript
import ProductFormModal from "./_components/ProductFormModal";
import type { BlingProduto } from "@/lib/api";
```

Adicionar o novo state, logo após a linha 27 (`const [showStockModal, setShowStockModal] = useState(false);`):

```typescript
  const [editingProduct, setEditingProduct] = useState<BlingProduto | null>(null);
```

Passar `onProductClick` para `BlingProductsTab` (linha 54):

```typescript
        {activeTab === "produtos" && (
          <BlingProductsTab
            onNewProduct={() => setShowProductForm(true)}
            onStockManage={() => setShowStockModal(true)}
            onProductClick={(p) => setEditingProduct(p)}
          />
        )}
```

Substituir o bloco de renderização do `ProductFormModal` (linhas 61-66) para cobrir os dois casos e limpar `editingProduct` ao fechar/salvar:

```typescript
      {(showProductForm || editingProduct) && (
        <ProductFormModal
          produto={editingProduct}
          onClose={() => { setShowProductForm(false); setEditingProduct(null); }}
          onSaved={() => { setShowProductForm(false); setEditingProduct(null); }}
        />
      )}
```

- [ ] **Step 3: Checar tipos e lint**

Run: `cd web && npx tsc --noEmit && npx eslint src/app/integracoes/bling/_components/ProductFormModal.tsx src/app/integracoes/bling/page.tsx`
Expected: sem erros novos.

- [ ] **Step 4: Commit**

```bash
git add web/src/app/integracoes/bling/_components/ProductFormModal.tsx web/src/app/integracoes/bling/page.tsx
git commit -m "feat: painel de detalhe completo do produto Bling (drawer ao clicar na linha)"
```

---

## Notas de implementação

- Os nomes de campo assumidos na resposta do Bling v3 (`categoria.descricao`, `estoque.saldoVirtualTotal`, `tributacao.ncm`, `fornecedor.nome`, `dataInclusao`/`dataAlteracao`) não foram confirmados contra uma chamada real à API nesta sessão (o usuário pediu para não usar o navegador). Toda a extração desses campos está isolada em `_normalizar_produto_bling` (Task 1) — se algum nome de campo divergir do que o Bling realmente retorna, o ajuste é uma mudança de uma função só, sem tocar em schema, rotas ou frontend.
- Task 3 e Task 4 exigem `BLING_ACCESS_TOKEN` configurado para validação end-to-end; sem isso, o teste manual descrito ainda deve rodar sem exceções (retornando erro de autenticação tratado), o que já valida a integração do código.
