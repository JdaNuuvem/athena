# Vínculo de estoque entre loja física e virtual

**Relacionado:** [2026-07-30-pdv-baixa-estoque-loja-fisica-design.md](2026-07-30-pdv-baixa-estoque-loja-fisica-design.md) (irmã — a baixa de PDV desta spec passa a valer pro saldo compartilhado automaticamente, sem precisar mudar nada lá, porque o resolver desta spec fica na mesma camada que `saida_async()` já usa). Segue o mesmo padrão de migração incremental já usado em [2026-07-28-produtos-catalogo-mestre-loja-reconciliacao-design.md](2026-07-28-produtos-catalogo-mestre-loja-reconciliacao-design.md), mas aqui migrando **tudo de uma vez**, por decisão explícita do usuário.

## Regra do usuário (não negociável)

> Todos os estoques e PDVs são independentes uns dos outros, a menos que o vínculo entre loja física e virtual esteja ativo.

Independência é o padrão. Vínculo é opt-in, por par de lojas, reversível.

## Decisões

- **Saldo único compartilhado**, não dois saldos espelhados. Loja física e virtual vinculadas leem/escrevem o MESMO número.
- **Cardinalidade**: 1 física pode ter várias virtuais vinculadas nela (hub-and-spoke). Cada virtual vincula em no máximo 1 física.
- **Ativar vínculo**: saldo da física vira o compartilhado. Linhas próprias que a virtual tinha em `estoque_lojas`/`estoque_saldos` sob o nome dela ficam órfãs (não apagadas — histórico de auditoria preservado — só param de ser a fonte ativa, porque escrita e leitura passam a resolver pro nome da física).
- **Desativar vínculo**: a virtual recebe uma cópia do saldo compartilhado no momento da desvinculação como novo ponto de partida independente (não zera, não seria razoável some do estoque visível da hora pra outra). A partir daí as duas voltam a divergir independentemente.
- **Escopo é só estoque (quantidade)**, não preço/mínimo/máximo — `produtos_loja` (config por loja: preço, promoção, comissão, mín/máx) continua independente por loja mesmo vinculada. Só a quantidade física resolve pra física.
- **Migração completa nesta spec** — todos os ~19 pontos de leitura/escrita crua identificados (ver "Levantamento completo" abaixo), não só os de maior uso.

## Modelo de dados

```sql
ALTER TABLE lojas ADD COLUMN IF NOT EXISTS loja_vinculada_id INT REFERENCES lojas(id);
```

Só tem sentido quando `tipo = 'virtual'` (aponta pra uma física). Validação na camada de aplicação (`vincular_estoque()`), não constraint de banco — mesmo padrão do resto do módulo lojas.

## Resolver central

`core/estoque_saldos.py` é a camada certa — é onde `mover_saldo`/`_mover_saldo_async` (escrita) e `saldo`/`_saldo_async` (leitura) já vivem, e é o único choke point real (o trigger `fn_espelhar_saldo_disponivel` espelha `estoque_lojas` a partir do que for gravado em `estoque_saldos`, então resolver aqui já cobre o espelho de graça).

Duas variantes — asyncpg (maioria do código) e psycopg2 sync (`routes/estoque.py`, `athena_bridge.py` usam conexão síncrona direta):

```python
# core/estoque_saldos.py
async def loja_efetiva_async(conn_or_db, loja: str) -> str:
    if not loja:
        return loja
    row = await conn_or_db.fetchrow(
        "SELECT l2.nome FROM lojas l1 JOIN lojas l2 ON l2.id = l1.loja_vinculada_id "
        "WHERE l1.nome = $1 AND l1.tipo = 'virtual' AND l1.loja_vinculada_id IS NOT NULL", loja)
    return row["nome"] if row else loja
```

```python
# core/lojas.py (ou onde fizer mais sentido reusar _db_sync-style — ver routes/estoque.py)
def loja_efetiva_sync(cur, loja: str) -> str:
    if not loja:
        return loja
    cur.execute(
        "SELECT l2.nome FROM lojas l1 JOIN lojas l2 ON l2.id = l1.loja_vinculada_id "
        "WHERE l1.nome = %s AND l1.tipo = 'virtual' AND l1.loja_vinculada_id IS NOT NULL", (loja,))
    row = cur.fetchone()
    return row[0] if row else loja
```

`vincular_estoque(loja_virtual_id, loja_fisica_id)` / `desvincular_estoque(loja_virtual_id)` em `core/lojas.py`: validam tipos (`virtual`/`fisica`), setam/limpam `loja_vinculada_id`, e no caso de desvincular, fazem a cópia do saldo compartilhado pra um novo conjunto de linhas `estoque_saldos`/`estoque_lojas` sob o nome da virtual (via `entrada_async` com motivo `"ajuste_inventario"`, uma entrada por sku que tiver saldo > 0 na física).

