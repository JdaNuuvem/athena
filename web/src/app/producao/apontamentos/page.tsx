"use client";
import { useState, useEffect } from "react";
export default function Page() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<Record<string,string>>({});
  const carregar=()=>{fetch("/api/producao/apontamentos").then(r=>r.json()).then(d=>setItems(d.data||[])).catch(()=>{}).finally(()=>setLoading(false));};
  useEffect(()=>{carregar();},[]);
  const handleCreate=async()=>{await fetch("/api/producao/apontamentos",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(form)});setShowForm(false);setForm({});carregar();};
  const handleDelete=async(id:number)=>{if(!confirm("Remover?"))return;await fetch("/api/producao/apontamentos/"+id,{method:"DELETE"});carregar();};
  return(
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between"><div><h1 className="text-lg font-bold text-neutral-100">Apontamentos</h1><p className="text-xs text-neutral-500 mt-1">Registro de producao</p></div><button onClick={()=>setShowForm(!showForm)} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg">+ Novo</button></div>
      {showForm&&(<div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-3"><div className="grid grid-cols-2 gap-3">{["op_id","maquina_id","operador","quantidade_produzida","quantidade_boa","quantidade_refugo"].map(c=>(<div key={c}><label className="text-xs text-neutral-500 capitalize">{c.replace(/_/g," ")}</label><input type="text" value={form[c]||""} onChange={e=>setForm({...form,[c]:e.target.value})} className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200 mt-1"/></div>))}</div><div className="flex gap-2"><button onClick={handleCreate} className="px-3 py-1 bg-emerald-600 text-white text-xs rounded">Salvar</button><button onClick={()=>setShowForm(false)} className="px-3 py-1 text-xs text-neutral-400">Cancelar</button></div></div>)}
      {loading?<p className="text-neutral-500 text-sm">Carregando...</p>:items.length===0?(<div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center"><p className="text-neutral-400 text-sm">Nenhum registro</p></div>):(<div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden"><table className="w-full text-xs"><thead><tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">{["op_id","maquina_id","operador","quantidade_produzida","quantidade_boa","quantidade_refugo"].map(c=><th key={c} className="text-left p-3 capitalize">{c.replace(/_/g," ")}</th>)}<th className="text-right p-3">Acoes</th></tr></thead><tbody>{items.map((item,i)=>(<tr key={item.id} className={"border-b border-neutral-700/50 "+(i%2===0?"bg-neutral-800":"bg-neutral-800/50")}>{["op_id","maquina_id","operador","quantidade_produzida","quantidade_boa","quantidade_refugo"].map(c=>(<td key={c} className="p-3 text-neutral-300">{c.includes("valor")||c.includes("quantidade")?Number(item[c]||0).toLocaleString("pt-BR"):String(item[c]??"—")}</td>))}<td className="p-3 text-right"><button onClick={()=>handleDelete(item.id)} className="text-red-400 text-xs">Remover</button></td></tr>))}</tbody></table></div>)}
    </div>
  );
}
