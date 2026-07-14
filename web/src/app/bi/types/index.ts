// Re-exports do SSOT
export type { KpiMetric, SubmenuItem } from "@/lib/types/ui";

// ── Tipos específicos do módulo BI ──

import type { ProdutoVenda as _ProdutoVenda } from "@/lib/types/domain";
export type ProdutoVenda = _ProdutoVenda;

export interface VendaDiaria {
  dia: string;
  valor: number;
  custo: number;
  margem: number;
}

export interface VendaSemanal {
  semana: string;
  valor: number;
  ticketMedio: number;
  pedidos: number;
}

export interface VendaMensal {
  mes: string;
  valor: number;
  custo: number;
  margem: number;
  variacaoPercent: number;
}

export interface CategoriaVenda {
  categoria: string;
  valor: number;
  percentual: number;
  produtos: ProdutoVenda[];
}

export interface IndicadorFinanceiro {
  id: string;
  nome: string;
  valor: number;
  unidade: string;
  tendencia: "up" | "down" | "stable";
  tendenciaValor: number;
  referencia: string;
  status: "good" | "warning" | "danger";
}

export interface ForecastDataPoint {
  periodo: string;
  historico?: number;
  previsao?: number;
  limiteInferior?: number;
  limiteSuperior?: number;
  sazonalidade?: number;
}

export interface AnomalyResult {
  id: number;
  tipo: "transacao" | "estoque" | "venda" | "preco";
  severidade: "critico" | "moderado" | "baixo";
  descricao: string;
  valor: number;
  impacto: string;
  data: string;
  recomendacao: string;
}

export interface CustomerSegment {
  segmento: string;
  percentual: number;
  receitaMedia: number;
  churn: number;
  descricao: string;
}

export interface MLRecommendation {
  id: number;
  tipo: "cross-sell" | "upsell" | "retencao";
  descricao: string;
  confianca: number;
  receitaEstimada: number;
  acao: string;
}

// ── Utilitários ──

import { fmtBRL as _fmtBRL } from "@/lib/format";
export { fmtBRL as formatCurrency, fmtBRLCompact } from "@/lib/format";

export function formatCompact(value: number): string {
  if (value >= 1_000_000) return (value / 1_000_000).toFixed(1) + "M";
  if (value >= 1_000) return _fmtBRL(value);
  return value.toFixed(1);
}
