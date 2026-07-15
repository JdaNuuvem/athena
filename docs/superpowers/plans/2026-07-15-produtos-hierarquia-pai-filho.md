# Plano curto — Hierarquia pai/filho na aba /produtos

Spec completo: [2026-07-15-produtos-hierarquia-pai-filho-design.md](../specs/2026-07-15-produtos-hierarquia-pai-filho-design.md)

## Ordem de implementação

1. **Banco (`hermes_agents/core/catalogo.py`)**
   Adicionar em `_ensure_tables()`: `ALTER TABLE catalogo_produtos ADD COLUMN IF NOT EXISTS id_bling BIGINT`,
   `sku_pai VARCHAR(50)`, `atributo VARCHAR(200)` + índice em `sku_pai`.

2. **Sync (`hermes_agents/bling_erp.py::sincronizar_produtos()`)**
   - Passo 1 (existente, estendido): gravar `id_bling` no upsert de `catalogo_produtos`; manter mapa
     `{id_bling: sku}` em memória durante a iteração das páginas.
   - Passo 2 (novo): após percorrer todas as páginas, resolver `idProdutoPai` → `sku_pai` usando o mapa e
     fazer `UPDATE catalogo_produtos SET sku_pai = ...`.
   - Passo 3 (novo): para produtos pai com `formato == "V"`, chamar `GET /produtos/{id}` no Bling, extrair
     `variacoes[].variacao.nome` e gravar em `atributo` de cada filho. Retry com backoff em 429 (máx. 2
     tentativas extras); falha isolada só entra em `erros`, não interrompe o resto.

3. **Backend — detalhe do produto (`hermes_agents/athena_bridge.py::detalhe_produto`)**
   Trocar a query de `fichas_tecnicas` para `catalogo_produtos` (resolve a inconsistência com a listagem) e
   adicionar `variacoes: [{sku, nome, valor, atributo}]` (`WHERE sku_pai = <sku>`).

4. **Backend — listagem (`hermes_agents/athena_bridge.py::listar_produtos`)**
   Adicionar `WHERE c.sku_pai IS NULL`; trocar `margem_pct/receita_30d/vendidos_30d` por `valor` (de
   `anuncios.preco WHERE marketplace='bling'`) e `total_variacoes` (`COUNT(*)` dos filhos).

5. **Tipos (`web/src/lib/types/domain.ts`)**
   Atualizar `Product`: remover `margem_pct/receita_30d/vendidos_30d/estoque_lojas/total_lojas`, adicionar
   `valor: number` e `total_variacoes: number`.

6. **Frontend — lista (`web/src/app/produtos/page.tsx`)**
   Tabela com só `SKU / Nome / Valor` + badge "N variações" quando `total_variacoes > 0`.

7. **Frontend — aba Variações (`web/src/app/produtos/[sku]/_components/VariacoesTab.tsx`)**
   Remover mock. Receber `variacoes` real via prop (de `client.tsx`, que já chama `detalheProduto`). Tabela:
   SKU/Nome/Preço. Grid de atributos: agrupar `atributo` (`"Nome:Valor"`) distintos entre os filhos; se nenhum
   filho tiver `atributo`, não mostrar o grid. Sem filhos: mensagem simples, sem tabela vazia.

8. **Deploy**
   Commit + push + redeploy manual no Coolify (sem auto-deploy configurado) + teste do sync em produção.

## Fora deste plano
Sync automático/agendado e edição local com envio pro Bling — specs separados, conforme já registrado no
spec de hoje.
