"use client";
import { useEffect, useState } from "react";
interface ValeRow { id: number; funcionario_id: number; nome: string; valor: number; motivo: string; data: string; status: string; }
export default function Page() {
  const [items, setItems] = useState<ValeRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<Record<string,string>>({});
  const load = () => { fetch("/api/rh/vale").then(r=>r.json()).then(d=>setItems((d.data||[]) as ValeRow[])).catch(()=>{}).finally(()=>setLoading(false)); };
  useEffect(()=>{load();},[]);
  const handleCreate = async () => { await fetch("/api/rh/vale",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({...form,valor:parseFloat(form.valor||"0")})}); setShowForm(false); setForm({}); load(); };
  const handlePagar = async (id:number) => { await fetch("/api/rh/vale/"+id,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({status:"pago"})}); load(); };
  const total = items.filter(i=>i.status!=="pago").reduce((s,i)=>s+(i.valor||0),0);
  return (<div className="p-6 space-y-4">
    <div className="flex items-center justify-between"><div><h1 className="text-lg font-bold text-neutral-100">Vale / Adiantamento</h1><p className="text-xs text-neutral-500 mt-1">Pendente: R$ {total.toLocaleString("pt-BR",{minimumFractionDigits:2})}</p></div><button onClick={()=>{setForm({});setShowForm(!showForm)}} className="px-3 py-1.5 bg-teal-600 text-white text-xs rounded-lg">+ Novo Vale</button></div>
    {showForm&&(<div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-3"><h3 className="text-sm font-semibold text-neutral-200">Novo Vale</h3><div className="grid grid-cols-2 gap-3">{[["funcionario_id","ID Func"],["nome","Nome"],["valor","Valor R$"],["motivo","Motivo"]].map(([k,l])=>(<div key={k}><label className="text-xs text-neutral-500">{l}</label><input type={k==="valor"?"number":"text"} value={form[k]||""} onChange={e=>setForm({...form,[k]:e.target.value})} className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200 mt-1"/></div>))}</div><div className="flex gap-2"><button onClick={handleCreate} className="px-3 py-1 bg-emerald-600 text-white text-xs rounded">Salvar</button><button onClick={()=>setShowForm(false)} className="px-3 py-1 text-xs text-neutral-400">Cancelar</button></div></div>)}
    {loading?<p className="text-neutral-500 text-sm">Carregando...</p>:items.length===0?<p className="text-neutral-500">Nenhum vale</p>:(
      <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto"><table className="w-full text-xs"><thead><tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">{["Func ID","Nome","Valor","Motivo","Data","Status"].map(c=><th key={c} className="text-left p-2">{c}</th>)}<th className="text-right p-2">Acao</th></tr></thead><tbody>{items.map((v,i)=>(<tr key={v.id} className={"border-b border-neutral-700/50 "+(i%2===0?"bg-neutral-800":"bg-neutral-800/50")}><td className="p-2">{v.funcionario_id}</td><td className="p-2 text-neutral-200">{v.nome}</td><td className="p-2 text-emerald-400">R$ {(v.valor||0).toFixed(2)}</td><td className="p-2 text-neutral-400">{v.motivo}</td><td className="p-2 text-neutral-500">{v.data?.slice(0,10)}</td><td className="p-2"><span className={"px-1.5 py-0.5 rounded text-[9px] "+(v.status==="pago"?"text-emerald-400 bg-emerald-900/30":"text-amber-400 bg-amber-900/30")}>{v.status||"pendente"}</span></td><td className="p-2 text-right">{v.status!=="pago"&&<button onClick={()=>handlePagar(v.id)} className="text-emerald-400 hover:text-emerald-300 text-xs">Pagar</button>}</td></tr>))}</tbody></table></div>)}</div>);
}
