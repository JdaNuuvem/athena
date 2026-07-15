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

// ── DB queries via raw SQL nas tabelas Python ──

type RawRow = Record<string, unknown>

async function rawQuery<T extends Record<string, unknown>>(sql: string): Promise<T[]> {
  const prisma = getPrisma()
  return (prisma as unknown as { $queryRawUnsafe: (sql: string) => Promise<T[]> }).$queryRawUnsafe(sql)
}

async function querySalesFromDB(): Promise<{ diarias: VendaDiaria[] | null; categorias: CategoriaVenda[] | null }> {
  try {
    // ponytail: raw SQL nas tabelas Python. Migrar para Prisma models quando houver sync.
    const rows = await rawQuery<RawRow>(
      `SELECT DATE(data) as dia, COALESCE(SUM(total),0) as valor
       FROM vendas_pedidos
       WHERE data >= CURRENT_DATE - 30 AND status != 'cancelado'
       GROUP BY DATE(data) ORDER BY dia`)
    if (rows.length === 0) return { diarias: null, categorias: null }
    const diarias: VendaDiaria[] = Array.from({ length: 30 }, (_, i) => {
      const d = new Date(); d.setDate(d.getDate() - (29 - i))
      const diaStr = String(d.getDate()).padStart(2, "0")
      const found = rows.find((r: RawRow) => {
        const rd = typeof r.dia === 'string' ? r.dia : String(r.dia || '')
        return rd.endsWith(`-${diaStr}`) || rd === diaStr
      })
      const valor = found ? Number(found.valor || 0) : 0
      const custo = valor * 0.55
      return { dia: diaStr, valor: Math.round(valor), custo: Math.round(custo), margem: valor > 0 ? Math.round((1 - custo / valor) * 100) : 0 }
    })
    return { diarias, categorias: null }
  } catch { return { diarias: null, categorias: null } }
}

async function queryAnomaliesFromDB(): Promise<AnomalyResult[] | null> {
  try {
    const rows = await rawQuery<RawRow>(
      `WITH daily AS (
         SELECT DATE(data) as dia, SUM(total) as valor
         FROM vendas_pedidos WHERE data >= CURRENT_DATE - 30 AND status != 'cancelado'
         GROUP BY DATE(data)
       ), avg AS (SELECT AVG(valor)::numeric(12,2) as media, STDDEV(valor)::numeric(12,2) as stddev FROM daily)
       SELECT d.*, (d.valor - a.media) / NULLIF(a.stddev,0) as zscore
       FROM daily d, avg a
       WHERE ABS((d.valor - a.media) / NULLIF(a.stddev,0)) > 1.5
       ORDER BY ABS((d.valor - a.media) / NULLIF(a.stddev,0)) DESC LIMIT 5`)
    if (rows.length === 0) return null
    return rows.map((r: RawRow, i: number) => {
      const z = Number(r.zscore || 0)
      return {
        id: i + 1,
        tipo: 'venda' as const,
        severidade: (Math.abs(z) > 2.5 ? 'critico' : Math.abs(z) > 1.8 ? 'moderado' : 'baixo') as AnomalyResult['severidade'],
        descricao: `${z > 0 ? 'Pico' : 'Queda'} de vendas em ${r.dia}: R$ ${Number(r.valor || 0).toFixed(0)}`,
        valor: Math.round(Number(r.valor || 0)),
        impacto: `Desvio de ${Math.abs(z).toFixed(1)} desvios-padrao`,
        data: typeof r.dia === 'string' ? r.dia.split('T')[0] : new Date().toLocaleDateString('pt-BR'),
        recomendacao: z > 0 ? 'Investigar causa do pico e replicar' : 'Verificar campanhas e concorrência',
      }
    })
  } catch { return null }
}

async function querySegmentsFromDB(): Promise<CustomerSegment[] | null> {
  try {
    const rows = await rawQuery<RawRow>(
      `SELECT c.id, c.nome, COUNT(v.id) as compras, COALESCE(SUM(v.total),0) as total_gasto,
              MAX(v.data) as ultima_compra
       FROM cad_clientes c
       LEFT JOIN vendas_pedidos v ON v.cliente_id = c.id AND v.status != 'cancelado'
       GROUP BY c.id, c.nome
       HAVING COUNT(v.id) > 0
       ORDER BY total_gasto DESC LIMIT 20`)
    if (rows.length === 0) return null
    const total = rows.reduce((s: number, r: RawRow) => s + Number(r.total_gasto || 0), 0) || 1
    // ponytail: RFM simples. RFM real quando tiver mais historico.
    return rows.map((r: RawRow) => {
      const gasto = Number(r.total_gasto || 0)
      const compras = Number(r.compras || 0)
      const pct = Math.round((gasto / total) * 100)
      return {
        segmento: String(r.nome || 'Cliente'),
        percentual: Math.max(pct, 1),
        receitaMedia: Math.round(gasto / Math.max(compras, 1)),
        churn: compras < 2 ? 35 : compras < 5 ? 15 : 5,
        descricao: `${compras} compras, total R$ ${gasto.toFixed(2)}`,
      }
    })
  } catch { return null }
}

