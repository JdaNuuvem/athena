# Estoque Rápido (Shopee)

**Origem:** substitui, para uso diário, o sistema externo `D:\JORGE CHARME E LEON\SISTEMAS\ESTOQUE RAPIDO` (Playwright + perfil de Chrome + login manual na Shopee Seller Center). O Hermes já tem integração oficial via API Shopee (OAuth, sem simulação de navegador) — esta spec cobre só a UI que falta: uma grade única para editar estoque de vários SKUs × várias lojas Shopee rapidamente.

## Decisões

- **Só Shopee.** Único marketplace com API funcionando no Hermes hoje (Mercado Livre, Amazon etc. em `integrations.py` são placeholders sem client real). Outros marketplaces ficam fora até terem client de API dedicado.
- **Nenhum motor novo.** Reusa integralmente o que já existe:
  - `core.estoque.ajustar_absoluto(sku, loja_nome, quantidade, motivo, usuario, ...)` — grava saldo local, resolve `loja_efetiva` (loja virtual vinculada a uma física compartilha o mesmo saldo — ver [2026-07-30-vinculo-estoque-fisica-virtual-design.md](2026-07-30-vinculo-estoque-fisica-virtual-design.md)) e gera auditoria/ledger.
  - `shopee.stock.sincronizar_estoque_shopee(sku, quantidade, loja_id)` — resolve `item_id`/`model_id` via tabela `anuncios` e chama a API Shopee. Já devolve dict síncrono (`{}` em sucesso ou `{"error": "..."}` em falha).
  - `core.lojas.listar_lojas_shopee()` — lojas ativas com token Shopee válido.
- **Feedback síncrono por célula.** O caminho existente (`routes/estoque.py:_sync_shopee_async`) dispara `sincronizar_estoque_todas_lojas_automatico` numa thread solta e não espera resposta — serve para o fluxo geral de estoque, mas não para esta tela, onde o usuário precisa ver na hora se o push para a Shopee deu certo. Os 2 endpoints novos chamam `sincronizar_estoque_shopee` **síncrono**, sem thread.
- **Saldo local e sync Shopee são passos separados, com falhas separadas** (mesmo princípio já usado em `routes/estoque.py:99-101`): se o saldo local não grava, não tenta a Shopee. Se o saldo local grava mas a Shopee falha (token expirado, item sem anúncio, etc.), a célula reporta as duas coisas: saldo salvo localmente + erro específico da Shopee.
- **Escopo é só quantidade.** Preço, promoção, comissão etc. continuam em `produtos_loja` / outras telas — não fazem parte desta grade.
- **Grid carrega direto ao abrir a aba**, paginada (50 linhas/página, ordenado por SKU), sem exigir busca prévia — contradiz o modelo de "selecione uma loja primeiro" de `estoque/lojas/page.tsx` de propósito, porque o objetivo aqui é abrir a aba e já começar a editar.
- **Linha (SKU) só aparece se tiver pelo menos 1 anúncio Shopee** (`anuncios.marketplace = 'shopee'`) em alguma das lojas conectadas. Célula de uma loja onde aquele SKU não tem anúncio fica desabilitada ("—"), não escondida — usuário vê de relance em quais lojas falta publicar.
- **Após salvar uma célula, a linha inteira é re-buscada e atualizada na tela** (não só a célula editada). Necessário porque lojas virtuais vinculadas à mesma loja física compartilham saldo — editar a coluna da Loja A pode mudar o número que aparece na coluna da Loja B também.

## Modelo de dados

Nenhuma tabela nova. Reusa:
- `anuncios (sku, marketplace, anuncio_id, shop_id, status, ...)` — mapeamento SKU ↔ item Shopee, populado por `shopee_sync.sync_produtos`.
- `estoque_lojas (sku, loja, quantidade, ...)` — saldo local por SKU × nome de loja (já passa pelo resolver de `loja_efetiva`).
- `lojas (id, nome, tipo, shopee_shop_id, shopee_access_token, loja_vinculada_id, ...)`.

## Backend

Novo módulo `hermes_agents/shopee/estoque_rapido.py`:

