# Ranking de Produtos — Métricas Novas no Dashboard

**Data:** 2026-08-09

## Contexto

O `/dashboard` principal já tem um modal "Ranking de produtos" (`web/src/app/_components/RankingProdutosModal.tsx`, acionado pelo link "Ver ranking completo") com 3 abas — Mais lucro, Mais vendidos, Menos vendidos — todas alimentadas por `core.relatorios.ranking_produtos(dias)`, dado real (receita/custo/comissão/frete/lucro/margem por SKU).

Pedido do usuário: adicionar Menos lucro, Parado em estoque, e mais sugestões de métricas relevantes de produto. Da conversa, o escopo final ficou em 8 métricas agrupadas em 3 categorias.

**Descoberta importante durante a investigação:** o modelo de dados de venda mudou desde que `ranking_produtos()` foi escrito. Hoje:
- **Loja física**: catálogo e vendas do PDV vêm 100% do i9Logic (`core/i9logic_catalogo.py`, `core/i9logic_vendas.py`, spec `2026-07-30-i9logic-catalogo-vendas-fisica-design.md`), sincronizados continuamente pra `vendas_pedidos`/`vendas_itens` (`origem='i9logic_pdv'`). `pdv_vendas`/`pdv_itens` (PDV próprio do Hermes) está morto pra loja física — confirmado pelo usuário, não recebe mais venda real.
- **Loja virtual**: Shopee, sincronizada direto pra `vendas_pedidos`/`vendas_itens` (`core/vendas.py::sincronizar_pedidos_shopee`).
- Ou seja, os dois canais já convergem pras MESMAS tabelas (`vendas_pedidos`/`vendas_itens`) — não é preciso (nem correto) unir com `pdv_vendas` como `ranking_produtos()` legado ainda faz (union inofensivo, mas morto — fora de escopo mexer nisso aqui).
- Estoque (`estoque_lojas`) continua sendo a fonte única de saldo pra ambos os tipos de loja — pra loja física é preenchido manualmente pelo usuário (ele está em processo de auditoria/inventário no momento desta spec — ver [[project_i9logic_custo_pendente]] na memória, `preco_custo` de produtos de loja física ainda não está cadastrado, então lucro/margem desses produtos aparece como "custo não cadastrado" até a auditoria terminar — comportamento esperado, já existe o campo `custo_cadastrado` pra sinalizar isso).

## As 8 métricas, em 3 categorias

| Categoria | Abas | Fonte de dado |
|---|---|---|
| **Vendas** | Mais vendidos, Menos vendidos, Em alta, Em queda | `ranking_produtos()` (existe) + `produtos_tendencia()` (novo) |
| **Lucratividade** | Mais lucro, Menos lucro, Maior margem %, Curva ABC | `ranking_produtos()` (existe) + `curvas()` (existe, sem mudança) |
| **Estoque** | Parado em estoque, Risco de ruptura | `estoque_parado()` (existe, core/bi.py) + `risco_ruptura()` (novo) |

4 das 8 abas são zero mudança de backend — só um sort/filter diferente em cima do `ranking_produtos()` que já existe:
- **Menos lucro**: mesma lista, ordenada por `lucro` ascendente (pode incluir prejuízo, valor negativo — informação real).
- **Maior margem %**: mesma lista, filtrada a `custo_cadastrado === true` (sem isso, margem de produto sem custo cadastrado é ruído/enganoso), ordenada por `margem_pct` descendente.
- **Mais/Menos vendidos**: já existem hoje, sem mudança.

## Funções novas em `core/relatorios.py`

Mesmo padrão de `ranking_produtos()`: `async def _go()` + `run_async` + `try/except` retornando lista vazia em erro. Consultam `vendas_pedidos`/`vendas_itens` diretamente (sem union com `pdv_vendas` — motivo na seção Contexto).

### `produtos_tendencia(dias=30)` — Em alta / Em queda

Soma `quantidade` vendida por SKU em dois períodos de mesmo tamanho: atual (`CURRENT_DATE - dias` até `CURRENT_DATE`) e anterior (`CURRENT_DATE - dias*2` até `CURRENT_DATE - dias`).

