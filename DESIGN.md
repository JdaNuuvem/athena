---
name: Athena
description: Painel de operação estilo cockpit de instrumentos para ERP interno multi-loja
colors:
  panel-950: "#05070a"
  panel-900: "#0a0e14"
  panel-850: "#10151d"
  panel-800: "#161d27"
  panel-750: "#1c2530"
  panel-700: "#242e3a"
  panel-border: "#232c38"
  panel-border-lit: "#34495e"
  ink-100: "#e7ecf2"
  ink-300: "#b3c0cf"
  ink-500: "#7c8ba0"
  ink-700: "#4c5866"
  accent-400: "#4ade80"
  accent-500: "#22c55e"
  status-ok: "#34d399"
  status-warn: "#f5b942"
  status-crit: "#f3556a"
  categorical-blue: "#5fa8f5"
  categorical-green: "#6ad17e"
  categorical-purple: "#b98ff5"
  categorical-orange: "#f5a35f"
  categorical-teal: "#22a89e"
  categorical-pink: "#dd6398"
  categorical-yellow: "#f0d55f"
typography:
  display:
    fontFamily: "ui-sans-serif, system-ui, sans-serif"
    fontWeight: 600
  numeric:
    fontFamily: "JetBrains Mono, ui-monospace, SF Mono, monospace"
    fontFeatureSettings: "tnum 1"
    letterSpacing: "-0.01em"
  label:
    fontSize: "11px"
    letterSpacing: "0.05em"
    textTransform: "uppercase"
rounded:
  instrument: "12px"
  card: "12px"
  hero: "16px"
spacing:
  sm: "8px"
  md: "16px"
  lg: "24px"
components:
  instrument:
    backgroundColor: "{colors.panel-850}"
    rounded: "{rounded.instrument}"
  instrument-lit:
    backgroundColor: "{colors.panel-850}"
    rounded: "{rounded.instrument}"
---

# Design System: Athena

> Revisado na Fase 1 da renovação de UX (2026-08-07) — ver
> `docs/superpowers/specs/2026-08-07-ux-renovacao-fase1-fundacao-design.md`.
> Accent, raio e regra de sombra mudaram; o resto deste documento (tipografia,
> layout, navegação, ícones) continua valendo sem alteração.

## Overview

**Creative North Star: "Cockpit de Instrumentos"**

Athena é o ERP interno que unifica loja física, Shopee, Bling e o vínculo de estoque entre canais numa única tela de operação. A superfície opera no modo Operate: quem usa não está sendo persuadido, está completando uma tarefa — bater caixa, checar estoque crítico, decidir o próximo pedido de compra. O painel se comporta como o painel de um cockpit: cada dado vive numa zona fixa e memorizável, a leitura é instantânea, e a cor nunca decora — ela reporta status. Fundo escuro por padrão, não por moda, mas porque reduz fadiga em uso prolongado (turnos de PDV, monitoramento contínuo de agentes). Tipografia monoespaçada e tabular em todo número, para que zeros, casas decimais e alinhamento vertical sejam sempre confiáveis num relance.

Rejeitado explicitamente: o padrão SaaS genérico de indigo/roxo como accent, `border-l-4` colorida como indicador de card, e qualquer emoji ou glyph unicode como ícone de interface. Cards "hero-metric" uniformes seguem rejeitados como padrão *default* — a Fase 1 da renovação de UX (2026-08-07) introduz uma única exceção deliberada: o instrumento primário mais importante de cada painel (ex. "Vendas hoje" no Dashboard) pode usar tratamento de gradiente pra funcionar como abertura visual da tela. É uma exceção de no máximo um card por tela, não um padrão geral — ver regra em Shapes/Don'ts.

**Key Characteristics:**
- Fundo quase-preto (`panel-950`), nunca neutral-900 de estoque
- Accent verde de vidro de instrumento, não indigo (verde, não ciano, desde a Fase 1 da renovação de UX)
- Cor reservada estritamente para status: verde = ok, âmbar = atenção, vermelho = crítico
- Números sempre em fonte monoespaçada tabular
- Navegação em zonas fixas nomeadas (Operação, Vendas, Catálogo & Estoque, Financeiro & Fiscal, Inteligência, Administração)

## Colors

Paleta fria e escura, com um único accent reservado para foco de navegação e um vocabulário de status estritamente semântico.

