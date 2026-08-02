// Re-exports do SSOT
// ponytail: NotaFiscal/NF_SITUACOES/NF_TIPOS/detectarTipoNota (que existiam
// aqui) eram pra um formato de dado diferente do que a pagina /fiscal/notas
// usa hoje — mapeavam o JSON CRU da API do Bling (nota.tipo como 0/1,
// nota.situacao como numero), enquanto a pagina real le' fiscal_notas_fiscais
// do banco local (colunas ja' resolvidas: tipo/status como texto, modelo
// como "55"/"65"/etc). Zero uso em todo o modulo fiscal — removidos.
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
