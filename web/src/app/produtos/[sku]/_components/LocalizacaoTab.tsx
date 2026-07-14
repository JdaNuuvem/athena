"use client";

const posicoesMock = [
  { rua: "A", prateleira: "01", caixa: "B2", palete: "P01", qtd: 120, lote: "L2025-0710A" },
  { rua: "A", prateleira: "01", caixa: "B3", palete: "P01", qtd: 80, lote: "L2025-0620B" },
  { rua: "A", prateleira: "03", caixa: "A1", palete: "P02", qtd: 45, lote: "L2025-0301D" },
  { rua: "B", prateleira: "02", caixa: "C4", palete: "P03", qtd: 200, lote: "L2025-0710A" },
  { rua: "C", prateleira: "04", caixa: "D1", palete: "P04", qtd: 15, lote: "L2025-0620B" },
];

const ruas = [...new Set(posicoesMock.map((p) => p.rua))].sort();

function getRuaColor(rua: string) {
  const colors = ["border-l-indigo-500", "border-l-emerald-500", "border-l-amber-500"];
  return colors[ruas.indexOf(rua) % colors.length];
}

export default function LocalizacaoTab() {
  const totalPorRua = ruas.map((rua) => ({
    rua,
    total: posicoesMock.filter((p) => p.rua === rua).reduce((s, p) => s + p.qtd, 0),
  }));

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-sm font-medium text-neutral-400 mb-3">Visão do Armazém</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {totalPorRua.map((r) => (
            <div key={r.rua} className={`bg-neutral-900 border border-neutral-800 border-l-4 ${getRuaColor(r.rua)} rounded-lg p-4`}>
              <p className="text-xs text-neutral-500 uppercase">Rua {r.rua}</p>
              <p className="text-lg font-medium text-neutral-200 numeric mt-1">{r.total} un</p>
              <p className="text-[10px] text-neutral-600">{posicoesMock.filter((p) => p.rua === r.rua).length} posições</p>
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium text-neutral-400">Posições de Estoque</h2>
          <button className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1.5 rounded-lg transition-colors">+ Nova Posição</button>
        </div>
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
          <table className="w-full text-sm min-w-[640px]">
            <thead>
              <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
                <th className="text-left p-3 font-medium">Rua</th>
                <th className="text-left p-3 font-medium">Prateleira</th>
                <th className="text-left p-3 font-medium">Caixa</th>
                <th className="text-left p-3 font-medium">Palete</th>
                <th className="text-right p-3 font-medium">Qtd</th>
                <th className="text-left p-3 font-medium">Lote</th>
              </tr>
            </thead>
            <tbody>
              {posicoesMock.map((p, i) => (
                <tr key={i} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                  <td className="p-3">
                    <span className={`inline-block w-2 h-2 rounded-full mr-2 ${p.rua === "A" ? "bg-indigo-500" : p.rua === "B" ? "bg-emerald-500" : "bg-amber-500"}`} />
                    <span className="text-neutral-300 font-medium">{p.rua}</span>
                  </td>
                  <td className="p-3 text-neutral-300">{p.prateleira}</td>
                  <td className="p-3 text-neutral-400 font-mono text-xs">{p.caixa}</td>
                  <td className="p-3 text-neutral-400 font-mono text-xs">{p.palete}</td>
                  <td className="p-3 text-right text-neutral-300 numeric">{p.qtd}</td>
                  <td className="p-3 text-neutral-400 text-xs font-mono">{p.lote}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
