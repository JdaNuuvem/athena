import type { FastifyInstance } from 'fastify'
import { getPrisma } from '../../shared/infrastructure/persistence/prisma-client'
import { authMiddleware } from '../../shared/infrastructure/auth/middleware'

// ── tipagem inline — mantém sincronia com web/src/app/bi/types/index.ts ──

interface VendaDiaria { dia: string; valor: number; custo: number; margem: number }
interface VendaSemanal { semana: string; valor: number; ticketMedio: number; pedidos: number }
interface VendaMensal { mes: string; valor: number; custo: number; margem: number; variacaoPercent: number }
interface ProdutoVenda { nome: string; sku: string; valor: number; qtd: number; margem: number }
interface CategoriaVenda { categoria: string; valor: number; percentual: number; produtos: ProdutoVenda[] }
interface IndicadorFinanceiro { id: string; nome: string; valor: number; unidade: string; tendencia: "up"|"down"|"stable"; tendenciaValor: number; referencia: string; status: "good"|"warning"|"danger" }
interface ForecastDataPoint { periodo: string; historico?: number; previsao?: number; limiteInferior?: number; limiteSuperior?: number; sazonalidade?: number }
interface AnomalyResult { id: number; tipo: "transacao"|"estoque"|"venda"|"preco"; severidade: "critico"|"moderado"|"baixo"; descricao: string; valor: number; impacto: string; data: string; recomendacao: string }
interface CustomerSegment { segmento: string; percentual: number; receitaMedia: number; churn: number; descricao: string }
interface MLRecommendation { id: number; tipo: "cross-sell"|"upsell"|"retencao"; descricao: string; confianca: number; receitaEstimada: number; acao: string }
interface ForecastResumo {
  receitaProjetada: number; crescimentoEsperado: number; confianca: number
  cenarios: { otimista: number; esperado: number; pessimista: number }
  fatores: Array<{ nome: string; impacto: string; valor: string }>
}

// ── generators (mesma lógica do frontend, portada para o server) ──

function gerarVendasDiarias(): VendaDiaria[] {
  return Array.from({ length: 30 }, (_, i) => {
    const base = 8000 + Math.sin(i / 5) * 2500
    const variacao = (Math.random() - 0.5) * 2000
    const custoRatio = 0.45 + Math.random() * 0.15
    return { dia: String(i + 1).padStart(2, "0"), valor: Math.round(base + variacao), custo: Math.round((base + variacao) * custoRatio), margem: Math.round((1 - custoRatio) * 100) }
  })
}

function gerarVendasSemanais(): VendaSemanal[] {
  const base = 65000
  return Array.from({ length: 12 }, (_, i) => {
    const valor = Math.round(base + (Math.random() - 0.4) * 15000)
    return { semana: `S${String(i + 1).padStart(2, "0")}`, valor, ticketMedio: Math.round(180 + Math.random() * 60), pedidos: Math.round(valor / (180 + Math.random() * 50)) }
  })
}

function gerarVendasMensais(): VendaMensal[] {
  const meses = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
  const base = 280000
  return meses.map((mes, i) => {
    const sazonalidade = 1 + Math.sin((i / 12) * Math.PI * 2) * 0.15
    const tendencia = 1 + i * 0.02
    const valor = Math.round(base * sazonalidade * tendencia * (0.9 + Math.random() * 0.2))
    return { mes, valor, custo: Math.round(valor * (0.5 + Math.random() * 0.15)), margem: Math.round(100 - (50 + Math.random() * 15)), variacaoPercent: Math.round((Math.random() - 0.2) * 20) }
  })
}

