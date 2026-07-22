"use client";

import { useState, useEffect, useRef, useCallback } from "react";

interface SearchResult { id: number; codigo: string; nome: string; preco: number; estoque_atual?: number; situacao: string; }
interface CartItem { codigo: string; descricao: string; quantidade: number; valor_unitario: number; desconto: number; }
interface Operador { id: number; nome: string; role: string; desconto_maximo_percent: number; }
const FORMAS = ["dinheiro", "pix", "cartao_credito", "cartao_debito", "vale", "voucher", "crediario"];

export default function PDVPage() {
  const [operador, setOperador] = useState<Operador | null>(null);
  const [operadorSenha, setOperadorSenha] = useState("");
  const [loginNome, setLoginNome] = useState("");
  const [loginSenha, setLoginSenha] = useState("");
  const [loginError, setLoginError] = useState("");
  const [caixa, setCaixa] = useState<any>(null);
  const [turno, setTurno] = useState<any>(null);
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
  const [msg, setMsg] = useState<{ text: string; type: "success" | "error" | "info" } | null>(null);
  const [tab, setTab] = useState<"venda" | "caixa" | "historico" | "orcamentos">("venda");
  const [saldoInicial, setSaldoInicial] = useState(0);
  const [lastVendaId, setLastVendaId] = useState<number | null>(null);

  // Fechamento modal
  const [showFechaModal, setShowFechaModal] = useState(false);
  const [fechaResumo, setFechaResumo] = useState<any>(null);
  const [fechaSaldo, setFechaSaldo] = useState("");
  const [fechaSenha, setFechaSenha] = useState("");
  const buscaRef = useRef<HTMLInputElement>(null);

  const notify = (text: string, type: "success" | "error" | "info" = "info") => { setMsg({ text, type }); setTimeout(() => setMsg(null), 3000); };

  // Auto-fill search from ?sku=
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const sku = params.get("sku");
    if (sku) { setSearchQ(sku); searchProducts(sku); }
  }, []);

  const loadDashboard = useCallback(async () => {
    try { const r = await fetch("/api/pdv/dashboard"); const d = await r.json(); setCaixa(d.caixa_aberto); } catch {}
  }, []);
  useEffect(() => { if (operador) loadDashboard(); }, [loadDashboard, operador]);

  const total = cart.reduce((s, i) => s + i.quantidade * i.valor_unitario - (i.desconto || 0), 0);
  const totalComDesconto = Math.max(0, total - desconto);
  const totalPago = pagamento.reduce((s, p) => s + (p.valor || 0), 0);
  const troco = Math.max(0, totalPago - totalComDesconto);
  const maxDesconto = operador?.desconto_maximo_percent ?? 0;
  const descontoPct = total > 0 ? (desconto / total) * 100 : 0;

  // Login
  const handleLogin = async () => {
    setLoginError("");
    try {
      const r = await fetch("/api/pdv/login", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nome: loginNome, senha: loginSenha }),
      });
      const d = await r.json();
      if (d.error) { setLoginError(d.error); return; }
      setOperador({ id: d.id, nome: d.nome, role: d.role, desconto_maximo_percent: d.desconto_maximo_percent });
      setOperadorSenha(loginSenha);
      setLoginSenha("");
    } catch { setLoginError("Erro de conexao"); }
  };

  const handleLogout = () => { setOperador(null); setOperadorSenha(""); setCaixa(null); setCart([]); };

  // Keyboard shortcuts
  useEffect(() => {
    if (!operador) return;
    const handler = (e: KeyboardEvent) => {
      if (tab !== "venda") return;
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
  }, [tab, cart, totalComDesconto, caixa, operador]);

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
      loadDashboard();
    } catch { notify("Erro ao finalizar", "error"); }
  };

  const abrirCaixa = async () => {
    if (!operador) return;
    try {
      const r = await fetch("/api/pdv/caixa/abrir", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ operador: operador.nome, saldo_inicial: saldoInicial,
          operador_id: operador.id, senha: operadorSenha }),
      });
      const d = await r.json();
      if (d.error) { notify(d.error, "error"); return; }
      setCaixa(d); notify("Caixa aberto!", "success");
    } catch { notify("Erro ao abrir caixa", "error"); }
  };

  const fecharCaixa = async () => {
    if (!caixa || !operador) return;
    const saldo = parseFloat(fechaSaldo);
    if (!saldo && saldo !== 0) { notify("Informe o saldo final", "error"); return; }
    try {
      const r = await fetch("/api/pdv/caixa/" + caixa.id + "/fechar", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ saldo_final: saldo, operador_id: operador.id, senha: fechaSenha }),
      });
      const d = await r.json();
      if (d.error) { notify(d.error, "error"); setShowFechaModal(false); return; }
      setShowFechaModal(false);
      notify(`Caixa fechado. Total vendas: R$ ${d.total_vendas?.toFixed(2)} | Em dinheiro: R$ ${d.vendas_dinheiro?.toFixed(2)} | Diferenca: R$ ${d.diferenca?.toFixed(2)}`, "info");
      setCaixa(null); setTurno(null);
    } catch { notify("Erro ao fechar", "error"); setShowFechaModal(false); }
  };

  const handleFecharCaixa = async () => {
    setFechaSaldo(""); setFechaSenha(""); setFechaResumo(null); setShowFechaModal(true);
    if (!caixa) return;
    try { const r = await fetch("/api/pdv/caixa/" + caixa.id + "/resumo"); setFechaResumo(await r.json()); } catch {}
  };

  // ── Login screen ──
  if (!operador) {
    return (
      <div className="h-screen flex items-center justify-center bg-neutral-950">
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-8 w-96">
          <h1 className="text-xl font-bold text-neutral-200 mb-2">PDV — Login</h1>
          <p className="text-sm text-neutral-500 mb-6">Identifique-se para operar o caixa</p>
          <div className="space-y-4">
            <input type="text" value={loginNome} onChange={e => setLoginNome(e.target.value)}
              placeholder="Nome do operador" autoFocus
              onKeyDown={e => e.key === "Enter" && handleLogin()}
              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-3 text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500" />
            <input type="password" value={loginSenha} onChange={e => setLoginSenha(e.target.value)}
              placeholder="Senha"
              onKeyDown={e => e.key === "Enter" && handleLogin()}
              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-3 text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500" />
            {loginError && <p className="text-red-400 text-sm">{loginError}</p>}
            <button onClick={handleLogin} className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-lg transition-colors">
              Entrar
            </button>
          </div>
          <p className="text-[10px] text-neutral-600 mt-4 text-center">Operador padrao: Admin / admin</p>
        </div>
      </div>
    );
  }

  // ── Fechamento modal ──
  const fechaModal = showFechaModal && (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowFechaModal(false)}>
      <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-[28rem] max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <h3 className="text-sm font-semibold text-neutral-200 mb-3">Fechar Caixa #{caixa?.id}</h3>
        {fechaResumo && !fechaResumo.error && (
          <div className="mb-4 space-y-2 text-xs">
            <div className="flex justify-between text-neutral-400"><span>Saldo inicial</span><span className="text-neutral-200">R$ {fechaResumo.saldo_inicial?.toFixed(2)}</span></div>
            <div className="border-t border-neutral-700 pt-2 mt-2">
              <p className="text-neutral-500 mb-1">Vendas por forma de pgto:</p>
              {Object.entries(fechaResumo.vendas_por_forma || {}).map(([forma, valor]) => (
                <div key={forma} className="flex justify-between"><span className="text-neutral-400 capitalize">{forma.replace(/_/g, " ")}</span><span className="text-neutral-200">R$ {(valor as number).toFixed(2)}</span></div>
              ))}
              {(!fechaResumo.vendas_por_forma || Object.keys(fechaResumo.vendas_por_forma).length === 0) && (
                <p className="text-neutral-600">Nenhuma venda no periodo</p>
              )}
            </div>
            {fechaResumo.sangrias > 0 && <div className="flex justify-between text-red-400"><span>Sangrias</span><span>- R$ {fechaResumo.sangrias.toFixed(2)}</span></div>}
            {fechaResumo.suprimentos > 0 && <div className="flex justify-between text-emerald-400"><span>Suprimentos</span><span>+ R$ {fechaResumo.suprimentos.toFixed(2)}</span></div>}
            <div className="border-t border-neutral-700 pt-2 flex justify-between font-bold text-sm">
              <span className="text-neutral-300">Saldo esperado (dinheiro)</span>
              <span className="text-amber-400">R$ {fechaResumo.saldo_esperado_dinheiro?.toFixed(2)}</span>
            </div>
          </div>
        )}
        {fechaResumo?.error && <p className="text-red-400 text-xs mb-3">{fechaResumo.error}</p>}
        <input type="number" step="0.01" value={fechaSaldo} onChange={e => setFechaSaldo(e.target.value)}
          placeholder="Saldo conferido (dinheiro em caixa)" autoFocus
          className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200 mb-2" />
        {fechaResumo && !fechaResumo.error && fechaSaldo && (
          <div className={"text-xs mb-2 " + (Math.abs(parseFloat(fechaSaldo) - (fechaResumo.saldo_esperado_dinheiro || 0)) < 0.01 ? "text-emerald-400" : "text-red-400")}>
            Diferença: R$ {(parseFloat(fechaSaldo || "0") - (fechaResumo.saldo_esperado_dinheiro || 0)).toFixed(2)}
          </div>
        )}
        <input type="password" value={fechaSenha} onChange={e => setFechaSenha(e.target.value)}
          placeholder="Senha para confirmar"
          onKeyDown={e => { if (e.key === "Enter") fecharCaixa(); }}
          className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200 mb-3" />
        <div className="flex gap-2">
          <button onClick={() => setShowFechaModal(false)} className="flex-1 py-2 text-sm text-neutral-400 hover:text-neutral-200">Cancelar</button>
          <button onClick={fecharCaixa} className="flex-1 py-2 bg-red-600 text-white text-sm rounded-lg">Fechar Caixa</button>
        </div>
      </div>
    </div>
  );

  // ── Main PDV ──
  return (
    <div className="h-screen flex flex-col">
      {fechaModal}

      {/* Top bar */}
      <div className="bg-neutral-900 border-b border-neutral-800 px-4 py-2 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-sm font-bold text-neutral-200">PDV</h1>
          <span className="text-[10px] text-neutral-500">{operador.nome} ({operador.role})</span>
        </div>
        <div className="flex items-center gap-3">
          {caixa && <span className="text-xs text-emerald-400">Caixa #{caixa.id} aberto</span>}
          <div className="flex gap-1 bg-neutral-800 rounded-lg p-0.5">
            {(["venda", "caixa", "historico", "orcamentos"] as const).map(t => (
              <button key={t} onClick={() => setTab(t)} className={"px-3 py-1 text-xs rounded-md " + (tab === t ? "bg-indigo-600 text-white" : "text-neutral-400")}>
                {t === "venda" ? "Venda" : t === "caixa" ? "Caixa" : t === "historico" ? "Historico" : "Orcamentos"}
              </button>
            ))}
          </div>
          <button onClick={handleLogout} className="text-[10px] text-neutral-500 hover:text-red-400">Sair</button>
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
                <button onClick={handleFecharCaixa} className="px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-500">Fechar Caixa</button>
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

      {tab === "historico" && <HistoricoTab operador={operador} operadorSenha={operadorSenha} />}

      {tab === "orcamentos" && <OrcamentosTab caixa={caixa} operador={operador} operadorSenha={operadorSenha} onVendaCriada={loadDashboard} />}

      {tab === "venda" && (
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
                  <button onClick={abrirCaixa} className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-lg">Abrir Caixa</button>
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
      )}
    </div>
  );
}

