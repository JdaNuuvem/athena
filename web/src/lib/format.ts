export const fmtBRL = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export const fmtBRLCompact = (v: number) => {
  if (v >= 1_000_000) return `R$ ${(v / 1_000_000).toFixed(1)}M`;
  return fmtBRL(v);
};

// Datas DATE (YYYY-MM-DD) sem hora — new Date(str) interpreta como UTC e
// desloca 1 dia pra tras em fusos negativos (Brasil). Formata via split direto.
export function fmtDataBR(v: unknown): string {
  const s = String(v ?? "");
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : "—";
}
