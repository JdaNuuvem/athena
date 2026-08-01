# PDV baixa estoque real da loja física

**Relacionado:** parte da reestruturação de regras por tipo de loja (física/virtual/vínculo opcional) pedida pelo usuário em 30/07/2026. Este documento cobre só a primeira frente: PDV decrementando estoque de verdade. Loja virtual e vínculo físico×virtual são specs separadas, na sequência.

## Por que este documento existe

`core/pdv.py::realizar_venda()` grava a venda (`pdv_vendas`/`pdv_itens`/`pdv_pagamentos`) mas nunca chama `core.estoque.saida()` nem nada equivalente — confirmado por grep no arquivo inteiro (as únicas 3 ocorrências de "estoque" em `core/pdv.py` são leitura de saldo, não escrita). Venda no PDV hoje não mexe em `estoque_lojas`. Isso contradiz a regra do usuário: "loja física... vai diminuindo conforme as vendas do PDV daquela loja em específico."

## Decisões

- **Atomicidade**: a baixa de estoque roda dentro da MESMA transação da venda (`realizar_venda()` já abre `async with conn.transaction()`), usando `saida_async(conn, ...)` — versão async-native de `core.estoque.saida()` já existente e feita exatamente pra esse caso (usada hoje por `core/entidades.py`, `bling_erp.py`, `core.estoque.transferir()`). Ou a venda inteira e a baixa de todos os itens acontecem juntas, ou nenhuma das duas.
- **Estoque insuficiente bloqueia a venda** (decisão do usuário) — mesmo padrão que `saida()`/`saida_async()` já aplicam em qualquer outro fluxo (transferência, saída manual): retornam erro com "insuficiente" quando o saldo não cobre. Se qualquer item da venda não tiver saldo, a transação inteira desfaz — nenhuma venda é criada, nenhum item é decrementado — e o erro identifica qual SKU faltou.
- **Cancelamento e devolução restauram estoque automaticamente** (decisão do usuário) — `cancelar_venda()` e `devolver_item_venda()` passam a chamar `entrada_async(conn, sku, loja, quantidade, "devolucao_cliente", ...)`. Motivo `devolucao_cliente` já existe em `MOTIVOS_ENTRADA` (core/estoque.py) — nenhum motivo novo de entrada necessário.
- **Loja da venda**: resolvida de `pdv_caixas.loja_id` (coluna já existe) → nome via join com `lojas`, mesma convenção do resto do módulo estoque (`loja` sempre trafega como nome/string, não id).
- **Motivo novo de saída**: `"venda_pdv"` adicionado a `MOTIVOS_SAIDA` (core/estoque.py), mapeado em `_MAPA_MOVIMENTO_SAIDA` pro `tipo_movimento="venda"` — esse tipo já existe em `TIPOS_MOVIMENTO` (core/estoque_saldos.py:26), não precisa criar nada no ledger.
- **`sku` do item**: `pdv_itens.produto_codigo` já É o SKU do catálogo — confirmado em `core/pdv.py::buscar_produtos()` (`c.sku AS codigo`, linha 547). Sem ambiguidade, sem mapeamento extra.

## Mudanças

- `core/estoque.py`: adiciona `"venda_pdv"` a `MOTIVOS_SAIDA` e a entrada correspondente em `_MAPA_MOVIMENTO_SAIDA`.
- `core/pdv.py::realizar_venda()`: depois de resolver `loja` do caixa, chama `saida_async(conn, item["produto_codigo"], loja, item["quantidade"], "venda_pdv", ...)` pra cada item, dentro do bloco de transação já existente. Se qualquer chamada retornar erro, levanta exceção pra abortar a transação (mesmo padrão já usado em `core.estoque.transferir()` pra perna 2).
- `core/pdv.py::cancelar_venda()`: abre transação (hoje não abre), busca todos os itens de `pdv_itens WHERE venda_id = ...`, chama `entrada_async()` pra cada um restaurando a quantidade original, na loja da venda.
- `core/pdv.py::devolver_item_venda()`: abre transação, chama `entrada_async()` só pra quantidade devolvida (não o item inteiro), mesma loja.

## Testes

`hermes_agents/tests/test_pdv_estoque.py`:
- Venda com estoque suficiente decrementa cada item corretamente na loja do caixa.
- Venda com um item sem saldo suficiente: transação inteira desfaz — nenhuma linha em `pdv_vendas`/`pdv_itens`, nenhum estoque alterado, erro identifica o SKU.
- `cancelar_venda()` restaura a quantidade de todos os itens da venda.
- `devolver_item_venda()` restaura só a quantidade parcial devolvida, mantendo o resto do item decrementado.

## Fora de escopo (registrado, não decidido aqui)

- `core/pdv.py::buscar_produtos()` mostra estoque somado de todas as lojas (`SUM(e.quantidade)` sem filtro de loja), não o saldo da loja do caixa que está vendendo — achado incidental durante esta investigação, não pedido pelo usuário, fica registrado pra decisão futura.
- Loja virtual (estoque próprio, visível na aba Estoque, alimentado manualmente) — próxima spec.
- Vínculo opcional físico×virtual (saldo compartilhado quando ativado) — próxima spec; quando existir, a baixa de PDV desta spec deve decrementar o saldo compartilhado se a loja física estiver vinculada, mas isso é decisão da spec de vínculo, não desta.

## Próximo passo

`superpowers:writing-plans` — plano de implementação TDD.