function gerarCategorias(): CategoriaVenda[] {
  return [
    { categoria: "Utilidades Domésticas", valor: 87500, percentual: 31, produtos: [
      { nome:"Organizador MC-001", sku:"ORG-001", valor:45300, qtd:320, margem:38.5 },
      { nome:"Kit Presente Luxo", sku:"KIT-012", valor:29100, qtd:145, margem:28.3 },
      { nome:"Jogo de Copos Crystal", sku:"JGC-003", valor:22400, qtd:210, margem:18.7 },
      { nome:"Porta Temperos Duplo", sku:"PTD-007", valor:18700, qtd:415, margem:14.2 },
    ]},
    { categoria: "Bebidas e Térmicos", valor: 72300, percentual: 25, produtos: [
      { nome:"Garrafa Térmica Pro", sku:"GTP-001", valor:38200, qtd:280, margem:42.1 },
      { nome:"Copo Térmico 500ml", sku:"CT5-002", valor:21400, qtd:350, margem:35.4 },
      { nome:"Cooler Compacto", sku:"COL-005", valor:12700, qtd:180, margem:22.8 },
    ]},
    { categoria: "Eletrônicos", valor: 54100, percentual: 19, produtos: [
      { nome:"Mini Projetor LED", sku:"MPL-001", valor:28100, qtd:95, margem:15.3 },
      { nome:"Carregador Rápido", sku:"CRF-003", valor:16800, qtd:520, margem:28.7 },
      { nome:"Fone Bluetooth", sku:"FBT-002", valor:9200, qtd:340, margem:31.2 },
    ]},
    { categoria: "Decoração", valor: 42300, percentual: 15, produtos: [
      { nome:"Vaso Decorativo", sku:"VAS-001", valor:15300, qtd:210, margem:45.0 },
      { nome:"Quadro Abstrato", sku:"QAB-003", valor:11200, qtd:140, margem:52.1 },
      { nome:"Cortina Blackout", sku:"CBL-002", valor:15800, qtd:180, margem:33.5 },
    ]},
    { categoria: "Pet", valor: 28900, percentual: 10, produtos: [
      { nome:"Cama Pet Premium", sku:"CPP-001", valor:12400, qtd:150, margem:40.2 },
      { nome:"Comedouro Automático", sku:"CAT-002", valor:9800, qtd:95, margem:35.8 },
      { nome:"Arranhador Torre", sku:"ATR-001", valor:6700, qtd:110, margem:38.1 },
    ]},
  ]
}

function gerarForecast(diasHistoricos = 60, diasProjecao = 30): ForecastDataPoint[] {
  const pontos: ForecastDataPoint[] = []
  const base = 8500; const tendencia = 35; const sazonalidadeAmp = 1200; const periodo = 7
  for (let i = 0; i < diasHistoricos; i++) {
    const t = i
    const sazonal = Math.sin((t / periodo) * Math.PI * 2) * sazonalidadeAmp
    const noise = (Math.random() - 0.5) * 800
    const valor = base + t * tendencia + sazonal + noise
    pontos.unshift({ periodo: `D-${diasHistoricos - i}`, historico: Math.round(Math.max(0, valor)) })
  }
  for (let i = 0; i < diasProjecao; i++) {
    const t = diasHistoricos + i
    const sazonal = Math.sin((t / periodo) * Math.PI * 2) * sazonalidadeAmp
    const valor = base + t * tendencia + sazonal
    const width = 600 + i * 25
    pontos.push({
      periodo: `D+${i + 1}`,
      historico: i === 0 ? Math.round(base + (diasHistoricos - 1) * tendencia + Math.sin((diasHistoricos - 1) / periodo * Math.PI * 2) * sazonalidadeAmp) : 0,
      previsao: i === 0 ? undefined : Math.round(valor),
      limiteInferior: i === 0 ? undefined : Math.round(valor - width),
      limiteSuperior: i === 0 ? undefined : Math.round(valor + width),
    })
  }
  return pontos
}

