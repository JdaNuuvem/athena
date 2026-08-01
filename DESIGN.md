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
  accent-400: "#5fd4ff"
  accent-500: "#2fb8f0"
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
  instrument: "6px"
  card: "6px"
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

## Overview

**Creative North Star: "Cockpit de Instrumentos"**

Athena é o ERP interno que unifica loja física, Shopee, Bling e o vínculo de estoque entre canais numa única tela de operação. A superfície opera no modo Operate: quem usa não está sendo persuadido, está completando uma tarefa — bater caixa, checar estoque crítico, decidir o próximo pedido de compra. O painel se comporta como o painel de um cockpit: cada dado vive numa zona fixa e memorizável, a leitura é instantânea, e a cor nunca decora — ela reporta status. Fundo escuro por padrão, não por moda, mas porque reduz fadiga em uso prolongado (turnos de PDV, monitoramento contínuo de agentes). Tipografia monoespaçada e tabular em todo número, para que zeros, casas decimais e alinhamento vertical sejam sempre confiáveis num relance.

Rejeitado explicitamente: o padrão SaaS genérico de indigo/roxo como accent, cards de hero-metric uniformes com borda lateral colorida, e qualquer emoji ou glyph unicode como ícone de interface.

**Key Characteristics:**
- Fundo quase-preto (`panel-950`), nunca neutral-900 de estoque
- Accent cyan de vidro de instrumento, não indigo
- Cor reservada estritamente para status: verde = ok, âmbar = atenção, vermelho = crítico
- Números sempre em fonte monoespaçada tabular
- Navegação em zonas fixas nomeadas (Operação, Vendas, Catálogo & Estoque, Financeiro & Fiscal, Inteligência, Administração)

## Colors

Paleta fria e escura, com um único accent reservado para foco de navegação e um vocabulário de status estritamente semântico.

### Primary
- **Instrument Cyan** (`#5fd4ff` / dim `#2fb8f0`): accent único do sistema. Usado em item de navegação ativo, indicador de sistema operando, foco de link. Nunca usado para decoração — sua raridade é o ponto.

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
- **Azul** (`#5fa8f5`), **Verde categórico** (`#6ad17e`, distinto do verde de status), **Roxo** (`#b98ff5`), **Laranja** (`#f5a35f`), **Teal** (`#22a89e`), **Rosa** (`#dd6398`), **Amarelo** (`#f0d55f`): usadas para codificação nominal — categoria de relatório, coluna de Kanban, canal de marketplace, série de gráfico — nunca para comunicar status (ok/atenção/crítico). Recalibradas mais escuras/dessaturadas que o padrão Tailwind para soarem "vidro de instrumento", não "SaaS genérico".

### Named Rules
**The Status-Only Rule.** Verde (`#34d399`), âmbar (`#f5b942`) e vermelho (`#f3556a`) só aparecem para reportar estado real (sistema operando, estoque crítico, agente com problema). Nunca usados como cor de marca ou decoração. Cores categóricas (acima) são uma categoria à parte — comunicam identidade/tipo, não estado.

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

Duas zonas fixas: sidebar de navegação (`<aside>`) e área de conteúdo (`<main>`). Em desktop (`sm:` e acima, ≥640px) a sidebar é `relative`, ocupando 240px expandida ou 56px recolhida, sempre visível. Em mobile, a sidebar é `fixed inset-y-0 left-0`, fora da tela por padrão (`-translate-x-full`) e desliza para dentro sobre um backdrop escurecido ao abrir pelo botão hamburger — nunca ocupa espaço no fluxo do documento nesse breakpoint. O conteúdo principal usa grid responsivo: instrumentos primários em 3 colunas no desktop, empilhados em 1 coluna no mobile; instrumentos secundários em grid de 2 colunas no mobile, 6 no desktop.

A navegação é agrupada em seis zonas nomeadas e fixas — Operação, Vendas, Catálogo & Estoque, Financeiro & Fiscal, Inteligência, Administração — cada uma com um rótulo de seção em maiúsculas. A ordem e composição das zonas não muda entre telas; é o mapa mental fixo do cockpit.

