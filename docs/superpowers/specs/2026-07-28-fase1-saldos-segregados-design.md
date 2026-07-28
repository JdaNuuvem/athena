# Fase 1 — Saldos Segregados + Ledger Formal

Parte da revisão de arquitetura de estoque multilojas. Fase 1 de 7 (ver decomposição completa no histórico da conversa que originou este spec). Pré-requisito para todas as fases seguintes (estrutura física, transferências completas, reservas, modelo colaborativo, venda cruzada, inventário/auditoria).

## Contexto atual

- `estoque_lojas(sku, loja, quantidade)` — um único campo de quantidade por (sku, loja). Não distingue disponível de reservado, em trânsito, bloqueado etc.
- `estoque_movimentacoes` — ledger existente, mas incompleto: sem `saldo_anterior`/`saldo_posterior`, sem IP/dispositivo, `tipo` limitado a `entrada/saida/transferencia_origem/transferencia_destino/rateio`.
- `estoque_transferencias.py` (`solicitar()`) **debita a origem imediatamente** ao criar a solicitação, antes de aprovação/envio. Enquanto a transferência está `pendente_aprovacao` ou `em_transito`, a quantidade correspondente não existe em nenhum saldo consultável — só como uma linha com `status` em `estoque_transferencias`. Bug real, não hipotético.
- 6 pontos de escrita direta em `estoque_lojas` fora de `core/estoque.py`: `routes/estoque.py`, `bling_erp.py`, `core/entidades.py` (3 ocorrências), `core/estoque_transferencias.py`.
- `core/entidades.py:242` interpola `LOJA_PRINCIPAL` via f-string dentro do SQL (não é input de usuário, mas foge do padrão parametrizado do resto do arquivo).

## Modelo de dados

### Tabela nova: `estoque_saldos`

```sql
CREATE TABLE estoque_saldos (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) NOT NULL,
    loja VARCHAR(50) NOT NULL,
    tipo VARCHAR(20) NOT NULL,
    quantidade DECIMAL(12,3) NOT NULL DEFAULT 0,
    data_atualizacao TIMESTAMP DEFAULT NOW(),
    UNIQUE(sku, loja, tipo)
)
```

`tipo` (CHECK constraint), os 11 buckets do doc original:
`disponivel`, `reservado`, `separacao`, `transito`, `bloqueado`, `devolucao`, `danificado`, `perdido`, `consignado`, `inventario`, `virtual`.

Nesta fase, apenas `disponivel` e `transito` têm produtor real (via `entrada/saida/transferir/ratear`). Os demais 9 existem no schema para as fases futuras que os produzirão (reserva → Fase 4, separação/expedição → Fase 3, devolução/dano/perda/consignado/inventário → Fase 7), sem quebrar o schema quando chegar a vez delas.

### `estoque_lojas.quantidade` como espelho

`estoque_saldos` (tipo=`disponivel`) passa a ser fonte de verdade. `estoque_lojas.quantidade` continua existindo, mas é mantido por **trigger Postgres** (`AFTER INSERT OR UPDATE ON estoque_saldos`, filtro `tipo = 'disponivel'`) que faz upsert em `estoque_lojas`. Trigger no banco — não app-level — porque garante consistência mesmo se algum caller ainda não migrado escrever direto (defesa em profundidade durante a transição).

Isso mantém os ~10 arquivos que só **leem** `estoque_lojas.quantidade` (bi.py, pdv.py, relatorios.py, catalogo.py, shopee.py, repositories_postgres.py etc.) funcionando sem alteração nesta fase. Migram para a API nova em fases futuras, sem pressa.

### `estoque_movimentacoes` expandido

Novas colunas:

- `tipo_saldo VARCHAR(20)` — qual bucket de `estoque_saldos` foi afetado.
- `saldo_anterior DECIMAL(12,3)`, `saldo_posterior DECIMAL(12,3)` — do bucket afetado, antes/depois desta movimentação.
- `ip VARCHAR(45)`, `dispositivo VARCHAR(300)` — capturados quando disponível (ver seção IP/dispositivo).

