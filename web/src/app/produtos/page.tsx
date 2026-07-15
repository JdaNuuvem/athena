"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { api, type Product } from "@/lib/api";

const ESTOQUE_ALERT = 10;
const ESTOQUE_CRITICO = 3;

function StockBadge({ qty }: { qty: number }) {
  if (qty <= 0) return <span className="text-[10px] bg-red-900/40 text-red-400 px-1.5 py-0.5 rounded-full font-medium">Sem estoque</span>;
  if (qty <= ESTOQUE_CRITICO) return <span className="text-[10px] bg-orange-900/40 text-orange-400 px-1.5 py-0.5 rounded-full font-medium">{qty} un</span>;
  if (qty <= ESTOQUE_ALERT) return <span className="text-[10px] bg-amber-900/30 text-amber-400 px-1.5 py-0.5 rounded-full">{qty} un</span>;
  return <span className="text-[10px] bg-emerald-900/20 text-emerald-400 px-1.5 py-0.5 rounded-full">{qty} un</span>;
}

function MargemBadge({ pct }: { pct: number }) {
  if (pct <= 0) return <span className="text-[10px] text-neutral-600">—</span>;
  if (pct < 15) return <span className="text-[10px] text-red-400 font-medium">{pct.toFixed(0)}%</span>;
  if (pct < 30) return <span className="text-[10px] text-amber-400">{pct.toFixed(0)}%</span>;
  return <span className="text-[10px] text-emerald-400">{pct.toFixed(0)}%</span>;
}

function ProdutoImagem({ src, nome }: { src?: string; nome: string }) {
  const [erro, setErro] = useState(false);
  if (!src || erro) {
    const inicial = (nome || "?").charAt(0).toUpperCase();
    return (
      <div className="w-10 h-10 rounded-md bg-neutral-800 border border-neutral-700 flex items-center justify-center text-neutral-500 text-sm font-bold shrink-0">
        {inicial}
      </div>
    );
  }
  return (
    <img
      src={src}
      alt={nome}
      className="w-10 h-10 rounded-md object-cover border border-neutral-700 shrink-0"
      onError={() => setErro(true)}
    />
  );
}

export default function ProdutosPage() {
  const [produtos, setProdutos] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [busca, setBusca] = useState("");
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const load = async (search?: string) => {
    setLoading(true);
    setError(null);
    try {
      const r = await api.listarProdutos({ busca: search });
      setProdutos((r.produtos ?? []) as Product[]);
      setTotal(r.total ?? 0);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erro ao carregar produtos");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const syncBling = async () => {
    setSyncing(true);
    setError(null);
    try {
      const r = await api.blingSyncProducts() as any;
      if (r.erros && r.erros.length > 0) setError(r.erros.join("; "));
      else if (r.sincronizados !== undefined) setError(`Sincronizados: ${r.sincronizados} produtos`);
      else if (r.erro) setError(r.erro);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao sincronizar com Bling");
    } finally {
      setSyncing(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    load(busca);
  };

  const navigate = (sku: string) => router.push(`/produtos/${sku}`);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-light text-neutral-300">Produtos</h1>
          <p className="text-xs text-neutral-500 mt-0.5">{total} produto{(total as number) !== 1 ? "s" : ""} no catálogo</p>
        </div>
        <button
          onClick={syncBling}
          disabled={syncing}
          className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs px-3 py-1.5 rounded-lg transition-colors"
        >
          {syncing ? "Sincronizando..." : "Sync Bling"}
        </button>
      </div>

      {error && (
        <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">{error}</div>
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
        <button type="submit" className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 rounded-lg text-sm transition-colors">
          Buscar
        </button>
      </form>

      {loading ? (
        <div className="text-neutral-500 text-sm">Carregando...</div>
      ) : (
        <div className="space-y-2">
          {produtos.map((p) => (
            <div
              key={p.sku}
              role="link"
              tabIndex={0}
              className="bg-neutral-900 border border-neutral-800 rounded-lg hover:border-neutral-700 hover:bg-neutral-800/30 cursor-pointer focus:outline-none focus:border-indigo-600 transition-colors"
              onClick={() => navigate(p.sku)}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") navigate(p.sku); }}
            >
              <div className="flex items-center gap-4 p-4">
                <ProdutoImagem src={p.imagem_url} nome={p.nome} />

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-sm text-neutral-200 font-medium truncate">{p.nome}</h3>
                    {(p.total_variacoes ?? 0) > 0 && (
                      <span className="text-[10px] bg-indigo-900/30 text-indigo-400 px-1.5 py-0.5 rounded-full shrink-0">
                        {p.total_variacoes} var
                      </span>
                    )}
                    {p.categoria && (
                      <span className="text-[10px] bg-neutral-800 text-neutral-500 px-1.5 py-0.5 rounded-full shrink-0">
                        {p.categoria}
                      </span>
                    )}
                  </div>
                  <p className="text-xs font-mono text-neutral-500 mt-0.5">{p.sku}</p>
                </div>

                <div className="flex items-center gap-4 shrink-0">
                  <div className="text-right">
                    <div className="text-sm text-emerald-400 font-semibold numeric">
                      R$ {Number(p.valor ?? 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                    </div>
                    <div className="text-[10px] text-neutral-500">
                      {p.total_lojas ?? 0} loja{(p.total_lojas ?? 0) !== 1 ? "s" : ""}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <div className="flex flex-col items-center gap-0.5">
                      <StockBadge qty={p.estoque_atual ?? 0} />
                      <MargemBadge pct={p.margem_pct ?? 0} />
                    </div>
                    <span className="text-neutral-600 text-sm">›</span>
                  </div>
                </div>
              </div>
            </div>
          ))}

          {produtos.length === 0 && (
            <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-8 text-center text-neutral-500 text-xs">
              Nenhum produto encontrado
            </div>
          )}
        </div>
      )}
    </div>
  );
}
