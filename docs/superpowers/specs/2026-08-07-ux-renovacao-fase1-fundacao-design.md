# Renovação de UX — Fase 1: Fundação (tokens + shell + piloto) — Design

Data: 2026-08-07

## Contexto

Pedido original: "renovar o UX" do sistema, motivado por duas queixas concretas — (1) várias telas não usam a largura total da tela, sobrando espaço morto; (2) o visual em geral está datado, com o Finexy (template de fintech, claro, verde, cards generosos) como referência de acabamento.

Investigação encontrou:
- **O desperdício de largura não é sistêmico.** `web/src/app/layout.tsx:414` (`<main className="flex-1 overflow-auto min-w-0">`) não tem nenhuma constraint. O problema está em **9 arquivos específicos** que envolvem o conteúdo inteiro num `max-w-*` — o cluster completo de Integrações/Shopee mais `roles/page.tsx` — enquanto os módulos "core" (Dashboard, Vendas, Estoque, PDV, Produtos) já são full-width. Lista completa na seção Componentes.
- **A infraestrutura de tema claro/escuro já existe e já funciona.** `web/src/lib/theme-context.tsx` (`ThemeProvider`/`useTheme()`), script anti-flash inline em `layout.tsx:17`, botão sun/moon já ativo na sidebar (`layout.tsx:206`), `chartAxisColors()` para os gráficos Recharts, paleta completa em `web/src/app/globals.css` para `:root` (escuro) e `[data-theme="light"]` (claro). Nada disso precisa ser construído — só **retonado**.
- O sistema de design atual (`DESIGN.md`, recuperado do histórico do git — está deletado da working tree sem commit) documenta um accent cyan único, raio de 6px ("One Radius Rule"), e proíbe drop-shadow (profundidade só por camada tonal). A direção visual aprovada nesta sessão (ver decisão abaixo) revisa deliberadamente essas três regras.

## Decisão de direção visual

Testado com mockups interativos (companion visual): duas direções foram comparadas — "Instrument Panel Refinado" (evolui o cyan/preto atual) vs "Fintech Fresh" (accent verde, cards mais arredondados, hero em gradiente, inspirado no Finexy). **Direção B (Fintech Fresh) aprovada.** Tema padrão de abertura: **escuro** (já é o fallback atual do script anti-flash — sem mudança de comportamento aí).

## Decomposição do projeto maior

- **Fase 1 (este documento):** retonar os tokens de cor (accent verde, 2 temas), ajustar radius e sombra, aplicar no shell (sidebar/topo) + `/dashboard` como piloto, corrigir o bug de `max-w-*` nos 9 arquivos, atualizar `DESIGN.md`.
- **Fases futuras (fora de escopo aqui):** aplicar o padrão validado nas ~130 telas restantes, módulo por módulo (Vendas/PDV, Estoque, Produtos, Shopee/Integrações, Financeiro/Fiscal, Atendimento/Chat, Admin), cada uma com seu próprio spec.

## Arquitetura

Nenhuma peça nova de mecanismo — só retonar valores em `web/src/app/globals.css`, que já é a fonte única de verdade (todo o app consome cor via `var(--panel-*)`, `var(--ink-*)`, `var(--accent-*)`, `var(--status-*)` ou via classes Tailwind retemadas pelo bloco `@theme`). Como o retone é 100% orientado a token, **a cor e o raio novos se propagam para as 137 telas automaticamente** assim que `globals.css` muda — isso não é escopo extra, é como a arquitetura já funciona. O que fica restrito ao piloto (`/dashboard`) é o *padrão de composição novo* (card hero em gradiente) — as outras 136 telas recebem a cor/raio novos hoje, mas continuam com a composição atual até sua própria fase.

## Componentes

### 1. `web/src/app/globals.css` — retone de tokens

**Accent (troca cyan → verde, nos dois temas):**
```css
/* :root (escuro) — era --accent-400: #5fd4ff / --accent-500: #2fb8f0 */
--accent-400: #22c088;
--accent-500: #159467;
--accent-glow: rgba(34, 192, 136, 0.18);

/* [data-theme="light"] — era --accent-400: #0e7490 / --accent-500: #155e75 */
--accent-400: #0f8a5f;
--accent-500: #0b6b49;
--accent-glow: rgba(15, 138, 95, 0.14);
```
Deliberadamente **diferente** de `--status-ok` (`#34d399` escuro / `#047857` claro) — accent é identidade/navegação, status é semântica de sucesso; DESIGN.md já separa os dois papéis, o retone preserva essa regra mesmo os dois ficando na família verde.

**Radius (revisa a "One Radius Rule" de 6px):**
```css
/* dentro do bloco @theme — eram 0.375rem (6px) nos dois */
--radius-lg: 0.75rem;  /* 12px — card padrão */
--radius-xl: 0.75rem;
```
Mais um token novo, fora do `@theme` (não é um alias Tailwind, é consumido só pela classe `.hero-gradient` abaixo):
```css
--radius-hero: 1rem; /* 16px — só o card hero */
```