const FORECAST_RESUMO: ForecastResumo = {
  receitaProjetada: 312450, crescimentoEsperado: 8.7, confianca: 92,
  cenarios: { otimista: 348200, esperado: 312450, pessimista: 274800 },
  fatores: [
    { nome:"Sazonalidade", impacto:"positivo", valor:"+4.2%" },
    { nome:"Tendência de Mercado", impacto:"positivo", valor:"+3.5%" },
    { nome:"Inflação", impacto:"negativo", valor:"-1.3%" },
    { nome:"Concorrência", impacto:"neutro", valor:"0%" },
  ],
}

const INDICADORES: IndicadorFinanceiro[] = [
  { id:"liquidez-corrente", nome:"Liquidez Corrente", valor:2.35, unidade:"x", tendencia:"up", tendenciaValor:0.15, referencia:"> 1.5", status:"good" },
  { id:"liquidez-seca", nome:"Liquidez Seca", valor:1.82, unidade:"x", tendencia:"up", tendenciaValor:0.08, referencia:"> 1.0", status:"good" },
  { id:"roi", nome:"ROI", valor:28.7, unidade:"%", tendencia:"up", tendenciaValor:3.2, referencia:"> 15%", status:"good" },
  { id:"roe", nome:"ROE", valor:34.5, unidade:"%", tendencia:"stable", tendenciaValor:-0.5, referencia:"> 20%", status:"good" },
  { id:"margem-bruta", nome:"Margem Bruta", valor:48.3, unidade:"%", tendencia:"down", tendenciaValor:-2.1, referencia:"> 45%", status:"warning" },
  { id:"margem-liquida", nome:"Margem Líquida", valor:18.7, unidade:"%", tendencia:"down", tendenciaValor:-1.3, referencia:"> 15%", status:"good" },
  { id:"margem-ebitda", nome:"Margem EBITDA", valor:24.5, unidade:"%", tendencia:"up", tendenciaValor:1.8, referencia:"> 20%", status:"good" },
  { id:"giro-estoque", nome:"Giro de Estoque", valor:8.2, unidade:"x/ano", tendencia:"up", tendenciaValor:0.7, referencia:"> 6.0", status:"good" },
  { id:"prazo-medio-receb", nome:"Prazo Médio Recebimento", valor:23, unidade:"dias", tendencia:"down", tendenciaValor:-3, referencia:"< 30 dias", status:"good" },
  { id:"prazo-medio-pagto", nome:"Prazo Médio Pagamento", valor:38, unidade:"dias", tendencia:"stable", tendenciaValor:1, referencia:"> 35 dias", status:"good" },
  { id:"indice-endividamento", nome:"Índice Endividamento", valor:0.42, unidade:"x", tendencia:"down", tendenciaValor:-0.03, referencia:"< 0.5", status:"good" },
  { id:"crescimento-receita", nome:"Crescimento Receita", valor:12.3, unidade:"%", tendencia:"down", tendenciaValor:-3.5, referencia:"> 10%", status:"warning" },
]

const ANOMALIAS: AnomalyResult[] = [
  { id:1, tipo:"transacao", severidade:"critico", descricao:'Transação atípica — R$ 45.200 em "Utilidades" por cliente novo', valor:45200, impacto:"Potencial fraude ou erro de faturamento", data:"13/07/2026", recomendacao:"Verificar pedido #PED-2347" },
  { id:2, tipo:"estoque", severidade:"moderado", descricao:'Consumo anômalo de "Organizador MC-001" — 3x acima da média', valor:12800, impacto:"Ruptura de estoque em 5 dias", data:"12/07/2026", recomendacao:"Ordem de compra emergencial de 200 un." },
  { id:3, tipo:"venda", severidade:"baixo", descricao:"Queda atípica de 40% nas vendas da categoria Pet", valor:-6400, impacto:"Possível problema de campanha", data:"11/07/2026", recomendacao:"Revisar campanhas e precificação" },
  { id:4, tipo:"preco", severidade:"moderado", descricao:'Margem de "Cooler Compacto" caiu para 9.8%', valor:3800, impacto:"Prejuízo estimado de R$ 3.800/mês", data:"10/07/2026", recomendacao:"Reajustar preço para R$ 79,90" },
  { id:5, tipo:"venda", severidade:"baixo", descricao:"Pico anômalo de vendas na madrugada (02:00-05:00)", valor:18200, impacto:"Possível ataque de bot", data:"09/07/2026", recomendacao:"Analisar origem do tráfego" },
]

