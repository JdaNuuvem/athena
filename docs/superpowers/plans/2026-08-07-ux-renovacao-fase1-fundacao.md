# Renovação de UX — Fase 1: Fundação Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retonar o sistema de design (accent verde, raio maior, sombra em tema claro), aplicar o padrão hero-metric no piloto (`/dashboard`), corrigir o bug de `max-w-*` em 9 telas, e atualizar `DESIGN.md`.

**Architecture:** Tudo é retone de token em `web/src/app/globals.css` (fonte única de verdade, já consumida por todo o app via CSS custom properties e o bloco `@theme` do Tailwind v4) + uma mudança pontual em `web/src/app/dashboard/page.tsx` pra aplicar o novo padrão hero num único instrumento. A infraestrutura de tema claro/escuro (`ThemeProvider`, toggle, script anti-flash) já existe e não é tocada. Sem chamada de API, sem estado novo, sem dependência nova.

**Tech Stack:** Next.js 15 / React 19 / Tailwind v4 (CSS custom properties + `@theme`), sem bibliotecas novas.

## Global Constraints

- Sem novas dependências no `web/package.json`.
- Accent novo deliberadamente distinto de `--status-ok` (accent = identidade/navegação, status = semântica de sucesso), mesmo os dois na família verde.
- Sombra nova (`--card-shadow`) só existe no tema claro — tema escuro continua com `--card-shadow: none`, sem drop-shadow, como documentado.
- O tratamento hero-gradient é usado em **um único** instrumento (`Vendas hoje`, no piloto `/dashboard`) — não é um padrão pra replicar em todo card sem critério; isso está documentado explicitamente no `DESIGN.md` atualizado.
- Nenhuma mudança em `KpiCard.tsx` nem em qualquer outra tela além do piloto — as ~130 telas restantes herdam cor/raio novos automaticamente via token, sem mudança de composição, e ficam para fases futuras.
- Nomes de variáveis/comentários novos em português, mesmo padrão do resto do repo.

---

### Task 1: Retone de tokens em `globals.css`

**Files:**
- Modify: `web/src/app/globals.css`

**Interfaces:**
- Produces: `--accent-400`/`--accent-500`/`--accent-glow` (novos valores, dois temas), `--radius-lg`/`--radius-xl` (0.75rem), `--radius-hero` (1rem, novo), `--card-shadow` (novo, tema-dependente), classe `.hero-gradient` (nova). Task 2 consome `--radius-hero` (via utilitário Tailwind `rounded-hero`, gerado automaticamente por estar dentro do bloco `@theme`) e a classe `.hero-gradient`.

- [ ] **Step 1: Trocar o bloco de radius dentro de `@theme`**

Em `web/src/app/globals.css`, localizar (dentro do bloco `@theme`, por volta da linha 92):
```css
  /* Card corner language: every `rounded-lg`/`rounded-xl` card (both used
     app-wide for the same bordered-panel element, inconsistently) now
     matches the instrument panel's own 6px radius exactly. One radius. */
  --radius-lg: 0.375rem;
  --radius-xl: 0.375rem;
```
Substituir por:
```css
  /* Card corner language: every `rounded-lg`/`rounded-xl` card (both used
     app-wide for the same bordered-panel element, inconsistently) matches
     the panel's radius exactly. Revisado na Fase 1 da renovação de UX
     (2026-08-07, era 0.375rem/6px — ver
     docs/superpowers/specs/2026-08-07-ux-renovacao-fase1-fundacao-design.md).
     --radius-hero e' usado por um unico instrumento em destaque (ver
     dashboard/page.tsx), nao um padrao geral de card. */
  --radius-lg: 0.75rem;
  --radius-xl: 0.75rem;
  --radius-hero: 1rem;
```

- [ ] **Step 2: Trocar o accent do tema escuro (`:root`)**

