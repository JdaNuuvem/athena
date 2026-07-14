"use client";
import { useState, useEffect } from "react";
export default function KBPage() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<Record<string,string>>({});
  const [busca, setBusca] = useState("");
  const carregar = () => { fetch("/api/atendimento/kb_artigos").then(r=>r.json()).then(d=>setItems(d.data||[])).catch(()=>{}).finally(()=>setLoading(false)); };
  useEffect(()=>{carregar();},[]);
  const handleCreate = async () => { await fetch("/api/atendimento/kb_artigos",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(form)}); setShowForm(false); setForm({}); carregar(); };
  const handleDelete = async (id:number) => { if(!confirm("Remover?"))return; await fetch("/api/atendimento/kb_artigos/"+id,{method:"DELETE"}); carregar(); };
  const filtered = items.filter(i => !busca || i.titulo?.toLowerCase().includes(busca.toLowerCase()) || i.tags?.toLowerCase().includes(busca.toLowerCase()));
  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between"><div><h1 className="text-lg font-bold text-neutral-100">Base de Conhecimento</h1><p className="text-xs text-neutral-500 mt-1">Artigos e documentacao</p></div><button onClick={()=>setShowForm(!showForm)} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg">+ Artigo</button></div>
      <input type="text" value={busca} onChange={e=>setBusca(e.target.value)} placeholder="Buscar artigos..." className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200" />
      {showForm&&(<div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-3"><h3 className="text-sm font-semibold text-neutral-200">Novo Artigo</h3><div className="space-y-2">{[["titulo","Titulo"],["categoria","Categoria"],["tags","Tags"]].map(([c,l])=>(<div key={c}><label className="text-xs text-neutral-500">{l}</label><input type="text" value={form[c]||""} onChange={e=>setForm({...form,[c]:e.target.value})} className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200 mt-1"/></div>))}<div><label className="text-xs text-neutral-500">Conteudo</label><textarea value={form["conteudo"]||""} onChange={e=>setForm({...form,conteudo:e.target.value})} className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200 mt-1 h-24" rows={4}/></div></div><div className="flex gap-2"><button onClick={handleCreate} className="px-3 py-1 bg-emerald-600 text-white text-xs rounded">Salvar</button><button onClick={()=>setShowForm(false)} className="px-3 py-1 text-xs text-neutral-400">Cancelar</button></div></div>)}
      {loading?<p className="text-neutral-500 text-sm">Carregando...</p>:filtered.length===0?(<div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center"><p className="text-neutral-400 text-sm">Nenhum artigo</p></div>):(<div className="grid grid-cols-1 md:grid-cols-2 gap-3">{filtered.map(a=>(<div key={a.id} className="bg-neutral-800 border border-neutral-700 rounded-lg p-4"><h3 className="text-sm font-semibold text-neutral-200">{a.titulo}</h3><p className="text-[10px] text-neutral-500">{a.categoria} | {a.visualizacoes||0} views</p><p className="text-xs text-neutral-400 mt-2 line-clamp-3">{a.conteudo}</p><div className="flex gap-2 mt-2"><span className="text-[10px] bg-neutral-700 rounded px-2 py-0.5 text-neutral-400">{a.tags}</span><button onClick={()=>handleDelete(a.id)} className="text-red-400 text-[10px] ml-auto">Remover</button></div></div>))}</div>)}
    </div>
  );
}