## Levantamento completo (todos os pontos que precisam do resolver)

Escrita — 17 pontos já passam por `mover_saldo`/`_mover_saldo_async`/`ajustar_absoluto_async` (`core/estoque.py`, `core/estoque_transferencias.py`, `core/estoque_aprovacoes.py`, `core/estoque_contagem.py`, `routes/estoque.py` pass-through, `bling_erp.py`, `core/entidades.py`) — **corrigidos automaticamente** assim que o resolver entra em `_mover_saldo_async`. Únicas exceções brutas: `core/estoque.py:524` (`reconciliar_loja_id`, só backfill de FK, sem risco de saldo) e o trigger do espelho (se autocura, nada a fazer).

Leitura/escrita crua que precisa de chamada explícita ao resolver:

| Arquivo:linha | Função | Driver |
|---|---|---|
| `core/estoque.py:55-92` | `listar()` | asyncpg |
| `core/estoque.py:247-276` | `movimentacoes()` | asyncpg |
| `core/estoque.py:360-370` | `sync_bling()` | asyncpg |
| `core/estoque_analise.py:35,93,104,178,189` | `giro()`, `ruptura()`, `cobertura()` | asyncpg |
| `core/estoque_aprovacoes.py:55` | `solicitar()` | asyncpg |
| `core/estoque_contagem.py:55-66,85-87` | `sugestoes()`, `registrar()` | asyncpg |
| `core/produtos_loja.py:129` | `listar_por_loja()` — só o JOIN com `estoque_lojas`, `pl.loja` do config em si continua sem resolver (produtos_loja config é independente por decisão acima) | asyncpg |
| `core/relatorios.py:77-78` | `estoque(loja_id)` | asyncpg |
| `core/repositories_postgres.py:156` | `buscar_quantidade()` | asyncpg |
| `routes/estoque.py:45-51,64,69` | `estoque_por_loja()` | psycopg2 sync |
| `athena_bridge.py:1605` | `listar_produtos()` | psycopg2 sync (confirmar driver ao implementar) |

Leituras que somam todas as lojas sem filtro (não precisam de nada — já corretas por construção): `athena_bridge.py` (demais), `core/bi.py`, `core/catalogo.py`, `core/estoque.py:404` (fallback), `core/pdv.py:553`, `core/relatorios.py:246`, `core/repositories_postgres.py:141,164`, `routes/estoque.py:160`, `routes/shopee.py:240`, `shopee/regras/estoque_alto.py:13`.

## UI

Aba "Virtual/Delivery" de uma loja tipo `virtual` (já existe em `web/src/app/lojas/[id]/`, backend `core/lojas_virtual.py`) ganha um campo novo: seletor "Loja física vinculada" (lista lojas `tipo='fisica'`, opção "Nenhuma" pra desvincular). Endpoint `PUT /api/lojas/manage/<id>/vinculo-estoque` com `{loja_fisica_id: number | null}`.

## Testes

`hermes_agents/tests/test_lojas_vinculo_estoque.py`:
- `loja_efetiva_async`: virtual vinculada resolve pra física; virtual sem vínculo retorna o próprio nome; física retorna o próprio nome (nunca resolve física→outra coisa); loja inexistente retorna o nome original sem erro.
- `vincular_estoque`: saldo da física vira o compartilhado; virtual não pode vincular em outra virtual (erro); física não pode ser "vinculada" (só virtual tem `loja_vinculada_id`).
- `desvincular_estoque`: virtual recebe cópia do saldo no momento da desvinculação; física mantém o saldo dela intocado.
- Venda no PDV de uma loja física com virtual vinculada: `giro()`/`cobertura()` da virtual mostram o mesmo saldo que a física, refletindo a venda.

## Fora de escopo (registrado, não decidido aqui)

- Merge/independência de `produtos_loja` (preço, promoção, mín/máx, comissão) — decisão explícita: fica sempre por loja, vínculo é só de quantidade.
- Limpeza/exclusão das linhas órfãs de `estoque_lojas`/`estoque_saldos` da virtual após vincular — ficam no banco como histórico, sem rotina de limpeza automática.
- Loja virtual com estoque próprio manual (spec anterior, ainda pendente) — este vínculo é o mecanismo que, quando ativado, torna aquela spec sem efeito prático pra aquela virtual específica (ela para de ter estoque próprio pra passar a usar o da física); as duas specs não se contradizem, só uma prevalece por loja dependendo se `loja_vinculada_id` está setado.

## Próximo passo

`superpowers:writing-plans` — plano de implementação TDD. Dado o tamanho (resolver + ~11 pontos de leitura em 9 arquivos + UI + vincular/desvincular), o plano deve agrupar por arquivo/responsabilidade, não por linha.
