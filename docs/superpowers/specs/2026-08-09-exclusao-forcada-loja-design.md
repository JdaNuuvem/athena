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

### Com FK real hoje (o que hoje dispara o 409)

Ordem respeitando dependência (filhas antes das mães):

1. `pdv_pagamentos`, `pdv_itens` (FK → `pdv_vendas.id`)
2. `pdv_vendas` (FK → `pdv_caixas.id`)
3. `pdv_caixas` (FK → `lojas.id`)
4. `vendas_itens` (FK → `vendas_pedidos.id`)
5. `vendas_pedidos` (FK → `lojas.id`)
6. `fin_cofre_movimentos` (FK → `fin_cofre.id`)
7. `fin_cofre` (FK → `lojas.id`)
8. `estoque_lojas`, `estoque_movimentacoes`, `estoque_transferencias` (`loja_origem_id` e `loja_destino_id`), `estoque_contagens` (FK → `lojas.id`)
9. `producao_ops`, `chat_conversas`, `shopee_estoque_snapshot` (FK → `lojas.id`)

### Sem FK hoje, mas referenciam `loja_id` (ficam órfãs numa exclusão comum — precisam ser limpas manualmente pra "apagar o histórico mesmo" ficar completo)

- `fin_contas_receber`, `fin_contas_pagar`, `compras_pedidos`, `autom_regras_preco`, `fiscal_notas_fiscais`

Todas via `DELETE FROM <tabela> WHERE loja_id = $1` dentro da mesma transação, mesmo sem FK forçando isso hoje.

### Referências que NÃO são apagadas — são desvinculadas

Se outra loja tiver `loja_vinculada_id` ou `loja_matriz_id` apontando para a loja sendo excluída, a transação faz `UPDATE lojas SET loja_vinculada_id = NULL WHERE loja_vinculada_id = $1` (e o mesmo para `loja_matriz_id`) **antes** do `DELETE FROM lojas` — nunca apaga a loja vinculadora.

### Fora de escopo desta feature

- `fiscal_notas_fiscais`, `fin_contas_receber`, `fin_contas_pagar`, `compras_pedidos` não terem FK real declarada para `lojas(id)` é uma lacuna de proteção do sistema como um todo (uma exclusão *comum* bem-sucedida hoje já deixaria essas tabelas órfãs silenciosamente, sem erro nenhum). Corrigir isso adicionando a FK de verdade é melhoria separada, documentada em `docs/DEMANDAS.md`, não faz parte desta feature.
- Colunas texto legadas (`estoque_lojas.loja`, `estoque_saldos.loja`, etc — dual-write da era "loja por nome") não são tocadas por esta feature. São resolvidas por nome, não por FK, e o dual-write pra `loja_id` já é decisão de outra frente do projeto.
- Exclusão em lote (múltiplas lojas de uma vez) não faz parte deste escopo.
- Backup/export automático dos dados antes de apagar não faz parte deste escopo (usuário confirmou que o dado em questão é lixo/teste, não histórico que precise ser preservado em algum lugar).

## Backend

### RBAC (`core/rbac.py`)

Novo insert avulso em `_ensure_tables()`, mesmo padrão de `lojas.ver_todas` (linha 176/203-204):

```python
await db.execute("INSERT INTO rbac_permissoes (codigo,descricao,modulo,acao) VALUES ($1,$2,$3,$4) ON CONFLICT DO NOTHING",
                  "lojas.excluir_forcado", "Excluir loja com dado vinculado (irreversivel)", "lojas", "excluir_forcado")
```

Só o role Admin recebe automaticamente (Admin já herda todas as permissões existentes, `perms=None` na tabela `ROLES_EXTRAS`/seed).

### `core/lojas.py` — duas funções novas

`impacto_exclusao(id_loja: int) -> dict` — só leitura. Roda `SELECT COUNT(*) FROM <tabela> WHERE loja_id = $1` pra cada tabela do escopo (as duas listas acima), devolve `{"loja": {...dict da loja...}, "impacto": {"pdv_caixas": N, "vendas_pedidos": N, ...}, "total_linhas": N}`. Se a loja não existir, `{"erro": "Loja nao encontrada"}`. Se a loja estiver ativa, `{"erro": "Loja precisa estar inativa antes de avaliar exclusao forcada"}`.

`excluir_forcado(id_loja: int, confirmar_nome: str) -> dict` — dentro de uma transação (`async with conn.transaction()`):

1. Busca a loja (`obter(id_loja)`); se não existir, `{"erro": "Loja nao encontrada"}`.
2. Se `status != 'inativa'`, `{"erro": "Loja precisa estar inativa antes de forcar exclusao"}` — sem tocar em nada.
3. Se `confirmar_nome != loja["nome"]` (comparação exata), `{"erro": "Nome de confirmacao nao confere"}` — sem tocar em nada.
4. `UPDATE lojas SET loja_vinculada_id = NULL WHERE loja_vinculada_id = $1`, idem `loja_matriz_id`.
5. `DELETE FROM <tabela> WHERE loja_id = $1` (ou coluna equivalente pra filhas indiretas, ex. `pdv_vendas.caixa_id IN (SELECT id FROM pdv_caixas WHERE loja_id=$1)`) pra cada tabela do escopo, na ordem listada acima. `db.execute(...)` do asyncpg devolve uma string de status tipo `"DELETE 5"` — a contagem de cada tabela é `int(resultado_execute.split()[-1])`, acumulada num dict `apagado`.
6. `DELETE FROM lojas WHERE id = $1`.
7. Se qualquer passo falhar, a transação inteira faz rollback (comportamento padrão de `async with conn.transaction()` em exceção não capturada) — devolve `{"erro": str(e)}`.
8. Sucesso: `{"ok": True, "apagado": {...contagens...}}`.

### Rotas (`routes/lojas_manage.py`)

```python
@lojas_manage_bp.route('/manage/<int:id_loja>/impacto-exclusao', methods=['GET'])
def lojas_impacto_exclusao(id_loja):
    from core.rbac import requer_permissao
    @requer_permissao("lojas.excluir_forcado")
    def _handler():
        resultado = core.lojas.impacto_exclusao(id_loja)
        if resultado.get("erro"):
            return jsonify(resultado), 400
        return jsonify(resultado)
    return _handler()

@lojas_manage_bp.route('/manage/<int:id_loja>/excluir-forcado', methods=['POST'])
def lojas_excluir_forcado(id_loja):
    from core.rbac import requer_permissao, usuario_atual_da_request
    from core.seguranca import auditar_exclusao
    @requer_permissao("lojas.excluir_forcado")
    def _handler():
        dados = request.get_json(silent=True) or {}
        confirmar_nome = dados.get("confirmar_nome", "")
        dados_antes = core.lojas.obter(id_loja)
        resultado = core.lojas.excluir_forcado(id_loja, confirmar_nome)
        if resultado.get("erro"):
            return jsonify(resultado), 400
        usuario = usuario_atual_da_request()
        auditar_exclusao("lojas", "manage-forcado", id_loja,
                          {**dados_antes, "apagado": resultado.get("apagado", {})})
        return jsonify(resultado)
    return _handler()
```

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