const SEGMENTOS: CustomerSegment[] = [
  { segmento:"Clientes Premium", percentual:12, receitaMedia:4850, churn:2.3, descricao:"Alta fidelidade, ticket médio elevado" },
  { segmento:"Compradores Regulares", percentual:38, receitaMedia:1250, churn:8.7, descricao:"Compram a cada 2-3 meses" },
  { segmento:"Compradores Ocasionais", percentual:35, receitaMedia:380, churn:18.4, descricao:"Compram em datas sazonais" },
  { segmento:"Em Risco de Churn", percentual:10, receitaMedia:620, churn:52.1, descricao:"Reduziram frequência em 60%" },
  { segmento:"Novos Clientes", percentual:5, receitaMedia:280, churn:35.0, descricao:"Primeira compra nos últimos 30 dias" },
]

const RECOMENDACOES: MLRecommendation[] = [
  { id:1, tipo:"cross-sell", descricao:'Clientes de "Garrafa Térmica Pro" têm 73% de chance de comprar "Copo Térmico 500ml"', confianca:73, receitaEstimada:12800, acao:"Criar bundle com 10% de desconto" },
  { id:2, tipo:"upsell", descricao:'20% dos clientes de "Fone Bluetooth" sobem para "Mini Projetor LED"', confianca:68, receitaEstimada:9400, acao:"Banner de upgrade no carrinho" },
  { id:3, tipo:"retencao", descricao:"58 clientes 'Em Risco de Churn' não compram há 60+ dias", confianca:85, receitaEstimada:22100, acao:"Cupom de 15% + frete grátis por 7 dias" },
  { id:4, tipo:"cross-sell", descricao:'Compras de "Cortina Blackout" têm 61% de chance de incluir "Vaso Decorativo"', confianca:61, receitaEstimada:7600, acao:"Sugerir combinação na finalização" },
  { id:5, tipo:"upsell", descricao:'31% dos clientes "Ocasionais" sobem para "Regular" com fidelidade', confianca:77, receitaEstimada:31500, acao:"Programa de pontos progressivo" },
]

// ── DB queries: tentam dados reais, retornam null se vazio ──

