"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, type Product } from "@/lib/api";
import { useStore } from "@/lib/store-context";

const ESTOQUE_ALERT = 10;
const ESTOQUE_CRITICO = 3;
const POR_PAGINA = 30;

function colorFromName(nome: string) {
  let h = 0;
  for (let i = 0; i < nome.length; i++) h = nome.charCodeAt(i) + ((h << 5) - h);
  return `hsl(${Math.abs(h) % 360}, 45%, 35%)`;
}

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

function ProdutoImagem({ src, nome }: { src?: string | null; nome: string }) {
  const [erro, setErro] = useState(false);
  const inicial = (nome || "?").charAt(0).toUpperCase();
  const bg = colorFromName(nome);

  if (src && !erro) {
    return (
      <img
        src={src}
        alt={nome}
        className="w-12 h-12 rounded-lg object-cover border border-neutral-700 shrink-0"
        onError={() => setErro(true)}
      />
    );
  }

  return (
    <div
      className="w-12 h-12 rounded-lg border border-neutral-700 flex items-center justify-center text-white text-lg font-bold shrink-0"
      style={{ backgroundColor: bg }}
    >
      {inicial}
    </div>
  );
}

function Pagination({ pagina, total, onChange }: { pagina: number; total: number; onChange: (p: number) => void }) {
  const totalPaginas = Math.max(1, Math.ceil(total / POR_PAGINA));
  if (totalPaginas <= 1) return null;

  const paginas: number[] = [];
  for (let i = 1; i <= totalPaginas; i++) {
    if (i === 1 || i === totalPaginas || Math.abs(i - pagina) <= 2) paginas.push(i);
    else if (paginas[paginas.length - 1] !== -1) paginas.push(-1);
  }

  return (
    <div className="flex items-center justify-center gap-1 pt-4">
      <button
        disabled={pagina <= 1}
        onClick={() => onChange(pagina - 1)}
        className="px-2 py-1 text-xs rounded bg-neutral-800 text-neutral-400 hover:bg-neutral-700 disabled:opacity-30"
      >
        ‹
      </button>
      {paginas.map((p, i) =>
        p === -1 ? (
          <span key={`gap-${i}`} className="text-neutral-600 text-xs px-1">…</span>
        ) : (
          <button
            key={p}
            onClick={() => onChange(p)}
            className={`px-2.5 py-1 text-xs rounded ${
              p === pagina
                ? "bg-indigo-600 text-white"
                : "bg-neutral-800 text-neutral-400 hover:bg-neutral-700"
            }`}
          >
            {p}
          </button>
        )
      )}
      <button
        disabled={pagina >= totalPaginas}
        onClick={() => onChange(pagina + 1)}
        className="px-2 py-1 text-xs rounded bg-neutral-800 text-neutral-400 hover:bg-neutral-700 disabled:opacity-30"
      >
        ›
      </button>
    </div>
  );
}

export default function ProdutosPage() {
  const { lojaId } = useStore();
  const [produtos, setProdutos] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState(1);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [mostrarVariacoes, setMostrarVariacoes] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const load = useCallback(async (search?: string, pg?: number, vars?: boolean) => {
    setLoading(true);
    setError(null);
    try {
      const p = pg ?? 1;
      const v = vars ?? mostrarVariacoes;
      const r = await api.listarProdutos({ busca: search, pagina: p, variacoes: v, loja: lojaId === "todas" ? undefined : lojaId });
      setProdutos((r.produtos ?? []) as Product[]);
      setTotal(r.total ?? 0);
      if (!search) setPagina(p);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Erro ao carregar produtos");
    } finally {
      setLoading(false);
    }
  }, [mostrarVariacoes, lojaId]);

  useEffect(() => { load(undefined, 1); }, [load]);

  useEffect(() => {
    const handler = () => load(busca, 1);
    window.addEventListener("loja-changed", handler);
    return () => window.removeEventListener("loja-changed", handler);
  }, [load, busca]);

  const toggleVariacoes = () => {
    const next = !mostrarVariacoes;
    setMostrarVariacoes(next);
    load(busca, 1, next);
  };

  const syncBling = async () => {
    setSyncing(true);
    setError(null);
    try {
      const r = await api.blingSyncProducts() as any;
      if (r.erros && r.erros.length > 0) setError(r.erros.join("; "));
      else if (r.sincronizados !== undefined) setError(`Sincronizados: ${r.sincronizados} produtos`);
      else if (r.erro) setError(r.erro);
      load(busca, 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao sincronizar com Bling");
    } finally {
      setSyncing(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    load(busca, 1);
  };

  const navigate = (sku: string) => router.push(`/produtos/${sku}`);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-light text-neutral-300">Produtos</h1>
          <p className="text-xs text-neutral-500 mt-0.5">{total} produto{total !== 1 ? "s" : ""} no catálogo</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleVariacoes}
            className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${
              mostrarVariacoes
                ? "bg-amber-600 hover:bg-amber-500 text-white"
                : "bg-neutral-800 hover:bg-neutral-700 text-neutral-400"
            }`}
          >
            {mostrarVariacoes ? "Só pais" : "Mostrar variações"}
          </button>
          <button
            onClick={syncBling}
            disabled={syncing}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs px-3 py-1.5 rounded-lg transition-colors"
          >
            {syncing ? "Sincronizando..." : "Sync Bling"}
          </button>
        </div>
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
              <div className="flex items-center gap-4 p-3">
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

          <Pagination pagina={pagina} total={total} onChange={(p) => load(busca, p)} />
        </div>
      )}
    </div>
  );
}