### Primary
- **Instrument Green** (`#4ade80` / dim `#22c55e`; tema claro: `#16a34a` / dim `#15803d`): accent único do sistema. Usado em item de navegação ativo, indicador de sistema operando, foco de link. O tratamento hero-gradient (ver Overview) usa tons mais escuros dedicados (`--accent-600`/`--accent-700`), não o accent-400/500 direto — texto branco em cima precisa de mais contraste do que o accent-400/500 garante (eles são claros de propósito, pra brilhar sobre fundo escuro). Deliberadamente distinto de `status-ok` (`#34d399` escuro / `#047857` claro) E de `emerald-500`/`emerald-600` (`#22b384`/`#189a70`, usado nos botões de confirmação) — accent é identidade/navegação, emerald/status é semântica de sucesso, mesmo as três famílias sendo verde. Nunca usado para decoração fora desses papéis — sua raridade é o ponto. (Revisado na Fase 1 da renovação de UX, 2026-08-07 — era cyan `#5fd4ff`/`#2fb8f0`; ajustado nesta mesma fase de um verde mais próximo do emerald para este tom, especificamente para evitar a colisão visual com os botões de confirmação.)

### Neutral
- **Void** (`#05070a`): fundo base do `body`, a camada mais escura, o "vácuo" atrás dos instrumentos.
- **Panel** (`#0a0e14`): fundo da sidebar e superfícies de segundo nível.
- **Instrument Face** (`#10151d`): fundo de cada card/instrumento — a "vidraça" do readout.
- **Panel Border** (`#232c38`) / **Panel Border Lit** (`#34495e`): borda padrão e borda de destaque (hover/foco) de instrumentos.
- **Ink 100** (`#e7ecf2`): texto primário, alto contraste.
- **Ink 300** (`#b3c0cf`): texto secundário.
- **Ink 500** (`#7c8ba0`): texto terciário, labels menos importantes.
- **Ink 700** (`#4c5866`): texto de apoio mínimo, eixos de gráfico, placeholders.

### Categorical (tags, canais, séries de gráfico)
- **Azul** (`#5fa8f5`), **Verde categórico** (`#6ad17e`, distinto do verde de status e do verde de accent), **Roxo** (`#b98ff5`), **Laranja** (`#f5a35f`), **Teal** (`#22a89e`), **Rosa** (`#dd6398`), **Amarelo** (`#f0d55f`): usadas para codificação nominal — categoria de relatório, coluna de Kanban, canal de marketplace, série de gráfico — nunca para comunicar status (ok/atenção/crítico) nem identidade de marca. Recalibradas mais escuras/dessaturadas que o padrão Tailwind para soarem "vidro de instrumento", não "SaaS genérico".

### Named Rules
**The Status-Only Rule.** Verde (`#34d399`), âmbar (`#f5b942`) e vermelho (`#f3556a`) só aparecem para reportar estado real (sistema operando, estoque crítico, agente com problema). Nunca usados como cor de marca ou decoração. Cores categóricas (acima) são uma categoria à parte — comunicam identidade/tipo, não estado. O accent verde (Primary, acima) é uma terceira categoria à parte — comunica identidade de marca/navegação, não estado nem tipo, mesmo próximo em matiz do `status-ok`.

## Typography

**Display/Body Font:** system-ui (fonte do sistema, sem carregamento de web font para texto corrido)
**Numeric/Label Font:** JetBrains Mono (via `next/font/google`, variável `--font-mono`)

**Character:** par funcional-instrumental — texto corrido em sans-serif do sistema para não competir com o dado, números sempre em monoespaçada tabular para que a leitura de painel nunca "pule" visualmente.

### Hierarchy

Escala compacta de 5 degraus, necessária pela densidade de informação de um painel de instrumentos (muitos rótulos e valores pequenos coexistindo por tela):

- **Display** (700, 28px, `.numeric`): valor numérico do instrumento primário (ex. "R$ 0,00" em Vendas Hoje). Único degrau grande da escala — reservado ao dado mais importante de cada bloco.
- **Title** (600, 13px, `letter-spacing: 0.14em` no wordmark / peso normal em item de navegação): wordmark "ATHENA", item de navegação da sidebar, título de seção de instrumento ("PAINEL DE OPERAÇÃO").
- **Label** (500, 11px, uppercase, `letter-spacing: 0.05em`, cor `ink-500`): rótulo de cada instrumento individual ("VENDAS HOJE", "TICKET MÉDIO").
- **Context** (400, 10px, cor `ink-500`/`ink-700`): linha de apoio dentro do instrumento (ex. "0 pedidos"), texto de tabela secundário, contexto de agente/lista.
- **Micro** (500, 9px, uppercase, `letter-spacing: 0.12em`, cor `ink-700`): rótulo de zona da sidebar ("OPERAÇÃO", "VENDAS") e badges/anotações mínimas — o degrau mais discreto, só para agrupamento estrutural, nunca para conteúdo que precise ser lido de relance.
- **Body**: texto de apoio e navegação sem tamanho fixo dedicado, sans-serif do sistema, `ink-300`/`ink-100`.

