# PDV — Gap Analysis para Produção

**Data:** 2026-07-21 | **Status:** Fase 1 funcional — 12 features implementadas, 24 gaps mapeados

---

## O que já existe

| # | Feature | Onde |
|---|---------|------|
| 1 | Carrinho multi-item c/ edit inline de qtd e preço | `web/src/app/pdv/page.tsx:219-236` |
| 2 | Busca por SKU/nome/ID com dropdown de resultados | `pdv.py:189-207`, `page.tsx:63-71` |
| 3 | 7 formas de pagamento + split (múltiplos por venda) | `page.tsx:7`, `pdv.py:258-260` |
| 4 | Abrir/fechar caixa com saldo | `pdv.py:151-177`, `page.tsx:118-136` |
| 5 | Sangria / suprimento | `pdv.py:240-244` |
| 6 | Turnos de operador (abrir/fechar) | `pdv.py:181-187` |
| 7 | Cancelamento de venda + registro de devolução | `pdv.py:209-221` |
| 8 | Histórico de vendas com filtros | `pdv.py:223-238`, `page.tsx:302-321` |
| 9 | Integração automática com fluxo de caixa | `entidades.py:369-386` |
| 10 | Atalhos de teclado (F2 busca, F4 desconto, F5 dinheiro, F6 PIX) | `page.tsx:45-61` |
| 11 | Schema NFC-e (tabela `pdv_nfce`) | `pdv.py:67-72` |
| 12 | Desconto total na venda | `page.tsx:252-256` |

---

## Estrutura atual

```
hermes_agents/
├── core/pdv.py              # 275 linhas — 10 tabelas, CRUD genérico, operações de caixa/venda
├── core/entidades.py         # ao_fechar_caixa_pdv() — integração com fin_fluxo_caixa
├── core/catalogo.py          # Índices para subqueries de preço/estoque do PDV
├── athena_bridge.py:1888     # 12 endpoints REST (Flask)
└── dashboard/pdv.html        # Snapshot renderizado

web/src/
├── app/pdv/page.tsx          # 321 linhas — 3 tabs (Venda, Caixa, Histórico)
├── app/layout.tsx            # Rota /pdv com permissão pdv:view
└── lib/api.ts:808            # evtFecharCaixaPDV() client
```

---

## Gap de produção — ordenado por criticidade

### Bloco 1 — CRÍTICO (loja física não roda sem)

| # | Gap | Descrição | Esforço | Arquivos afetados |
|---|-----|-----------|---------|-------------------|
| **1** | **Leitor de código de barras** | `buscar_produtos()` só consulta por `sku`, `descricao` e `id`. Precisa adicionar coluna `codigo_barras` em `catalogo_produtos` (ou usar campo existente do Bling) + adaptar query SQL + trigger Enter automático (leitor já emula teclado). | M | `pdv.py:189-207`, `catalogo.py` |
| **2** | **Impressão de cupom** | Sem impressora térmica não é PDV real. Precisa: template de cupom não fiscal (logo, itens, totais, formas pgto), comunicação ESC/POS via serial/USB, disparo pós-venda e no fechamento. Lib sugerida: `python-escpos`. | G | Novo `core/pdv_impressao.py`, `page.tsx` |
| **3** | **Cliente vinculado à venda** | Campo `cliente` é texto livre. Precisa: coluna `cliente_id INT REFERENCES cad_clientes(id)` em `pdv_vendas`, autocomplete de clientes no frontend, busca por nome/CPF/telefone. | M | `pdv.py:20,250`, `page.tsx:278` |
| **4** | **Fechamento com conferência detalhada** | Fechamento atual é `prompt("Saldo final?")`. Precisa: tela de conferência com quebra por forma de pagamento (cédulas, moedas, PIX recebido, cartão), campo `saldo_conferido` vs `saldo_calculado`, diferença automática, justificativa de quebra. | M | `pdv.py:154-177`, `page.tsx:126-136` (nova tab/subtab) |
| **5** | **Autenticação de operador** | `pdv_operadores.senha` nunca é verificado. Precisa: hash de senha (bcrypt), endpoint `POST /api/pdv/login`, JWT/session, middleware de verificação nas ações críticas (abrir/fechar caixa, cancelar venda, desconto > limite). | P | `pdv.py:46-49`, `athena_bridge.py:1888` |
| **6** | **Vinculação com loja** | `pdv_caixas` não tem `loja_id` no schema de `pdv.py` (só FK externa em `entidades.py`). Precisa: adicionar coluna, filtrar dashboard/caixas/vendas por loja, preparar multi-loja. | P | `pdv.py:9-14`, `pdv.py:263-275` |
| **7** | **Devolução parcial** | Só existe cancelamento total da venda. Precisa: endpoint `POST /api/pdv/venda/<id>/devolver-item`, estornar 1 item do carrinho, recalcular total, opção de estornar pagamento parcial. | M | `pdv.py:209-221`, `page.tsx` |

