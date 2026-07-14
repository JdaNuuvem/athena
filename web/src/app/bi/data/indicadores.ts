import type { IndicadorFinanceiro } from "../types";

export const INDICADORES: IndicadorFinanceiro[] = [
  { id: "liquidez-corrente", nome: "Liquidez Corrente", valor: 2.35, unidade: "x", tendencia: "up", tendenciaValor: 0.15, referencia: "> 1.5", status: "good" },
  { id: "liquidez-seca", nome: "Liquidez Seca", valor: 1.82, unidade: "x", tendencia: "up", tendenciaValor: 0.08, referencia: "> 1.0", status: "good" },
  { id: "roi", nome: "ROI (Retorno s/ Invest.)", valor: 28.7, unidade: "%", tendencia: "up", tendenciaValor: 3.2, referencia: "> 15%", status: "good" },
  { id: "roe", nome: "ROE (Retorno s/ Patrimônio)", valor: 34.5, unidade: "%", tendencia: "stable", tendenciaValor: -0.5, referencia: "> 20%", status: "good" },
  { id: "margem-bruta", nome: "Margem Bruta", valor: 48.3, unidade: "%", tendencia: "down", tendenciaValor: -2.1, referencia: "> 45%", status: "warning" },
  { id: "margem-liquida", nome: "Margem Líquida", valor: 18.7, unidade: "%", tendencia: "down", tendenciaValor: -1.3, referencia: "> 15%", status: "good" },
  { id: "margem-ebitda", nome: "Margem EBITDA", valor: 24.5, unidade: "%", tendencia: "up", tendenciaValor: 1.8, referencia: "> 20%", status: "good" },
  { id: "giro-estoque", nome: "Giro de Estoque", valor: 8.2, unidade: "x/ano", tendencia: "up", tendenciaValor: 0.7, referencia: "> 6.0", status: "good" },
  { id: "prazo-medio-receb", nome: "Prazo Médio Recebimento", valor: 23, unidade: "dias", tendencia: "down", tendenciaValor: -3, referencia: "< 30 dias", status: "good" },
  { id: "prazo-medio-pagto", nome: "Prazo Médio Pagamento", valor: 38, unidade: "dias", tendencia: "stable", tendenciaValor: 1, referencia: "> 35 dias", status: "good" },
  { id: "indice-endividamento", nome: "Índice Endividamento", valor: 0.42, unidade: "x", tendencia: "down", tendenciaValor: -0.03, referencia: "< 0.5", status: "good" },
  { id: "crescimento-receita", nome: "Crescimento Receita", valor: 12.3, unidade: "%", tendencia: "down", tendenciaValor: -3.5, referencia: "> 10%", status: "warning" },
];

export const STATUS_TEXTO: Record<string, string> = { good: "Saudável", warning: "Atenção", danger: "Crítico" };
export const STATUS_COR: Record<string, string> = { good: "text-emerald-400", warning: "text-amber-400", danger: "text-red-400" };
