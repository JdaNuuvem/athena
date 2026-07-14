// Re-exports do SSOT
export type { NotaFiscal } from "@/lib/types/domain";
export { NF_SITUACOES, NF_TIPOS, detectarTipoNota } from "@/lib/types/domain";
export type { KpiMetric, SubmenuItem, TabOption, Column, StatusBadgeVariant } from "@/lib/types/ui";
export { STATUS_BADGE_VARIANTS } from "@/lib/types/ui";

// ── Tipos específicos do módulo Fiscal ──

export interface TributoRecord {
  id: number;
  tributo: string;
  apuracao: string;
  baseCalculo: number;
  aliquota: string;
  valor: number;
  vencimento: string;
  status: "pago" | "pendente";
}

export type ObrigacaoStatus = "entregue" | "pendente" | "andamento";

export interface Obrigacao {
  id: number;
  nome: string;
  descricao: string;
  ultimaEntrega: string;
  proximoVencimento: string;
  periodicidade: string;
  status: ObrigacaoStatus;
}

export interface CfopRecord {
  codigo: string;
  descricao: string;
  tipo: "Entrada" | "Saída";
}

export interface NcmRecord {
  codigo: string;
  descricao: string;
  aliquotaIPI: string;
  aliquotaNacional: string;
}

export interface CestRecord {
  codigo: string;
  descricao: string;
  ncm: string;
}

export interface IbptRecord {
  ncm: string;
  aliquotaFederal: string;
  aliquotaEstadual: string;
  aliquotaMunicipal: string;
}

// ── Utilitários ──

export { fmtBRL as formatCurrency, fmtBRLCompact } from "@/lib/format";
