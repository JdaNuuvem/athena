"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";

export default function ProdutoClientPage() {
  const { sku } = useParams<{ sku: string }>();
  const [produto, setProduto] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.detalheProduto(sku)
      .then((d) => setProduto(d as Record<string, unknown>))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [sku]);

  if (loading) return <div className="p-6 text-neutral-500">Carregando...</div>;
  if (!produto) return <div className="p-6 text-red-400">Produto não encontrado</div>;

  const formatarMoeda = (v: unknown) => {
    const n = typeof v === "number" ? v : parseFloat(String(v || 0));
    return isNaN(n) ? 0 : n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  };

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div>
        <a href="/produtos" className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors">
          ← Produtos
        </a>
        <h1 className="text-lg font-light text-neutral-300 mt-1">
          {String(produto.descricao || produto.nome || sku)}
        </h1>
        <p className="text-xs font-mono text-neutral-500 mt-1">{sku}</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          ["Margem", `${Number(produto.margem_pct || 0).toFixed(1)}%`],
          ["Receita 30d", formatarMoeda(produto.receita_30d)],
          ["Lucro 30d", formatarMoeda(produto.lucro_30d)],
          ["Vendidos 30d", String(produto.vendidos_30d || 0)],
        ].map(([label, value]) => (
          <div key={label} className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
            <div className="text-[10px] text-neutral-500 uppercase tracking-wider mb-1">{label}</div>
            <div className="text-sm text-neutral-200 font-medium">{value}</div>
          </div>
        ))}
      </div>

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
                    <td className="px-3 py-2 text-right">{formatarMoeda(e.preco)}</td>
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