```python
def produtos_tendencia(dias=30):
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"""
            SELECT vi.sku,
                   MAX(vi.descricao) AS descricao,
                   SUM(CASE WHEN vp.data >= CURRENT_DATE - $1::int THEN vi.quantidade ELSE 0 END) AS qtd_atual,
                   SUM(CASE WHEN vp.data < CURRENT_DATE - $1::int THEN vi.quantidade ELSE 0 END) AS qtd_anterior
            FROM vendas_itens vi JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
            WHERE vp.data >= CURRENT_DATE - $1::int * 2 AND vp.status != 'cancelado'
              AND vi.sku IS NOT NULL AND vi.sku != ''
            GROUP BY vi.sku
        """, dias)
        return [dict(r) for r in (rows or [])]
    try:
        linhas = run_async(_go())
    except Exception as e:
        return []

    resultado = []
    for r in linhas:
        atual = float(r["qtd_atual"] or 0)
        anterior = float(r["qtd_anterior"] or 0)
        if atual == 0 and anterior == 0:
            continue
        crescimento = round((atual - anterior) / anterior * 100, 1) if anterior else None
        resultado.append({
            "sku": r["sku"], "descricao": r["descricao"] or r["sku"],
            "quantidade_atual": round(atual, 2), "quantidade_anterior": round(anterior, 2),
            "crescimento_pct": crescimento,
        })
    return resultado
```

Casos especiais (mesma filosofia anti-número-fabricado já usada em `_variacao()` de `core/bi.py`):
- `anterior=0, atual>0` → produto novo/reativado, `crescimento_pct: None` (não inventa "+∞%"). No frontend, aba "Em alta" mostra esses primeiro (rótulo "Novo" em vez de percentual), critério: produto sem histórico vendendo agora é o sinal de alta mais forte que existe.
- `atual=0, anterior>0` → `crescimento_pct: -100`, aparece naturalmente no fim de "Em queda".
- SKU sem venda nos dois períodos não entra na lista.

Frontend ordena: "Em alta" = `crescimento_pct` descendente com os `null` (Novo) no topo; "Em queda" = `crescimento_pct` ascendente, `null` excluído (não decrescimento, sem base de comparação).

### `risco_ruptura(dias=30)` — vendendo bem, estoque acabando

Diferente de "Parado em estoque" (zero venda) e de `rupturas()` já existente em `core/relatorios.py` (zero estoque) — aqui é o meio-termo: velocidade de venda alta, estoque baixo.

```python
def risco_ruptura(dias=30):
    async def _go():
        db = await get_db()
        rows = await db.fetch(f"""
            SELECT vi.sku, MAX(vi.descricao) AS descricao, SUM(vi.quantidade) AS qtd_vendida,
                   (SELECT COALESCE(SUM(e.quantidade), 0) FROM estoque_lojas e WHERE e.sku = vi.sku) AS estoque_atual
            FROM vendas_itens vi JOIN vendas_pedidos vp ON vp.id = vi.pedido_id
            WHERE vp.data >= CURRENT_DATE - $1::int AND vp.status != 'cancelado'
              AND vi.sku IS NOT NULL AND vi.sku != ''
            GROUP BY vi.sku
        """, dias)
        return [dict(r) for r in (rows or [])]
    try:
        linhas = run_async(_go())
    except Exception as e:
        return []

    resultado = []
    for r in linhas:
        qtd_vendida = float(r["qtd_vendida"] or 0)
        estoque_atual = float(r["estoque_atual"] or 0)
        velocidade_diaria = qtd_vendida / dias
        if velocidade_diaria <= 0 or estoque_atual <= 0:
            continue
        resultado.append({
            "sku": r["sku"], "descricao": r["descricao"] or r["sku"],
            "estoque_atual": round(estoque_atual, 2), "quantidade_vendida": round(qtd_vendida, 2),
            "velocidade_diaria": round(velocidade_diaria, 3),
            "dias_restantes": round(estoque_atual / velocidade_diaria, 1),
        })
    resultado.sort(key=lambda p: p["dias_restantes"])
    return resultado[:15]
```

## Rotas novas (`routes/relatorios.py`)

Sem decorator de RBAC — mesmo padrão de `/ranking-produtos` e `/produtos` já existentes nesse arquivo (dado agregado de dashboard, não temos por-loja sensível aqui).

```python
@relatorios_bp.route("/estoque-parado", methods=["GET"])
def rel_estoque_parado():
    from core.bi import estoque_parado
    dias = request.args.get("dias", 60, type=int)
    limite = request.args.get("limite", 15, type=int)
    return jsonify(estoque_parado(dias, limite))


@relatorios_bp.route("/produtos-tendencia", methods=["GET"])
def rel_produtos_tendencia():
    from core.relatorios import produtos_tendencia
    dias = request.args.get("dias", 30, type=int)
    return jsonify(produtos_tendencia(dias))


@relatorios_bp.route("/risco-ruptura", methods=["GET"])
def rel_risco_ruptura():
    from core.relatorios import risco_ruptura
    dias = request.args.get("dias", 30, type=int)
    return jsonify(risco_ruptura(dias))
```

`/api/relatorios/curvas` já existe (`routes/relatorios.py:155`), sem mudança.

