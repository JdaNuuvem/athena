"use client";

import { useState, useEffect } from "react";

interface CartItem { codigo: string; descricao: string; quantidade: number; valor_unitario: number; }

const FORMAS = ["dinheiro", "pix", "cartao_credito", "cartao_debito", "vale", "voucher"];

export default function PDVPage() {
  const [caixa, setCaixa] = useState<any>(null);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [codigo, setCodigo] = useState("");
  const [qtd, setQtd] = useState(1);
  const [cliente, setCliente] = useState("");
  const [desconto, setDesconto] = useState(0);
  const [pagamento, setPagamento] = useState<{forma:string;valor:number}[]>([{forma:"dinheiro",valor:0}]);
  const [msg, setMsg] = useState("");
  const [tab, setTab] = useState<"venda"|"caixa"|"historico">("venda");

  useEffect(() => {
    fetch("/api/pdv/dashboard").then(r=>r.json()).then(d=>setCaixa(d.caixa_aberto)).catch(()=>{});
  }, []);

  const total = cart.reduce((s,i) => s + i.quantidade * i.valor_unitario, 0) - desconto;
  const totalPago = pagamento.reduce((s,p) => s + (p.valor||0), 0);
  const troco = totalPago - total;

  const addItem = () => {
    if (!codigo.trim()) return;
    setCart([...cart, { codigo: codigo.trim(), descricao: codigo.trim(), quantidade: qtd, valor_unitario: 0 }]);
    setCodigo(""); setQtd(1);
  };

  const removeItem = (i: number) => setCart(cart.filter((_,idx) => idx !== i));

  const finalizar = async () => {
    if (!caixa) return setMsg("Abra o caixa primeiro!");
    if (cart.length === 0) return setMsg("Adicione itens ao carrinho");
    const r = await fetch("/api/pdv/venda", {
      method: "POST", headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ caixa_id: caixa.id, itens: cart, pagamentos: pagamento.map(p=>({...p,valor: p.valor||total})), cliente, operador:"Admin", desconto }),
    });
    const d = await r.json();
    if (d.error) setMsg(d.error);
    else { setMsg("Venda #" + d.venda.id + " finalizada! Total: R$ " + d.total.toFixed(2)); setCart([]); setCliente(""); setDesconto(0); setPagamento([{forma:"dinheiro",valor:0}]); }
  };

  const abrirCaixa = async () => {
    const r = await fetch("/api/pdv/caixa/abrir", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({operador:"Admin"}) });
    const d = await r.json(); setCaixa(d); setMsg("Caixa aberto!");
  };

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-neutral-100">PDV</h1>
        <div className="flex gap-1 bg-neutral-800 rounded-lg p-1">
          {(["venda","caixa","historico"] as const).map(t => (
            <button key={t} onClick={()=>setTab(t)} className={"px-3 py-1 text-xs rounded-md "+(tab===t?"bg-indigo-600 text-white":"text-neutral-400")}>{t==="venda"?"Venda":t==="caixa"?"Caixa":"Historico"}</button>
          ))}
        </div>
      </div>

      {msg && <div className="bg-indigo-900/30 border border-indigo-800 text-indigo-300 text-xs px-3 py-2 rounded-lg">{msg}</div>}

      {tab === "venda" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 space-y-3">
            <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-3 flex gap-2">
              <input type="text" value={codigo} onChange={e=>setCodigo(e.target.value)} onKeyDown={e=>e.key==="Enter"&&addItem()}
                placeholder="Codigo de barras ou SKU..." className="flex-1 bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm text-neutral-200" />
              <input type="number" value={qtd} onChange={e=>setQtd(Number(e.target.value))} min={1} className="w-20 bg-neutral-900 border border-neutral-700 rounded px-2 py-2 text-sm text-neutral-200 text-center" />
              <button onClick={addItem} className="px-4 py-2 bg-emerald-600 text-white text-sm rounded-lg hover:bg-emerald-500">+</button>
            </div>
            <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
              <table className="w-full text-xs">
                <thead><tr className="border-b border-neutral-700 text-neutral-400"><th className="text-left p-3">Codigo</th><th className="text-left p-3">Descricao</th><th className="text-right p-3">Qtd</th><th className="text-right p-3">Unit</th><th className="text-right p-3">Subtotal</th><th className="p-3"></th></tr></thead>
                <tbody>{cart.map((item,i) => (
                  <tr key={i} className="border-b border-neutral-700/50">
                    <td className="p-3 text-neutral-300 font-mono">{item.codigo}</td>
                    <td className="p-3 text-neutral-200"><input type="text" value={item.descricao} onChange={e=>{const c=[...cart];c[i]={...c[i],descricao:e.target.value};setCart(c)}} className="bg-transparent text-neutral-200 text-xs w-full" /></td>
                    <td className="p-3 text-right"><input type="number" value={item.quantidade} onChange={e=>{const c=[...cart];c[i]={...c[i],quantidade:Number(e.target.value)};setCart(c)}} min={1} className="bg-neutral-900 rounded px-1 py-0.5 w-16 text-right text-xs text-neutral-200" /></td>
                    <td className="p-3 text-right"><input type="number" step="0.01" value={item.valor_unitario} onChange={e=>{const c=[...cart];c[i]={...c[i],valor_unitario:Number(e.target.value)};setCart(c)}} className="bg-neutral-900 rounded px-1 py-0.5 w-20 text-right text-xs text-neutral-200" placeholder="0,00" /></td>
                    <td className="p-3 text-right text-emerald-400">R$ {(item.quantidade*item.valor_unitario).toLocaleString("pt-BR",{minimumFractionDigits:2})}</td>
                    <td className="p-3"><button onClick={()=>removeItem(i)} className="text-red-400 text-xs">X</button></td>
                  </tr>
                ))}</tbody>
              </table>
              {cart.length===0 && <div className="p-8 text-center text-neutral-500 text-xs">Nenhum item. Leia o codigo de barras ou digite o SKU.</div>}
            </div>
          </div>
          <div className="space-y-3">
            <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-3">
              <div className="flex justify-between text-sm"><span className="text-neutral-400">Subtotal</span><span className="text-neutral-200">R$ {(total+desconto).toLocaleString("pt-BR",{minimumFractionDigits:2})}</span></div>
              <div className="flex items-center gap-2"><span className="text-sm text-neutral-400">Desconto</span><input type="number" value={desconto} onChange={e=>setDesconto(Number(e.target.value))} className="w-24 bg-neutral-900 rounded px-2 py-1 text-right text-sm text-neutral-200" /></div>
              <div className="flex justify-between text-lg font-bold"><span className="text-neutral-200">Total</span><span className="text-emerald-400">R$ {total.toLocaleString("pt-BR",{minimumFractionDigits:2})}</span></div>
            </div>
            <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-2">
              <h3 className="text-sm font-medium text-neutral-300">Pagamento</h3>
              {pagamento.map((p,i) => (
                <div key={i} className="flex gap-2">
                  <select value={p.forma} onChange={e=>{const c=[...pagamento];c[i]={...c[i],forma:e.target.value};setPagamento(c)}} className="bg-neutral-900 rounded px-2 py-1.5 text-xs text-neutral-200 flex-1">{FORMAS.map(f=><option key={f} value={f}>{f.replace(/_/g," ")}</option>)}</select>
                  <input type="number" step="0.01" value={p.valor||total} onChange={e=>{const c=[...pagamento];c[i]={...c[i],valor:Number(e.target.value)};setPagamento(c)}} className="w-24 bg-neutral-900 rounded px-2 py-1 text-right text-xs text-neutral-200" />
                  {i>0 && <button onClick={()=>setPagamento(pagamento.filter((_,j)=>j!==i))} className="text-red-400 text-xs">X</button>}
                </div>
              ))}
              <button onClick={()=>setPagamento([...pagamento,{forma:"dinheiro",valor:0}])} className="text-xs text-indigo-400">+ forma pgto</button>
              {troco > 0 && <div className="text-xs text-amber-400">Troco: R$ {troco.toLocaleString("pt-BR",{minimumFractionDigits:2})}</div>}
            </div>
            <div className="space-y-2">
              <input type="text" value={cliente} onChange={e=>setCliente(e.target.value)} placeholder="Cliente (opcional)" className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200" />
              {caixa ? (
                <button onClick={finalizar} className="w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-lg">Finalizar Venda</button>
              ) : (
                <button onClick={abrirCaixa} className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-lg">Abrir Caixa</button>
              )}
            </div>
          </div>
        </div>
      )}

      {tab === "caixa" && (
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Operacoes de Caixa</h3>
            {caixa ? (
              <div className="space-y-3 text-sm"><p className="text-neutral-400">Caixa #{caixa.id} <span className="text-emerald-400">Aberto</span></p>
                <p className="text-neutral-400">Saldo inicial: R$ {(caixa.saldo_inicial||0).toLocaleString("pt-BR",{minimumFractionDigits:2})}</p>
              </div>
            ) : <button onClick={abrirCaixa} className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg">Abrir Caixa</button>}
          </div>
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Sangria / Suprimento</h3>
            <p className="text-xs text-neutral-500">Use os endpoints: POST /api/pdv/caixa/{'{id}'}/sangria ou /suprimento</p>
          </div>
        </div>
      )}

      {tab === "historico" && (
        <HistoricoTab />
      )}
    </div>
  );
}

function HistoricoTab() {
  const [vendas, setVendas] = useState<any[]>([]);
  useEffect(() => {
    fetch("/api/pdv/vendas").then(r=>r.json()).then(d=>setVendas(d.data||[])).catch(()=>{});
  }, []);
  return (
    <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
      <table className="w-full text-xs">
        <thead><tr className="border-b border-neutral-700 text-neutral-400"><th className="text-left p-3">#</th><th className="text-left p-3">Cliente</th><th className="text-right p-3">Total</th><th className="text-left p-3">Data</th></tr></thead>
        <tbody>{vendas.map((v,i) => (
          <tr key={v.id} className={"border-b border-neutral-700/50 "+(i%2===0?"bg-neutral-800":"bg-neutral-800/50")}>
            <td className="p-3 text-neutral-200 font-mono">{v.numero||v.id}</td>
            <td className="p-3 text-neutral-300">{v.cliente||"—"}</td>
            <td className="p-3 text-right text-emerald-400">R$ {(v.total||0).toLocaleString("pt-BR",{minimumFractionDigits:2})}</td>
            <td className="p-3 text-neutral-500">{String(v.data||"").slice(0,16)}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}
