"use client";

import { useState, useEffect, useRef, useCallback } from "react";

interface SearchResult { id: number; codigo: string; nome: string; preco: number; estoque_atual?: number; situacao: string; }
interface CartItem { codigo: string; descricao: string; quantidade: number; valor_unitario: number; }
const FORMAS = ["dinheiro", "pix", "cartao_credito", "cartao_debito", "vale", "voucher", "crediario"];

export default function PDVPage() {
  const [caixa, setCaixa] = useState<any>(null);
  const [turno, setTurno] = useState<any>(null);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [searchQ, setSearchQ] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [showSearch, setShowSearch] = useState(false);
  const [cliente, setCliente] = useState("");
  const [desconto, setDesconto] = useState(0);
  const [pagamento, setPagamento] = useState<{ forma: string; valor: number }[]>([{ forma: "dinheiro", valor: 0 }]);
  const [msg, setMsg] = useState<{ text: string; type: "success" | "error" | "info" } | null>(null);
  const [tab, setTab] = useState<"venda" | "caixa" | "historico">("venda");
  const searchRef = useRef<HTMLInputElement>(null);
  const [saldoInicial, setSaldoInicial] = useState(0);

  const notify = (text: string, type: "success" | "error" | "info" = "info") => { setMsg({ text, type }); setTimeout(() => setMsg(null), 3000); };

  const loadDashboard = useCallback(async () => {
    try { const r = await fetch("/api/pdv/dashboard"); const d = await r.json(); setCaixa(d.caixa_aberto); } catch {}
  }, []);
  useEffect(() => { loadDashboard(); }, [loadDashboard]);

  const total = cart.reduce((s, i) => s + i.quantidade * i.valor_unitario, 0);
  const totalComDesconto = Math.max(0, total - desconto);
  const totalPago = pagamento.reduce((s, p) => s + (p.valor || 0), 0);
  const troco = Math.max(0, totalPago - totalComDesconto);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (tab !== "venda") return;
      if (e.ctrlKey || e.metaKey) return;
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) {
        if (e.key === "Escape") { (e.target as HTMLInputElement).blur(); return; }
        return;
      }
      if (e.key === "F2" || e.key === "/") { e.preventDefault(); searchRef.current?.focus(); return; }
      if (e.key === "F4") { e.preventDefault(); document.getElementById("desconto-input")?.focus(); return; }
      if (e.key === "F5") { e.preventDefault(); setPagamento([{ forma: "dinheiro", valor: totalComDesconto }]); finalizarComPgto("dinheiro"); return; }
      if (e.key === "F6") { e.preventDefault(); finalizarComPgto("pix"); return; }
      if (e.key === "Enter" && cart.length > 0) { e.preventDefault(); finalizarComPgto("dinheiro"); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [tab, cart, totalComDesconto, caixa]);

  const searchProducts = useCallback(async (q: string) => {
    if (!q || q.length < 1) { setSearchResults([]); setShowSearch(false); return; }
    try {
      const r = await fetch("/api/pdv/produtos/buscar?q=" + encodeURIComponent(q));
      const d = await r.json();
      setSearchResults(d.data || []);
      setShowSearch((d.data || []).length > 0);
    } catch { setSearchResults([]); }
  }, []);

  const handleSearchKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      if (searchResults.length === 1) { addFromSearch(searchResults[0]); }
      else if (searchResults.length > 0) { addFromSearch(searchResults[0]); }
    }
    if (e.key === "Escape") { setShowSearch(false); searchRef.current?.blur(); }
    if (e.key === "ArrowDown" && searchResults.length > 0) {
      e.preventDefault(); const first = document.querySelector("[data-search-item]") as HTMLElement; first?.focus();
    }
  };

  const addFromSearch = (prod: SearchResult) => {
    if (!prod.preco || prod.preco <= 0) { notify("Preco zerado! Verifique o cadastro.", "error"); return; }
    setCart(prev => {
      const existing = prev.findIndex(i => i.codigo === prod.codigo);
      if (existing >= 0) {
        const n = [...prev]; n[existing] = { ...n[existing], quantidade: n[existing].quantidade + 1 }; return n;
      }
      return [...prev, { codigo: prod.codigo, descricao: prod.nome || prod.codigo, quantidade: 1, valor_unitario: prod.preco }];
    });
    setSearchQ(""); setSearchResults([]); setShowSearch(false);
    notify(`${prod.codigo} adicionado`, "success");
  };

  const removeItem = (i: number) => setCart(cart.filter((_, idx) => idx !== i));

  const finalizarComPgto = async (formaPadrao: string) => {
    if (!caixa) return notify("Abra o caixa primeiro!", "error");
    if (cart.length === 0) return notify("Adicione itens ao carrinho", "error");
    let pgts = pagamento;
    if (pgts[0]?.valor === 0) pgts = [{ forma: formaPadrao, valor: totalComDesconto }];
    try {
      const r = await fetch("/api/pdv/venda", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ caixa_id: caixa.id, itens: cart, pagamentos: pgts, cliente, operador: "Admin", desconto }),
      });
      const d = await r.json();
      if (d.error) { notify(d.error, "error"); return; }
      notify(`Venda #${d.venda.id} - R$ ${d.total.toFixed(2)}`, "success");
      setCart([]); setCliente(""); setDesconto(0); setPagamento([{ forma: "dinheiro", valor: 0 }]);
      loadDashboard();
    } catch (e) { notify("Erro ao finalizar", "error"); }
  };

  const abrirCaixa = async () => {
    try {
      const r = await fetch("/api/pdv/caixa/abrir", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ operador: "Admin", saldo_inicial: saldoInicial }) });
      const d = await r.json(); setCaixa(d);
      notify("Caixa aberto!", "success");
    } catch { notify("Erro ao abrir caixa", "error"); }
  };

  const fecharCaixa = async () => {
    if (!caixa) return;
    const saldo = prompt("Saldo final do caixa:");
    if (!saldo) return;
    try {
      const r = await fetch("/api/pdv/caixa/" + caixa.id + "/fechar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ saldo_final: parseFloat(saldo) }) });
      const d = await r.json();
      notify(`Caixa fechado. Vendas: R$ ${d.total_vendas?.toFixed(2)} | Sangrias: R$ ${d.sangrias?.toFixed(2)} | Diferenca: R$ ${d.diferenca?.toFixed(2)}`, "info");
      setCaixa(null); setTurno(null);
    } catch { notify("Erro ao fechar", "error"); }
  };

  return (
    <div className="h-screen flex flex-col">
      {/* Top bar */}
      <div className="bg-neutral-900 border-b border-neutral-800 px-4 py-2 flex items-center justify-between shrink-0">
        <h1 className="text-sm font-bold text-neutral-200">PDV</h1>
        <div className="flex items-center gap-3">
          {caixa && <span className="text-xs text-emerald-400">Caixa #{caixa.id} aberto</span>}
          <div className="flex gap-1 bg-neutral-800 rounded-lg p-0.5">
            {(["venda", "caixa", "historico"] as const).map(t => (
              <button key={t} onClick={() => setTab(t)} className={"px-3 py-1 text-xs rounded-md " + (tab === t ? "bg-indigo-600 text-white" : "text-neutral-400")}>
                {t === "venda" ? "Venda" : t === "caixa" ? "Caixa" : "Historico"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {msg && (
        <div className={"mx-4 mt-2 text-xs px-3 py-2 rounded-lg border " +
          (msg.type === "success" ? "bg-emerald-900/30 border-emerald-800 text-emerald-400" :
           msg.type === "error" ? "bg-red-900/30 border-red-800 text-red-400" : "bg-indigo-900/30 border-indigo-800 text-indigo-300")}>
          {msg.text}
        </div>
      )}

      {tab === "caixa" && (
        <div className="p-4 space-y-3">
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 max-w-md">
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Caixa</h3>
            {caixa ? (
              <div className="space-y-2 text-sm">
                <p className="text-neutral-400">Status: <span className="text-emerald-400">Aberto</span></p>
                <p className="text-neutral-400">Saldo inicial: <span className="text-neutral-200">R$ {(caixa.saldo_inicial || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</span></p>
                <button onClick={fecharCaixa} className="px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-500">Fechar Caixa</button>
              </div>
            ) : (
              <div className="space-y-2">
                <input type="number" value={saldoInicial} onChange={e => setSaldoInicial(Number(e.target.value))} placeholder="Saldo inicial" className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm text-neutral-200" />
                <button onClick={abrirCaixa} className="w-full py-2 bg-emerald-600 text-white text-sm rounded-lg">Abrir Caixa</button>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === "historico" && <HistoricoTab />}

      {tab === "venda" && (
        <div className="flex-1 flex overflow-hidden">
          {/* Cart area */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Search */}
            <div className="p-3 border-b border-neutral-800 shrink-0 relative">
              <input ref={searchRef} type="text" value={searchQ}
                onChange={e => { setSearchQ(e.target.value); searchProducts(e.target.value); }}
                onKeyDown={handleSearchKey}
                placeholder="Buscar por codigo, SKU ou nome (F2)..." autoFocus
                className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-3 text-lg text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500" />
              {showSearch && (
                <div className="absolute top-full left-3 right-3 bg-neutral-850 border border-neutral-700 rounded-lg shadow-xl z-20 max-h-64 overflow-y-auto">
                  {searchResults.map((p, i) => (
                    <div key={p.id} data-search-item tabIndex={0}
                      onClick={() => addFromSearch(p)}
                      onKeyDown={e => { if (e.key === "Enter") addFromSearch(p); }}
                      className="flex items-center justify-between px-3 py-2 hover:bg-neutral-700 cursor-pointer text-sm border-b border-neutral-700/50 last:border-0">
                      <div><span className="text-neutral-200">{p.codigo}</span><span className="text-neutral-500 ml-2">{p.nome}</span></div>
                      <div className="flex items-center gap-3">
                        <span className="text-neutral-400 text-xs">{p.estoque_atual ?? "—"} und</span>
                        <span className="text-emerald-400 font-medium">R$ {p.preco?.toFixed(2)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Cart items */}
            <div className="flex-1 overflow-y-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-neutral-500 text-xs border-b border-neutral-800"><th className="text-left p-3 w-20">Codigo</th><th className="text-left p-3">Descricao</th><th className="text-right p-3 w-16">Qtd</th><th className="text-right p-3 w-24">Unit</th><th className="text-right p-3 w-24">Subtotal</th><th className="w-8"></th></tr></thead>
                <tbody>
                  {cart.map((item, i) => (
                    <tr key={i} className="border-b border-neutral-800/50">
                      <td className="p-3 text-neutral-300 font-mono text-xs">{item.codigo}</td>
                      <td className="p-3 text-neutral-200">
                        <input type="text" value={item.descricao}
                          onChange={e => { const c = [...cart]; c[i] = { ...c[i], descricao: e.target.value }; setCart(c); }}
                          className="bg-transparent text-neutral-200 text-sm w-full" />
                      </td>
                      <td className="p-3 text-right">
                        <input type="number" value={item.quantidade} min={1}
                          onChange={e => { const c = [...cart]; c[i] = { ...c[i], quantidade: Math.max(1, Number(e.target.value)) }; setCart(c); }}
                          className="bg-neutral-900 rounded px-1 py-0.5 w-14 text-right text-sm text-neutral-200" />
                      </td>
                      <td className="p-3 text-right">
                        <input type="number" step="0.01" value={item.valor_unitario}
                          onChange={e => { const c = [...cart]; c[i] = { ...c[i], valor_unitario: Number(e.target.value) }; setCart(c); }}
                          className="bg-neutral-900 rounded px-1 py-0.5 w-20 text-right text-sm text-neutral-200" />
                      </td>
                      <td className="p-3 text-right text-emerald-400 font-medium">R$ {(item.quantidade * item.valor_unitario).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
                      <td className="p-3"><button onClick={() => removeItem(i)} className="text-red-400 hover:text-red-300 text-lg">×</button></td>
                    </tr>
                  ))}
                  {cart.length === 0 && (
                    <tr><td colSpan={6} className="p-8 text-center text-neutral-600 text-sm">Nenhum item. Pressione F2 para buscar.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Sidebar */}
          <div className="w-80 border-l border-neutral-800 flex flex-col bg-neutral-900/50 shrink-0">
            <div className="p-4 space-y-4 flex-1">
              <div className="bg-neutral-800 rounded-lg p-3 space-y-2">
                <div className="flex justify-between text-sm"><span className="text-neutral-400">Subtotal</span><span className="text-neutral-200">R$ {total.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</span></div>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-neutral-400">Desconto</span>
                  <input id="desconto-input" type="number" min={0} max={total} value={desconto} onChange={e => setDesconto(Number(e.target.value))}
                    className="flex-1 bg-neutral-900 rounded px-2 py-1 text-right text-sm text-neutral-200" placeholder="F4" />
                </div>
                <div className="flex justify-between text-lg font-bold"><span className="text-neutral-200">Total</span><span className="text-emerald-400">R$ {totalComDesconto.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</span></div>
              </div>

              <div className="bg-neutral-800 rounded-lg p-3 space-y-2">
                <h3 className="text-xs font-medium text-neutral-400">Pagamento</h3>
                {pagamento.map((p, i) => (
                  <div key={i} className="flex gap-1.5">
                    <select value={p.forma} onChange={e => { const c = [...pagamento]; c[i] = { ...c[i], forma: e.target.value }; setPagamento(c); }}
                      className="flex-1 bg-neutral-900 rounded px-2 py-1.5 text-xs text-neutral-200">{FORMAS.map(f => <option key={f} value={f}>{f.replace(/_/g, " ")}</option>)}</select>
                    <input type="number" step="0.01" value={p.valor || totalComDesconto} onChange={e => { const c = [...pagamento]; c[i] = { ...c[i], valor: Number(e.target.value) }; setPagamento(c); }}
                      className="w-28 bg-neutral-900 rounded px-2 py-1 text-right text-xs text-neutral-200" />
                    {pagamento.length > 1 && <button onClick={() => setPagamento(pagamento.filter((_, j) => j !== i))} className="text-red-400 text-xs px-1">×</button>}
                  </div>
                ))}
                <button onClick={() => setPagamento([...pagamento, { forma: "dinheiro", valor: 0 }])} className="text-xs text-indigo-400">+ forma pagamento</button>
                {troco > 0 && <div className="text-xs font-bold text-amber-400">Troco: R$ {troco.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</div>}
              </div>

              <div className="space-y-2">
                <input type="text" value={cliente} onChange={e => setCliente(e.target.value)} placeholder="Cliente (opcional)" className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200" />
                {caixa ? (
                  <button onClick={() => finalizarComPgto("dinheiro")} className="w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-base rounded-lg transition-colors">Finalizar Venda (F5)</button>
                ) : (
                  <button onClick={abrirCaixa} className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-lg">Abrir Caixa</button>
                )}
              </div>
            </div>

            {/* Shortcuts help */}
            <div className="p-3 border-t border-neutral-800 text-[10px] text-neutral-600 space-y-0.5">
              <div><kbd className="bg-neutral-800 px-1.5 py-0.5 rounded text-neutral-500 mr-1">F2</kbd> Buscar produto</div>
              <div><kbd className="bg-neutral-800 px-1.5 py-0.5 rounded text-neutral-500 mr-1">F4</kbd> Desconto</div>
              <div><kbd className="bg-neutral-800 px-1.5 py-0.5 rounded text-neutral-500 mr-1">F5</kbd> Dinheiro</div>
              <div><kbd className="bg-neutral-800 px-1.5 py-0.5 rounded text-neutral-500 mr-1">F6</kbd> PIX</div>
              <div><kbd className="bg-neutral-800 px-1.5 py-0.5 rounded text-neutral-500 mr-1">Enter</kbd> Finalizar</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function HistoricoTab() {
  const [vendas, setVendas] = useState<any[]>([]);
  useEffect(() => {
    fetch("/api/pdv/historico?limit=50").then(r => r.json()).then(d => setVendas(d.data || [])).catch(() => {});
  }, []);
  return (
    <div className="overflow-auto">
      <table className="w-full text-xs"><thead><tr className="text-neutral-500 border-b border-neutral-800 sticky top-0 bg-neutral-950"><th className="text-left p-3">#</th><th className="text-left p-3">Cliente</th><th className="text-right p-3">Total</th><th className="text-left p-3">Data</th><th className="text-center p-3">Status</th></tr></thead>
        <tbody>{vendas.map((v, i) => (
          <tr key={v.id} className={"border-b border-neutral-800/50 " + (i % 2 === 0 ? "bg-neutral-900/30" : "")}>
            <td className="p-3 text-indigo-400 font-mono">{v.numero || v.id}</td>
            <td className="p-3 text-neutral-300">{v.cliente || "—"}</td>
            <td className="p-3 text-right text-emerald-400">R$ {(v.total || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
            <td className="p-3 text-neutral-500">{String(v.data || "").slice(0, 16)}</td>
            <td className="p-3 text-center"><span className={"px-2 py-0.5 rounded text-[10px] " + (v.status === "cancelada" ? "bg-red-900/30 text-red-400" : "bg-emerald-900/30 text-emerald-400")}>{v.status || "finalizada"}</span></td>
          </tr>
        ))}</tbody></table>
    </div>
  );
}
