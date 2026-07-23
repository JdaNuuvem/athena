# ATHENA — Auditoria Completa de Módulos

**Data:** 2026-07-22 | **338 endpoints REST** | **31 páginas frontend** | **24 módulos backend**

---

## 🔴 CRÍTICO — Segurança

| # | Problema | Local | Impacto |
|---|----------|-------|---------|
| 1 | **297/338 endpoints (88%) sem autenticação** — RBAC existe mas não está ligado | `athena_bridge.py` — só PDV + KPI têm `_autenticado()` | Qualquer pessoa na rede acessa dados financeiros, clientes, estoque, RH |
| 2 | **Token master hardcoded** `athena-token-123456789` em 3 locais | `athena_bridge.py:18`, `rbac.py:219` | Backdoor de admin total |
| 3 | **4 senhas hardcoded** no source (admin, joao, maria, pedro) | `athena_bridge.py:172-175`, `rbac.py:81-84` | Seed data com senhas conhecidas |
| 4 | **Credenciais do Coolify expostas** no repo | `AGENTS.md` (raiz) | Acesso ao servidor de produção |

**Ação:** Ligar `_autenticado()` em todos os endpoints, remover fallback do token master, usar env vars pras senhas de seed.

---

## 🟠 ALTO — Erros silenciosos + Integridade

| # | Problema | Arquivos |
|---|----------|----------|
| 5 | **116 bare `except:`** — erros engolidos sem log | 15+ arquivos, principalmente `relatorios.py` (22x), `pdv.py` (10x), `catalogo.py` (8x) |
| 6 | **11 FKs sem constraint** — dados órfãos possíveis | `sql/schema.sql`, `create_tables_fase2.sql`, `create_tables_fase3.sql` |
| 7 | Relatórios retornam `{"total":0}` em erro de DB — silencioso, parece dado real | `core/relatorios.py` (22 funções) |

**Ação:** Substituir `except:` por `except Exception: log(...)`, adicionar FKs via ALTER TABLE.

---

## 🟡 MÉDIO — Módulos com gaps funcionais

### Backend

| Módulo | Linhas | Status | Gap principal |
|--------|--------|--------|---------------|
| **automações** | 119 | INERTE | Tabelas existem, **zero execução**: sem dispatcher de webhooks, sem worker de filas, sem scheduler, sem runner de bots |
| **SLA (atendimento)** | 150 | PARCIAL | Regras de SLA definidas mas **nunca aplicadas** — `criar_ticket` carrega SLA e descarta |
| **PDV** | 551 | FUNCIONAL | `buscar_clientes` com ILIKE em string crua (SQLi menor), `login_operador`/`verificar_operador` com ~40 linhas duplicadas |
| **estoque** | 294 | FUNCIONAL | SQL injection via `_where_loja` com interpolação de string, `ratear` referencia colunas que não batem com schema |
| **produção** | 155 | FUNCIONAL | Sem BOM template (só por OP), sem inspeção de qualidade, `finalizar_op` engole erro do `entidades` |
| **RH** | 434 | FUNCIONAL | Bug seed data: `(3,4)` em `rh_funcionario_beneficio`, sem cálculo IRRF/INSS, sem fechamento de folha |
| **documentos** | 104 | FUNCIONAL | Sem validação de tipo/tamanho, `download()` carrega arquivo inteiro em RAM (OOM), sem S3 |
| **CRM** | 256 | FUNCIONAL | `funil()` sem filtro de data (all-time), `importar_contatos_bling` duplica se email blank |
| **entidades** | 506 | FUNCIONAL | 35 ALTER TABLE por startup, sem rollback em hooks parciais, `vincular_todos_clientes` LIMIT 1000 |
| **config** | 148 | FUNCIONAL | API keys em plaintext no DB + arquivo, sem validação |
| **memory** | 308 | FUNCIONAL | Coluna `embedding FLOAT[]` existe mas não usada — busca é keyword ILIKE puro |
| **catalogo** | 210 | FUNCIONAL | Sem `delete` de produtos, migração de 3 tabelas legadas sem dedup |
| **compras** | 137 | FUNCIONAL | Fornecedor duplicado (`compras_fornecedores` vs `cad_fornecedores`), dashboard sem filtro de data |
| **vendas** | 378 | FUNCIONAL | Sync é N+1 (3 retries por pedido), `criar_pedido` sem transação, MAX_PAGINAS=50 sem continuação |
| **fiscal** | 627 | FUNCIONAL | Bling 50-página sem auto-continuação, `_mapear_nfe_detalhe` usa chaves fallback |

