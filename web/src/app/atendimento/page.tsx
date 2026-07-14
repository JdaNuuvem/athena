"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

export default function AtendimentoPage() {
  const [dash, setDash] = useState<any>(null);

  useEffect(() => {
    fetch("/api/atendimento/dashboard").then(r=>r.json()).then(setDash).catch(()=>{});
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div><h1 className="text-lg font-bold text-neutral-100">Atendimento</h1><p className="text-xs text-neutral-500 mt-1">Tickets, chat, canais e base de conhecimento</p></div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Tickets Abertos</p>
          <p className="text-xl font-bold text-amber-400">{dash?.tickets_abertos ?? 0}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Hoje</p>
          <p className="text-xl font-bold text-blue-400">{dash?.hoje ?? 0}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Tempo Medio Resposta</p>
          <p className="text-xl font-bold text-emerald-400">{Math.round(dash?.tempo_medio_resposta || 0)} min</p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        {["whatsapp","telegram","instagram","facebook","chat","email"].map(c => {
          const canal = dash?.canais?.find((x:any) => x.canal === c);
          return <div key={c} className="bg-neutral-800 border border-neutral-700 rounded-lg p-3 text-center">
            <p className="text-xs text-neutral-500 capitalize">{c}</p>
            <p className="text-lg font-bold text-neutral-200">{canal?.cnt ?? 0}</p>
          </div>
        })}
      </div>

      <div>
        <h2 className="text-sm font-semibold text-neutral-300 mb-3">SLA por Prioridade</h2>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead><tr className="border-b border-neutral-700 text-neutral-400"><th className="text-left p-3">Prioridade</th><th className="text-center p-3">Resposta (min)</th><th className="text-center p-3">Resolucao (h)</th></tr></thead>
            <tbody>{(dash?.slas || []).map((s:any) => (
              <tr key={s.prioridade} className="border-b border-neutral-700/50">
                <td className="p-3 text-neutral-200 capitalize">{s.prioridade}</td>
                <td className="p-3 text-center text-neutral-300">{s.tempo_resposta_min}</td>
                <td className="p-3 text-center text-neutral-300">{s.tempo_resolucao_h}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </div>

      <div>
        <h2 className="text-sm font-semibold text-neutral-300 mb-3">Modulos</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {[
            {href:"/atendimento/tickets",label:"Tickets",color:"bg-amber-600"},
            {href:"/atendimento/chat",label:"Chat",color:"bg-blue-600"},
            {href:"/atendimento/canais",label:"Canais",color:"bg-purple-600"},
            {href:"/atendimento/sla",label:"SLA",color:"bg-pink-600"},
            {href:"/atendimento/kb",label:"Base Conhecimento",color:"bg-teal-600"},
          ].map(m => (
            <Link key={m.href} href={m.href} className={m.color+" hover:opacity-90 text-white rounded-lg p-4"}>
              <p className="text-sm font-semibold">{m.label}</p>
              <p className="text-[10px] opacity-80 mt-1">Gerenciar {m.label.toLowerCase()}</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
