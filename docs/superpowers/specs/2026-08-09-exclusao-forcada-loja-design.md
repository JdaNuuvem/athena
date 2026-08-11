# Exclusão Forçada de Loja — Design

**Data:** 2026-08-09
**Status:** Aprovado para planejamento

## Contexto

`DELETE /api/lojas/manage/<id>` (`core/lojas.py::deletar()`) bloqueia hoje com HTTP 409 quando existe dado vinculado à loja em qualquer tabela com FK real (`estoque_lojas`, `vendas_pedidos`, `pdv_caixas`, `fin_cofre`, etc) — comportamento intencional, corrigido de propósito num commit anterior (`f2e5f33`) pra não mascarar o erro como 404 genérico. A mensagem de erro já orienta "Desative-a em vez de excluir", e o fluxo de desativação (`PUT /api/lojas/manage/<id>` com `{"status": "inativa"}`) já existe e funciona.

Usuário tem um caso real onde precisa apagar de vez uma loja online com histórico vinculado (estoque, vendas, caixas) que ele confirma ser dado errado/lixo (não é venda real que precise ser preservada) — e confirma que pode acontecer de novo no futuro (loja de teste/erro sendo criada e precisando ser removida por completo). Não é bug fix: o bloqueio atual está correto e deve continuar sendo o caminho padrão. Isto é uma funcionalidade nova, deliberadamente perigosa, que precisa de múltiplas camadas de proteção porque é irreversível (não existe soft-delete na tabela `lojas` — é `DELETE` físico).

**Confirmado com o usuário:** a loja em questão não emitiu nenhuma nota fiscal (NF-e) — não há a complicação de retenção fiscal obrigatória (Receita Federal exige guarda de documento fiscal por anos) se aplicando a este caso. Essa investigação não muda o desenho da feature (que segue genérica pra qualquer loja), mas é o motivo de a feature não incluir nenhuma trava especial de "bloquear se houver nota fiscal emitida" — fica como observação para o operador avaliar caso a caso antes de confirmar, não como validação automática do sistema.

## Decisões (fechadas com o usuário durante o brainstorming)

- **Escopo:** funcionalidade permanente no admin (não é script pontual) — pode ser necessária de novo no futuro.
- **Pré-requisito:** só permite forçar exclusão de loja já **inativa** (`status='inativa'`). Não dá pra forçar em loja ativa — reforça que desativar continua sendo o primeiro passo sempre.
- **Permissão:** nova, `lojas.excluir_forcado`, só Admin por padrão (mesmo padrão de `lojas.ver_todas`, que também é um insert avulso fora do produto cartesiano `MODULOS x ACOES_PADRAO` em `core/rbac.py`).
- **Confirmação:** usuário precisa digitar o nome exato da loja antes do botão de exclusão real habilitar (mesmo padrão do GitHub pra apagar repositório).
- **Prévia obrigatória:** antes de qualquer exclusão real, endpoint de dry-run mostra quantas linhas seriam apagadas por tabela.
- **Atomicidade:** toda a cascata roda numa única transação — sucesso total ou rollback total, nunca cascata parcial.
- **Auditoria:** reaproveita `auditar_exclusao` (`core/seguranca.py`) já usado na exclusão normal, com o payload enriquecido pela contagem de linhas apagadas por tabela.

## Escopo de tabelas e ordem da cascata

**Revisado pós-aprovação:** a varredura em nível de implementação (lendo o `CREATE TABLE` real de cada módulo, não só o que a exclusão comum hoje bloqueia) achou uma árvore bem mais profunda do que a listada na primeira aprovação — faltavam 6 tabelas `pdv_*`, 2 `vendas_*`, as 5 `producao_*` e o cross-reference `crm_negociacoes`. Essa varredura também achou que `compras_pedidos` e `fin_contas_pagar` são dado **centralizado** (o `loja_id` delas é só um valor default de "loja principal", não um escopo real por loja — ver `core/compras.py:38-40`) — apagar por `loja_id` nessas duas destruiria registro da empresa inteira se a loja alvo calhar de ser a principal. Reapresentado ao usuário como duas perguntas extras; decisões abaixo.

### Com FK real hoje (o que hoje dispara o 409)

Ordem respeitando dependência (filhas antes das mães), com a coluna/subquery exata usada no `WHERE`:

