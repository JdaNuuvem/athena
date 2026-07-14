// ── Entidades de domínio (SSOT para todos os módulos) ──

// ── Bling / Nota Fiscal (SSOT: BlingFinancialTab.tsx) ──

export interface NotaFiscal {
  id: number;
  numero: string;
  dataEmissao?: string;
  dataOperacao?: string;
  contato: { nome: string; numeroDocumento?: string };
  situacao: number;
  tipo: number;
  chaveAcesso?: string;
  loja?: { id: number };
  naturezaOperacao?: { id: number };
  valorNota?: number;
  total?: number;
}

export const NF_SITUACOES: Record<number, string> = { 1: "Emitida", 2: "Cancelada", 3: "Inutilizada", 4: "Denegada" };
export const NF_TIPOS: Record<number, string> = { 0: "Saída", 1: "Entrada" };

export function detectarTipoNota(nota: NotaFiscal): string {
  const n = nota.numero || "";
  if (n.startsWith("55")) return "NF-e";
  if (n.startsWith("65")) return "NFC-e";
  if (n.match(/^[A-Z]/)) return "NFS-e";
  if (n.startsWith("57")) return "CT-e";
  if (n.startsWith("58")) return "MDF-e";
  return NF_TIPOS[nota.tipo] === "Entrada" ? "NF-e Entrada" : "NF-e";
}

export interface ContaReceber {
  id: number;
  numero: string;
  vencimento?: string;
  valor?: number;
  contato: { nome: string };
  situacao: number | string;
}

// ── Pedido / Order ──

export interface Pedido {
  id: number;
  numero: string;
  data?: string;
  dataSaida?: string;
  contato: { nome: string; numeroDocumento?: string; tipoPessoa?: string };
  total: number;
  totalProdutos?: number;
  situacao: { id: number; valor: number } | string;
  itens?: Array<{ codigo: string; descricao?: string; quantidade: number; valor: number }>;
  loja?: { id: number };
}

export const PEDIDO_SITUACOES: Record<number, string> = { 1: "Aberto", 6: "Concluído", 9: "Cancelado", 12: "Em andamento", 15: "Faturado", 18: "Devolvido" };
export const PEDIDO_SIT_COLORS: Record<number, string> = { 1: "bg-yellow-900/30 text-yellow-400", 6: "bg-emerald-900/30 text-emerald-400", 9: "bg-red-900/30 text-red-400", 12: "bg-blue-900/30 text-blue-400", 15: "bg-emerald-900/30 text-emerald-400", 18: "bg-orange-900/30 text-orange-400" };

// ── Conta Financeira (unificada) ──

export interface ContaFinanceira {
  id: number;
  tipo: "pagar" | "receber";
  descricao: string;
  valor: number;
  vencimento: string;
  data_baixa?: string;
  status: string;
  forma_pagamento?: string;
  contraparte?: string;
  referencia?: string;
}

// ── Produto ──

export interface Product {
  sku: string;
  nome: string;
  margem_pct: number;
  receita_30d: number;
  vendidos_30d: number;
  estoque_lojas: Array<{ loja: string; preco: number; status: string }>;
  total_lojas: number;
}

export interface BlingProduct {
  id: number;
  codigo: string;
  descricao: string;
  preco: number;
  estoque_atual: number;
  estoque_minimo: number;
  situacao: string;
}

export interface ProdutoVenda {
  nome: string;
  sku: string;
  valor: number;
  qtd: number;
  margem: number;
}

// ── Loja ──

export interface Loja {
  id: number;
  nome: string;
  tipo?: string;
}

// ── Cliente / Contato ──

export interface Contato {
  nome: string;
  documento?: string;
  tipoPessoa?: string;
}

export interface Cliente {
  id: number;
  nome: string;
  tipo: string;
  documento: string;
  limite_credito: number;
  score: number;
  status: string;
  contatos: Contato[];
}

// ── Fornecedor ──

export interface Fornecedor {
  id: number;
  nome: string;
  tipo: string;
  documento: string;
  contato: string;
}

// ── Tipos Bling (API) ──