```python
def listar_grid(busca: str = "", pagina: int = 1, por_pagina: int = 50) -> dict:
    """
    1. lojas = core.lojas.listar_lojas_shopee()  # colunas
    2. skus_pagina = SELECT DISTINCT a.sku, COALESCE(cp.descricao, ...) FROM anuncios a
       LEFT JOIN catalogo_produtos cp ON cp.sku = a.sku
       WHERE a.marketplace = 'shopee' AND a.shop_id = ANY(shop_ids das lojas)
         AND (busca = '' OR a.sku ILIKE %busca% OR cp.descricao ILIKE %busca%)
       ORDER BY a.sku LIMIT por_pagina OFFSET (pagina-1)*por_pagina
       -- + COUNT(*) equivalente para total
    3. pares_com_anuncio = SELECT sku, shop_id FROM anuncios
       WHERE marketplace='shopee' AND sku = ANY(skus_pagina) AND shop_id = ANY(shop_ids)
       -- define quais células são editáveis
    4. Para cada loja, resolve nome_efetivo (mesma lógica de core.lojas.loja_efetiva,
       só que em lote — evita 1 query por loja) e busca
       SELECT sku, loja, quantidade FROM estoque_lojas
       WHERE sku = ANY(skus_pagina) AND loja = ANY(nomes_efetivos)
    5. Monta {produtos: [{sku, nome, estoque: {loja_id: quantidade|None}}], lojas: [...], total}
    """

def atualizar_celula(sku: str, loja_id: int, quantidade: float, usuario: dict, ip: str, dispositivo: str) -> dict:
    """
    1. loja = lojas.buscar_por_id(loja_id)  -> loja.nome
    2. resultado_local = core.estoque.ajustar_absoluto(sku, loja.nome, quantidade,
                            "estoque_rapido", usuario["user_id"], usuario["nome"], ip, dispositivo)
       Se erro: return {"ok": False, "erro_local": resultado_local["erro"]}
    3. resultado_shopee = shopee.stock.sincronizar_estoque_shopee(sku, int(quantidade), loja_id)
    4. linha_atualizada = listar_grid(busca=sku, pagina=1, por_pagina=1)["produtos"][0]  # snapshot pós-write
    5. return {"ok": "error" not in resultado_shopee, "salvo_local": True,
               "erro_shopee": resultado_shopee.get("error"), "linha": linha_atualizada}
    """
```

Rotas em `routes/shopee.py`:
- `GET /api/shopee/estoque-rapido?busca=&pagina=&por_pagina=` → `listar_grid`.
- `PUT /api/shopee/estoque-rapido/celula` body `{sku, loja_id, quantidade}` → `atualizar_celula`. Requer permissão `produtos.editar` (mesmo padrão das rotas de estoque existentes).

## Frontend

Nova rota `web/src/app/estoque/rapido/page.tsx`, seguindo o mesmo estilo visual de `estoque/lojas/page.tsx` (tabela dark, paginação numérica já existente naquele arquivo, reusada tal e qual).

- Busca por SKU/nome no topo — reseta para página 1.
- Tabela: coluna fixa SKU + nome; 1 coluna por loja Shopee conectada (cabeçalho = nome da loja).
- Célula com anúncio: input numérico. `Enter` ou blur dispara `PUT /api/shopee/estoque-rapido/celula` (autosave, mesmo padrão de edição inline já usado no grid de `estoque/lojas`).
- Estados da célula durante/depois do save: "salvando..." → ✓ verde (sync Shopee ok) | ✗ vermelho com tooltip (`erro_shopee`, ex: token expirado) | erro vermelho pleno (nem o saldo local salvou).
- Ao receber resposta com `linha` atualizada, substitui todas as células daquele SKU na tabela local (cobre o caso de lojas vinculadas compartilhando saldo).
- Célula sem anúncio: cinza, texto "—", `disabled`.
- Novo item de menu "Estoque Rápido" na seção Estoque do menu lateral (`web/src/app/layout.tsx`), ao lado de "Lojas"/"Análise".
- `lib/api.ts`: novas funções `estoqueRapidoListar(params)` e `estoqueRapidoAtualizarCelula(sku, lojaId, quantidade)`.

## Erros e casos de borda

- Loja sem token Shopee válido (expirado): não aparece como coluna (já filtrado por `listar_lojas_shopee`, que exige `tem_token`). Se expirar *durante* uso da tela, `sincronizar_estoque_shopee` retorna `{"error": ...}` e a célula mostra ✗ com o erro — saldo local já foi salvo.
- SKU sem anúncio em nenhuma loja: não aparece na grade (a query já filtra por existência em `anuncios`).
- Quantidade negativa ou não numérica: validação no input (`type="number" min="0"`), espelhando o padrão de `EstoqueMultiLojaModal.tsx`.
- Duas colunas Shopee apontando pra mesma loja física vinculada: ambas mostram o mesmo valor; salvar uma reflete na outra via re-fetch da linha (ver decisão acima).

## Testes

- Backend: `hermes_agents/tests/test_shopee_estoque_rapido.py` — `listar_grid` (paginação, busca, célula `None` quando sem anúncio, resolução de loja vinculada) e `atualizar_celula` (sucesso local+Shopee, falha local não chama Shopee, falha Shopee com sucesso local reportando os dois estados separadamente). Segue o padrão de mocks já usado em `test_shopee_stock.py`.
- Frontend: smoke manual (rodar app, abrir `/estoque/rapido`, editar uma célula, confirmar autosave + feedback visual) — sem suite E2E dedicada nesta fase, mesmo padrão das outras telas de estoque no projeto.

## Fora de escopo

- Outros marketplaces além de Shopee.
- Edição de preço/outros campos de `produtos_loja`.
- Importação em massa via CSV/XLSX (cadastro de produto/anúncio já é feito em outras telas do Hermes).
- Migração/desligamento do sistema `ESTOQUE RAPIDO` original — fica de fora até a nova aba estar validada em uso real.
