"use client";

import { useState, useEffect, useCallback } from "react";
import { api, type EstoqueRapidoLoja, type EstoqueRapidoProduto } from "@/lib/api";
import { Can } from "@/lib/auth";

type CellStatus = "idle" | "salvando" | "ok" | "erro";

export default function EstoqueRapidoPage() {
  const [lojas, setLojas] = useState<EstoqueRapidoLoja[]>([]);
  const [produtos, setProdutos] = useState<EstoqueRapidoProduto[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState(1);
  const POR_PAGINA = 50;

  const [valores, setValores] = useState<Record<string, string>>({});
  const [status, setStatus] = useState<Record<string, CellStatus>>({});
  const [mensagemErro, setMensagemErro] = useState<Record<string, string>>({});

  const chave = (sku: string, lojaId: number) => `${sku}:${lojaId}`;

  const load = useCallback(async (buscaAtual: string, pg: number) => {
    setLoading(true);
    setErro(null);
    try {
      const r = await api.shopeeEstoqueRapidoListar({ busca: buscaAtual, pagina: pg, por_pagina: POR_PAGINA });
      setLojas(r.lojas);
      setProdutos(r.produtos);
      setTotal(r.total);
      const iniciais: Record<string, string> = {};
      r.produtos.forEach((p) => {
        r.lojas.forEach((l) => {
          const q = p.estoque[l.id];
          if (q !== null && q !== undefined) iniciais[chave(p.sku, l.id)] = String(q);
        });
      });
      setValores(iniciais);
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar grid de estoque");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(busca, 1); }, [load]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPagina(1);
    load(busca, 1);
  };

  const salvarCelula = async (sku: string, lojaId: number) => {
    const k = chave(sku, lojaId);
    const quantidade = Number(valores[k]);
    if (!Number.isFinite(quantidade) || quantidade < 0) return;
    setStatus((s) => ({ ...s, [k]: "salvando" }));
    try {
      const r = await api.shopeeEstoqueRapidoAtualizarCelula(sku, lojaId, quantidade);
      if (!r.ok) {
        setStatus((s) => ({ ...s, [k]: "erro" }));
        setMensagemErro((m) => ({ ...m, [k]: r.erro_shopee || r.erro_local || "Falha ao salvar" }));
      } else {
        setStatus((s) => ({ ...s, [k]: "ok" }));
        setMensagemErro((m) => ({ ...m, [k]: "" }));
      }
      if (r.linha) {
        setProdutos((prev) => prev.map((p) => (p.sku === r.linha!.sku ? r.linha! : p)));
        const novosValores: Record<string, string> = {};
        lojas.forEach((l) => {
          const q = r.linha!.estoque[l.id];
          if (q !== null && q !== undefined) novosValores[chave(r.linha!.sku, l.id)] = String(q);
        });
        setValores((v) => ({ ...v, ...novosValores }));
      }
    } catch (e: unknown) {
      setStatus((s) => ({ ...s, [k]: "erro" }));
      setMensagemErro((m) => ({ ...m, [k]: e instanceof Error ? e.message : "Erro ao salvar" }));
    }
  };

  const totalPaginas = Math.max(1, Math.ceil(total / POR_PAGINA));

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-lg font-light text-neutral-300">Estoque Rápido</h1>
        <p className="text-xs text-neutral-500 mt-0.5">{total} SKU{total !== 1 ? "s" : ""} com anúncio em alguma loja Shopee</p>
      </div>

      {erro && (
        <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">{erro}</div>
      )}

      <form onSubmit={handleSearch} className="flex gap-2 max-w-md">
        <label htmlFor="buscaRapido" className="sr-only">Buscar SKU</label>
        <input
          id="buscaRapido"
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
      ) : lojas.length === 0 ? (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-8 text-center text-neutral-500 text-xs">
          Nenhuma loja Shopee conectada. Conecte uma loja em{" "}
          <a href="/integracoes/shopee" className="text-indigo-400 underline">Integrações &gt; Shopee</a>.
        </div>
      ) : produtos.length === 0 ? (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-8 text-center text-neutral-500 text-xs">
          Nenhum SKU encontrado com anúncio Shopee.
        </div>
      ) : (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-800 text-neutral-500 text-xs uppercase">
                  <th className="text-left px-4 py-3 font-medium">SKU</th>
                  {lojas.map((l) => (
                    <th key={l.id} className="text-right px-4 py-3 font-medium w-32">{l.nome}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {produtos.map((p) => (
                  <tr key={p.sku} className="border-b border-neutral-800/50 hover:bg-neutral-800/20">
                    <td className="px-4 py-2.5">
                      <div className="font-mono text-xs text-neutral-500">{p.sku}</div>
                      <div className="text-neutral-300 text-xs max-w-64 truncate">{p.nome}</div>
                    </td>
                    {lojas.map((l) => {
                      const temAnuncio = p.estoque[l.id] !== null && p.estoque[l.id] !== undefined;
                      const k = chave(p.sku, l.id);
                      const st = status[k] ?? "idle";
                      if (!temAnuncio) {
                        return <td key={l.id} className="px-4 py-2.5 text-right text-neutral-600 text-xs">—</td>;
                      }
                      return (
                        <td key={l.id} className="px-4 py-2.5 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <Can permission="produtos.editar">
                              <input
                                type="number"
                                min="0"
                                step="1"
                                value={valores[k] ?? ""}
                                onChange={(e) => setValores((v) => ({ ...v, [k]: e.target.value }))}
                                onBlur={() => salvarCelula(p.sku, l.id)}
                                onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
                                disabled={st === "salvando"}
                                title={st === "erro" ? mensagemErro[k] : undefined}
                                className={`w-20 bg-neutral-800 border rounded px-2 py-1 text-xs text-right text-neutral-200 numeric focus:outline-none disabled:opacity-60 ${
                                  st === "erro" ? "border-red-600" : st === "ok" ? "border-emerald-700" : "border-neutral-700"
                                }`}
                              />
                            </Can>
                            {st === "salvando" && <span className="text-neutral-500 text-[10px]">...</span>}
                            {st === "ok" && <span className="text-emerald-400 text-xs">✓</span>}
                            {st === "erro" && <span className="text-red-400 text-xs" title={mensagemErro[k]}>✗</span>}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {totalPaginas > 1 && (
        <div className="flex items-center justify-center gap-1">
          <button disabled={pagina <= 1} onClick={() => { setPagina(pagina - 1); load(busca, pagina - 1); }}
            className="px-2 py-1 text-xs rounded bg-neutral-800 text-neutral-400 hover:bg-neutral-700 disabled:opacity-30">Anterior</button>
          <span className="text-xs text-neutral-500 px-2">{pagina} / {totalPaginas}</span>
          <button disabled={pagina >= totalPaginas} onClick={() => { setPagina(pagina + 1); load(busca, pagina + 1); }}
            className="px-2 py-1 text-xs rounded bg-neutral-800 text-neutral-400 hover:bg-neutral-700 disabled:opacity-30">Próxima</button>
        </div>
      )}
    </div>
  );
}
