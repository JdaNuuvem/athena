# Product

## Register

product

## Platform

web

## Users

Operadores de fábrica (chão de produção, ambientes com variação de luz, sessões longas), donos de negócio (decisões estratégicas via relatórios dos agentes) e equipe de vendas (acompanhamento de pedidos Telegram/WhatsApp e lojas físicas). Mercado SMB brasileiro. Usuários fluentes em ferramentas operacionais — não são engenheiros, mas cobram precisão das informações.

## Product Purpose

Hermes Agent Swarm / Athena OS é uma plataforma de gestão industrial multi-agente: 14 agentes AI especializados (produção, marketplaces, qualidade, manutenção, financeiro, vendas digitais) que operam como um diretor de operações digital. O produto existe para que uma fábrica de manufatura tome decisões melhores mais rápido — qual produto fabricar, onde está perdendo margem, qual molde precisa de manutenção — sem precisar consolidar dados manualmente de múltiplos sistemas.

Sucesso: o operador abre o dashboard e toma uma decisão sem precisar abrir mais nenhuma outra tela.

## Brand Personality

Preciso · Industrial · Confiável

Tom: consultor sênior que fala com dados, não com entusiasmo. Sem hype, sem tech buzzwords, sem "potencialize seus resultados". Respostas diretas, números visíveis, estado do sistema sempre claro.

Referências de feel: Bloomberg Terminal (densidade máxima de dados, cor funcional), Grafana (dark mode operacional, sem ornamento).

## Anti-references

- Dashboards SaaS genéricos: gradiente roxo, cream/sand background, glassmorphism, cards com ícone + texto repetidos ad infinitum
- ERP anos 2000 (SAP/Totvs visual): cinza caótico, sem hierarquia, densidade sem legibilidade
- BI corporativo padrão (PowerBI/Tableau default): azul marinho + gráficos de pizza, visual de apresentação, não de operação
- Qualquer coisa que pareça uma landing page dentro de um painel operacional

## Design Principles

1. **Dados primeiro** — a UI é um conduíte para decisões, não um showcase. Se um número importa, ele é visível sem hover ou clique.
2. **Densidade ganho** — compacto porque o trabalho exige, não para impressionar. Cada pixel de margem removida deve justificar a redução de espaço com mais informação útil.
3. **Sinal semântico** — cor carrega significado operacional exclusivo: verde=saudável, amarelo=atenção, vermelho=crítico. Nenhuma cor decorativa. Se não é estado, não é cor.
4. **Escuro por necessidade** — operadores em ambientes industriais com variação de luz, sessões de 8+ horas. Dark mode não é estética, é ergonomia.
5. **Confiança por consistência** — mesmo botão, mesmo formulário, mesmo padrão nos 14 painéis de agentes. Variação visual sem propósito cria desconfiança.

## Accessibility & Inclusion

- Alvo: WCAG AA em todo o produto, AAA onde possível (relação de contraste ≥ 7:1 para texto primário)
- Operadores em ambientes industriais com variação de iluminação: fontes não abaixo de 12px, contraste mínimo de texto primário ≥ 7:1 contra superfície
- Navegação por teclado completa em todos os formulários e modais
- `prefers-reduced-motion`: substituir animações por crossfade instantâneo
- Sem dependência de cor sozinha para transmitir estado (sempre acompanhar de ícone ou label)
