# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Equipe interna da própria empresa (operadores de PDV, gerentes de loja, financeiro/RH, compras, admin). Uso não-público — acessado durante o expediente, no computador/tablet da loja física ou do escritório. Já são usuários treinados no sistema atual.

## Product Purpose

Athena é o ERP interno que administra a operação inteira do negócio: vendas (PDV físico + Shopee), estoque, catálogo de produtos, financeiro, RH, compras, fiscal, e a gestão de múltiplas lojas (físicas e virtuais). Existe pra centralizar operações que hoje ficariam espalhadas entre sistemas separados (Bling, Shopee, planilhas).

## Positioning

Unifica loja física + Shopee + Bling numa tela só — vínculo de estoque física/virtual (saldo compartilhado opcional entre uma loja física e sua virtual vinculada), RBAC por loja (cada usuário vê só as lojas às quais está vinculado), e integração direta com Shopee/Bling/i9Logic sem precisar alternar entre sistemas. Um ERP genérico (Bling, Tiny) não faz esse vínculo nativo entre canais.

## Operating Context

Módulos confirmados em produção: PDV (abrir/fechar caixa, vender, cancelar, devolver item, sangria/suprimento), Estoque (entrada/saída/transferência/contagem/análise de giro-ruptura-cobertura), Produtos (catálogo mestre + produtos por loja + publicação Shopee), Financeiro (contas a pagar/receber, fluxo de caixa, DRE), RH (folha, benefícios, ponto, férias), Compras, Fiscal (notas, tributos, obrigações), Lojas (cadastro física/virtual/marketplace, vínculo de estoque, responsáveis), Relatórios, Chat interno, Integrações (Shopee, Bling, i9Logic). Deploy real em produção (Coolify, athena.zoikom.site) com dados e transações reais.

## Capabilities and Constraints

**Rotas/URLs e fluxos de trabalho atuais devem ser preservados** — redesign é visual/estrutural (layout, hierarquia, componentes), não uma reformulação de fluxo. O passo-a-passo de cada operação (abrir caixa → vender → fechar caixa; cadastrar produto → vincular loja → publicar Shopee) precisa continuar funcionando como hoje, já que a equipe está treinada nele. Stack: Next.js 15 (App Router), React 19, Tailwind CSS 4, Recharts. Backend Flask/Python separado (fora do escopo deste redesign).

## Brand Commitments

Nome do produto: **Athena**. Tema visual atual é dark (paleta neutral-900/800 com indigo como accent) — fato do estado atual, não necessariamente vínculo obrigatório pro redesign (o usuário pediu "estilo empresarial e profissional", decisão de mundo visual fica pra new-work).

## Evidence on Hand

Código-fonte completo e funcional de todas as telas listadas em Operating Context (`web/src/app/`), já em uso real. Nenhuma pesquisa de usuário formal ou benchmark documentado — inferências sobre uso vêm da natureza operacional do sistema (ERP interno).

## Product Principles

1. **Fluxo sobre estética** — é ferramenta de trabalho usada centenas de vezes por dia; velocidade e previsibilidade da tarefa vêm antes de qualquer efeito visual.
2. **Multi-loja é estrutural, não incidental** — quase toda tela precisa deixar claro em qual loja/contexto o usuário está operando.
3. **Confiança em dados sensíveis** — módulos financeiro/fiscal/estoque lidam com dinheiro e obrigações reais; hierarquia visual deve deixar erro e discrepância óbvios, nunca escondidos em ruído.
4. **Consistência entre módulos** — um usuário que aprende PDV deve reconhecer os mesmos padrões em Estoque, Financeiro, etc.

## Accessibility & Inclusion

Nenhum requisito formal confirmado ainda.