`tipo` (tipo de movimento) usa os 18 valores do documento original: `compra, venda, ajuste, inventario, transferencia_saida, transferencia_transito, transferencia_recebida, reserva, liberacao_reserva, separacao, expedicao, recebimento, devolucao, troca, perda, roubo, extravio, bonificacao, cancelamento, estorno`. **Validação só em Python** (`TIPOS_MOVIMENTO` em `core/estoque_saldos.py`, checada dentro de `mover_saldo()`), não como CHECK constraint de banco — a tabela já tem linhas históricas com `tipo` em `entrada/saida/transferencia_origem/transferencia_destino/rateio`, fora do novo enum, e `ALTER TABLE ADD CONSTRAINT CHECK` validaria (e rejeitaria) essas linhas existentes.

Nomes de transferência mudam de `transferencia_origem/transferencia_destino` (2 linhas, saldo pulando direto) para `transferencia_saida` (disponível→transito na origem), `transferencia_transito` (não usado como linha de ledger separada — o estado "em trânsito" já é o saldo em si), `transferencia_recebida` (transito→disponível no destino ao confirmar). Mantém 2 linhas de ledger por transferência concluída (saída + recebida), como hoje.

Apenas os tipos com caller nesta fase (`entrada`→`compra`/`devolucao_cliente`/etc conforme motivo já existente, `saida`, `ajuste`, `transferencia_saida`, `transferencia_recebida`, `rateio`... — reaproveita os motivos já existentes em `MOTIVOS_ENTRADA`/`MOTIVOS_SAIDA`/`MOTIVOS_TRANSFERENCIA`) geram linha real. Os demais 12 ficam no CHECK sem gerador — a fase que implementar o fluxo (reserva, separação, devolução formal etc.) usa o tipo já pronto.

## API — `core/estoque.py`

Duas funções novas, internas, por trás das quais tudo passa a operar:

- `saldo(sku, loja, tipo='disponivel') -> float` — leitura de um bucket.
- `mover_saldo(sku, loja, tipo_origem, tipo_destino, quantidade, tipo_movimento, motivo, usuario_id=None, usuario_nome='', ip=None, dispositivo=None) -> dict` — única função que escreve em `estoque_saldos` e `estoque_movimentacoes`, na mesma transação. `tipo_origem=None` = entrada pura (crédito sem débito de outro bucket); `tipo_destino=None` = saída pura (débito sem crédito).

`entrada()`, `saida()`, `transferir()`, `ratear()` (assinaturas públicas inalteradas) viram wrappers finos sobre `mover_saldo()`:

- `entrada` → `mover_saldo(tipo_origem=None, tipo_destino='disponivel', tipo_movimento=motivo mapeado)`
- `saida` → `mover_saldo(tipo_origem='disponivel', tipo_destino=None, ...)`
- `transferir` → continua instantâneo (sem estado pendente, comportamento atual preservado — quem precisa do estado `transito`/aprovação é o fluxo separado de `estoque_transferencias.py`, tratado no próximo item). Duas chamadas: `mover_saldo(origem, tipo_origem='disponivel', tipo_destino=None, tipo_movimento='transferencia_saida')` (débito puro na origem) depois `mover_saldo(destino, tipo_origem=None, tipo_destino='disponivel', tipo_movimento='transferencia_recebida')` (crédito puro no destino). Nunca passa pelo bucket `transito` — esse é exclusivo do fluxo com aprovação.
- `ratear` → uma chamada `mover_saldo` por loja de destino, tipo_movimento='ajuste' com motivo descritivo (comportamento equivalente ao atual).

## Corrige `estoque_transferencias.py`