export interface BlingOrder {
  id: number;
  numero: string;
  data: string;
  total_venda: number;
  situacao: string;
  contato_nome: string;
  imported_at: string;
}

export interface BlingReceivable {
  id: number;
  descricao: string;
  valor: number;
  data_vencimento: string;
  situacao: string;
}

export interface BlingInvoice {
  id: number;
  numero: string;
  serie: string;
  data_emissao: string;
  valor_nota: number;
  situacao: string;
  cliente_nome: string;
  imported_at: string;
}

export interface BlingDeposito {
  id: number;
  descricao: string;
  situacao: string;
  [key: string]: unknown;
}

export interface BlingEstoqueSaldo {
  idProduto: number;
  codigo: string;
  saldo: number;
  [key: string]: unknown;
}

export interface BlingResumoVendas {
  total_receita: number;
  total_pedidos: number;
  dias_analisados: number;
  top_skus: Array<{ sku: string; quantidade: number; receita: number }>;
  vendas_diarias: Array<[string, number]>;
}

export interface BlingWebhook {
  id: number;
  url: string;
  evento: string;
  situacao: string;
  [key: string]: unknown;
}

export interface BlingConfig {
  api_key: string;
  sandbox: boolean;
  auto_sync: boolean;
  sync_interval_minutes: number;
  sync_products: boolean;
  sync_orders: boolean;
  sync_invoices: boolean;
  sync_receivables: boolean;
  sync_stock: boolean;
  auth_url: string;
  autenticado: boolean;
}

export interface BlingStatus {
  client_id_setado: boolean;
  autenticado: boolean;
  auth_url: string;
}

// ── Outros ──

export interface Agent {
  id: string;
  name: string;
  role: string;
  status: string;
  context: string;
  taskCount: number;
}

export interface KPIOverview {
  receita_total: number;
  total_pedidos: number;
  total_produtos: number;
  total_anuncios: number;
  ticket_medio: number;
  receita_por_canal: Record<string, number>;
  top_skus: Array<{
    sku: string;
    nome: string;
    qtd: number;
    receita: number;
    margem: number;
  }>;
}

export interface Integration {
  id: string;
  name: string;
  category: string;
  status: string;
}

// ── Estoque ──

export type TipoMovimentacao =
  | "entrada" | "saida" | "transferencia" | "ajuste" | "perda"
  | "inventario" | "producao" | "consumo" | "devolucao" | "troca"
  | "reserva" | "separacao" | "expedicao";

export const TIPOS_MOVIMENTACAO: Record<TipoMovimentacao, string> = {
  entrada: "Entrada", saida: "Saída", transferencia: "Transferência",
  ajuste: "Ajuste", perda: "Perda", inventario: "Inventário",
  producao: "Produção", consumo: "Consumo", devolucao: "Devolução",
  troca: "Troca", reserva: "Reserva", separacao: "Separação", expedicao: "Expedição",
};

export const TIPO_MOV_COLORS: Record<TipoMovimentacao, string> = {
  entrada: "bg-emerald-900/30 text-emerald-400",
  saida: "bg-red-900/30 text-red-400",
  transferencia: "bg-blue-900/30 text-blue-400",
  ajuste: "bg-amber-900/30 text-amber-400",
  perda: "bg-orange-900/30 text-orange-400",
  inventario: "bg-purple-900/30 text-purple-400",
  producao: "bg-indigo-900/30 text-indigo-400",
  consumo: "bg-rose-900/30 text-rose-400",
  devolucao: "bg-yellow-900/30 text-yellow-400",
  troca: "bg-cyan-900/30 text-cyan-400",
  reserva: "bg-teal-900/30 text-teal-400",
  separacao: "bg-sky-900/30 text-sky-400",
  expedicao: "bg-lime-900/30 text-lime-400",
};

export interface MovimentacaoEstoque {
  id: number;
  tipo: TipoMovimentacao;
  sku: string;
  produto: string;
  quantidade: number;
  deposito_origem?: string;
  deposito_destino?: string;
  documento?: string;
  motivo?: string;
  responsavel: string;
  data: string;
  custo_unitario?: number;
  custo_total?: number;
}

export type TipoInventario = "ciclico" | "geral" | "parcial";

