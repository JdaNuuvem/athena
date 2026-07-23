"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { SearchResult, CartItem, Operador, FORMAS } from "./types";

export function VendaTab({ operador, operadorSenha, caixa, notify, onCaixaChange }: {
  operador: Operador;
  operadorSenha: string;
  caixa: any;
  notify: (text: string, type: "success" | "error" | "info") => void;
  onCaixaChange: () => void;
}) {
  const [cart, setCart] = useState<CartItem[]>([]);
  const [searchQ, setSearchQ] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [showSearch, setShowSearch] = useState(false);
  const [cliente, setCliente] = useState("");
  const [clienteId, setClienteId] = useState<number | null>(null);
  const [clienteSearch, setClienteSearch] = useState("");
  const [clienteResults, setClienteResults] = useState<any[]>([]);
  const [clienteShow, setClienteShow] = useState(false);
  const [desconto, setDesconto] = useState(0);
  const [pagamento, setPagamento] = useState<{ forma: string; valor: number }[]>([{ forma: "dinheiro", valor: 0 }]);
  const [lastVendaId, setLastVendaId] = useState<number | null>(null);
  const buscaRef = useRef<HTMLInputElement>(null);

  const total = cart.reduce((s, i) => s + i.quantidade * i.valor_unitario - (i.desconto || 0), 0);
  const totalComDesconto = Math.max(0, total - desconto);
  const totalPago = pagamento.reduce((s, p) => s + (p.valor || 0), 0);
  const troco = Math.max(0, totalPago - totalComDesconto);
  const maxDesconto = operador?.desconto_maximo_percent ?? 0;
  const descontoPct = total > 0 ? (desconto / total) * 100 : 0;

  // Auto-fill search from ?sku=
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const sku = params.get("sku");
    if (sku) { setSearchQ(sku); searchProducts(sku); }
  }, []);

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
    if (e.key === "Escape") { setShowSearch(false); buscaRef.current?.blur(); }
  };

  const addFromSearch = (prod: SearchResult) => {
    if (!Number(prod.preco) || Number(prod.preco) <= 0) { notify("Preco zerado! Verifique o cadastro.", "error"); return; }
    setCart(prev => {
      const existing = prev.findIndex(i => i.codigo === prod.codigo);
      if (existing >= 0) {
        const n = [...prev]; n[existing] = { ...n[existing], quantidade: n[existing].quantidade + 1 }; return n;
      }
      return [...prev, { codigo: prod.codigo, descricao: prod.nome || prod.codigo, quantidade: 1, valor_unitario: prod.preco, desconto: 0 }];
    });
    setSearchQ(""); setSearchResults([]); setShowSearch(false);
    notify(`${prod.codigo} adicionado`, "success");
  };

  const removeItem = (i: number) => setCart(cart.filter((_, idx) => idx !== i));

  const escHtml = (s: unknown) => String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

  const imprimirCupom = async (vendaId: number) => {
    try {
      const r = await fetch("/api/pdv/venda/" + vendaId + "/cupom");
      const d = await r.json();
      if (d.error) { notify(d.error, "error"); return; }
      const itensHtml = d.itens.map((it: any) => `<tr><td style="padding:2px 4px;font-size:12px">${escHtml(it.produto_codigo)}</td><td style="padding:2px 4px;font-size:12px">${escHtml(it.descricao)}</td><td style="padding:2px 4px;text-align:right;font-size:12px">${Number(it.quantidade)}</td><td style="padding:2px 4px;text-align:right;font-size:12px">R$ ${Number(it.valor_unitario).toFixed(2)}</td><td style="padding:2px 4px;text-align:right;font-size:12px">R$ ${Number(it.valor_total).toFixed(2)}</td></tr>`).join("");
      const pgtsHtml = d.pagamentos.map((p: any) => `<div style="font-size:12px">${escHtml(String(p.forma).replace(/_/g, " "))}: R$ ${Number(p.valor).toFixed(2)}</div>`).join("");
      const w = window.open("", "_blank", "width=320,height=600")!;
      w.document.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>Cupom #${vendaId}</title><style>body{font-family:monospace;width:280px;margin:0 auto;padding:10px}hr{border:0;border-top:1px dashed #ccc}.center{text-align:center}</style></head><body>
        <div class="center"><strong>ATHENA</strong><br><small>${new Date().toLocaleString("pt-BR")}</small></div><hr>
        <div class="center"><strong>VENDA #${vendaId}</strong></div>
        ${d.venda.cliente ? `<div class="center">Cliente: ${escHtml(d.venda.cliente)}</div>` : ""}
        <hr><table style="width:100%">${itensHtml}</table><hr>
        ${pgtsHtml}
        <div style="font-size:12px;margin-top:4px">Desconto: R$ ${Number(d.venda.desconto || 0).toFixed(2)}</div>
        <div style="font-size:14px;font-weight:bold;margin-top:4px">TOTAL: R$ ${Number(d.venda.total).toFixed(2)}</div><hr>
        <div class="center"><small>Obrigado pela preferencia!</small></div>
      </body></html>`);
      w.document.close(); setTimeout(() => w.print(), 500);
    } catch { notify("Erro ao gerar cupom", "error"); }
  };

  const salvarOrcamento = async () => {
    if (cart.length === 0) return notify("Adicione itens ao carrinho", "error");
    try {
      const r = await fetch("/api/pdv/orcamento", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ itens: cart, cliente, cliente_id: clienteId,
          operador: operador?.nome, operador_id: operador?.id, desconto }),
      });
      const d = await r.json();
      if (d.error) { notify(d.error, "error"); return; }
      notify(`Orcamento #${d.orcamento.id} salvo`, "success");
      setCart([]); setCliente(""); setClienteId(null); setClienteSearch(""); setDesconto(0);
    } catch { notify("Erro ao salvar", "error"); }
  };

  const searchClientes = useCallback(async (q: string) => {
    if (!q || q.length < 2) { setClienteResults([]); setClienteShow(false); return; }
    try {
      const r = await fetch("/api/pdv/clientes/buscar?q=" + encodeURIComponent(q));
      const d = await r.json();
      setClienteResults(d.data || []);
      setClienteShow((d.data || []).length > 0);
    } catch { setClienteResults([]); }
  }, []);

  const finalizarComPgto = async (formaPadrao: string) => {
    if (!operador) return notify("Faca login primeiro", "error");
    if (!caixa) return notify("Abra o caixa primeiro!", "error");
    if (cart.length === 0) return notify("Adicione itens ao carrinho", "error");
    if (maxDesconto > 0 && descontoPct > maxDesconto) return notify(`Desconto maximo: ${maxDesconto}%`, "error");
    let pgts = pagamento;
    if (pgts[0]?.valor === 0) pgts = [{ forma: formaPadrao, valor: totalComDesconto }];
    try {
      const r = await fetch("/api/pdv/venda", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ caixa_id: caixa.id, itens: cart, pagamentos: pgts, cliente, cliente_id: clienteId,
          operador: operador.nome, operador_id: operador.id, desconto }),
      });
      const d = await r.json();
      if (d.error) { notify(d.error, "error"); return; }
      notify(`Venda #${d.venda.id} - R$ ${d.total.toFixed(2)}`, "success");
      setLastVendaId(d.venda.id);
      setCart([]); setCliente(""); setClienteId(null); setClienteSearch(""); setDesconto(0); setPagamento([{ forma: "dinheiro", valor: 0 }]);
      onCaixaChange();
    } catch { notify("Erro ao finalizar", "error"); }
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey) return;
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) {
        if (e.key === "Escape") { (e.target as HTMLInputElement).blur(); return; }
        return;
      }
      if (e.key === "F2" || e.key === "/") { e.preventDefault(); buscaRef.current?.focus(); return; }
      if (e.key === "F4") { e.preventDefault(); document.getElementById("desconto-input")?.focus(); return; }
      if (e.key === "F5") { e.preventDefault(); setPagamento([{ forma: "dinheiro", valor: totalComDesconto }]); finalizarComPgto("dinheiro"); return; }
      if (e.key === "F6") { e.preventDefault(); finalizarComPgto("pix"); return; }
      if (e.key === "Enter" && cart.length > 0) { e.preventDefault(); finalizarComPgto("dinheiro"); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [cart, totalComDesconto, caixa, operador]);

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Cart area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="p-3 border-b border-neutral-800 shrink-0 relative">
          <input ref={buscaRef} type="text" value={searchQ}
            onChange={e => { setSearchQ(e.target.value); searchProducts(e.target.value); }}
            onKeyDown={handleSearchKey}
            placeholder="Codigo de barras, SKU ou nome (F2)..." autoFocus
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
                    <span className="text-neutral-400 text-xs">{Number(p.estoque_atual ?? 0) || "—"} und</span>
                    <span className="text-emerald-400 font-medium">R$ {Number(p.preco || 0).toFixed(2)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-neutral-500 text-xs border-b border-neutral-800"><th className="text-left p-3 w-20">Codigo</th><th className="text-left p-3">Descricao</th><th className="text-right p-3 w-14">Qtd</th><th className="text-right p-3 w-20">Unit</th><th className="text-right p-3 w-16">Desc</th><th className="text-right p-3 w-24">Subtotal</th><th className="w-8"></th></tr></thead>
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
                  <td className="p-3 text-right">
                    <input type="number" step="0.01" min={0} value={item.desconto || 0}
                      onChange={e => { const c = [...cart]; c[i] = { ...c[i], desconto: Number(e.target.value) }; setCart(c); }}
                      className="bg-neutral-900 rounded px-1 py-0.5 w-16 text-right text-xs text-amber-400" />
                  </td>
                  <td className="p-3 text-right text-emerald-400 font-medium">R$ {((item.quantidade * item.valor_unitario) - (item.desconto || 0)).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
                  <td className="p-3"><button onClick={() => removeItem(i)} className="text-red-400 hover:text-red-300 text-lg">×</button></td>
                </tr>
              ))}
              {cart.length === 0 && (
                <tr><td colSpan={7} className="p-8 text-center text-neutral-600 text-sm">Nenhum item. Leia um codigo de barras ou pressione F2 para buscar.</td></tr>
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
              <input id="desconto-input" type="number" min={0} max={maxDesconto > 0 ? (total * maxDesconto / 100) : total}
                value={desconto} onChange={e => setDesconto(Number(e.target.value))}
                className="flex-1 bg-neutral-900 rounded px-2 py-1 text-right text-sm text-neutral-200" placeholder="F4" />
              {maxDesconto > 0 && <span className="text-[10px] text-neutral-500">max {maxDesconto}%</span>}
            </div>
            {maxDesconto > 0 && descontoPct > 0 && (
              <div className="text-[10px] text-neutral-500 text-right">{descontoPct.toFixed(1)}% de desconto</div>
            )}
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

          <div className="space-y-2 relative">
            <input type="text" value={clienteId ? cliente : clienteSearch}
              onChange={e => { setClienteSearch(e.target.value); setCliente(e.target.value); setClienteId(null); searchClientes(e.target.value); }}
              onFocus={() => { if (clienteResults.length > 0) setClienteShow(true); }}
              onBlur={() => setTimeout(() => setClienteShow(false), 200)}
              placeholder="Cliente (opcional — busca por nome/CPF)" className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200" />
            {clienteShow && (
              <div className="absolute top-full left-0 right-0 bg-neutral-850 border border-neutral-700 rounded-lg shadow-xl z-20 max-h-40 overflow-y-auto">
                {clienteResults.map((c: any) => (
                  <div key={c.id} onClick={() => { setCliente(c.nome); setClienteId(c.id); setClienteSearch(""); setClienteShow(false); }}
                    className="px-3 py-2 hover:bg-neutral-700 cursor-pointer text-sm border-b border-neutral-700/50 last:border-0">
                    <span className="text-neutral-200">{c.nome}</span>
                    <span className="text-neutral-500 ml-2 text-xs">{c.documento || c.telefone || ""}</span>
                  </div>
                ))}
              </div>
            )}
            {lastVendaId && (
              <button onClick={() => { imprimirCupom(lastVendaId); setLastVendaId(null); }}
                className="w-full py-1.5 bg-amber-700 hover:bg-amber-600 text-amber-100 text-xs rounded-lg">Imprimir Cupom #{lastVendaId}</button>
            )}
            {caixa ? (
              <>
                <button onClick={() => finalizarComPgto("dinheiro")} className="w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-base rounded-lg transition-colors">Finalizar Venda (F5)</button>
                <button onClick={salvarOrcamento} className="w-full py-2 bg-neutral-700 hover:bg-neutral-600 text-neutral-300 text-sm rounded-lg">Salvar como Orcamento</button>
              </>
            ) : (
              <button onClick={onCaixaChange} className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-lg">Abrir Caixa</button>
            )}
          </div>
        </div>

        <div className="p-3 border-t border-neutral-800 text-[10px] text-neutral-600 space-y-0.5">
          <div><kbd className="bg-neutral-800 px-1.5 py-0.5 rounded text-neutral-500 mr-1">F2</kbd> Buscar produto</div>
          <div><kbd className="bg-neutral-800 px-1.5 py-0.5 rounded text-neutral-500 mr-1">F4</kbd> Desconto</div>
          <div><kbd className="bg-neutral-800 px-1.5 py-0.5 rounded text-neutral-500 mr-1">F5</kbd> Dinheiro</div>
          <div><kbd className="bg-neutral-800 px-1.5 py-0.5 rounded text-neutral-500 mr-1">F6</kbd> PIX</div>
          <div><kbd className="bg-neutral-800 px-1.5 py-0.5 rounded text-neutral-500 mr-1">Enter</kbd> Finalizar</div>
        </div>
      </div>
    </div>
  );
}
