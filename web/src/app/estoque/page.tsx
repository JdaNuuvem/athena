"use client";

import { useState, useEffect, useCallback } from "react";
import {
  listarBlingProdutos, listarBlingDepositos, obterSaldoDeposito,
  atualizarEstoqueDeposito, sincronizarBlingProdutos,
  BlingProduto, BlingDeposito,
} from "@/lib/api";

interface StockRow {
  id: number; codigo: string; nome: string; preco: number;
  situacao: string; imagemURL: string; estoques: Record<number, number>;
  totalEstoque: number;
}

export default function EstoquePage() {
  const [rows, setRows] = useState<StockRow[]>([]);
  const [depositos, setDepositos] = useState<BlingDeposito[]>([]);
  const [selectedDeps, setSelectedDeps] = useState<Set<number>>(new Set());
  const [showDepSelect, setShowDepSelect] = useState(false);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);

  // Filters
  const [busca, setBusca] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [stockFilter, setStockFilter] = useState<string>("");

  // Bulk edit
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkQty, setBulkQty] = useState(0);
  const [bulkDep, setBulkDep] = useState<number>(0);

  // Stock modal
  const [modalProduto, setModalProduto] = useState<StockRow | null>(null);

  const carregar = useCallback(async () => {
    try {
      setLoading(true); setErro(null);
      const [prodR, depR] = await Promise.all([
        listarBlingProdutos(1, 200),
        listarBlingDepositos().catch(() => ({ data: [] })),
      ]);
      const deps: BlingDeposito[] = depR.data || [];
      setDepositos(deps);
      if (selectedDeps.size === 0 && deps.length > 0) {
        setSelectedDeps(new Set([deps[0].id]));
      }
      const products: BlingProduto[] = prodR.data || [];
      const stockRows: StockRow[] = [];
      for (const p of products) {
        const estoques: Record<number, number> = {};
        let total = 0;
        for (const d of deps) {
          try {
            const r = await obterSaldoDeposito(d.id, [p.id]);
            const item = (r.data || []).find((x: any) => x.idProduto === p.id);
            const saldo = item ? (item.saldo ?? 0) : 0;
            estoques[d.id] = saldo;
            total += saldo;
          } catch { estoques[d.id] = 0; }
        }
        stockRows.push({
          id: p.id, codigo: p.codigo,
          nome: (p as any).nome || p.descricao || (p as any).descricaoCurta || "—",
          preco: p.preco || 0, situacao: p.situacao || "A",
          imagemURL: (p as any).imagemURL || "",
          estoques, totalEstoque: total,
        });
      }
      setRows(stockRows);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  const toggleDep = (id: number) => {
    setSelectedDeps(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleProduct = (id: number) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const handleBulkAdjust = async (delta: number) => {
    if (selected.size === 0 || bulkDep === 0) return;
    try {
      for (const pid of Array.from(selected)) {
        await atualizarEstoqueDeposito({
          idDeposito: bulkDep, idProduto: pid,
          operacao: delta > 0 ? "E" : "S", quantidade: Math.abs(delta),
        });
      }
      setSucesso(`${selected.size} produtos ajustados em ${delta > 0 ? "+" : ""}${delta}`);
      carregar();
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro"); }
  };

  const filtered = rows.filter(r => {
    if (statusFilter && r.situacao !== statusFilter) return false;
    if (stockFilter === "zero" && r.totalEstoque > 0) return false;
    if (stockFilter === "baixo" && r.totalEstoque >= 10) return false;
    if (stockFilter === "ok" && r.totalEstoque < 10) return false;
    if (!busca) return true;
    const t = busca.toLowerCase();
    return r.codigo.toLowerCase().includes(t) || r.nome.toLowerCase().includes(t) || String(r.id).includes(t);
  });

  const totalGeral = rows.reduce((s, r) => s + r.totalEstoque, 0);
  const stockColor = (q: number) => q <= 0 ? "text-red-400" : q < 10 ? "text-yellow-400" : "text-emerald-400";

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-neutral-100">Estoque</h1>
          <p className="text-xs text-neutral-500 mt-1">{rows.length} produtos &middot; {totalGeral} itens em estoque</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => carregar()} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">🔄 Atualizar</button>
          <button onClick={async () => { await sincronizarBlingProdutos(); carregar(); }} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">📥 Sincronizar Bling</button>
        </div>
      </div>

      {erro && <div className="bg-red-900/30 border border-red-800 text-red-400 text-xs px-3 py-2 rounded-lg">{erro}</div>}
      {sucesso && <div className="bg-emerald-900/30 border border-emerald-800 text-emerald-400 text-xs px-3 py-2 rounded-lg">{sucesso}</div>}

      {/* Store selector */}
      <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-neutral-300">Lojas / Depositos</span>
          <button onClick={() => setShowDepSelect(!showDepSelect)} className="text-xs text-indigo-400">
            {showDepSelect ? "OK" : selectedDeps.size === depositos.length ? "Todas selecionadas" : `${selectedDeps.size} selecionadas`}
          </button>
        </div>
        {showDepSelect && (
          <div className="flex flex-wrap gap-1.5">
            {depositos.map(d => (
              <button key={d.id} onClick={() => toggleDep(d.id)}
                className={`px-2 py-0.5 text-[10px] rounded-full border transition-colors ${selectedDeps.has(d.id) ? "bg-indigo-600/30 border-indigo-500 text-indigo-300" : "border-neutral-600 text-neutral-500 hover:border-neutral-500"}`}>
                {d.descricao}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <input type="text" value={busca} onChange={e => setBusca(e.target.value)}
          placeholder="Buscar SKU, nome ou ID..." className="flex-1 min-w-[200px] bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500" />
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="bg-neutral-800 border border-neutral-700 rounded-lg px-2 py-1.5 text-xs text-neutral-200">
          <option value="">Todos status</option><option value="A">Ativos</option><option value="I">Inativos</option>
        </select>
        <select value={stockFilter} onChange={e => setStockFilter(e.target.value)} className="bg-neutral-800 border border-neutral-700 rounded-lg px-2 py-1.5 text-xs text-neutral-200">
          <option value="">Todo estoque</option><option value="zero">Sem estoque</option><option value="baixo">Baixo (&lt;10)</option><option value="ok">Com estoque</option>
        </select>
        <span className="text-xs text-neutral-500 py-1.5">{filtered.length} resultados</span>
      </div>

      {/* Bulk actions */}
      {selected.size > 0 && (
        <div className="bg-indigo-900/20 border border-indigo-800 rounded-lg p-3 flex items-center gap-3">
          <span className="text-xs text-indigo-300">{selected.size} selecionados</span>
          <select value={bulkDep} onChange={e => setBulkDep(Number(e.target.value))} className="bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200">
            <option value={0}>Deposito...</option>
            {depositos.map(d => <option key={d.id} value={d.id}>{d.descricao}</option>)}
          </select>
          <input type="number" value={bulkQty} onChange={e => setBulkQty(Number(e.target.value))} placeholder="Qtd" className="w-20 bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200" />
          <button onClick={() => handleBulkAdjust(bulkQty)} className="px-2 py-1 bg-emerald-600 text-white text-xs rounded">+ Adicionar</button>
          <button onClick={() => handleBulkAdjust(-bulkQty)} className="px-2 py-1 bg-red-600 text-white text-xs rounded">− Remover</button>
          <button onClick={() => setSelected(new Set())} className="text-xs text-neutral-500 ml-auto">Limpar</button>
        </div>
      )}

      {/* Table */}
      {loading ? <div className="text-neutral-500 text-sm py-8 text-center">Carregando estoque...</div> : filtered.length === 0 ? (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center"><p className="text-neutral-400 text-sm">Nenhum produto encontrado</p></div>
      ) : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="p-2 w-8"><input type="checkbox" checked={selected.size === filtered.length && filtered.length > 0} onChange={() => selected.size === filtered.length ? setSelected(new Set()) : setSelected(new Set(filtered.map(r => r.id)))} /></th>
                <th className="text-left p-2 w-10"></th>
                <th className="text-left p-2">SKU</th>
                <th className="text-left p-2">Nome</th>
                {Array.from(selectedDeps).map(did => <th key={did} className="text-right p-2 w-20">{depositos.find(d => d.id === did)?.descricao?.slice(0,12)}</th>)}
                <th className="text-right p-2 w-20 font-bold">Total</th>
                <th className="text-right p-2">Preco</th>
                <th className="text-center p-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r, i) => (
                <tr key={r.id} className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"} ${selected.has(r.id) ? "bg-indigo-900/20" : ""}`}>
                  <td className="p-2"><input type="checkbox" checked={selected.has(r.id)} onChange={() => toggleProduct(r.id)} /></td>
                  <td className="p-1.5">{r.imagemURL ? <img src={r.imagemURL} alt="" className="w-6 h-6 object-cover rounded bg-neutral-700" /> : <div className="w-6 h-6 rounded bg-neutral-700" />}</td>
                  <td className="p-2 text-neutral-200 font-mono text-[11px]">{r.codigo}</td>
                  <td className="p-2 text-neutral-200 max-w-[180px] truncate" title={r.nome}>{r.nome}</td>
                  {Array.from(selectedDeps).map(did => (
                    <td key={did} className="p-2 text-right font-mono">
                      <span className={`cursor-pointer hover:underline ${stockColor(r.estoques[did] || 0)}`}
                        onClick={() => setModalProduto(r)} title="Clique para editar estoque">
                        {r.estoques[did] || 0}
                      </span>
                    </td>
                  ))}
                  <td className={`p-2 text-right font-bold ${stockColor(r.totalEstoque)}`}>{r.totalEstoque}</td>
                  <td className="p-2 text-right text-emerald-400">R$ {(r.preco||0).toLocaleString("pt-BR",{minimumFractionDigits:2})}</td>
                  <td className="p-2 text-center">
                    <span className={`px-1.5 py-0.5 rounded text-[9px] ${r.situacao==="A"?"bg-emerald-900/30 text-emerald-400":"bg-neutral-700 text-neutral-400"}`}>{r.situacao==="A"?"Ativo":"Inativo"}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Stock Modal */}
      {modalProduto && (
        <StockEditModal
          produto={modalProduto}
          depositos={depositos}
          onClose={() => setModalProduto(null)}
          onSaved={() => { setModalProduto(null); carregar(); }}
        />
      )}
    </div>
  );
}

// Internal stock modal
function StockEditModal({ produto, depositos, onClose, onSaved }: { produto: StockRow; depositos: BlingDeposito[]; onClose: () => void; onSaved: () => void; }) {
  const [saldos, setSaldos] = useState<{idDep:number;nome:string;saldo:number;ajuste:number}[]>([]);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    setSaldos(depositos.map(d => ({
      idDep: d.id, nome: d.descricao,
      saldo: produto.estoques[d.id] || 0, ajuste: 0,
    })));
  }, [produto, depositos]);

  const total = saldos.reduce((s,d) => s + d.saldo, 0);
  const handleAjuste = (i: number, v: number) => {
    setSaldos(prev => { const n = [...prev]; n[i] = {...n[i], ajuste: Math.max(-n[i].saldo, v)}; return n; });
  };
  const handleSplit = () => {
    const per = Math.floor(total / (saldos.length || 1));
    setSaldos(prev => prev.map(d => ({...d, ajuste: per - d.saldo})));
  };
  const handleSave = async (i: number) => {
    const s = saldos[i]; if (s.ajuste === 0) return;
    try {
      setSaving(true);
      await atualizarEstoqueDeposito({ idDeposito: s.idDep, idProduto: produto.id, operacao: s.ajuste > 0 ? "E" : "S", quantidade: Math.abs(s.ajuste) });
      setMsg(`${s.nome}: ${s.ajuste > 0 ? "+" : ""}${s.ajuste}`);
      setSaldos(prev => { const n = [...prev]; n[i] = { ...n[i], saldo: n[i].saldo + n[i].ajuste, ajuste: 0 }; return n; });
    } catch (e) { setMsg("Erro: " + (e instanceof Error ? e.message : "")); }
    finally { setSaving(false); }
  };

  const sc = (q: number) => q <= 0 ? "text-red-400" : q < 10 ? "text-yellow-400" : "text-emerald-400";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-neutral-850 border border-neutral-700 rounded-xl w-full max-w-md mx-4 shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between p-3 border-b border-neutral-700">
          <div><h3 className="text-sm font-semibold text-neutral-100">{produto.codigo}</h3><p className="text-[10px] text-neutral-500">{produto.nome}</p></div>
          <button onClick={onClose} className="text-neutral-500 hover:text-neutral-300">✕</button>
        </div>
        <div className="p-3 space-y-2 max-h-[70vh] overflow-y-auto">
          {msg && <div className="bg-emerald-900/30 text-emerald-400 text-[10px] px-2 py-1 rounded">{msg}</div>}
          <div className="flex items-center justify-between bg-neutral-900 rounded px-3 py-2">
            <span className="text-xs text-neutral-400">Total</span>
            <div className="flex items-center gap-2">
              <span className={`text-sm font-bold ${sc(total)}`}>{total}</span>
              <button onClick={handleSplit} className="text-[10px] bg-indigo-600 text-white px-2 py-0.5 rounded">Dividir</button>
            </div>
          </div>
          {saldos.map((s, i) => (
            <div key={s.idDep} className="bg-neutral-800 border border-neutral-700/50 rounded px-3 py-2">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-neutral-300 truncate max-w-[150px]">{s.nome}</span>
                <div className="flex items-center gap-2">
                  {s.ajuste !== 0 && <button onClick={() => handleSave(i)} disabled={saving} className="text-[10px] bg-emerald-600 text-white px-2 py-0.5 rounded">Salvar</button>}
                  <span className={`text-sm font-bold font-mono ${sc(s.saldo)}`}>{s.saldo}</span>
                  {s.ajuste !== 0 && <span className={`text-[10px] font-bold ${s.ajuste > 0 ? "text-emerald-400" : "text-red-400"}`}>{s.ajuste > 0 ? "+" + s.ajuste : s.ajuste}</span>}
                </div>
              </div>
              <div className="flex items-center gap-1">
                {[-10, -1].map(v => <button key={v} onClick={() => handleAjuste(i, s.ajuste + v)} className="text-[10px] bg-neutral-700 hover:bg-neutral-600 text-neutral-300 px-1.5 py-0.5 rounded">{v}</button>)}
                <input type="number" value={s.ajuste} onChange={e => handleAjuste(i, Number(e.target.value))}
                  className="flex-1 bg-neutral-900 border border-neutral-600 rounded px-2 py-1 text-xs text-neutral-200 text-center w-14" />
                {[1, 10].map(v => <button key={v} onClick={() => handleAjuste(i, s.ajuste + v)} className="text-[10px] bg-neutral-700 hover:bg-neutral-600 text-neutral-300 px-1.5 py-0.5 rounded">+{v}</button>)}
              </div>
            </div>
          ))}
          {saldos.some(s => s.ajuste !== 0) && (
            <button onClick={async () => { for (let i=0; i<saldos.length; i++) await handleSave(i); onSaved(); }}
              className="w-full py-2 bg-indigo-600 text-white text-xs rounded-lg">Salvar Tudo</button>
          )}
        </div>
      </div>
    </div>
  );
}