async function querySalesFromDB(): Promise<{ diarias: VendaDiaria[] | null; categorias: CategoriaVenda[] | null }> {
  try {
    const prisma = getPrisma()
    const thirtyDaysAgo = new Date(Date.now() - 30 * 864e5)

    const orders = await prisma.order.findMany({
      where: { createdAt: { gte: thirtyDaysAgo } },
      include: { lines: true },
      orderBy: { createdAt: 'asc' },
    })

    if (orders.length === 0) return { diarias: null, categorias: null }

    // aggregate by day
    const dayMap = new Map<string, { valor: number; custo: number }>()
    for (const o of orders) {
      const day = String(o.createdAt.getDate()).padStart(2, "0")
      const entry = dayMap.get(day) ?? { valor: 0, custo: 0 }
      entry.valor += o.grandTotal
      entry.custo += o.grandTotal * 0.55 // estimate
      dayMap.set(day, entry)
    }

    const diarias: VendaDiaria[] = Array.from({ length: 30 }, (_, i) => {
      const dia = String(i + 1).padStart(2, "0")
      const e = dayMap.get(dia) ?? { valor: 0, custo: 0 }
      return { dia, valor: Math.round(e.valor), custo: Math.round(e.custo), margem: e.valor > 0 ? Math.round((1 - e.custo / e.valor) * 100) : 0 }
    })

    // category aggregation from order lines
    const skuSet = new Set<string>()
    for (const o of orders) for (const l of o.lines) skuSet.add(l.sku)

    type ProdInfo = { name: string; category: string }
    type ProdAgg = { qtd: number; valorTotal: number }
    type CatAgg = { category: string; valor: number; productMap: Map<string, ProdAgg> }

    const products = await prisma.product.findMany({ where: { sku: { in: [...skuSet] } } })
    const catMap = new Map<string, CatAgg>()
    const productNameMap = new Map<string, ProdInfo>(products.map((p: { sku: string; name: string; category: string }) => [p.sku, { name: p.name, category: p.category }]))

    for (const o of orders) {
      for (const l of o.lines) {
        const info: ProdInfo = productNameMap.get(l.sku) ?? { name: l.name, category: "Sem Categoria" }
        const c: CatAgg = catMap.get(info.category) ?? { category: info.category, valor: 0, productMap: new Map() }
        c.valor += l.unitPrice * l.quantity
        const pe: ProdAgg = c.productMap.get(l.sku) ?? { qtd: 0, valorTotal: 0 }
        pe.qtd += l.quantity
        pe.valorTotal += l.unitPrice * l.quantity
        c.productMap.set(l.sku, pe)
        catMap.set(info.category, c)
      }
    }

    const total = [...catMap.values()].reduce((s: number, c: CatAgg) => s + c.valor, 0)
    const categorias: CategoriaVenda[] = [...catMap.entries()].map(([, c]: [string, CatAgg]) => ({
      categoria: c.category,
      valor: Math.round(c.valor),
      percentual: total > 0 ? Math.round((c.valor / total) * 100) : 0,
      produtos: [...c.productMap.entries()].map(([sku, p]: [string, ProdAgg]) => ({
        nome: productNameMap.get(sku)?.name ?? sku,
        sku,
        valor: Math.round(p.valorTotal),
        qtd: p.qtd,
        margem: 30 + Math.random() * 20,
      })),
    }))

    return { diarias, categorias }
  } catch { return { diarias: null, categorias: null } }
}

async function queryAnomaliesFromDB(): Promise<AnomalyResult[] | null> {
  try {
    const alerts = await getPrisma().anomalyAlert.findMany({
      orderBy: { detectedAt: 'desc' },
      take: 20,
    })
    if (alerts.length === 0) return null
    return alerts.map((a: typeof alerts[0], i: number) => ({
      id: i + 1,
      tipo: (a.context as AnomalyResult['tipo']) ?? "venda",
      severidade: (a.severity === "high" ? "critico" : a.severity === "medium" ? "moderado" : "baixo") as AnomalyResult['severidade'],
      descricao: `${a.metric}: esperado ${a.expectedValue}, real ${a.actualValue}`,
      valor: a.actualValue,
      impacto: `Desvio de ${a.deviationPercent}%`,
      data: a.detectedAt.toLocaleDateString("pt-BR"),
      recomendacao: a.acknowledged ? "Em análise" : "Validar com equipe",
    }))
  } catch { return null }
}

async function querySegmentsFromDB(): Promise<CustomerSegment[] | null> {
  try {
    const segments = await getPrisma().customerSegment.findMany({
      distinct: ['segment'],
      orderBy: { segment: 'asc' },
    })
    if (segments.length === 0) return null
    const total = segments.reduce((s: number, seg: typeof segments[0]) => s + seg.frequency, 0) || 1
    return segments.map((seg: typeof segments[0]) => ({
      segmento: seg.segment,
      percentual: Math.round((seg.frequency / total) * 100),
      receitaMedia: seg.monetary,
      churn: seg.recency > 60 ? 35 : 8,
      descricao: `RFM: R${seg.recency}F${seg.frequency}M${seg.monetary}`,
    }))
  } catch { return null }
}