### Named Rules
**The Five-Step Rule.** Todo texto do sistema cai em um dos cinco degraus acima (28/13/11/10/9px). Um novo tamanho arbitrário fora dessa escala é drift, não uma decisão de design.

### Named Rules
**The Tabular Rule.** Todo número exibido ao usuário — moeda, quantidade, contagem — usa `.numeric`. Nenhum número solto em fonte proporcional.

## Layout

Duas zonas fixas: sidebar de navegação (`<aside>`) e área de conteúdo (`<main>`). Em desktop (`sm:` e acima, ≥640px) a sidebar é `relative`, ocupando 240px expandida ou 56px recolhida, sempre visível. Em mobile, a sidebar é `fixed inset-y-0 left-0`, fora da tela por padrão (`-translate-x-full`) e desliza para dentro sobre um backdrop escurecido ao abrir pelo botão hamburger — nunca ocupa espaço no fluxo do documento nesse breakpoint. O conteúdo principal usa grid responsivo: instrumentos primários em 3 colunas no desktop, empilhados em 1 coluna no mobile; instrumentos secundários em grid de 2 colunas no mobile, 6 no desktop. `<main>` não tem `max-width` — o conteúdo ocupa a área total disponível; telas com `max-w-*` no wrapper raiz são drift, não uma decisão documentada (achado corrigido na Fase 1 da renovação de UX, 2026-08-07, em 8 telas do módulo Integrações/Shopee + `roles`) — exceto telas de formulário/configuração, que mantêm largura de leitura por escolha, não por drift.

A navegação é agrupada em seis zonas nomeadas e fixas — Operação, Vendas, Catálogo & Estoque, Financeiro & Fiscal, Inteligência, Administração — cada uma com um rótulo de seção em maiúsculas. A ordem e composição das zonas não muda entre telas; é o mapa mental fixo do cockpit.

## Elevation & Depth

Sistema é majoritariamente flat com leve profundidade tonal: instrumentos usam uma face mais clara (`panel-850`) sobre o fundo (`panel-950`/`panel-900`), delimitada por borda de 1px. No tema escuro, nunca sombra projetada. No tema claro (Fase 1 da renovação de UX, 2026-08-07), uma sombra suave e única (`--card-shadow: 0 1px 3px rgba(0,0,0,0.06)`) foi adicionada a todo `.instrument` — sem ela, cards claros sobre fundo quase-branco perdem a separação visual que a borda sozinha resolve bem no escuro mas não em luz de dia.

### Shadow Vocabulary
- **Instrument inset** (`box-shadow: inset 0 1px 0 rgba(255,255,255,0.03)`): reflexo raso de vidro dentro de todo `.instrument`, sempre presente nos dois temas — não é sombra de elevação Material, é o brilho da própria vidraça.
- **Instrument-lit halo** (`box-shadow: 0 0 0 1px var(--panel-border-lit), 0 8px 20px -12px rgba(0,0,0,0.6)`): halo externo reservado a `.instrument-lit`, usado só em estados de destaque/foco, sem mudança entre temas.
- **Card shadow** (`box-shadow: var(--card-shadow)`, só tema claro): sombra suave e única em todo `.instrument` no tema claro, exceto `.instrument-lit`, que mantém seu próprio halo nos dois temas e sobrescreve o `--card-shadow`. `none` no tema escuro.

### Named Rules
**The No-Drop-Shadow Rule (revisada, Fase 1 da renovação de UX, 2026-08-07).** Tema escuro: profundidade só por camada tonal e borda, nunca `box-shadow` projetada, exceto o halo reservado a `.instrument-lit`. Tema claro: uma sombra suave e única (`--card-shadow`) é permitida em todo `.instrument` — não é uma exceção caso a caso, é a regra do tema claro.

## Shapes

Cantos discretos e consistentes: instrumentos e cards usam `border-radius: 12px` (`--radius-lg`/`--radius-xl`, unificados no tema do Tailwind — era 6px até a Fase 1 da renovação de UX, 2026-08-07). O único instrumento hero-gradient permitido por tela (ver Overview) usa `border-radius: 16px` (`--radius-hero`), levemente maior, reforçando que é o ponto de entrada visual do painel, não um instrumento comum — e não tem borda própria, a transição do gradiente já delimita a forma. Nunca `rounded-2xl`/`rounded-3xl` genérico de dashboard SaaS fora desses dois valores. Ícones são SVG lineares próprios (`stroke-width: 1.5`, viewBox 24×24), nunca emoji ou glyph unicode.

