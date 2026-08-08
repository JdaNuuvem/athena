"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { api, type ShopeeProdutoSincronizado } from "@/lib/api";
import { fmtBRL } from "@/lib/format";
import Icon from "@/app/_components/Icon";

interface AnunciosShopeeTabProps {
  lojaId: number;
  lojaNome: string;
}

type Ordenacao = "mais_vendidos" | "az" | "preco_asc" | "preco_desc";

const ORDENACOES: { value: Ordenacao; label: string }[] = [
  { value: "mais_vendidos", label: "Mais vendidos" },
  { value: "az", label: "A-Z" },
  { value: "preco_asc", label: "Menor preço" },
  { value: "preco_desc", label: "Maior preço" },
];

const STATUS_COR: Record<string, string> = {
  ativo: "bg-emerald-500/20 text-emerald-400",
  normal: "bg-emerald-500/20 text-emerald-400",
  pausado: "bg-amber-500/20 text-amber-400",
  banido: "bg-red-500/20 text-red-400",
};

// Puxa os anuncios ja sincronizados da loja Shopee selecionada (tabela
// "anuncios") e deixa ordenar/filtrar client-side — volume por loja e'
// pequeno o bastante (algumas centenas) pra nao precisar paginacao server-side.
export default function AnunciosShopeeTab({ lojaId, lojaNome }: AnunciosShopeeTabProps) {
  const [produtos, setProdutos] = useState<ShopeeProdutoSincronizado[]>([]);
  const [loading, setLoading] = useState(true);
  const [sincronizando, setSincronizando] = useState(false);
  const [busca, setBusca] = useState("");
  const [ordenacao, setOrdenacao] = useState<Ordenacao>("mais_vendidos");

  const fetchProdutos = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.shopeeProdutosSincronizados(lojaId, 90);
      setProdutos(r.produtos || []);
    } catch { setProdutos([]); }
    finally { setLoading(false); }
  }, [lojaId]);

  useEffect(() => { fetchProdutos(); }, [fetchProdutos]);

  const handleSincronizar = async () => {
    setSincronizando(true);
    try { await api.shopeeSync(lojaId); await fetchProdutos(); }
    catch (e) { alert(String(e)); }
    finally { setSincronizando(false); }
  };

  const exibidos = useMemo(() => {
    let lista = produtos;
    if (busca) {
      const q = busca.toLowerCase();
      lista = lista.filter(p => p.titulo?.toLowerCase().includes(q) || p.sku?.toLowerCase().includes(q));
    }
    const ordenada = [...lista];
    switch (ordenacao) {
      case "mais_vendidos": ordenada.sort((a, b) => (b.qtd_vendida || 0) - (a.qtd_vendida || 0)); break;
      case "az": ordenada.sort((a, b) => (a.titulo || "").localeCompare(b.titulo || "", "pt-BR")); break;
      case "preco_asc": ordenada.sort((a, b) => (a.preco || 0) - (b.preco || 0)); break;
      case "preco_desc": ordenada.sort((a, b) => (b.preco || 0) - (a.preco || 0)); break;
    }
    return ordenada;
  }, [produtos, busca, ordenacao]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-neutral-200">Anúncios — {lojaNome}</h3>
          {!loading && (
            <span className="rounded-full bg-neutral-800 px-2 py-0.5 text-[10px] font-medium text-neutral-400">{exibidos.length}</span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Icon name="search" size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-500" />
            <input
              type="text"
              placeholder="Buscar por título ou SKU..."
              value={busca}
              onChange={e => setBusca(e.target.value)}
              className="w-56 rounded-lg border border-neutral-700 bg-neutral-800 py-1.5 pl-8 pr-3 text-xs text-neutral-200 placeholder-neutral-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
            />
          </div>
          <select
            value={ordenacao}
            onChange={e => setOrdenacao(e.target.value as Ordenacao)}
            className="rounded-lg border border-neutral-700 bg-neutral-800 py-1.5 px-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
          >
            {ORDENACOES.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <button
            onClick={handleSincronizar}
            disabled={sincronizando}
            className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-500 disabled:opacity-50"
          >
            <Icon name="automacoes" size={13} className={sincronizando ? "animate-spin" : ""} />
            {sincronizando ? "Sincronizando..." : "Sincronizar"}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-xl border border-neutral-800 bg-neutral-900/40" />
          ))}
        </div>
      ) : exibidos.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-neutral-800 bg-neutral-900/40 py-10 text-neutral-500">
          <Icon name="inbox" size={22} />
          <span className="text-xs">{busca ? "Nenhum anúncio corresponde à busca" : "Nenhum anúncio sincronizado ainda — clique em Sincronizar"}</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {exibidos.map(p => (
            <div key={`${p.sku}-${p.anuncio_id}`} className="flex gap-3 rounded-xl border border-neutral-800 bg-neutral-900/40 p-3">
              <div className="h-16 w-16 shrink-0 overflow-hidden rounded-lg bg-neutral-800">
                {p.imagem_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={p.imagem_url} alt={p.titulo} className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full w-full items-center justify-center text-neutral-600">
                    <Icon name="produtos" size={20} />
                  </div>
                )}
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <p className="truncate text-xs font-medium text-neutral-200" title={p.titulo}>{p.titulo}</p>
                <p className="text-[10px] text-neutral-500">SKU {p.sku}</p>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-emerald-400">{fmtBRL(p.preco || 0)}</span>
                  <span className={`rounded px-1.5 py-0.5 text-[10px] ${STATUS_COR[p.status] ?? "bg-neutral-500/20 text-neutral-400"}`}>{p.status}</span>
                </div>
                <div className="flex items-center gap-3 text-[10px] text-neutral-500">
                  <span>Estoque: {p.estoque}</span>
                  <span>Vendidos (90d): {p.qtd_vendida}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