## Frontend — tipos e client (`web/src/lib/api.ts`)

```typescript
export interface EstoqueParadoItem {
  sku: string; nome: string; quantidade: number; valor_imobilizado: number; dias_sem_venda: number;
}

export interface ProdutoTendenciaItem {
  sku: string; descricao: string; quantidade_atual: number; quantidade_anterior: number;
  crescimento_pct: number | null;
}

export interface RiscoRupturaItem {
  sku: string; descricao: string; estoque_atual: number; quantidade_vendida: number;
  velocidade_diaria: number; dias_restantes: number;
}

export interface CurvaAbcItem {
  sku: string; descricao: string; valor_total: number; qtd: number; pct: number; pct_acum: number;
  classe: "A" | "B" | "C";
}

export interface CurvaAbcResponse { total_valor: number; total_itens: number; itens: CurvaAbcItem[] }
```

```typescript
relatorioEstoqueParado: (dias: number, limite = 15) =>
  request<EstoqueParadoItem[]>(`/api/relatorios/estoque-parado?dias=${dias}&limite=${limite}`),

relatorioProdutosTendencia: (dias: number) =>
  request<ProdutoTendenciaItem[]>(`/api/relatorios/produtos-tendencia?dias=${dias}`),

relatorioRiscoRuptura: (dias: number) =>
  request<RiscoRupturaItem[]>(`/api/relatorios/risco-ruptura?dias=${dias}`),

relatorioCurvas: (dias: number) =>
  request<CurvaAbcResponse>(`/api/relatorios/curvas?dias=${dias}`),
```

## Frontend — `RankingProdutosModal.tsx`

**Estrutura de estado:** categoria (`"vendas" | "lucratividade" | "estoque"`) + aba dentro da categoria + `dias` global (já existe). Cada categoria carrega seus 1-2 datasets em paralelo na primeira vez que é selecionada, guarda em cache local (state), não rebusca ao trocar de aba dentro da mesma categoria (mesmo espírito do fetch único atual que já alimenta 3 abas via sort client-side). Trocar `dias` invalida todo o cache.

- **Vendas**: `ranking_produtos` (Mais vendidos / Menos vendidos, sort client-side) + `produtos_tendencia` (Em alta / Em queda).
- **Lucratividade**: `ranking_produtos` (Mais lucro / Menos lucro / Maior margem %, sort/filter client-side) + `curvas` (ABC).
- **Estoque**: `estoque_parado` + `risco_ruptura` (já vêm ordenados do backend, sem sort client-side).

**UI:** seletor de categoria (3 botões/chips) acima do `TabBar` de abas — trocar categoria troca também o `TabBar` pras abas daquela categoria. Card de cada item reaproveita o layout visual atual (rank + nome/SKU à esquerda, valor à direita), só troca o que aparece no lado direito por métrica:
- Vendidos/Em alta/Em queda → quantidade + rótulo (un., ou "Novo"/percentual pra tendência)
- Lucro/Menos lucro/Margem → valor R$ + margem % (como já é hoje)
- ABC → valor R$ + badge de classe (A/B/C)
- Parado → valor imobilizado R$ + dias sem venda
- Risco de ruptura → dias restantes + velocidade de venda

## Testes

- Backend: `produtos_tendencia` — cálculo de crescimento correto, caso `anterior=0` retorna `None` (não inventa percentual), caso `atual=0` retorna -100%, SKU sem venda em nenhum período não aparece. `risco_ruptura` — só entra quem tem venda E estoque positivos, ordenação por `dias_restantes` ascendente, exclui zerados/parados corretamente (não sobrepõe com `estoque_parado`/`rupturas`).
- Rotas: 3 rotas novas respondem 200 com o parâmetro `dias` default e customizado.
- Frontend: `tsc --noEmit` limpo; smoke visual manual (Playwright ou navegador) confirmando as 8 abas renderizam com dado real, incluindo os casos de borda (produto sem custo cadastrado, produto "Novo" em tendência).

## Fora de escopo

- Mexer em `pdv_vendas`/`pdv_itens` (tabela morta, não é desta feature).
- Fix da union Bling+PDV legada dentro de `ranking_produtos()`/`curvas()` — inofensiva (contribui 0 linhas), não é bug ativo, não faz parte deste pedido.
- Separar métricas por tipo de loja (física vs virtual) na UI — as duas já convergem nas mesmas tabelas; se o usuário quiser um filtro por loja no futuro, é extensão natural (adicionar `loja_id` como parâmetro), não parte desta spec.
- Preencher `preco_custo` dos produtos de loja física — pendência do usuário (auditoria em andamento), não desta feature.