- `solicitar()`: em vez de `_debitar_origem` direto em `estoque_lojas`, chama `mover_saldo(sku, origem, 'disponivel', 'transito', quantidade, 'transferencia_saida', motivo, usuario_id, usuario_nome)` **somente quando a transferência não exige aprovação** (quantidade dentro do limite livre). Quantidade fica visível como saldo `transito`, não desaparece.
- **Nota de design (revista na Task 3):** quando a transferência exige aprovação, `solicitar()` não move saldo nenhum — fica só a linha `pendente_aprovacao` em `estoque_transferencias`. O débito `disponivel -> transito` foi movido para `aprovar()`, que agora chama o mesmo `mover_saldo(sku, origem, 'disponivel', 'transito', quantidade_solicitada, 'transferencia_saida', ...)` antes de marcar `status = 'em_transito'`. Consequência: `rejeitar()` **nunca precisa devolver saldo**, porque só é chamável a partir de `pendente_aprovacao` — estado em que a origem nunca foi debitada. Essa abordagem (debitar cedo e reembolsar em `rejeitar()`, como a versão original desta seção descrevia) foi descartada por ser mais arriscada: um caminho de reembolso é mais uma oportunidade de bug (ex.: reembolso duplicado, reembolso após falha parcial) do que simplesmente nunca debitar até a aprovação de fato acontecer.
- `aprovar()`: agora debita `disponivel -> transito` via `mover_saldo` (ver nota acima) antes de mudar `status` para `em_transito`.
- `rejeitar()`: só muda `status` para `rejeitada`; não chama `mover_saldo` (não há saldo para devolver — ver nota acima).
- `confirmar()`: em vez de `_creditar_destino` direto, chama `mover_saldo(sku, origem, 'transito', None, quantidade_recebida, 'transferencia_recebida'...)` para dar baixa no trânsito da origem, e `mover_saldo(sku, destino, None, 'disponivel', quantidade_recebida, 'transferencia_recebida'...)` para creditar o destino. Discrepância (`quantidade_recebida != quantidade_solicitada`) já é tratada hoje (`status = com_discrepancia`); mantém.

## Migração dos escritores diretos

Passam a chamar `core/estoque.py` em vez de SQL cru contra `estoque_lojas`:

1. `routes/estoque.py` — ponto de entrada HTTP; também de onde vem IP/dispositivo (ver abaixo).
2. `bling_erp.py` (linha ~749) — sync de saldo vindo do Bling; usa `entrada`/`saida`/ajuste conforme sinal do delta, ou uma chamada `mover_saldo` direta com `tipo_movimento='ajuste'`, motivo `sync_bling`.
3. `core/entidades.py` (3 ocorrências, linhas ~242/299/337/352) — baixa/entrada por produção interna e consumo de componentes; passam a chamar `entrada()`/`saida()` de `core/estoque.py`. De brinde, corrige a interpolação f-string de `LOJA_PRINCIPAL` (deixa de existir — a chamada passa a loja como parâmetro normal da função, não dentro de SQL).
4. `core/estoque_transferencias.py` — coberto acima.
5. `tests/test_estoque_seguranca.py` — ajusta fixtures/asserts para a tabela `estoque_saldos` onde necessário.

## IP / dispositivo

`routes/estoque.py` passa `ip=request.remote_addr, dispositivo=request.headers.get('User-Agent', '')` nas chamadas a `entrada/saida/transferir`. Callers sem contexto HTTP (webhook Bling, jobs do scheduler, `entidades.py`) passam `ip=None, dispositivo=None` — a coluna aceita NULL.

## Fora de escopo desta fase

- Fluxo de reserva real (origem pedido/PDV/loja virtual, expiração) — Fase 4.
- Separação/expedição como etapas distintas do fluxo de transferência — Fase 3.
- Contagem de inventário, geração automática de ajuste por diferença — Fase 7.
- Hierarquia física (empresa/depósito/setor/.../posição) — Fase 2.
- Migração dos ~10 arquivos que só leem `estoque_lojas.quantidade` — ficam no espelho por enquanto.

## Testes

- Unitário: `mover_saldo` com todas as combinações origem/destino/None, incluindo saldo insuficiente (erro, sem gravar).
- Trigger: escrever em `estoque_saldos` (tipo=disponivel) e conferir que `estoque_lojas.quantidade` reflete, inclusive via SQL direto (fora de `core/estoque.py`) para provar que a defesa em profundidade funciona.
- Integração: fluxo completo de transferência (`solicitar`→`aprovar`→`confirmar`) checando saldo `transito` aparece na origem durante a janela pendente e desaparece ao confirmar, com saldo `disponivel` do destino refletindo.
- Regressão: os 10 arquivos leitores continuam retornando os mesmos valores de `estoque_lojas.quantidade` antes/depois da migração.
