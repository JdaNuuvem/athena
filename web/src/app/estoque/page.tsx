"use client";

import { useState, useEffect, useCallback } from "react";
import { useStore } from "@/lib/store-context";
import {
  api,
  listarBlingProdutos, listarBlingDepositos, obterSaldoDeposito,
  atualizarEstoqueDeposito, BlingDeposito,
} from "@/lib/api";

interface LojaInfo { id: number; nome: string; ativa: boolean; bling_id?: number | null; }
interface EstoqueRow {
  id: number; sku: string; nome: string; deposito: string; quantidade: number; imagemURL: string;
  situacao: string; preco: number; totalEstoque: number; estoques: Record<number, number>;
  marca: string; fornecedorNome: string; estoqueMinimo: number | null; estoqueMaximo: number | null; custoUnit: number | null;
}

export default function EstoquePage() {
  const { lojaId, lojas } = useStore();
  const [rows, setRows] = useState<EstoqueRow[]>([]);
  const [depositos, setDepositos] = useState<BlingDeposito[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [busca, setBusca] = useState("");
  const [stockFilter, setStockFilter] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [lojaAtiva, setLojaAtiva] = useState<LojaInfo | null>(null);

  const carregar = useCallback(async () => {
    try {
      setLoading(true); setErro(null);

      // Encontrar a loja selecionada
      const loja = lojas.find(l => String(l.id) === lojaId);
      setLojaAtiva(loja || null);

      // Carregar depositos do Bling
      const depR = await listarBlingDepositos().catch(() => ({ data: [] as BlingDeposito[] }));
      const deps = depR.data || [];
      setDepositos(deps);

      // Determinar quais depositos filtrar
      let depositosFiltrados = deps;
      if (loja && loja.bling_id) {
        depositosFiltrados = deps.filter(d => d.id === loja.bling_id);
      }

      // Carregar produtos
      const prodR = await listarBlingProdutos(1, 200);
      const products = prodR.data || [];

      // Carregar limites (min/max, fornecedor, custo) do catalogo local, indexado por SKU
      const limites = await api.produtosLimites().catch(() => ({} as Record<string, import("@/lib/api").ProdutoLimites>));

      // Carregar estoque para cada produto nos depositos filtrados
      const stockRows: EstoqueRow[] = [];
      for (const p of products) {
        const estoques: Record<number, number> = {};
        let total = 0;
        for (const d of depositosFiltrados) {
          try {
            const r = await obterSaldoDeposito(d.id, [p.id]);
            const item = (r.data || []).find((x: any) => x.idProduto === p.id);
            const saldo = item ? (item.saldo ?? item.saldoFisico ?? item.saldoVirtual ?? 0) : 0;
            estoques[d.id] = saldo;
            total += saldo;
          } catch { estoques[d.id] = 0; }
        }
        const lim = limites[p.codigo];
        stockRows.push({
          id: p.id, sku: p.codigo,
          nome: (p as any).nome || p.descricao || (p as any).descricaoCurta || "—",
          deposito: loja?.nome || "Todas",
          quantidade: total,
          imagemURL: (p as any).imagemURL || "",
          situacao: p.situacao || "A",
          preco: p.preco || 0,
          totalEstoque: total,
          estoques,
          marca: lim?.marca || "",
          fornecedorNome: lim?.fornecedor_nome || "",
          estoqueMinimo: lim?.estoque_minimo ?? null,
          estoqueMaximo: lim?.estoque_maximo ?? null,
          custoUnit: lim?.preco_custo ?? null,
        });
      }
      setRows(stockRows);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar");
    } finally { setLoading(false); }
  }, [lojaId, lojas]);

  useEffect(() => { carregar(); }, [carregar]);

  const handleSyncBling = async () => {
    setSyncing(true);
    try {
      const r = await fetch("/api/lojas/sync/bling", { method: "POST" });
      const d = await r.json();
      if (d.error) setErro(d.error);
      else {
        setSucesso(`${d.sync} lojas sincronizadas do Bling`);
        carregar();
      }
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro"); }
    finally { setSyncing(false); }
  };

  const handleQuickStock = async (prod: EstoqueRow, depId: number, delta: number) => {
    try {
      await atualizarEstoqueDeposito({
        idDeposito: depId, idProduto: prod.id,
        operacao: delta > 0 ? "E" : "S", quantidade: Math.abs(delta),
      });
      setSucesso(`${prod.sku}: ${delta > 0 ? "+" : ""}${delta}`);
      carregar();
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro"); }
  };

  const filtered = rows.filter(r => {
    if (!busca) return true;
    const t = busca.toLowerCase();
    return r.sku.toLowerCase().includes(t) || r.nome.toLowerCase().includes(t) || String(r.id).includes(t);
  }).filter(r => {
    const limite = r.estoqueMinimo ?? 10; // usa o minimo real do Bling quando disponivel
    if (stockFilter === "zero") return r.totalEstoque <= 0;
    if (stockFilter === "baixo") return r.totalEstoque > 0 && r.totalEstoque < limite;
    if (stockFilter === "ok") return r.totalEstoque >= limite;
    return true;
  });

  const stockColor = (q: number, minimo?: number | null) => {
    const limite = minimo ?? 10;
    return q <= 0 ? "text-red-400" : q < limite ? "text-yellow-400" : "text-emerald-400";
  };
  const totalGeral = rows.reduce((s, r) => s + r.totalEstoque, 0);

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-neutral-100">Estoque</h1>
          <p className="text-xs text-neutral-500 mt-1">
            {lojaAtiva ? `Loja: ${lojaAtiva.nome}` : "Todas as lojas"} &middot; {filtered.length} produtos &middot; {totalGeral} itens
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={handleSyncBling} disabled={syncing}
            className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500 disabled:opacity-50">
            {syncing ? "Sincronizando..." : "Sync Lojas Bling"}
          </button>
          <button onClick={() => carregar()}
            className="px-3 py-1.5 bg-neutral-700 text-neutral-300 text-xs rounded-lg hover:bg-neutral-600">
            Atualizar Estoque
          </button>
        </div>
      </div>

      {erro && <div className="bg-red-900/30 border border-red-800 text-red-400 text-xs px-3 py-2 rounded-lg">{erro}</div>}
      {sucesso && <div className="bg-emerald-900/30 border border-emerald-800 text-emerald-400 text-xs px-3 py-2 rounded-lg">{sucesso}</div>}

      {!lojaAtiva && lojaId !== "todas" && (
        <div className="bg-amber-900/30 border border-amber-800 text-amber-400 text-xs px-3 py-2 rounded-lg">
          Loja nao encontrada nos depositos Bling. Clique em Sync Lojas Bling para importar.
        </div>
      )}

      {/* Filtros */}
      <div className="flex flex-wrap gap-2">
        <input type="text" value={busca} onChange={e => setBusca(e.target.value)}
          placeholder="Buscar SKU, nome ou ID..." className="flex-1 min-w-[200px] bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500" />
        <select value={stockFilter} onChange={e => setStockFilter(e.target.value)} className="bg-neutral-800 border border-neutral-700 rounded-lg px-2 py-1.5 text-xs text-neutral-200">
          <option value="">Todo estoque</option><option value="zero">Sem estoque</option><option value="baixo">Baixo (&lt;10)</option><option value="ok">Com estoque</option>
        </select>
        <span className="text-xs text-neutral-500 py-1.5">{filtered.length} resultados</span>
      </div>

      {/* Depósitos visíveis */}
      {depositos.length > 0 && lojaId === "todas" && (
        <div className="flex flex-wrap gap-1">
          {depositos.map(d => (
            <span key={d.id} className="text-[10px] bg-neutral-800 border border-neutral-700 text-neutral-400 px-2 py-0.5 rounded-full">{d.descricao}</span>
          ))}
        </div>
      )}

      {/* Tabela */}
      {loading ? (
        <div className="text-neutral-500 text-sm py-8 text-center">Carregando estoque do Bling...</div>
      ) : filtered.length === 0 ? (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center">
          <p className="text-neutral-400 text-sm">Nenhum produto encontrado</p>
          <p className="text-neutral-600 text-xs mt-1">Selecione uma loja ou sincronize com o Bling</p>
        </div>
      ) : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="text-left p-2 w-10"></th>
                <th className="text-left p-2">SKU</th>
                <th className="text-left p-2">Nome</th>
                {lojaId === "todas" && depositos.slice(0, 4).map(d => (
                  <th key={d.id} className="text-right p-2 w-16">{d.descricao?.slice(0, 8)}</th>
                ))}
                <th className="text-right p-2 font-bold">Total</th>
                <th className="text-right p-2">Mín/Máx</th>
                <th className="text-left p-2">Fornecedor</th>
                <th className="text-right p-2">Preco</th>
                <th className="text-center p-2">Acoes</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r, i) => (
                <tr key={r.id} className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}>
                  <td className="p-1.5">
                    {r.imagemURL ? <img src={r.imagemURL} alt="" className="w-6 h-6 object-cover rounded bg-neutral-700" /> : <div className="w-6 h-6 rounded bg-neutral-700" />}
                  </td>
                  <td className="p-2 text-neutral-200 font-mono text-[11px]">{r.sku}</td>
                  <td className="p-2 text-neutral-200 max-w-[160px] truncate" title={r.nome}>
                    {r.nome}
                    {r.marca && <span className="block text-[9px] text-neutral-500">{r.marca}</span>}
                  </td>
                  {lojaId === "todas" && depositos.slice(0, 4).map(d => (
                    <td key={d.id} className="p-2 text-right font-mono">
                      <span className={stockColor(r.estoques[d.id] || 0, r.estoqueMinimo)} title="Clique +/- para ajustar">
                        {r.estoques[d.id] || 0}
                      </span>
                      <div className="flex justify-end gap-0.5 mt-0.5">
                        <button onClick={() => handleQuickStock(r, d.id, -1)} className="text-[9px] text-neutral-600 hover:text-red-400">−</button>
                        <button onClick={() => handleQuickStock(r, d.id, 1)} className="text-[9px] text-neutral-600 hover:text-emerald-400">+</button>
                      </div>
                    </td>
                  ))}
                  <td className={`p-2 text-right font-bold ${stockColor(r.totalEstoque, r.estoqueMinimo)}`}>{r.totalEstoque}</td>
                  <td className="p-2 text-right text-neutral-500 font-mono text-[10px]">
                    {r.estoqueMinimo != null || r.estoqueMaximo != null
                      ? `${r.estoqueMinimo ?? "—"} / ${r.estoqueMaximo ?? "—"}`
                      : "—"}
                  </td>
                  <td className="p-2 text-neutral-400 max-w-[140px] truncate" title={r.fornecedorNome}>{r.fornecedorNome || "—"}</td>
                  <td className="p-2 text-right text-emerald-400">R$ {(r.preco || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
                  <td className="p-2 text-center">
                    <span className={`px-1.5 py-0.5 rounded text-[9px] ${r.situacao === "A" ? "bg-emerald-900/30 text-emerald-400" : "bg-neutral-700 text-neutral-400"}`}>{r.situacao === "A" ? "Ativo" : "Inativo"}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