function OrcamentosTab({ caixa, operador, operadorSenha, onVendaCriada }: { caixa: any; operador: Operador; operadorSenha: string; onVendaCriada: () => void }) {
  const [orcamentos, setOrcamentos] = useState<any[]>([]);
  const [pgtoForma, setPgtoForma] = useState("dinheiro");

  const load = () => {
    fetch("/api/pdv/vendas?limit=30").then(r => r.json()).then(d => {
      setOrcamentos((d.data || []).filter((v: any) => v.status === "orcamento"));
    }).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const converter = async (id: number, total: number) => {
    if (!caixa) return alert("Abra o caixa primeiro!");
    try {
      const r = await fetch("/api/pdv/orcamento/" + id + "/converter", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ caixa_id: caixa.id, pagamentos: [{ forma: pgtoForma, valor: total }],
          operador: operador.nome, operador_id: operador.id }),
      });
      const d = await r.json();
      if (d.error) { alert(d.error); return; }
      alert(`Orcamento #${id} convertido em venda!`);
      load(); onVendaCriada();
    } catch { alert("Erro ao converter"); }
  };

  return (
    <div className="overflow-auto p-4">
      <h3 className="text-sm font-semibold text-neutral-200 mb-3">Orcamentos Pendentes</h3>
      {orcamentos.length === 0 && <p className="text-neutral-600 text-sm">Nenhum orcamento pendente.</p>}
      {orcamentos.map(o => (
        <div key={o.id} className="bg-neutral-800 border border-neutral-700 rounded-lg p-3 mb-2 flex items-center justify-between">
          <div>
            <span className="text-indigo-400 font-mono text-sm">#{o.id}</span>
            <span className="text-neutral-400 text-xs ml-3">{o.cliente || "Sem cliente"}</span>
            <span className="text-neutral-500 text-xs ml-3">{String(o.data || "").slice(0, 16)}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-emerald-400 font-medium text-sm">R$ {Number(o.total || 0).toFixed(2)}</span>
            <select value={pgtoForma} onChange={e => setPgtoForma(e.target.value)}
              className="bg-neutral-900 rounded px-2 py-1 text-xs text-neutral-200">
              {FORMAS.map(f => <option key={f} value={f}>{f.replace(/_/g, " ")}</option>)}
            </select>
            <button onClick={() => converter(o.id, o.total)}
              className="px-3 py-1 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">Converter em Venda</button>
          </div>
        </div>
      ))}
    </div>
  );
}