**Sombra em tema claro (revisa "sem drop-shadow"; só no claro — no escuro continua zero, por camada tonal, sem mudança):**
```css
[data-theme="light"] {
  /* ...tokens existentes... */
  --card-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}
:root {
  --card-shadow: none; /* escuro: sem sombra, como já era */
}
.instrument {
  /* adiciona ao lado do box-shadow inset já existente em .instrument::before */
  box-shadow: var(--card-shadow);
}
```

**Classe nova `.hero-gradient`** (card de destaque — usada só pelo `PrimaryInstrument` "Vendas hoje" do piloto nesta fase):
```css
.hero-gradient {
  background: linear-gradient(135deg, var(--accent-400), var(--accent-500));
  border-radius: var(--radius-hero);
  border: none;
  color: #ffffff;
}
```

### 2. `web/src/app/dashboard/page.tsx` — piloto

`PrimaryInstrument` (`dashboard/page.tsx:33-45`) ganha uma prop `hero?: boolean`. Quando `true` (só na primeira chamada, "Vendas hoje", linha 137), troca a classe `instrument instrument-lit` por `hero-gradient`, e os textos internos (label/valor/trend) passam a usar branco/branco-translúcido em vez de `var(--ink-*)` (o gradiente já é escuro o bastante nos dois temas pra não precisar de tratamento condicional por tema). As outras duas `PrimaryInstrument` (Vendas do mês, Fluxo de caixa) e todas as `SecondaryInstrument` continuam com a mesma estrutura — herdam cor/raio novos automaticamente, sem mudança de código além do CSS acima.

### 3. Sidebar/shell (`web/src/app/layout.tsx`)

Nenhuma mudança de código — o botão de toggle (`layout.tsx:206`), o dot de marca (`layout.tsx:200`, usa `var(--accent-400)`) e os destaques de item ativo (`var(--accent-glow)`) já são 100% orientados a token. Validar visualmente após o retone que o contraste do texto sobre `--accent-glow` continua legível nos dois temas (checagem manual, não é código).

### 4. Correção do `max-w-*` (bug de largura)

Remover a constraint de largura do wrapper raiz nestes 9 arquivos, alinhando com o padrão full-width já usado por dashboard/vendas/estoque/pdv/produtos:
- `web/src/app/integracoes/page.tsx:42` (`max-w-4xl`)
- `web/src/app/integracoes/hermes/page.tsx:22` (`max-w-4xl`)
- `web/src/app/integracoes/shopee/page.tsx:207` (`max-w-3xl`)
- `web/src/app/integracoes/shopee/dashboard/page.tsx:287` (`max-w-5xl`)
- `web/src/app/integracoes/shopee/pedidos/page.tsx:180` (`max-w-5xl`)
- `web/src/app/integracoes/shopee/produtos/page.tsx:343` (`max-w-6xl`)
- `web/src/app/integracoes/shopee-ads/page.tsx:19` (`max-w-4xl`)
- `web/src/app/roles/page.tsx:75` (`max-w-6xl mx-auto`)

Grids internos de cada página (já usam `grid-cols-*` responsivo, ver investigação) não precisam de reestruturação — só o wrapper raiz muda.

### 5. `DESIGN.md`

Restaurar (`git show HEAD:DESIGN.md`) e atualizar as seções de cor (accent verde), raio (12px/16px hero) e sombra (permitida em tema claro, token `--card-shadow`) para refletir o novo estado. Demais seções (tipografia, mono tabular, layout de duas zonas) continuam válidas, sem mudança.

## Fluxo de dados

Não há fluxo de dados novo — é CSS/tema estático, sem chamada de API nem estado de servidor. O único estado é o `theme` já existente em `ThemeProvider` (client-side, localStorage), inalterado nesta fase.

## Erros

- Nenhum caso de erro novo — não há rede, não há validação de input. Risco real é visual (contraste ruim em algum estado específico), coberto pela verificação manual abaixo, não por tratamento de erro em código.

## Testes

Sem lógica nova testável via unit/E2E (é retone de CSS + troca de 2 classes numa página). Verificação:
- `npx tsc --noEmit` limpo após as mudanças em `dashboard/page.tsx`.
- Smoke visual manual: abrir `/dashboard` nos dois temas, confirmar card hero legível, confirmar toggle continua funcionando, confirmar as 9 páginas de Integrações/Shopee + `roles` agora ocupam a largura total.
- Rodar a suíte Playwright existente (`npm run test:e2e`) pra garantir que nenhum teste depende de uma classe/cor específica que mudou (nenhum encontrado na investigação, mas confirmar).

## Fora de escopo nesta fase

- As ~130 telas restantes do app (ficam para fases futuras, módulo por módulo).
- Padrão de "chip" de ícone colorido nos cards secundários, mostrado no mockup — não tem um lugar natural na estrutura atual de `SecondaryInstrument` (sem slot de ícone, exigiria mapear um ícone por métrica) e não é necessário pra validar a direção visual. Deliberadamente adiado, não esquecido — entra numa fase futura se fizer sentido quando o padrão for replicado nas outras telas.
- Restyle do componente compartilhado `KpiCard.tsx` (usado por Vendas e outras telas) para ganhar tratamento hero/chip — ele já herda cor/raio novos automaticamente via classes Tailwind retemadas; a composição nova fica restrita ao piloto.
- Qualquer ajuste de RBAC, dado ou lógica de negócio — é puramente visual.
