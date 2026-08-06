"use client";

import { useTheme } from "@/lib/theme-context";

interface Props {
  dados: Array<{ estado: string; total: number; valor: number }>;
}

// Grid esquemático (nao geografico) do Brasil — cada UF numa celula, posicao
// aproximada por lat/lon real da capital, preservando norte->sul e oeste->leste.
const POSICOES: Record<string, [number, number]> = {
  RR: [0, 3],
  AP: [1, 4], PA: [1, 5], MA: [1, 6],
  AM: [2, 2], CE: [2, 7], RN: [2, 8],
  AC: [3, 0], RO: [3, 1], TO: [3, 5], PI: [3, 6], PB: [3, 8],
  MT: [4, 3], PE: [4, 8],
  GO: [5, 4], DF: [5, 5], BA: [5, 6], AL: [5, 8],
  MS: [6, 3], MG: [6, 6], SE: [6, 7],
  SP: [7, 5], RJ: [7, 6], ES: [7, 7],
  PR: [8, 4],
  SC: [9, 5],
  RS: [10, 4],
};

const fmtBRL = (v: number) => "R$ " + Number(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function MapaBrasilPedidos({ dados }: Props) {
  const { theme } = useTheme();
  const corVazio = theme === "dark" ? "rgba(38, 38, 38, 0.6)" : "rgba(226, 232, 240, 0.8)";
  const corTextoFraco = theme === "dark" ? "#a3a3a3" : "#64748b";
  const corTextoForte = "#052e1f";
  const porUf = new Map(dados.map((d) => [d.estado, d]));
  const maxTotal = Math.max(1, ...dados.map((d) => d.total));

  return (
    <div className="flex flex-col md:flex-row gap-5">
      <div
        className="grid gap-1 shrink-0 mx-auto md:mx-0"
        style={{ gridTemplateColumns: "repeat(9, 28px)", gridTemplateRows: "repeat(11, 28px)" }}
      >
        {Object.entries(POSICOES).map(([uf, [row, col]]) => {
          const d = porUf.get(uf);
          const total = d?.total || 0;
          const intensidade = total > 0 ? 0.18 + (total / maxTotal) * 0.82 : 0;
          return (
            <div
              key={uf}
              title={d ? `${uf}: ${total} pedido${total === 1 ? "" : "s"} · ${fmtBRL(d.valor)}` : `${uf}: sem pedidos no período`}
              className="rounded flex items-center justify-center text-[9px] font-medium border border-neutral-800"
              style={{
                gridColumn: col + 1,
                gridRow: row + 1,
                background: total > 0 ? `rgba(52, 211, 153, ${intensidade})` : corVazio,
                color: total > 0 && intensidade > 0.5 ? corTextoForte : corTextoFraco,
              }}
            >
              {uf}
            </div>
          );
        })}
      </div>
      <div className="flex-1 min-w-0 space-y-1.5">
        <p className="text-xs text-neutral-500 uppercase tracking-wider mb-2">Top estados</p>
        {dados.slice(0, 8).map((d) => (
          <div key={d.estado} className="flex items-center gap-2 text-xs">
            <span className="text-neutral-400 w-6 shrink-0 font-mono">{d.estado}</span>
            <div className="flex-1 bg-neutral-800 rounded-full h-1.5 overflow-hidden">
              <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${Math.round((d.total / maxTotal) * 100)}%` }} />
            </div>
            <span className="text-neutral-300 numeric shrink-0 w-8 text-right">{d.total}</span>
          </div>
        ))}
        {dados.length === 0 && <p className="text-xs text-neutral-600">Sem pedidos com estado identificado no período.</p>}
      </div>
    </div>
  );
}