### Named Rules
**The One Radius Rule (revisada, Fase 1 da renovação de UX, 2026-08-07).** Todo card do sistema renderiza a 12px, exceto o único instrumento hero por tela (16px, ver acima). `rounded-lg` e `rounded-xl` continuam unificados no tema — não existe uma terceira escala de raio além do padrão e do hero.

## Components

### Instrumentos (Primary / Secondary)
- **Shape:** `border-radius: 12px` (16px no único instrumento hero-gradient da tela, se houver), borda 1px `panel-border` (instrumento hero não tem borda).
- **Primary:** instrumento grande — label uppercase + número grande `.numeric` + indicador de status (LED colorido) opcional + linha de contexto (ex. "0 pedidos"). No máximo um por tela pode usar o tratamento hero-gradient (fundo em gradiente do accent, texto branco, sem LED de status — o próprio gradiente já comunica destaque).
- **Secondary:** grid compacto de instrumentos menores, mesma estrutura reduzida, sem indicador de status obrigatório, nunca hero-gradient.
- **Estado:** cor do número muda conforme status semântico (`status-ok`/`status-warn`/`status-crit`); o resto do instrumento permanece neutro (exceto o hero-gradient, que é sempre branco sobre o gradiente).

### Navegação (Sidebar)
- **Estilo:** fundo `panel-900`, borda direita `panel-border`, itens agrupados por zona com rótulo de seção uppercase `ink-500`.
- **Item ativo:** fundo destacado + texto `accent-400`.
- **Item padrão/hover:** texto `ink-300`, hover para `ink-100`.
- **Mobile:** vira drawer `fixed` com backdrop, fechado por padrão, abre via botão hamburger no header.

### Ícones
- **Estilo:** SVG próprio (`Icon.tsx`), stroke 1.5, sem preenchimento, 24×24 viewBox. Nunca emoji ou glyph unicode (ex. ◀▶▾▸⏻☰ foram todos substituídos).

## Do's and Don'ts

### Do:
- **Do** usar `.numeric` em todo valor numérico exibido (moeda, contagem, quantidade).
- **Do** reservar `accent-400`/`accent-500` (verde) exclusivamente para foco de navegação, indicadores de sistema, e o tratamento hero-gradient — nunca decoração fora desses papéis.
- **Do** usar verde/âmbar/vermelho (`status-ok`/`warn`/`crit`) apenas para reportar estado real.
- **Do** reservar o tratamento hero-gradient para no máximo um instrumento por tela — o dado mais importante do contexto (ex. "Vendas hoje" no Dashboard).
- **Do** manter a sidebar fechada por padrão em mobile (`< 640px`) e aberta por padrão em desktop.
- **Do** usar ícones SVG próprios do `Icon.tsx`, nunca emoji ou glyph unicode.
- **Do** deixar `<main>` sem `max-width` — o conteúdo ocupa a área total disponível.

### Don't:
- **Don't** usar indigo ou qualquer accent de "SaaS genérico" — o accent do sistema é verde.
- **Don't** usar `border-l-4` colorida como indicador de card.
- **Don't** replicar o tratamento hero-gradient em mais de um instrumento por tela — ele existe pra marcar um único ponto de entrada visual, não um padrão de card geral; fora desse uso único, cada instrumento continua sendo um readout dedicado, não um cartão genérico.
- **Don't** aplicar a classe `.instrument` a elementos que precisam de `position: fixed`/`absolute` fora do próprio readout — ela define `position: relative` incondicional e sobrescreve outras estratégias de posicionamento (bug já identificado e corrigido na sidebar mobile).
- **Don't** formatar moeda manualmente com `.toFixed(2)` — sempre usar o helper `fmtBRL` (locale `pt-BR`, vírgula decimal).
- **Don't** limitar a largura de telas de dado/lista/dashboard com `max-w-*` — use a área total disponível (padrão já seguido por Dashboard/Vendas/Estoque/PDV/Produtos). Exceção: telas de formulário/configuração (ex. `config/page.tsx`, `integracoes/shopee/page.tsx`, `produtos/novo/page.tsx`) podem manter uma largura de leitura confortável — a regra é sobre telas de dado denso, não sobre todo `<main>`.