Localizar (por volta da linha 128):
```css
  /* Signature accent — an instrument-glass cyan, never the stock SaaS indigo. */
  --accent-400: #5fd4ff;
  --accent-500: #2fb8f0;
  --accent-glow: rgba(95, 212, 255, 0.16);
```
Substituir por:
```css
  /* Signature accent — instrument-glass green (Fase 1 da renovacao de UX,
     2026-08-07 — era cyan #5fd4ff/#2fb8f0). Deliberadamente distinto de
     --status-ok (#34d399) mesmo os dois na familia verde: accent e'
     identidade/navegacao, status e' semantica de sucesso. */
  --accent-400: #22c088;
  --accent-500: #159467;
  --accent-glow: rgba(34, 192, 136, 0.18);
  --card-shadow: none;
```

- [ ] **Step 3: Trocar o accent do tema claro (`[data-theme="light"]`)**

Localizar (por volta da linha 235):
```css
  --accent-400: #0e7490;
  --accent-500: #155e75;
  --accent-glow: rgba(14, 116, 144, 0.14);
```
Substituir por:
```css
  --accent-400: #0f8a5f;
  --accent-500: #0b6b49;
  --accent-glow: rgba(15, 138, 95, 0.14);
  --card-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
```

- [ ] **Step 4: Fazer `.instrument` consumir o token de radius e o novo `--card-shadow`**

Localizar (por volta da linha 340, seção "A dedicated readout"):
```css
.instrument {
  background: var(--panel-850);
  border: 1px solid var(--panel-border);
  border-radius: 6px;
  position: relative;
}
```
Substituir por:
```css
.instrument {
  background: var(--panel-850);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--card-shadow);
  position: relative;
}
```
(`.instrument-lit` mantém seu próprio `box-shadow` sem mudança — ele já sobrescreve o de `.instrument` por ordem no arquivo, isso é esperado e não deve ser alterado.)

- [ ] **Step 5: Adicionar a classe `.hero-gradient`**

Logo depois do bloco `.instrument-hover` (por volta da linha 368, antes da seção "Cross-cutting surface utilities"), adicionar:
```css
/* Instrumento em destaque — reservado a UM unico card por tela (ver
   dashboard/page.tsx). Nao e' um padrao geral de card, e' a abertura
   visual do painel. Fase 1 da renovacao de UX, 2026-08-07. */
.hero-gradient {
  background: linear-gradient(135deg, var(--accent-400), var(--accent-500));
  border: none;
  color: #ffffff;
}
```

- [ ] **Step 6: Verificar visualmente**

```bash
cd web && npm run dev
```
Abrir `http://localhost:3000/dashboard` (ou a porta que subir), confirmar que o dot da marca na sidebar e o item de navegação ativo já aparecem verdes (não cyan). Clicar no toggle sun/moon e confirmar que o tema claro também troca pra verde, sem quebrar contraste. (`.hero-gradient` ainda não é usada por nenhum componente até a Task 2 — nada renderiza gradiente ainda, isso é esperado.)

- [ ] **Step 7: Commit**

```bash
git add web/src/app/globals.css
git commit -m "feat: retona tokens de cor pra accent verde, raio maior e sombra em tema claro"
```

---

### Task 2: Piloto — instrumento hero em `/dashboard`

**Files:**
- Modify: `web/src/app/dashboard/page.tsx`

**Interfaces:**
- Consumes: classe `.hero-gradient` e utilitário `rounded-hero` (Task 1).

- [ ] **Step 1: Adicionar a prop `hero` a `PrimaryInstrument`**

