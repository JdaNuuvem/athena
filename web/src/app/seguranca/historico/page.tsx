"use client";
import { useState, useEffect } from "react";

export default function Page() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filtro, setFiltro] = useState("");
  const apiUrl = "/api/historico";

  useEffect(() => {
    fetch(apiUrl).then(r=>r.json()).then(d => {
      setItems(d.historico || []);
    }).catch(()=>{}).finally(()=>setLoading(false));
  }, []);

  const filtered = items.filter((i:any) => !filtro || JSON.stringify(i).toLowerCase().includes(filtro.toLowerCase()));

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between"><div><h1 className="text-lg font-bold text-neutral-100">Historico</h1><p className="text-xs text-neutral-500 mt-1">Alteracoes por entidade</p></div></div>
      <input type="text" value={filtro} onChange={e=>setFiltro(e.target.value)} placeholder="Filtrar..." className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200" />
      {loading ? <p className="text-neutral-500">Carregando...</p> : filtered.length===0 ? <p className="text-neutral-500">Nenhum registro</p> : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
          <table className="w-full text-xs"><thead><tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
            {Object.keys(filtered[0]||{}).filter(k=>k!=="dados_antes"&&k!=="dados_depois"&&k!=="stacktrace"&&k!=="data"&&k!=="dados").slice(0,6).map((k:string)=>(
              <th key={k} className="text-left p-2 capitalize">{k.replace(/_/g," ")}</th>
            ))}</tr></thead>
            <tbody>{filtered.slice(0,100).map((item:any,i:number)=>(
              <tr key={i} className={"border-b border-neutral-700/50 "+(i%2===0?"bg-neutral-800":"bg-neutral-800/50")}>
                {Object.keys(item).filter(k=>k!=="dados_antes"&&k!=="dados_depois"&&k!=="stacktrace"&&k!=="data"&&k!=="dados").slice(0,6).map((k:string)=>(
                  <td key={k} className="p-2 text-neutral-300">{String(item[k]??"—").slice(0,100)}</td>
                ))}</tr>
            ))}</tbody></table>
        </div>
      )}</div>
  );
}