## Elevation & Depth

Sistema é majoritariamente flat com leve profundidade tonal: instrumentos usam uma face mais clara (`panel-850`) sobre o fundo (`panel-950`/`panel-900`), delimitada por borda de 1px, nunca sombra projetada.

### Shadow Vocabulary
- **Instrument inset** (`box-shadow: inset 0 1px 0 rgba(255,255,255,0.03)`): reflexo raso de vidro dentro de todo `.instrument`, sempre presente — não é sombra de elevação Material, é o brilho da própria vidraça.
- **Instrument-lit halo** (`box-shadow: 0 0 0 1px var(--panel-border-lit), 0 8px 20px -12px rgba(0,0,0,0.6)`): halo externo reservado a `.instrument-lit`, usado só em estados de destaque/foco.

### Named Rules
**The No-Drop-Shadow Rule.** Profundidade vem de camadas tonais (`panel-950` → `panel-850`) e borda, nunca de `box-shadow` projetada para fora, exceto o halo reservado a `.instrument-lit`.

## Shapes

Cantos discretos e consistentes: instrumentos e cards usam `border-radius: 6px`. `rounded-lg` e `rounded-xl` foram sobrescritos no tema do Tailwind pra ambos valerem 6px (em vez dos padrões de 8px/12px) — todo card do sistema herda automaticamente, sem exceção por arquivo, mesmo os que ainda usam a classe `rounded-xl` no código. Nunca `rounded-2xl`/`rounded-3xl` genérico de dashboard SaaS. Bordas de 1px em `panel-border` delimitam toda superfície; não há divisórias sem borda. Ícones são SVG lineares próprios (`stroke-width: 1.5`, viewBox 24×24), nunca emoji ou glyph unicode.

### Named Rules
**The One Radius Rule.** Todo card do sistema renderiza a 6px, igual ao `.instrument` — `rounded-lg` e `rounded-xl` foram unificados no tema, não existe mais uma segunda escala de raio pra card. Não introduza `rounded-2xl`/`rounded-3xl` num card novo.

## Components

### Instrumentos (Primary / Secondary)
- **Shape:** `border-radius: 6px`, borda 1px `panel-border`.
- **Primary:** instrumento grande — label uppercase + número grande `.numeric` + indicador de status (LED colorido) opcional + linha de contexto (ex. "0 pedidos").
- **Secondary:** grid compacto de instrumentos menores, mesma estrutura reduzida, sem indicador de status obrigatório.
- **Estado:** cor do número muda conforme status semântico (`status-ok`/`status-warn`/`status-crit`); o resto do instrumento permanece neutro.

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
- **Do** reservar `accent-400`/`accent-500` (cyan) exclusivamente para foco de navegação e indicadores de sistema — nunca decoração.
- **Do** usar verde/âmbar/vermelho (`status-ok`/`warn`/`crit`) apenas para reportar estado real.
- **Do** manter a sidebar fechada por padrão em mobile (`< 640px`) e aberta por padrão em desktop.
- **Do** usar ícones SVG próprios do `Icon.tsx`, nunca emoji ou glyph unicode.

### Don't:
- **Don't** usar indigo ou qualquer accent de "SaaS genérico" — o accent do sistema é cyan.
- **Don't** aplicar a classe `.instrument` a elementos que precisam de `position: fixed`/`absolute` fora do próprio readout — ela define `position: relative` incondicional e sobrescreve outras estratégias de posicionamento (bug já identificado e corrigido na sidebar mobile).
- **Don't** usar `border-l-4` colorida ou cards "hero-metric" uniformes para alertas — cada instrumento é um readout dedicado, não um cartão genérico.
- **Don't** formatar moeda manualmente com `.toFixed(2)` — sempre usar o helper `fmtBRL` (locale `pt-BR`, vírgula decimal).
