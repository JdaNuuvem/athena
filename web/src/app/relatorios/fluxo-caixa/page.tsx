"use client";
import { useState, useEffect } from "react";

export default function Page() {
  const [data, setData] = useState<Record<string,any>|null>(null);
  const [dias, setDias] = useState(30);
  const apis: Record<string,string> = {
    vendas:"/api/relatorios/vendas", lucro:"/api/relatorios/lucro", "ticket-medio":"/api/relatorios/ticket-medio",
    estoque:"/api/relatorios/estoque", clientes:"/api/relatorios/clientes", fornecedores:"/api/relatorios/fornecedores",
    dre:"/api/relatorios/dre", "fluxo-caixa":"/api/relatorios/fluxo-caixa", aging:"/api/relatorios/aging", previsao:"/api/relatorios/previsao",
  };
  useEffect(() => {
    let url = apis["fluxo-caixa"] || "/api/relatorios/fluxo-caixa";
    if (["vendas","lucro","ticket-medio","dre","fluxo-caixa","clientes","previsao"].includes("fluxo-caixa")) url += "?dias="+dias;
    fetch(url).then(r=>r.json()).then(setData).catch(()=>{});
  }, [dias]);

  const fmt = (v: any) => typeof v === "number" ? v.toLocaleString("pt-BR",{minimumFractionDigits:2}) : String(v??"—");
  const brl = (v: any) => typeof v === "number" ? "R$ "+v.toLocaleString("pt-BR",{minimumFractionDigits:2}) : "R$ —";

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between"><div><h1 className="text-lg font-bold text-neutral-100">Fluxo de Caixa</h1><p className="text-xs text-neutral-500 mt-1">Entradas, saidas e saldo</p></div>
        {["vendas","lucro","ticket-medio","dre","fluxo-caixa","clientes","previsao"].includes("fluxo-caixa") && (
          <select value={dias} onChange={e=>setDias(Number(e.target.value))} className="bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200">
            {[7,15,30,60,90].map(d=><option key={d} value={d}>{d} dias</option>)}
          </select>
        )}
      </div>
      {data ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(data).filter(([k])=>typeof data[k]==="number").map(([k,v])=>(
              <div key={k} className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
                <p className="text-xs text-neutral-500 capitalize">{k.replace(/_/g," ")}</p>
                <p className="text-lg font-bold text-neutral-200">{(k.includes("pct")||k.includes("margem")) ? v+"%" : (k.includes("total")||k.includes("valor")||k.includes("lucro")||k.includes("receita")||k.includes("entrada")||k.includes("saida")||k.includes("saldo")||k.includes("ticket")||k.includes("media")||k.includes("previsao")||k.includes("cmv")||k.includes("custo")||k.includes("compras")) ? brl(v) : fmt(v)}</p>
              </div>
            ))}
          </div>
          {data.diarias && (
            <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-neutral-300 mb-3">Vendas Diarias</h3>
              <div className="overflow-hidden"><table className="w-full text-xs"><thead><tr className="border-b border-neutral-700 text-neutral-400"><th className="text-left p-2">Data</th><th className="text-right p-2">Qtd</th><th className="text-right p-2">Valor</th></tr></thead><tbody>{data.diarias.map((d:any,i:number)=>(<tr key={i} className="border-b border-neutral-700/50"><td className="p-2 text-neutral-300">{d.dia?.slice(0,10)}</td><td className="p-2 text-right text-neutral-400">{d.qtd}</td><td className="p-2 text-right text-emerald-400">{brl(d.valor)}</td></tr>))}</tbody></table></div>
            </div>
          )}
          {data.top && (
            <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-neutral-300 mb-3">Top 10</h3>
              <div className="overflow-hidden"><table className="w-full text-xs"><thead><tr className="border-b border-neutral-700 text-neutral-400">{Object.keys(data.top[0]||{}).map((k:string)=><th key={k} className="text-left p-2 capitalize">{k.replace(/_/g," ")}</th>)}</tr></thead><tbody>{data.top.map((r:any,i:number)=>(<tr key={i} className="border-b border-neutral-700/50">{Object.values(r).map((v:any,j:number)=><td key={j} className="p-2 text-neutral-300">{typeof v==="number"?brl(v):String(v)}</td>)}</tr>))}</tbody></table></div>
            </div>
          )}
        </div>
      ) : <p className="text-neutral-500">Carregando...</p>}
    </div>
  );
}
