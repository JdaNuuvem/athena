# DESIGN.md — Athena OS / Hermes Agent Swarm

## Identity

Industrial operational dashboard. Dark by ergonomic necessity (8h+ sessions, variable ambient light on factory floors). Dense by design — every pixel earns its place. Visual language derived from Bloomberg Terminal and Grafana: functional color, no ornament.

---

## Color System

Uses Tailwind v4 default scale. No custom tokens currently defined.

### Surfaces

| Role | Token | Hex | Usage |
|---|---|---|---|
| Body | `neutral-950` | `#0a0a0a` | Page background |
| Card | `neutral-900` | `#171717` | Panel, table, form surface |
| Elevated | `neutral-800` | `#262626` | Borders, dividers, hover states, secondary buttons |
| Muted bg | `neutral-800/30` | `#262626` 30% | Row hover on tables |

### Text

| Role | Token | Usage |
|---|---|---|
| Primary | `neutral-200` | Main content, headings, values |
| Secondary | `neutral-300` | Sub-headings, field values with moderate weight |
| Tertiary | `neutral-400` | Labels, section headers, secondary data |
| Muted | `neutral-500` | Timestamps, IDs, loading states |
| Faint | `neutral-600` | Placeholder text, disabled labels |

### Accent

| Role | Token | Usage |
|---|---|---|
| Interactive | `indigo-600` | Primary buttons, focus rings |
| Active bg | `indigo-600/20` | Active nav item background |
| Active text | `indigo-300` | Active nav item label |
| Data accent | `indigo-400` | SKU codes, IDs in monospace |

### Semantic — operational states only, no decorative color

| State | Token | Usage |
|---|---|---|
| Healthy / running | `green-400` / `green-500` | Agent status dots, success badges |
| Warning / idle | `yellow-400` / `yellow-500` | Attention states, pending status |
| Critical / error | `red-400` / `red-500` | Errors, critical alerts, status dots |
| Error bg | `red-950/40` | Error message container background |

**Rule:** Color appears only when it carries operational meaning. No decorative color, no gradient fills, no colored section backgrounds.

---

## Typography

No custom fonts. System stack for zero-latency render on factory hardware.

```
font-family: ui-sans-serif, system-ui, -apple-system, sans-serif
font-family (data): ui-monospace, SFMono-Regular, Menlo, monospace
```

### Scale

| Class | Size | Usage |
|---|---|---|
| `text-[10px]` | 10px | Table column headers (uppercase + tracking), role labels, unit labels |
| `text-xs` | 12px | Secondary metadata, agent IDs, timestamps, badge text |
| `text-sm` | 14px | Body default, nav items, table cell content, button labels |
| `text-base` | 16px | Nav icons (symbolic characters) |
| `text-lg` | 18px | Page titles (`font-light`) |

### Conventions

- Page titles: `text-lg font-light text-neutral-300`
- Section headers: `text-sm font-medium text-neutral-400 uppercase tracking-wider`
- Table headers: `text-[10px] uppercase tracking-wider text-neutral-500 font-medium`
- Numeric / code data: `font-mono text-xs` (or `font-mono text-sm`)
- SKU / ID values: `font-mono text-xs text-indigo-400`
- Minimum body font: 12px (per accessibility requirement for industrial environments)

---

## Spacing

4px base grid. Tailwind default scale — `p-1` = 4px.

| Context | Value |
|---|---|
| Page padding | `p-6` (24px) |
| Section gap | `space-y-6` (24px) |
| Card padding (standard) | `p-4` (16px) |
| Card padding (compact) | `p-3` (12px) |
| Table cell | `p-3` (12px) horizontal + vertical |
| Grid gap (cards) | `gap-4` (16px) |
| Grid gap (compact) | `gap-3` (12px) |
| Nav item | `px-3 py-2` |
| Section header bottom margin | `mb-3` (12px) |

### Border radius

- Cards, panels, buttons, inputs: `rounded-lg` (8px)
- Status dots: `rounded-full`
- Small badges: `rounded` (4px)

---

## Components

### Sidebar

```
width: w-56 (224px) open / w-14 (56px) collapsed
bg: neutral-900
border-right: border-r border-neutral-800
transition: transition-all duration-200
```

- Header: logo/wordmark `ATHENA` in `font-semibold text-sm tracking-wide`, toggle button
- Nav items: `flex items-center gap-3 px-3 py-2 rounded-lg text-sm`
  - Default: `text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800`
  - Active: `bg-indigo-600/20 text-indigo-300`
  - Icons: Unicode symbols (⊞ ◈ ◇ ⇄ ▤ ⚙ ↔) — `text-base w-5 text-center`
- Footer: user name + role, logout link. Collapsed: icon-only logout.

### Cards / Panels

```
bg-neutral-900 border border-neutral-800 rounded-lg
```

