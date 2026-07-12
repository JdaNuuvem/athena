"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";

export default function ProdutoDetailPage() {
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

  const estoque = (produto.estoque_lojas as Array<{ marketplace: string; preco: number; posicao_busca: number; avaliacao_media: number; status: string }>) || [];

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <div>
        <a href="/produtos" className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors">
          ← Produtos
        </a>
        <h1 className="text-lg font-light text-neutral-300 mt-1">{produto.nome as string}</h1>
        <span className="text-xs font-mono text-indigo-400 numeric">{sku}</span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <DetailBox label="Margem" value={`${Number(produto.margem_pct || 0).toFixed(1)}%`} />
        <DetailBox label="Receita (30d)" value={`R$ ${Number(produto.receita_30d || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`} />
        <DetailBox label="Vendidos (30d)" value={String(produto.vendidos_30d || 0)} />
        <DetailBox label="Lucro (30d)" value={`R$ ${Number(produto.lucro_30d || 0).toFixed(2)}`} />
      </div>

      {estoque.length > 0 && (
        <section>
          <h2 className="text-xs text-neutral-500 uppercase tracking-wider mb-2">Lojas / Marketplaces</h2>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
            <table className="w-full text-sm min-w-[480px]">
              <thead>
                <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
                  <th className="text-left p-3 font-medium">Loja</th>
                  <th className="text-right p-3 font-medium">Preço</th>
                  <th className="text-right p-3 font-medium">Posição</th>
                  <th className="text-right p-3 font-medium">Avaliação</th>
                  <th className="text-center p-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {estoque.map((e, i) => (
                  <tr key={i} className="border-b border-neutral-800/50 last:border-0">
                    <td className="p-3 text-neutral-300">{e.marketplace}</td>
                    <td className="p-3 text-right text-neutral-300 numeric">R$ {e.preco.toFixed(2)}</td>
                    <td className="p-3 text-right text-neutral-400 numeric">{e.posicao_busca ?? "—"}</td>
                    <td className="p-3 text-right text-neutral-400 numeric">{e.avaliacao_media ?? "—"}</td>
                    <td className="p-3 text-center">
                      <span className={`text-[10px] px-2 py-0.5 rounded-full ${e.status === "ativo" ? "bg-green-900/50 text-green-400" : "bg-neutral-800 text-neutral-400"}`}>
                        {e.status}
                      </span>
                    </td>
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

function DetailBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
      <div className="text-[10px] text-neutral-500 uppercase tracking-wider mb-1">{label}</div>
      <div className="text-xl font-light text-neutral-100 numeric">{value}</div>
    </div>
  );
}