### Bloco 2 — IMPORTANTE (roda sem, mas é gambiarra)

| # | Gap | Descrição | Esforço | Arquivos afetados |
|---|-----|-----------|---------|-------------------|
| **8** | **TEF / integração cartão** | Pagamento "cartao_credito/debito" é manual (operador digita valor). Precisa: integração com adquirente (Stone/Rede/Getnet/Cielo) via API REST ou DLL nativa, captura de bandeira/parcelas/autorização automáticas. | G | `pdv.py:258-260`, novo módulo TEF |
| **9** | **Modo offline com sync** | 100% dependente do backend Flask. Precisa: IndexedDB local (Dexie.js), fila de vendas offline, detecção de conectividade, sync automático quando online, tratamento de conflitos (estoque). | GG | `page.tsx`, novo `web/src/lib/offline-sync.ts` |
| **10** | **Emissão NFC-e** | Schema `pdv_nfce` existe, zero código de emissão. Precisa: certificado digital A1, assinatura XML (xmldsig), envio SOAP SEFAZ, consulta status, cancelamento, inutilização, DANFE. Alternativa: API terceiro (TecnoSpeed, FocusNFe, Nuvem Fiscal). | GG | Novo `core/pdv_nfce.py`, `pdv.py:67-72` |
| **11** | **Desconto por item** | Só existe desconto no total da venda. Precisa: coluna `desconto` em `pdv_itens`, input de desconto por linha no carrinho, recálculo automático. | P | `pdv.py:22-27`, `page.tsx:219-236` |
| **12** | **Vendedor / comissão** | `pdv_vendas` não tem `vendedor_id`. Precisa: relacionar com `cad_vendedores`, cálculo de comissão no fechamento, relatório de comissão por período. | M | `pdv.py:15-21`, `cadastros.py` |
| **13** | **Pré-venda / orçamento** | Criar venda com `status = 'orcamento'`, converter em venda finalizada com 1 clique, prazo de validade, listagem de orçamentos pendentes. | M | `pdv.py:19,246-261`, `page.tsx` |
| **14** | **Senha em ações críticas** | Cancelar venda, desconto > X%, fechar caixa, sangria — tudo sem confirmação de senha. Precisa: modal de senha antes dessas ações, log de auditoria. | P | `page.tsx`, `pdv.py` |
| **15** | **Limite de desconto por operador** | Operador pode dar 100% de desconto. Precisa: coluna `desconto_maximo_percent` em `pdv_operadores`, validação no backend, override com senha de gerente. | P | `pdv.py:46-49,249` |
| **16** | **Transação atômica na venda** | `realizar_venda()` faz 3 inserts separados (venda, itens, pagamentos). Se o 2º falhar, fica venda órfã sem itens. Precisa: `BEGIN/COMMIT/ROLLBACK` com asyncpg transaction. | P | `pdv.py:246-261` |
| **17** | **Fechamento confere formas de pagamento** | `fechar_caixa()` compara `saldo_final` só com total de vendas, ignora que PIX e cartão não são dinheiro físico. Precisa: agrupar pagamentos por forma, calcular saldo esperado em espécie separado de eletrônico. | M | `pdv.py:154-177` |

### Bloco 3 — DESEJÁVEL (diferencial, não bloqueia)

