import { useState } from "react";
import type { CategoriaVenda, ProdutoVenda } from "../types";
import { formatCurrency } from "../types";

interface DrillDownTableProps {
  categorias: CategoriaVenda[];
}

export default function DrillDownTable({ categorias }: DrillDownTableProps) {
  const [expandida, setExpandida] = useState<string | null>(null);

  return (
    <div className="space-y-1">
      <div className="text-xs text-neutral-500 mb-2">Clique na categoria para ver produtos</div>
      <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
              <th className="text-left p-3 w-8"></th>
              <th className="text-left p-3">Categoria</th>
              <th className="text-right p-3">Receita</th>
              <th className="text-right p-3">% Total</th>
              <th className="text-center p-3">Produtos</th>
            </tr>
          </thead>
          <tbody>
            {categorias.map((cat, i) => (
              <>
                <tr
                  key={cat.categoria}
                  onClick={() => setExpandida(expandida === cat.categoria ? null : cat.categoria)}
                  className={`border-b border-neutral-700/50 cursor-pointer hover:bg-neutral-750 ${
                    i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"
                  } ${expandida === cat.categoria ? "!bg-neutral-750" : ""}`}
                >
                  <td className="p-3 text-indigo-400">{expandida === cat.categoria ? "▼" : "▶"}</td>
                  <td className="p-3 text-neutral-200 font-medium">{cat.categoria}</td>
                  <td className="p-3 text-right text-emerald-400 font-mono">{formatCurrency(cat.valor)}</td>
                  <td className="p-3 text-right text-neutral-300">{cat.percentual}%</td>
                  <td className="p-3 text-center text-neutral-400">{cat.produtos.length}</td>
                </tr>
                {expandida === cat.categoria && cat.produtos.map((produto: ProdutoVenda) => (
                  <tr key={produto.sku} className="border-b border-neutral-700/30 bg-neutral-850">
                    <td className="p-3"></td>
                    <td className="p-3 text-neutral-400 pl-6">
                      <span className="text-neutral-300">{produto.nome}</span>
                      <span className="text-neutral-600 ml-2">({produto.sku})</span>
                    </td>
                    <td className="p-3 text-right text-neutral-400 font-mono">{formatCurrency(produto.valor)}</td>
                    <td className="p-3 text-right">
                      <span className={`text-[10px] ${
                        produto.margem >= 25 ? "text-emerald-400" : produto.margem >= 15 ? "text-amber-400" : "text-red-400"
                      }`}>Margem {produto.margem}%</span>
                    </td>
                    <td className="p-3 text-center text-neutral-500">{produto.qtd} un</td>
                  </tr>
                ))}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