### Frontend

| Página | Status | Gap |
|--------|--------|-----|
| **BI** (4 sub-páginas) | PARCIAL | Importa `./types` mas `bi/types.ts` **não existe** (broken build). **Mock data hardcoded**: R$ 287k receita, 32.5% margem — fallback quando API falha |
| **Fiscal** | PARCIAL | Importa `./types` mas `fiscal/types.ts` **não existe** (broken build) |
| **Atendimento** | PARCIAL | Link para `/atendimento/chat` mas **diretório não existe** |
| **Dashboard** | PARCIAL | `alertas: []` hardcoded, nunca populado |
| **PDV** | FUNCIONAL | 691 linhas num arquivo só, hint `"Operador padrao: Admin / admin"` exposto |
| **Config** | INEXISTENTE | Diretório `/config` não existe |
| **Workflows** | DEV-ONLY | 7 workflows hardcoded como constantes, não puxa da API |
| **Automacoes** | CASCATA | Página funcional mas backend é inerte — CRUD sem executor |
| **Sub-páginas template** | FUNCIONAL | ~20 sub-páginas usam padrão genérico de tabela+modal (compras/notas, crm/leads, producao/ops, automacoes/filas, etc.) — funcional mas sem UI específica |

---

## 🟢 FUNCIONAL — Módulos OK

| Módulo | Backend | Frontend | Notas |
|--------|---------|----------|-------|
| Dashboard | OK | OK (sem alertas) | KPIs, gráfico de vendas, agentes ativos |
| Cadastros | OK | OK | 6 tabs (empresas, clientes, fornecedores, transportadoras, vendedores) |
| Produtos | OK | OK | 8 tabs no detalhe, Bling sync, hierarquia pai/filho |
| Estoque | OK | OK | Multidepósito, rateio, edição inline |
| Vendas | OK | OK | Dashboard, 9 tabs de status, expansão de detalhe |
| Financeiro | OK | OK | 8 tabs, DRE, fluxo caixa, boletos, PIX |
| CRM | OK | OK | Funil, pipeline, leads, contatos, propostas, contratos |
| Produção | OK | OK | OPs, BOM, máquinas, apontamentos, custos |
| RH | OK | OK | Funcionários, ponto, férias, folha, benefícios |
| Documentos | OK | OK | Upload drag-drop, preview, vínculo com entidades |
| Relatórios | OK | OK (19 sub-páginas) | Vendas, lucro, DRE, fluxo caixa, aging, previsão, etc. |
| Agentes | OK | OK | 14 agentes, chat por agente |
| Bling | OK | OK (módulo mais completo) | OAuth2, produtos, pedidos, NF-e, contatos, webhooks |
| Shopee | OK | OK | OAuth2 multiloja, sync produtos/estoque, config |
| Hermes (Chat) | OK | OK | Chat IA com memória, roteamento entre agentes |
| Segurança | OK | OK | RBAC, auditoria, logs, histórico |
| Lojas | OK | OK | CRUD, Bling sync, seletor no sidebar |

---

## 📊 Resumo por criticidade

| Nível | Itens | Esforço estimado |
|-------|-------|-----------------|
| 🔴 Crítico | Auth global, tokens hardcoded, credenciais expostas | 4-6h |
| 🟠 Alto | Erros silenciosos, FKs faltando | 3-4h |
| 🟡 Médio | Módulos inertes (automações, SLA), SQLi leves, bugs de seed | 8-12h |
| 🟢 Baixo | Refinamentos (BI mock data, split de arquivos, UI específica) | 10-15h |
| **Total** | | **25-37h** |

---

## 🎯 Ordem de ataque recomendada

1. **🔴 Auth global** — ligar `_autenticado()` em massa, remover token master hardcoded
2. **🔴 Remover senhas hardcoded** — `AGENTS.md`, seed data do rbac
3. **🟠 Erros silenciosos** — substituir bare `except:` por `except Exception: log(...)`
4. **🟡 Automações** — desbloquear módulo (webhook dispatcher, queue worker)
5. **🟡 Frontend broken** — criar `bi/types.ts`, `fiscal/types.ts`, `/atendimento/chat`
6. **🟢 Polimento** — split `pdv/page.tsx` (691 linhas), BI mock data, templates CRUD