| # | Gap | Descrição | Esforço | Arquivos afetados |
|---|-----|-----------|---------|-------------------|
| **18** | **Balança integrada** | Produtos por peso (KG). Ler porta serial da balança (protocolo comum: Toledo/Filizola), capturar peso estável, multiplicar por preço/kg, exibir no carrinho. | M | Novo módulo serial, `page.tsx` |
| **19** | **Tabela de preços** | Preço diferente por grupo de cliente (atacado, varejo, revenda, funcionário). Tabela `pdv_tabelas_preco` + lookup na venda. | M | `pdv.py`, `catalogo.py` |
| **20** | **Grade de produtos touch** | Grid visual com imagens dos produtos mais vendidos, categorias como abas, otimizado pra touch screen tablet (alvos grandes). | M | `page.tsx` (nova tab "Produtos") |
| **21** | **CPF na nota** | Campo CPF do consumidor na venda para NFC-e (obrigatório acima de R$ 200 em alguns estados). Validação de dígito, busca de cliente por CPF. | P | `pdv.py:20`, `page.tsx` |
| **22** | **Relatório de fechamento** | PDF impresso/visual do resumo: totais por forma de pgto, sangrias, suprimentos, quebra, vendas do período, ticket médio. | M | Novo `core/pdv_relatorios.py` |
| **23** | **Múltiplos caixas simultâneos** | `GET /api/pdv/dashboard` busca "algum caixa aberto" (genérico). Precisa: filtrar por loja + terminal/operador, permitir N caixas abertos ao mesmo tempo. | P | `pdv.py:263-275`, `page.tsx:34-36` |
| **24** | **Histórico detalhado** | Ver itens da venda no histórico + pagamentos + reimprimir cupom. Hoje só mostra cabeçalho da venda. | P | `page.tsx:302-321` |
| **25** | **Impressão etiqueta gôndola** | Imprimir etiqueta de preço com código de barras, nome e preço (formato PIMACO ou similar). | M | Novo endpoint + template |
| **26** | **Consulta rápida de preço** | Digitar código e ver preço/estoque sem adicionar ao carrinho (modo consulta, tipo F1). | P | `page.tsx` |
| **27** | **Auditoria de ações PDV** | Log de toda ação: abertura, fechamento, cancelamento, desconto, sangria. Tabela `pdv_auditoria` + tela de consulta. | M | `pdv.py`, `seguranca.py` |

---

## Problemas estruturais do backend atual (`pdv.py` — 275 linhas)

| # | Problema | Local | Impacto |
|---|----------|-------|---------|
| 1 | `realizar_venda()` sem transação atômica | `:246-261` | Venda pode ficar sem itens se um insert falhar |
| 2 | Zero validação de permissão/senha | Todo o arquivo | Qualquer request pode fechar caixa ou cancelar venda |
| 3 | `fechar_caixa()` não agrupa por forma de pagamento | `:154-177` | Saldo esperado mistura dinheiro com PIX/cartão |
| 4 | `buscar_produtos()` não consulta `codigo_barras` | `:189-207` | Leitor de código de barras inútil |
| 5 | `_ensure_tables()` sem `loja_id` em `pdv_caixas` | `:9-14` | Multi-loja impossível |
| 6 | Decimal não convertido pra float em `_list()` (só preco/estoque) | `:87-88` | JSON serialization quebra em campos decimal |
| 7 | `abrir_turno()` referencia campo `operador` que não existe na tabela | `:182-183` | Bug — `pdv_turnos` não tem coluna `operador` |
| 8 | `_list()` converte `preco`/`estoque_atual` pra float mas são campos do catálogo, não genéricos | `:87-88` | Conversão vaza pra outras tabelas indevidamente |

---

## Plano de ataque (menor esforço → maior impacto)

### Fase 1 — Segurança e leitor (4-6h)
1. Auth operador com senha (hash bcrypt + endpoint login)
2. Adicionar `codigo_barras` na busca + tratar Enter do leitor
3. Limite de desconto por operador
4. Senha em ações críticas (cancelar, fechar, sangria)

### Fase 2 — Caixa e cliente (6-8h)
5. Tela de conferência no fechamento (quebra por forma, cédulas)
6. Cliente vinculado com autocomplete
7. Devolução parcial de itens
8. Transação atômica na venda
9. Fechamento separa dinheiro de eletrônico

### Fase 3 — Impressão e descontos (6-8h)
10. Desconto por item no carrinho
11. Impressão de cupom não fiscal (ESC/POS)
12. Relatório de fechamento impresso
13. Pré-venda / orçamento

### Fase 4 — Fiscal e TEF (3-5 dias)
14. Emissão NFC-e (certificado + SEFAZ)
15. TEF / integração cartão
16. CPF na nota

### Fase 5 — Resiliência e UX (5-7 dias)
17. Modo offline com sync
18. Vendedor / comissão
19. Grade de produtos touch
20. Histórico detalhado + reimpressão
21. Tabela de preços
22. Balança integrada
23. Múltiplos caixas simultâneos
24. Auditoria de ações

---

## Resumo

| Bloco | Gaps | Esforço estimado |
|-------|------|-----------------|
| Crítico (7) | Leitor, impressão, cliente, conferência, auth, loja, devolução parcial | 20-25h |
| Importante (10) | TEF, offline, NFC-e, desconto item, vendedor, pré-venda, senha, limite, transação, fechamento | 40-50h |
| Desejável (8) | Balança, tabela preço, touch, CPF, relatório, multi-caixa, histórico, etiqueta, consulta, auditoria | 25-30h |
| **Total (25 gaps)** | | **85-105h** |