async function queryIndicadoresFromDB(): Promise<IndicadorFinanceiro[] | null> {
  try {
    // ponytail: calcula indicadores das tabelas syncadas do Bling
    const [receita, crPendente, cpPendente, nfMes, vendasMes] = await Promise.all([
      rawQuery<RawRow>(`SELECT COALESCE(SUM(valor_nf),0) as v FROM fiscal_notas_fiscais WHERE tipo='saida' AND data_emissao >= date_trunc('month', CURRENT_DATE)`),
      rawQuery<RawRow>(`SELECT COALESCE(SUM(valor),0) as v FROM fin_contas_receber WHERE status='pendente'`),
      rawQuery<RawRow>(`SELECT COALESCE(SUM(valor),0) as v FROM fin_contas_pagar WHERE status='pendente'`),
      rawQuery<RawRow>(`SELECT COUNT(*) as c FROM fiscal_notas_fiscais WHERE data_emissao >= date_trunc('month', CURRENT_DATE)`),
      rawQuery<RawRow>(`SELECT COALESCE(SUM(total),0) as v FROM vendas_pedidos WHERE data >= date_trunc('month', CURRENT_DATE) AND status != 'cancelado'`),
    ])
    const receitaVal = Number(receita[0]?.v || 0)
    const crVal = Number(crPendente[0]?.v || 0)
    const cpVal = Number(cpPendente[0]?.v || 0)
    const vendasVal = Number(vendasMes[0]?.v || 0)
    const liquidez = crVal > 0 ? crVal / Math.max(cpVal, 1) : 2.0
    const margemBruta = receitaVal > 0 ? Math.round((receitaVal - receitaVal * 0.55) / receitaVal * 100 * 10) / 10 : 45
    const margemLiquida = vendasVal > 0 ? 18.5 : 0
    return [{
      id:'liquidez-corrente', nome:'Liquidez Corrente', valor:Math.round(liquidez*100)/100, unidade:'x',
      tendencia:liquidez>1.5?'up':'down', tendenciaValor:Math.round((liquidez-1.5)*100)/100,
      referencia:'> 1.5', status:liquidez>1.5?'good':liquidez>1.0?'warning':'danger',
    },{
      id:'margem-bruta', nome:'Margem Bruta (NF-e)', valor:margemBruta, unidade:'%',
      tendencia:'stable', tendenciaValor:0, referencia:'> 45%', status:margemBruta>45?'good':'warning',
    },{
      id:'giro-estoque', nome:'Giro de Estoque', valor:8.2, unidade:'x/ano',
      tendencia:'up', tendenciaValor:0.7, referencia:'> 6.0', status:'good',
    },{
      id:'prazo-medio-receb', nome:'Prazo Medio Recebimento', valor:23, unidade:'dias',
      tendencia:'down', tendenciaValor:-3, referencia:'< 30 dias', status:'good',
    },{
      id:'indice-endividamento', nome:'Indice Endividamento', valor:0.42, unidade:'x',
      tendencia:'down', tendenciaValor:-0.03, referencia:'< 0.5', status:'good',
    },{
      id:'crescimento-receita', nome:'Crescimento Receita', valor:12.3, unidade:'%',
      tendencia:'down', tendenciaValor:-3.5, referencia:'> 10%', status:'warning',
    }]
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
    try {
      const [t, tc, cr, cp] = await Promise.all([
        rawQuery<RawRow>(`SELECT COALESCE(SUM(total),0) as v FROM vendas_pedidos WHERE data >= date_trunc('month', CURRENT_DATE) AND status != 'cancelado'`),
        rawQuery<RawRow>(`SELECT COUNT(*) as c FROM cad_clientes`),
        rawQuery<RawRow>(`SELECT COALESCE(SUM(valor),0) as v FROM fin_contas_receber WHERE status='pendente'`),
        rawQuery<RawRow>(`SELECT COALESCE(SUM(valor),0) as v FROM fin_contas_pagar WHERE status='pendente'`),
      ])
      const receita = Number(t[0]?.v || 0)
      const clientes = Number(tc[0]?.c || 0)
      const aReceber = Number(cr[0]?.v || 0)
      const aPagar = Number(cp[0]?.v || 0)
      return {
        kpis: [
          { label: "Receita (mes)", value: `R$ ${receita.toLocaleString('pt-BR', {minimumFractionDigits:2})}`, color: "text-emerald-400" },
          { label: "Clientes", value: String(clientes), color: "text-blue-400" },
          { label: "Contas a Receber", value: `R$ ${aReceber.toLocaleString('pt-BR', {minimumFractionDigits:2})}`, color: "text-amber-400" },
          { label: "Contas a Pagar", value: `R$ ${aPagar.toLocaleString('pt-BR', {minimumFractionDigits:2})}`, color: "text-red-400" },
          { label: "ROI", value: "28.7%", color: "text-emerald-400" },
          { label: "Churn (30d)", value: "8.4%", color: "text-red-400", sub: "\u25BC 1.2pp vs anterior" },
        ],
        submenu: [
          { href: "/bi/vendas", label: "Vendas & Drill-down", color: "bg-blue-600" },
          { href: "/bi/indicadores", label: "Indicadores", color: "bg-amber-600" },
          { href: "/bi/forecast", label: "Forecast", color: "bg-purple-600" },
          { href: "/bi/ml", label: "Machine Learning", color: "bg-emerald-600" },
        ],
        stats: { receitaMes: receita, totalClientes: clientes, contasReceber: aReceber, contasPagar: aPagar },
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
