"use client";
import { useState, useEffect } from "react";
import Link from "next/link";

export default function ProducaoPage() {
  const [dash, setDash] = useState<any>(null);
  useEffect(() => { fetch("/api/producao/dashboard").then(r=>r.json()).then(setDash).catch(()=>{}); }, []);
  return (
    <div className="p-6 space-y-6">
      <div><h1 className="text-lg font-bold text-neutral-100">Producao</h1><p className="text-xs text-neutral-500 mt-1">OPs, BOM, Maquinas, Apontamentos, Custos e Perdas</p></div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4"><p className="text-xs text-neutral-500">OPs Ativas</p><p className="text-xl font-bold text-blue-400">{dash?.ops_ativas??0}</p></div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4"><p className="text-xs text-neutral-500">OPs Hoje</p><p className="text-xl font-bold text-amber-400">{dash?.ops_hoje??0}</p></div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4"><p className="text-xs text-neutral-500">Maquinas Ativas</p><p className="text-xl font-bold text-emerald-400">{dash?.maquinas_ativas??0}</p></div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4"><p className="text-xs text-neutral-500">Maquinas Paradas</p><p className="text-xl font-bold text-red-400">{dash?.maquinas_paradas??0}</p></div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4"><p className="text-xs text-neutral-500">Perdas</p><p className="text-xl font-bold text-orange-400">{dash?.total_perdas??0}</p></div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4"><p className="text-xs text-neutral-500">Rendimento</p><p className="text-xl font-bold text-emerald-400">{dash?.rendimento_pct??0}%</p></div>
      </div>
      <div><h2 className="text-sm font-semibold text-neutral-300 mb-3">Modulos</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[{href:"/producao/ops",label:"OPs",color:"bg-blue-600"},{href:"/producao/bom",label:"BOM",color:"bg-purple-600"},{href:"/producao/maquinas",label:"Maquinas",color:"bg-teal-600"},{href:"/producao/apontamentos",label:"Apontamentos",color:"bg-amber-600"},{href:"/producao/consumo",label:"Consumo",color:"bg-pink-600"},{href:"/producao/perdas",label:"Perdas",color:"bg-red-600"},{href:"/producao/custos",label:"Custos",color:"bg-indigo-600"}].map(m=>(
            <Link key={m.href} href={m.href} className={m.color+" hover:opacity-90 text-white rounded-lg p-4"}><p className="text-sm font-semibold">{m.label}</p></Link>
          ))}</div>
      </div>
    </div>
  );
}
