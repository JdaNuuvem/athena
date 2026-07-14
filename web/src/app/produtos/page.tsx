"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api, type Product } from "@/lib/api";

export default function ProdutosPage() {
  const [produtos, setProdutos] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [busca, setBusca] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const load = async (search?: string) => {
    setLoading(true);
    setError(null);
    try {
      const r = await api.listarProdutos({ busca: search });
      setProdutos(r.produtos as Product[]);
      setTotal(r.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erro ao carregar produtos");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    load(busca);
  };

  const navigate = (sku: string) => router.push(`/produtos/${sku}`);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-lg font-light text-neutral-300">Produtos</h1>

      {error && (
        <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      <form onSubmit={handleSearch} className="flex gap-2 max-w-md">
        <label htmlFor="busca" className="sr-only">Buscar produto</label>
        <input
          id="busca"
          type="text"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          placeholder="Buscar por SKU ou nome..."
          className="flex-1 bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-transparent"
        />
        <button
          type="submit"
          className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 rounded-lg text-sm transition-colors"
        >
          Buscar
        </button>
      </form>

      {loading ? (
        <div className="text-neutral-500 text-sm">Carregando...</div>
      ) : (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
          <table className="w-full text-sm min-w-[640px]">
            <thead>
              <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
                <th className="text-left p-3 font-medium">SKU</th>
                <th className="text-left p-3 font-medium">Nome</th>
                <th className="text-right p-3 font-medium">Margem</th>
                <th className="text-right p-3 font-medium">Receita (30d)</th>
                <th className="text-right p-3 font-medium">Vendidos</th>
                <th className="text-center p-3 font-medium">Lojas</th>
              </tr>
            </thead>
            <tbody>
              {produtos.map((p) => (
                <tr
                  key={p.sku}
                  role="link"
                  tabIndex={0}
                  aria-label={`Ver produto ${p.nome}`}
                  className="border-b border-neutral-800/50 last:border-0 hover:bg-neutral-800/30 cursor-pointer focus:outline-none focus:bg-neutral-800/50"
                  onClick={() => navigate(p.sku)}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") navigate(p.sku); }}
                >
                  <td className="p-3 text-indigo-400 font-mono text-xs numeric">{p.sku}</td>
                  <td className="p-3 text-neutral-300">{p.nome}</td>
                  <td className="p-3 text-right numeric">
                    <span className={(p.margem_pct ?? 0) >= 25 ? "text-green-400" : (p.margem_pct ?? 0) >= 15 ? "text-yellow-400" : "text-red-400"}>
                      {(p.margem_pct ?? 0).toFixed(1)}%
                    </span>
                  </td>
                  <td className="p-3 text-right text-neutral-300 numeric">
                    R$ {(p.receita_30d ?? 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="p-3 text-right text-neutral-400 numeric">{p.vendidos_30d ?? 0}</td>
                  <td className="p-3 text-center">
                    <span className="text-xs bg-neutral-800 text-neutral-400 px-2 py-0.5 rounded-full numeric">
                      {p.total_lojas ?? 0}
                    </span>
                  </td>
                </tr>
              ))}
              {produtos.length === 0 && (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-neutral-500 text-xs">
                    Nenhum produto encontrado
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <div className="border-t border-neutral-800 p-3 text-xs text-neutral-500 text-right numeric">
            {total} produto{(total as number) !== 1 ? "s" : ""} encontrado{(total as number) !== 1 ? "s" : ""}
          </div>
        </div>
      )}
    </div>
  );
}
