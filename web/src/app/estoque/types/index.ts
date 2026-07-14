export type {
  TipoMovimentacao,
  TipoInventario,
  MetodoCusteio,
  CurvaClassificacao,
  MovimentacaoEstoque,
  Inventario,
  ItemInventario,
  Deposito,
  EnderecoDeposito,
  CurvaABCItem,
  IndicadorGiro,
  IndicadorRuptura,
  IndicadorCobertura,
} from "@/lib/types/domain";

export {
  TIPOS_MOVIMENTACAO,
  TIPO_MOV_COLORS,
  TIPOS_INVENTARIO,
  METODOS_CUSTEIO,
} from "@/lib/types/domain";

import { fmtBRL } from "@/lib/format";
export { fmtBRL as formatCurrency, fmtBRLCompact } from "@/lib/format";

export function fmtQtd(v: number): string {
  if (v >= 1000) return `${(v / 1000).toFixed(1)}k`;
  return String(v);
}