1. `pdv_devolucoes` — `venda_id IN (SELECT id FROM pdv_vendas WHERE caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = $1))`
2. `pdv_pagamentos` — mesma subquery de `pdv_devolucoes`
3. `pdv_itens` — mesma subquery
4. `pdv_turnos` — `caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id = $1)`
5. `pdv_caixa_conferencia` — mesma subquery de `pdv_turnos`
6. `pdv_caixa_contagem` — mesma subquery
7. `pdv_suprimentos` — mesma subquery
8. `pdv_sangrias` — mesma subquery
9. `pdv_vendas` — mesma subquery
10. `pdv_caixas` — `loja_id = $1`
11. `vendas_pagamentos` — `pedido_id IN (SELECT id FROM vendas_pedidos WHERE loja_id = $1)`
12. `vendas_historico_status` — mesma subquery de `vendas_pagamentos`
13. `vendas_itens` — mesma subquery
14. `vendas_pedidos` — `loja_id = $1` (FK `NOT VALID`, ver `core/vendas.py:36`)
15. `fin_cofre_movimentos` — `cofre_id IN (SELECT id FROM fin_cofre WHERE loja_id = $1)`
16. `fin_cofre` — `loja_id = $1`
17. `estoque_lojas`, `estoque_movimentacoes`, `estoque_contagens` — `loja_id = $1` (coluna dual-write aditiva, nullable)
18. `estoque_transferencias` — `loja_origem_id = $1 OR loja_destino_id = $1`
19. `producao_bom`, `producao_apontamentos`, `producao_consumo`, `producao_perdas`, `producao_custos` — `op_id IN (SELECT id FROM producao_ops WHERE loja_id = $1)`
20. `producao_ops` — `loja_id = $1` (FK adicionada via `core/entidades.py`, não no `CREATE TABLE` original)
21. `chat_conversas` — `loja_id = $1` (filhas `chat_participantes`/`chat_mensagens`/`chat_leituras` já têm `ON DELETE CASCADE` — não precisam de `DELETE` manual)
22. `shopee_estoque_snapshot` — `loja_id = $1`
23. `loja_integracoes` — `loja_id = $1` (`loja_id INT NOT NULL REFERENCES lojas(id) ON DELETE CASCADE`, ver `core/lojas_integracoes.py:28-36`; tem `credenciais JSONB`)
24. `loja_responsaveis` — `loja_id = $1` (mesmo padrão de FK `ON DELETE CASCADE`, ver `core/lojas_responsaveis.py:22-30`)
25. `usuario_lojas` — `loja_id = $1` (mesmo padrão de FK `ON DELETE CASCADE`, ver `core/usuario_lojas.py:18-24`)

**Correção pós-review final:** os 3 itens acima (`loja_integracoes`, `loja_responsaveis`, `usuario_lojas`) já eram apagados hoje pelo `ON DELETE CASCADE` no `DELETE FROM lojas` final, mas ficavam ausentes da prévia de impacto e do payload de auditoria — achado do review final da branch, corrigido pra a prévia obrigatória ser honesta sobre tudo que é destruído, sem mudar o que de fato é apagado.

**Não é apagado, é desvinculado:** `crm_negociacoes.pedido_id` (nullable, FK → `vendas_pedidos.id`) recebe `UPDATE crm_negociacoes SET pedido_id = NULL WHERE pedido_id IN (SELECT id FROM vendas_pedidos WHERE loja_id = $1)` **antes** do passo 14 — a negociação em si nunca é apagada, só perde a referência ao pedido.

### Sem FK hoje, mas referenciam `loja_id` (ficam órfãs numa exclusão comum — precisam ser limpas manualmente pra "apagar o histórico mesmo" ficar completo)

- `fiscal_nfe_itens`, `fiscal_impostos_nota` — `nota_id IN (SELECT id FROM fiscal_notas_fiscais WHERE loja_id = $1)`
- `fiscal_notas_fiscais` — `loja_id = $1`
- `fin_contas_receber` — `loja_id = $1`
- `autom_regras_preco` — `loja_id = $1`
- `vendas` — `loja_id = $1` (tabela legada, `loja_id INTEGER` simples sem FK, ver `hermes_agents/sql/schema.sql:138-152` e `hermes_agents/deploy_to_hermes.py:390-404`; sem tabelas filhas)

Todas via `DELETE FROM <tabela> WHERE <where acima>` dentro da mesma transação, mesmo sem FK forçando isso hoje.