Em `web/src/app/dashboard/page.tsx`, localizar (linhas 33-45):
```tsx
function PrimaryInstrument({ label, value, status, trend }: { label: string; value: string; status?: Status; trend?: string }) {
  const color = status ? STATUS_COLOR[status] : "var(--ink-100)";
  return (
    <div className="instrument instrument-lit px-5 py-4 flex-1 min-w-[200px]">
      <div className="flex items-center justify-between">
        <div className="text-[10px] uppercase tracking-[0.12em]" style={{ color: "var(--ink-500)" }}>{label}</div>
        {status && <span aria-hidden className="w-1.5 h-1.5 rounded-full" style={{ background: color, boxShadow: `0 0 6px ${color}` }} />}
      </div>
      <div className="numeric text-[28px] leading-tight font-medium mt-1.5" style={{ color }}>{value}</div>
      {trend && <div className="text-[11px] mt-1" style={{ color: "var(--ink-700)" }}>{trend}</div>}
    </div>
  );
}
```
Substituir por:
```tsx
function PrimaryInstrument({ label, value, status, trend, hero }: { label: string; value: string; status?: Status; trend?: string; hero?: boolean }) {
  const color = hero ? "#ffffff" : status ? STATUS_COLOR[status] : "var(--ink-100)";
  return (
    <div className={hero ? "hero-gradient rounded-hero px-5 py-4 flex-1 min-w-[200px]" : "instrument instrument-lit px-5 py-4 flex-1 min-w-[200px]"}>
      <div className="flex items-center justify-between">
        <div className="text-[10px] uppercase tracking-[0.12em]" style={{ color: hero ? "rgba(255,255,255,0.85)" : "var(--ink-500)" }}>{label}</div>
        {status && !hero && <span aria-hidden className="w-1.5 h-1.5 rounded-full" style={{ background: color, boxShadow: `0 0 6px ${color}` }} />}
      </div>
      <div className="numeric text-[28px] leading-tight font-medium mt-1.5" style={{ color }}>{value}</div>
      {trend && <div className="text-[11px] mt-1" style={{ color: hero ? "rgba(255,255,255,0.75)" : "var(--ink-700)" }}>{trend}</div>}
    </div>
  );
}
```

- [ ] **Step 2: Aplicar `hero` só em "Vendas hoje"**

Localizar (linha 137):
```tsx
        <PrimaryInstrument label="Vendas hoje" value={fmtBRL(dash.vendasDia)} status="ok" trend={`${dash.vendasQtd} pedido${dash.vendasQtd === 1 ? "" : "s"}`} />
```
Substituir por:
```tsx
        <PrimaryInstrument label="Vendas hoje" value={fmtBRL(dash.vendasDia)} status="ok" trend={`${dash.vendasQtd} pedido${dash.vendasQtd === 1 ? "" : "s"}`} hero />
```
As outras duas chamadas de `PrimaryInstrument` (linhas 138 e 139-143, "Vendas do mês" e "Fluxo de caixa") **não** mudam — continuam sem a prop `hero`.

- [ ] **Step 3: Verificar tipos**

```bash
cd web && npx tsc --noEmit
```
Expected: sem erros.

- [ ] **Step 4: Verificar visualmente nos dois temas**

Com o dev server rodando (Task 1, Step 6), abrir `/dashboard`. Confirmar: "Vendas hoje" aparece com fundo em gradiente verde, texto branco legível, os outros dois instrumentos primários continuam no estilo padrão (não-gradiente). Alternar o toggle de tema e confirmar que o card hero continua legível no claro (fundo verde mais escuro nesse tema, texto branco deve continuar com bom contraste).

Se houver acesso a ferramenta de browser automatizado (ex. Playwright MCP), tirar um screenshot de `/dashboard` em cada tema e conferir visualmente em vez de só descrever.

- [ ] **Step 5: Commit**

```bash
git add web/src/app/dashboard/page.tsx
git commit -m "feat: aplica instrumento hero-gradient em Vendas hoje no Dashboard"
```

---

### Task 3: Restaurar e atualizar `DESIGN.md`

**Files:**
- Create: `DESIGN.md` (restaura um arquivo deletado da working tree, não commitado — `git show HEAD:DESIGN.md` tem o conteúdo original)

**Interfaces:**
- Nenhuma — é documentação, não é importado por código.

- [ ] **Step 1: Criar `DESIGN.md` com o conteúdo abaixo (já incorpora as revisões da Fase 1)**