async function queryIndicadoresFromDB(): Promise<IndicadorFinanceiro[] | null> {
  try {
    const metrics = await getPrisma().kPIMetric.findMany()
    if (metrics.length === 0) return null
    return metrics.map((m: typeof metrics[0]) => ({
      id: m.name.toLowerCase().replace(/\s+/g, "-"),
      nome: m.name,
      valor: m.value,
      unidade: m.unit,
      tendencia: (m.value >= m.target ? "up" : "down") as "up" | "down" | "stable",
      tendenciaValor: Math.round((m.value - m.target) * 10) / 10,
      referencia: `> ${m.target}${m.unit}`,
      status: (m.value >= m.target ? "good" : m.value >= m.target * 0.8 ? "warning" : "danger") as "good" | "warning" | "danger",
    }))
  } catch { return null }
}

// ── route registration ──

export function registerBIRoutes(server: FastifyInstance): void {
  server.addHook('onRoute', (opts) => {
    if (opts.url.startsWith('/api/bi/')) {
      const prev = opts.preHandler
      opts.preHandler = prev
        ? [authMiddleware(null), ...(Array.isArray(prev) ? prev : [prev])]
        : [authMiddleware(null)]
    }
  })

  server.get('/api/bi/dashboard', async () => {
    // ponytail: DB-first with fallback. Add real KPI queries when BI DB is seeded.
    try {
      const prisma = getPrisma()
      const [totalOrders, totalCustomers] = await Promise.all([
        prisma.order.count(),
        prisma.customer.count(),
      ])
      return {
        kpis: [
          { label: "Receita (mês)", value: "R$ 287.320", color: "text-emerald-400" },
          { label: "Ticket Médio", value: "R$ 243,00", color: "text-blue-400" },
          { label: "Margem Média", value: "32.5%", color: "text-amber-400" },
          { label: "Previsão (próx. mês)", value: "R$ 312.450", color: "text-indigo-400", sub: "+8.7% vs atual" },
          { label: "ROI", value: "28.7%", color: "text-emerald-400" },
          { label: "Churn (30d)", value: "8.4%", color: "text-red-400", sub: "▼ 1.2pp vs anterior" },
        ],
        submenu: [
          { href: "/bi/vendas", label: "Vendas & Drill-down", color: "bg-blue-600" },
          { href: "/bi/indicadores", label: "Indicadores", color: "bg-amber-600" },
          { href: "/bi/forecast", label: "Forecast", color: "bg-purple-600" },
          { href: "/bi/ml", label: "Machine Learning", color: "bg-emerald-600" },
        ],
        stats: { totalOrders, totalCustomers },
      }
    } catch { return { error: "Dashboard unavailable" } }
  })

  server.get('/api/bi/vendas/diarias', async () => {
    const { diarias } = await querySalesFromDB()
    return diarias ?? gerarVendasDiarias()
  })

  server.get('/api/bi/vendas/semanais', async () => {
    return gerarVendasSemanais()
  })

  server.get('/api/bi/vendas/mensais', async () => {
    return gerarVendasMensais()
  })

  server.get('/api/bi/vendas/categorias', async () => {
    const { categorias } = await querySalesFromDB()
    return categorias ?? gerarCategorias()
  })

  server.get('/api/bi/forecast', async () => {
    const pontos = gerarForecast()
    return { pontos, resumo: FORECAST_RESUMO }
  })

  server.get('/api/bi/indicadores', async () => {
    const dbIndicadores = await queryIndicadoresFromDB()
    return dbIndicadores ?? INDICADORES
  })

  server.get('/api/bi/ml/anomalias', async () => {
    const dbAnomalias = await queryAnomaliesFromDB()
    return dbAnomalias ?? ANOMALIAS
  })

  server.get('/api/bi/ml/segmentos', async () => {
    const dbSegments = await querySegmentsFromDB()
    return dbSegments ?? SEGMENTOS
  })

  server.get('/api/bi/ml/recomendacoes', async () => {
    return RECOMENDACOES
  })
}