**Correção pós-review final:** `vendas` faltava no escopo original — achado do review final da branch. Reapresentado ao usuário (controller), que decidiu explicitamente incluir `vendas` na cascata real de exclusão forçada.

**Decisão do usuário sobre `fiscal_notas_fiscais`:** ao contrário da recomendação inicial ("bloquear se a loja emitiu nota fiscal"), o usuário escolheu **"só avisa, deixa passar"** — a tela de prévia mostra a contagem de `fiscal_notas_fiscais` igual a qualquer outra tabela do escopo, sem nenhum bloqueio automático adicional. Cabe ao operador avaliar antes de confirmar.

### Removido do escopo (decisão do usuário — dado centralizado, não por loja)

`compras_pedidos` (+ filhas `compras_itens`, `compras_recebimentos`, `compras_notas_entrada`) e `fin_contas_pagar` **não entram** na cascata: seu `loja_id` é um valor default de "loja principal" (`LOJA_PRINCIPAL_ID`), não um escopo real por loja — apagar por `loja_id` nessas tabelas apagaria compras/contas a pagar da empresa inteira sempre que a loja-alvo for a principal. Usuário escolheu "Remove do escopo (Recomendado)" quando essa diferença foi levantada. Ficam de fora tanto do dry-run de impacto quanto da exclusão real.

### Referências que NÃO são apagadas — são desvinculadas

Se outra loja tiver `loja_vinculada_id` ou `loja_matriz_id` apontando para a loja sendo excluída, a transação faz `UPDATE lojas SET loja_vinculada_id = NULL WHERE loja_vinculada_id = $1` (e o mesmo para `loja_matriz_id`) **antes** do `DELETE FROM lojas` — nunca apaga a loja vinculadora.

### Fora de escopo desta feature

- `fiscal_notas_fiscais`, `fin_contas_receber` não terem FK real declarada para `lojas(id)` é uma lacuna de proteção do sistema como um todo (uma exclusão *comum* bem-sucedida hoje já deixaria essas tabelas órfãs silenciosamente, sem erro nenhum). Corrigir isso adicionando a FK de verdade é melhoria separada, documentada em `docs/DEMANDAS.md`, não faz parte desta feature.
- Colunas texto legadas (`estoque_lojas.loja`, `estoque_saldos.loja`, etc — dual-write da era "loja por nome") não são tocadas por esta feature. São resolvidas por nome, não por FK, e o dual-write pra `loja_id` já é decisão de outra frente do projeto.
- Exclusão em lote (múltiplas lojas de uma vez) não faz parte deste escopo.
- Backup/export automático dos dados antes de apagar não faz parte deste escopo (usuário confirmou que o dado em questão é lixo/teste, não histórico que precise ser preservado em algum lugar).
- `compras_pedidos`/`fin_contas_pagar` ficarem órfãos de `loja_id` numa loja excluída (via exclusão comum ou futura) é uma lacuna pré-existente do sistema, documentada em `docs/DEMANDAS.md` — não é resolvida por esta feature porque a coluna não representa escopo real.

## Backend

**Nota:** o pseudocódigo original desta seção (blueprint `lojas_manage_bp`, `obter()` retornando `{"erro":...}`) não batia com o código real (`routes/lojas_manage.py` usa `lojas_bp`; `core/lojas.py::obter()` retorna `None`, não um dict de erro, quando a loja não existe). O código exato — já corrigido contra o arquivo real — está no plano de implementação, não duplicado aqui: `docs/superpowers/plans/2026-08-09-exclusao-forcada-loja.md`.

Resumo do desenho (sem código, ver plano pra exato):

- **RBAC (`core/rbac.py`):** novo insert avulso `lojas.excluir_forcado` em `_ensure_tables()`, mesmo padrão de `lojas.ver_todas` — seed inicial (`if count == 0`) **e** fix-up idempotente pra bancos já seedados, ambos concedendo a permissão automaticamente ao role Admin.
- **`core/lojas.py`:** uma constante `_CASCATA_EXCLUSAO_FORCADA` (lista ordenada de `(tabela, where_clause)`, filhas antes de mães) reaproveitada por `impacto_exclusao(id_loja)` (só leitura, `SELECT COUNT(*)` por tabela) e `excluir_forcado(id_loja, confirmar_nome)` (transação: valida loja/status/nome, desvincula `crm_negociacoes.pedido_id`, apaga cascata, desvincula `loja_vinculada_id`/`loja_matriz_id` de outras lojas, apaga a loja).
- **Rotas (`routes/lojas_manage.py`):** `GET /api/lojas/manage/<id>/impacto-exclusao` e `POST /api/lojas/manage/<id>/excluir-forcado`, ambas gated só por `@requer_permissao("lojas.excluir_forcado")` (sem `@requer_acesso_loja`), seguindo o estilo de closure `_go()` já usado pelas outras rotas deste blueprint.