function HistoricoTab({ operador, operadorSenha }: { operador: Operador; operadorSenha: string }) {
  const [vendas, setVendas] = useState<any[]>([]);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [itens, setItens] = useState<any[]>([]);
  const [devolverItem, setDevolverItem] = useState<{ itemId: number; qtd: number; motivo: string } | null>(null);
  const [devolverSenha, setDevolverSenha] = useState("");

  useEffect(() => {
    fetch("/api/pdv/historico?limit=50").then(r => r.json()).then(d => setVendas(d.data || [])).catch(() => {});
  }, []);

  const toggleExpand = async (vendaId: number) => {
    if (expanded === vendaId) { setExpanded(null); setItens([]); return; }
    setExpanded(vendaId);
    try {
      const r = await fetch("/api/pdv/itens?venda_id=" + vendaId);
      const d = await r.json();
      setItens(d.data || []);
    } catch { setItens([]); }
  };

  const handleDevolver = async () => {
    if (!devolverItem || !devolverItem.qtd) return;
    try {
      const r = await fetch("/api/pdv/venda/" + devolverItem.itemId + "/devolver-item", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ quantidade: devolverItem.qtd, motivo: devolverItem.motivo,
          operador: operador.nome, operador_id: operador.id, senha: devolverSenha || operadorSenha }),
      });
      const d = await r.json();
      if (d.error) { alert(d.error); return; }
      alert(`Devolvido: ${devolverItem.qtd} un — R$ ${d.valor_devolvido?.toFixed(2)}`);
      setDevolverItem(null); setDevolverSenha("");
      toggleExpand(expanded!);
    } catch { alert("Erro ao devolver"); }
  };

  return (
    <div className="overflow-auto">
      <table className="w-full text-xs">
        <thead><tr className="text-neutral-500 border-b border-neutral-800 sticky top-0 bg-neutral-950">
          <th className="text-left p-3 w-12">#</th><th className="text-left p-3">Cliente</th><th className="text-right p-3">Total</th>
          <th className="text-left p-3">Data</th><th className="text-center p-3">Status</th><th className="w-8"></th>
        </tr></thead>
        <tbody>
          {vendas.map((v, i) => (<>
            <tr key={v.id} className={"border-b border-neutral-800/50 " + (i % 2 === 0 ? "bg-neutral-900/30" : "") + (expanded === v.id ? " bg-neutral-800/50" : "")}>
              <td className="p-3 text-indigo-400 font-mono">{v.numero || v.id}</td>
              <td className="p-3 text-neutral-300">{v.cliente || "—"}</td>
              <td className="p-3 text-right text-emerald-400">R$ {(v.total || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
              <td className="p-3 text-neutral-500">{String(v.data || "").slice(0, 16)}</td>
              <td className="p-3 text-center"><span className={"px-2 py-0.5 rounded text-[10px] " + (v.status === "cancelada" ? "bg-red-900/30 text-red-400" : "bg-emerald-900/30 text-emerald-400")}>{v.status || "finalizada"}</span></td>
              <td className="p-3">
                {v.status !== "cancelada" && (
                  <button onClick={() => toggleExpand(v.id)} className="text-neutral-500 hover:text-neutral-300 text-lg">
                    {expanded === v.id ? "−" : "+"}
                  </button>
                )}
              </td>
            </tr>
            {expanded === v.id && (
              <tr key={v.id + "-items"}><td colSpan={6} className="p-0">
                <div className="bg-neutral-900/50 px-6 py-3 border-b border-neutral-800">
                  <table className="w-full text-xs">
                    <thead><tr className="text-neutral-600"><th className="text-left py-1">Codigo</th><th className="text-left py-1">Descricao</th><th className="text-right py-1">Qtd</th><th className="text-right py-1">Unit</th><th className="text-right py-1">Subtotal</th><th className="w-16"></th></tr></thead>
                    <tbody>
                      {itens.map((it: any) => (
                        <tr key={it.id} className="border-b border-neutral-800/30">
                          <td className="py-1 text-neutral-400 font-mono">{it.produto_codigo}</td>
                          <td className="py-1 text-neutral-300">{it.descricao}</td>
                          <td className="py-1 text-right text-neutral-300">{Number(it.quantidade)}</td>
                          <td className="py-1 text-right text-neutral-400">R$ {Number(it.valor_unitario || 0).toFixed(2)}</td>
                          <td className="py-1 text-right text-emerald-400">R$ {Number(it.valor_total || 0).toFixed(2)}</td>
                          <td className="py-1 text-right">
                            <button onClick={() => setDevolverItem({ itemId: it.id, qtd: 1, motivo: "" })}
                              className="text-[10px] text-red-400 hover:text-red-300">Devolver</button>
                          </td>
                        </tr>
                      ))}
                      {itens.length === 0 && (
                        <tr><td colSpan={6} className="py-2 text-neutral-600">Carregando itens...</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </td></tr>
            )}
          </>))}
        </tbody>
      </table>

      {/* Devolucao modal */}
      {devolverItem && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setDevolverItem(null)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-80" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Devolver Item</h3>
            <div className="space-y-2">
              <input type="number" min={0.001} step="0.001" value={devolverItem.qtd}
                onChange={e => setDevolverItem({ ...devolverItem, qtd: Number(e.target.value) })}
                placeholder="Quantidade" autoFocus
                className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200" />
              <input type="text" value={devolverItem.motivo}
                onChange={e => setDevolverItem({ ...devolverItem, motivo: e.target.value })}
                placeholder="Motivo (opcional)"
                className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200" />
              <input type="password" value={devolverSenha}
                onChange={e => setDevolverSenha(e.target.value)}
                placeholder="Senha"
                className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200" />
              <div className="flex gap-2 pt-2">
                <button onClick={() => setDevolverItem(null)} className="flex-1 py-2 text-sm text-neutral-400">Cancelar</button>
                <button onClick={handleDevolver} className="flex-1 py-2 bg-red-600 text-white text-sm rounded-lg">Devolver</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