- KPI card (single metric): `p-3`, label in `text-xs text-neutral-500`, value in `text-2xl font-semibold`
- Section panel: `overflow-hidden` when contains table (removes double border at edges)
- Agent card: status dot + id + name + role + task count

### Tables

```
w-full text-sm
container: bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden
```

- Header row: `border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider`
- Header cell: `text-left p-3 font-medium` (right-align for numbers)
- Body row: `border-b border-neutral-800/50 last:border-0 hover:bg-neutral-800/30`
- Body cell: `p-3 text-neutral-300` (or `text-neutral-200` for primary value)
- Numeric cells: `text-right`

### Buttons

| Variant | Classes |
|---|---|
| Primary | `bg-indigo-600 hover:bg-indigo-700 text-white text-sm px-4 py-2 rounded-lg transition-colors` |
| Secondary | `bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-sm px-4 py-2 rounded-lg transition-colors` |
| Danger | `bg-red-600 hover:bg-red-700 text-white text-sm px-4 py-2 rounded-lg transition-colors` |
| Ghost | `text-neutral-400 hover:text-neutral-200 text-sm transition-colors` |

### Form Inputs

```
bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200
focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-transparent
placeholder:text-neutral-600
```

### Status Indicators

Status dot (agent, connection, health):
```
w-2 h-2 rounded-full
running → bg-green-500
idle    → bg-yellow-500
error   → bg-red-500
```

Badge (text label):
```
text-xs px-2 py-0.5 rounded font-medium
success → bg-green-500/20 text-green-400
warning → bg-yellow-500/20 text-yellow-400
error   → bg-red-500/20 text-red-400
neutral → bg-neutral-800 text-neutral-400
```

---

## Layout Patterns

### Page shell

```
body: bg-neutral-950 text-neutral-100 min-h-screen flex
sidebar: fixed left, shrink-0
main: flex-1 overflow-auto
page content: p-6 space-y-6
```

### KPI grid

```
grid grid-cols-2 md:grid-cols-4 gap-4
```

### Agent grid

```
grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3
```

### Integration tabs

Tab bar at the top of integration pages with horizontal nav. Active tab distinguished by indigo underline or fill.

---

## States

### Loading

```tsx
<div className="p-6 text-neutral-500">Carregando...</div>
```

For inline sections, centered spinner or skeleton rows with `bg-neutral-800 animate-pulse rounded`.

### Empty state

```tsx
<div className="bg-neutral-900 border border-neutral-800 rounded-lg p-8 text-center">
  <p className="text-neutral-500">Sem dados disponíveis</p>
</div>
```

### Error state

```tsx
<div className="bg-red-950/40 border border-red-800 rounded-lg p-4">
  <p className="text-red-400 text-sm">{errorMessage}</p>
</div>
```

### Success feedback

Inline `text-green-400 text-sm` or toast (not yet implemented — pattern TBD).

---

## Motion

Minimal and purposeful. Factory operators don't need animation — they need information.

| Transition | Value | Usage |
|---|---|---|
| Interactive (hover, focus) | `transition-colors duration-150` | Buttons, nav items, table rows |
| Sidebar toggle | `transition-all duration-200` | Width collapse |
| Default easing | `ease-out` | All transitions |

`prefers-reduced-motion`: replace all transitions with instant state change (no `duration` or `transition` classes). Not yet implemented via CSS variable — future: `@media (prefers-reduced-motion: reduce) { *, *::before, *::after { transition-duration: 0.01ms !important; } }` in globals.css.

---

## Accessibility

Target: WCAG AA, AAA where achievable.

- Primary text (`neutral-200` on `neutral-950`): contrast ~13.5:1 ✓ AAA
- Secondary text (`neutral-400` on `neutral-950`): contrast ~5.9:1 ✓ AA
- Indigo-300 on indigo-600/20 (active nav): passes AA at 14px
- Minimum font size: 12px (text-xs) — no text below this threshold
- Status always paired with label or icon — never color alone
- Focus ring: `focus:ring-2 focus:ring-indigo-600` on all interactive elements
- Keyboard navigation: full keyboard access on all forms and nav (enforced by semantic HTML — `<a>`, `<button>`, `<input>`)

---

## Decisions & Rationale

**Dark mode is not aesthetic — it's ergonomic.** Operators in variable-light industrial environments + 8h sessions. High contrast on dark surface reduces eye strain and glare.

**No custom fonts.** System fonts render instantly on any device. Factory hardware may have restricted web access or slow connections.

**Unicode symbols for icons.** No icon library dependency. Symbols (⊞ ◈ ◇ ⇄ ▤ ⚙ ↔) render consistently, load with zero bytes.

**Indigo as sole accent.** One accent color = unambiguous signal. Every indigo element is interactive or data-active. Semantic colors (green/yellow/red) communicate operational state only.

**`font-light` page titles.** Heavy headers feel like reporting UIs. Light weight reads as operational output — system-generated, not branded.