export const TIPOS_INVENTARIO: Record<TipoInventario, string> = {
  ciclico: "Cíclico", geral: "Geral", parcial: "Parcial",
};

export interface Inventario {
  id: number;
  tipo: TipoInventario;
  deposito: string;
  data_inicio: string;
  data_fim?: string;
  status: "aberto" | "em_andamento" | "concluido" | "cancelado";
  responsavel: string;
  itens_contados: number;
  itens_divergentes: number;
  acuracia_pct: number;
}

export interface ItemInventario {
  id: number;
  inventario_id: number;
  sku: string;
  produto: string;
  saldo_sistema: number;
  saldo_contado: number;
  divergencia: number;
  custo_unitario: number;
  divergencia_valor: number;
}

export interface Deposito {
  id: number;
  codigo: string;
  nome: string;
  tipo: "proprio" | "terceiro" | "virtual";
  // ponytail: string for now, replace with Loja references when multi-store wired
  loja?: string;
  endereco?: EnderecoDeposito;
  ativo: boolean;
}

export interface EnderecoDeposito {
  rua: string;
  predio?: string;
  corredor?: string;
  estante?: string;
  prateleira?: string;
  posicao?: string;
}

export type MetodoCusteio = "peps" | "ueps" | "custo_medio";

export const METODOS_CUSTEIO: Record<MetodoCusteio, string> = {
  peps: "PEPS (FIFO)", ueps: "UEPS (LIFO)", custo_medio: "Custo Médio",
};

export type CurvaClassificacao = "A" | "B" | "C";

export interface CurvaABCItem {
  sku: string;
  produto: string;
  valor_consumo: number;
  pct_individual: number;
  pct_acumulado: number;
  classificacao: CurvaClassificacao;
  giro: number;
  estoque_atual: number;
  cobertura_dias: number;
}

export interface IndicadorGiro {
  sku: string;
  produto: string;
  saidas_30d: number;
  estoque_medio: number;
  giro: number;
  tendencia: "up" | "down" | "stable";
}

export interface IndicadorRuptura {
  sku: string;
  produto: string;
  dias_ruptura: number;
  vendas_perdidas_estimadas: number;
  impacto_receita: number;
  ultimo_abastecimento?: string;
}

export interface IndicadorCobertura {
  sku: string;
  produto: string;
  estoque_atual: number;
  demanda_diaria_media: number;
  cobertura_dias: number;
  estoque_minimo: number;
  estoque_maximo: number;
  status: "excesso" | "normal" | "baixo" | "critico";
}

// ── Fiscal ──

export interface FiscalTributo {
  id: number;
  nome: string;
  sigla: string;
  aliquota: number;
  aliquota_interestadual: number;
  regime: string;
  tipo: string;
  incidencia: string;
  fato_gerador: string;
  ativo: boolean;
}

export interface FiscalObrigacao {
  id: number;
  nome: string;
  sigla: string;
  descricao: string;
  periodicidade: string;
  data_vencimento: string;
  orgao: string;
  status: string;
  responsavel: string;
  multa_por_atraso: number;
}

export interface FiscalNotaFiscal {
  id: number;
  numero: string;
  serie: string;
  modelo: string;
  chave_acesso: string;
  tipo: string;
  data_emissao: string;
  data_operacao: string;
  natureza_operacao: string;
  cfop: string;
  contato_nome: string;
  contato_documento: string;
  valor_nf: number;
  valor_produtos: number;
  valor_frete: number;
  valor_total_tributos: number;
  status: string;
  bling_id: number;
}

export interface FiscalNFeItem {
  id: number;
  nota_id: number;
  codigo: string;
  descricao: string;
  ncm: string;
  quantidade: number;
  valor_unitario: number;
  valor_total: number;
  base_icms: number;
  valor_icms: number;
  aliquota_icms: number;
}

export interface FiscalDashboard {
  nfs_mes: number;
  nfs_total: number;
  valor_mes: number;
  obrigacoes_pendentes: number;
  obrigacoes_atrasadas: number;
  tributos_ativos: number;
  contas_receber_pendentes: number;
  contas_pagar_pendentes: number;
}
