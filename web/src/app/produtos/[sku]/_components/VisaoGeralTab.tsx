"use client";

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

interface Props {
  produto: Record<string, unknown>;
  formatarMoeda: (v: unknown) => string;
}

const vendasDiariasMock = [
  { dia: "01/07", vendas: 12 }, { dia: "05/07", vendas: 18 }, { dia: "10/07", vendas: 8 },
  { dia: "15/07", vendas: 22 }, { dia: "20/07", vendas: 15 }, { dia: "25/07", vendas: 28 }, { dia: "30/07", vendas: 10 },
];

export default function VisaoGeralTab({ produto, formatarMoeda }: Props) {
  const custo = Number(produto.preco_custo || 0);
  const valor = Number(produto.valor || 0);
  const margemReal = custo && valor ? (((valor - custo) / valor) * 100).toFixed(1) : null;
  const estoqueMin = produto.estoque_minimo != null ? Number(produto.estoque_minimo) : null;
  const abaixoMinimo = estoqueMin != null && Number(produto.estoque_atual || 0) < estoqueMin;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {[
          ["Margem", `${Number(produto.margem_pct || 0).toFixed(1)}%`],
          ["Margem Real (custo)", margemReal !== null ? `${margemReal}%` : "—"],
          ["Receita 30d", formatarMoeda(produto.receita_30d)],
          ["Lucro 30d", formatarMoeda(produto.lucro_30d)],
          ["Vendidos 30d", String(produto.vendidos_30d || 0)],
          ["Estoque Atual", String(produto.estoque_atual || 0)],
        ].map(([label, value]) => (
          <div key={label} className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
            <div className="text-[10px] text-neutral-500 uppercase tracking-wider mb-1">{label}</div>
            <div className="text-sm text-neutral-200 font-medium numeric">{value}</div>
          </div>
        ))}
      </div>

      <section>
        <h2 className="text-sm font-medium text-neutral-400 mb-3">Ficha do Produto</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {[
            ["Marca", String(produto.marca || "—")],
            ["Categoria", String(produto.categoria || "—")],
            ["NCM", String(produto.ncm || "—")],
            ["Código de Barras", String(produto.codigo_barras || "—")],
            ["Peso Bruto", produto.peso_bruto ? `${produto.peso_bruto} kg` : "—"],
            ["Fornecedor", String(produto.fornecedor_nome || "—")],
          ].map(([label, value]) => (
            <div key={label} className="bg-neutral-900 border border-neutral-800 rounded-lg p-3">
              <div className="text-[10px] text-neutral-500 uppercase tracking-wider mb-1">{label}</div>
              <div className="text-xs text-neutral-300 font-medium truncate" title={value}>{value}</div>
            </div>
          ))}
        </div>
        {estoqueMin != null && (
          <div className={`mt-2 text-xs px-3 py-2 rounded-lg ${abaixoMinimo ? "bg-red-900/30 text-red-400 border border-red-800" : "bg-neutral-900 text-neutral-500 border border-neutral-800"}`}>
            Estoque mínimo (Bling): {estoqueMin} un{produto.estoque_maximo != null ? ` · máximo: ${produto.estoque_maximo} un` : ""}
            {abaixoMinimo ? " — abaixo do mínimo!" : ""}
          </div>
        )}
      </section>

      <section>
        <h2 className="text-sm font-medium text-neutral-400 mb-3">Vendas Diárias (30d)</h2>
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={vendasDiariasMock}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis dataKey="dia" tick={{ fill: "#71717a", fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#71717a", fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: "8px", fontSize: 12 }} labelStyle={{ color: "#a1a1aa" }} />
              <Line type="monotone" dataKey="vendas" stroke="#818cf8" strokeWidth={2} dot={{ fill: "#818cf8", r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      {Array.isArray(produto.estoque_lojas) && (produto.estoque_lojas as unknown[]).length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-neutral-400 mb-2">Estoque por Loja</h2>
          <div className="overflow-x-auto border border-neutral-800 rounded-lg">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-neutral-900 text-neutral-400 text-left">
                  <th className="px-3 py-2 font-medium">Loja</th>
                  <th className="px-3 py-2 font-medium text-right">Preço</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {(produto.estoque_lojas as Array<Record<string, unknown>>).map((e, i) => (
                  <tr key={i} className="border-t border-neutral-800 text-neutral-300">
                    <td className="px-3 py-2">{String(e.loja || "—")}</td>
                    <td className="px-3 py-2 text-right numeric">{formatarMoeda(e.preco)}</td>
                    <td className="px-3 py-2">{String(e.status || "—")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