```markdown
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
  accent-400: "#22c088"
  accent-500: "#159467"
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
- **Instrument Green** (`#22c088` / dim `#159467`; tema claro: `#0f8a5f` / dim `#0b6b49`): accent único do sistema. Usado em item de navegação ativo, indicador de sistema operando, foco de link, e no tratamento hero-gradient (ver Overview). Deliberadamente distinto de `status-ok` (`#34d399` escuro / `#047857` claro) mesmo os dois na família verde — accent é identidade/navegação, status é semântica de sucesso. Nunca usado para decoração fora desses papéis — sua raridade é o ponto. (Revisado na Fase 1 da renovação de UX, 2026-08-07 — era cyan `#5fd4ff`/`#2fb8f0`.)

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

Duas zonas fixas: sidebar de navegação (`<aside>`) e área de conteúdo (`<main>`). Em desktop (`sm:` e acima, ≥640px) a sidebar é `relative`, ocupando 240px expandida ou 56px recolhida, sempre visível. Em mobile, a sidebar é `fixed inset-y-0 left-0`, fora da tela por padrão (`-translate-x-full`) e desliza para dentro sobre um backdrop escurecido ao abrir pelo botão hamburger — nunca ocupa espaço no fluxo do documento nesse breakpoint. O conteúdo principal usa grid responsivo: instrumentos primários em 3 colunas no desktop, empilhados em 1 coluna no mobile; instrumentos secundários em grid de 2 colunas no mobile, 6 no desktop. `<main>` não tem `max-width` — o conteúdo ocupa a área total disponível; telas com `max-w-*` no wrapper raiz são drift, não uma decisão documentada (achado corrigido na Fase 1 da renovação de UX, 2026-08-07, em 9 telas do módulo Integrações/Shopee + `roles`).

A navegação é agrupada em seis zonas nomeadas e fixas — Operação, Vendas, Catálogo & Estoque, Financeiro & Fiscal, Inteligência, Administração — cada uma com um rótulo de seção em maiúsculas. A ordem e composição das zonas não muda entre telas; é o mapa mental fixo do cockpit.

## Elevation & Depth

Sistema é majoritariamente flat com leve profundidade tonal: instrumentos usam uma face mais clara (`panel-850`) sobre o fundo (`panel-950`/`panel-900`), delimitada por borda de 1px. No tema escuro, nunca sombra projetada. No tema claro (Fase 1 da renovação de UX, 2026-08-07), uma sombra suave e única (`--card-shadow: 0 1px 3px rgba(0,0,0,0.06)`) foi adicionada a todo `.instrument` — sem ela, cards claros sobre fundo quase-branco perdem a separação visual que a borda sozinha resolve bem no escuro mas não em luz de dia.

### Shadow Vocabulary
- **Instrument inset** (`box-shadow: inset 0 1px 0 rgba(255,255,255,0.03)`): reflexo raso de vidro dentro de todo `.instrument`, sempre presente nos dois temas — não é sombra de elevação Material, é o brilho da própria vidraça.
- **Instrument-lit halo** (`box-shadow: 0 0 0 1px var(--panel-border-lit), 0 8px 20px -12px rgba(0,0,0,0.6)`): halo externo reservado a `.instrument-lit`, usado só em estados de destaque/foco, sem mudança entre temas.
- **Card shadow** (`box-shadow: var(--card-shadow)`, só tema claro): sombra suave e única em todo `.instrument` no tema claro. `none` no tema escuro.

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
- **Don't** limitar a largura do conteúdo principal com `max-w-*` — use a área total disponível (padrão já seguido por Dashboard/Vendas/Estoque/PDV/Produtos).
```

- [ ] **Step 2: Commit**

```bash
git add DESIGN.md
git commit -m "docs: restaura e atualiza DESIGN.md com accent verde, raio 12/16px e sombra em tema claro"
```

---

### Task 4: Corrigir `max-w-*` nas 9 telas

**Files:**
- Modify: `web/src/app/integracoes/page.tsx:42`
- Modify: `web/src/app/integracoes/hermes/page.tsx:22`
- Modify: `web/src/app/integracoes/shopee/page.tsx:207`
- Modify: `web/src/app/integracoes/shopee/dashboard/page.tsx:287`
- Modify: `web/src/app/integracoes/shopee/pedidos/page.tsx:180`
- Modify: `web/src/app/integracoes/shopee/produtos/page.tsx:343`
- Modify: `web/src/app/integracoes/shopee-ads/page.tsx:19`
- Modify: `web/src/app/roles/page.tsx:75`

**Interfaces:**
- Nenhuma — mudança isolada de classe CSS por arquivo, sem interface entre eles.

- [ ] **Step 1: Remover a constraint de largura de cada arquivo**

Linhas confirmadas por leitura direta (não inferidas) — aplicar exatamente estas 8 trocas:

`web/src/app/integracoes/page.tsx:42`, de:
```tsx
    <div className="p-6 space-y-6 max-w-4xl">