Nenhuma das duas rotas usa `@requer_acesso_loja` — exclusão forçada é ação administrativa central (só Admin tem a permissão `lojas.excluir_forcado` de qualquer forma), a restrição por `usuario_lojas` não se aplica aqui.

## Frontend (`web/src/app/lojas/page.tsx`)

- Botão "Excluir" continua chamando `api.lojasDeletar(id)` normalmente primeiro — comportamento hoje intocado.
- Quando a resposta for 409 **e** a loja estiver `status === "inativa"` **e** o usuário tiver a permissão `lojas.excluir_forcado` (via `useAuth().hasPermission`): mostra opção adicional "Excluir mesmo assim" junto da mensagem de erro (não substitui a mensagem, complementa).
- Se a loja ainda estiver ativa, essa opção não aparece — só a mensagem padrão orientando desativar primeiro.
- Clique em "Excluir mesmo assim" abre um modal:
  - Busca `api.lojasImpactoExclusao(id)` ao abrir, mostra loading enquanto carrega.
  - Lista a contagem por tabela (`impacto`) e o total.
  - Campo de texto pedindo pra digitar o nome exato da loja.
  - Botão "Excluir permanentemente" (vermelho, `disabled` até o texto digitado bater exatamente com `loja.nome`).
  - Ao confirmar, chama `api.lojasExcluirForcado(id, nomeDigitado)`. Sucesso: fecha modal, remove a loja da lista local, mostra toast/mensagem de confirmação com o total de linhas apagadas. Erro: mostra a mensagem de erro dentro do próprio modal, não fecha.

### `web/src/lib/api.ts`

Duas funções novas, mesmo padrão de `lojasDeletar`:

```typescript
export interface ImpactoExclusaoLoja {
  loja: { id: number; nome: string; [key: string]: unknown };
  impacto: Record<string, number>;
  total_linhas: number;
}

export async function lojasImpactoExclusao(id: number): Promise<ImpactoExclusaoLoja & { erro?: string }> {
  return request<ImpactoExclusaoLoja & { erro?: string }>(`/api/lojas/manage/${id}/impacto-exclusao`);
}

export async function lojasExcluirForcado(id: number, confirmarNome: string): Promise<{ ok?: boolean; apagado?: Record<string, number>; erro?: string }> {
  return request(`/api/lojas/manage/${id}/excluir-forcado`, {
    method: "POST",
    body: JSON.stringify({ confirmar_nome: confirmarNome }),
  });
}
```

## Testes

- **Backend — `impacto_exclusao`:** loja inexistente retorna erro; loja ativa retorna erro pedindo desativação; loja inativa sem dado vinculado retorna todas as contagens zeradas; loja inativa com dado retorna contagem correta por tabela (mockar `db.fetchval` por tabela).
- **Backend — `excluir_forcado`:** loja inexistente retorna erro sem tocar em nada; loja ativa retorna erro sem tocar em nada; `confirmar_nome` errado (case-sensitive, com espaço extra, etc) retorna erro sem apagar nada; sucesso apaga na ordem certa e retorna contagem; falha no meio da transação faz rollback completo (nenhuma tabela fica parcialmente limpa — testar simulando exceção no meio da sequência de deletes); loja vinculada por `loja_vinculada_id`/`loja_matriz_id` de outra loja tem essas colunas nulificadas, a loja vinculadora não é apagada.
- **Backend — rotas:** RBAC nega sem a permissão `lojas.excluir_forcado` (granular, não só bypass de token master — mesmo padrão já estabelecido nas rotas de divergência de saldo hoje); RBAC libera com a permissão; auditoria é chamada com o payload de contagens no sucesso.
- **Frontend:** manual (sem backend local disponível) — confirmar que "Excluir mesmo assim" só aparece pra loja inativa + permissão, que o botão de confirmação fica desabilitado até o nome bater exatamente, que erro do backend aparece dentro do modal sem fechá-lo.