```
para:
```tsx
    <div className="p-6 space-y-6">
```

`web/src/app/integracoes/hermes/page.tsx:22`, de:
```tsx
    <div className="p-6 space-y-6 max-w-4xl">
```
para:
```tsx
    <div className="p-6 space-y-6">
```

`web/src/app/integracoes/shopee/page.tsx:207`, de:
```tsx
    <div className="p-6 space-y-6 max-w-3xl">
```
para:
```tsx
    <div className="p-6 space-y-6">
```

`web/src/app/integracoes/shopee/dashboard/page.tsx:287`, de:
```tsx
    <div className="p-6 space-y-4 max-w-5xl">
```
para:
```tsx
    <div className="p-6 space-y-4">
```

`web/src/app/integracoes/shopee/pedidos/page.tsx:180`, de:
```tsx
    <div className="p-6 space-y-4 max-w-5xl">
```
para:
```tsx
    <div className="p-6 space-y-4">
```

`web/src/app/integracoes/shopee/produtos/page.tsx:343`, de:
```tsx
    <div className="p-6 space-y-5 max-w-6xl">
```
para:
```tsx
    <div className="p-6 space-y-5">
```

`web/src/app/integracoes/shopee-ads/page.tsx:19`, de:
```tsx
    <div className="p-6 space-y-6 max-w-4xl">
```
para:
```tsx
    <div className="p-6 space-y-6">
```

`web/src/app/roles/page.tsx:75` (único com `mx-auto` junto — remover os dois), de:
```tsx
    <div className="p-6 max-w-6xl mx-auto space-y-4">
```
para:
```tsx
    <div className="p-6 space-y-4">
```

- [ ] **Step 2: Verificar tipos**

```bash
cd web && npx tsc --noEmit
```
Expected: sem erros (é só remoção de classe string, não deveria quebrar tipo nenhum — rodar mesmo assim, é rápido e pega erro de digitação acidental no className).

- [ ] **Step 3: Verificar visualmente pelo menos 2 das 9 telas**

Com o dev server rodando, abrir `/integracoes/shopee/dashboard` e `/roles` (as duas com layout mais denso) e confirmar que o conteúdo agora ocupa a largura total da tela.

- [ ] **Step 4: Rodar a suíte E2E existente**

```bash
cd web && npm run test:e2e
```
Expected: nenhum teste depende de largura/classe específica dessas páginas (confirmar que nada quebrou; se algo depender de `max-w-*` removido, investigar antes de seguir).

- [ ] **Step 5: Commit**

```bash
git add web/src/app/integracoes/page.tsx web/src/app/integracoes/hermes/page.tsx web/src/app/integracoes/shopee/page.tsx web/src/app/integracoes/shopee/dashboard/page.tsx web/src/app/integracoes/shopee/pedidos/page.tsx web/src/app/integracoes/shopee/produtos/page.tsx web/src/app/integracoes/shopee-ads/page.tsx web/src/app/roles/page.tsx
git commit -m "fix: remove max-w-* das telas de Integrações/Shopee e Roles, alinha com padrão full-width"
```
