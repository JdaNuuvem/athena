"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import HelpTooltip from "@/app/_components/HelpTooltip";

export default function AutomacoesPage() {
  const [dash, setDash] = useState<any>(null);
  useEffect(() => { fetch("/api/automacoes/dashboard").then(r=>r.json()).then(setDash).catch(()=>{}); }, []);
  return (
    <div className="p-6 space-y-6">
      <div><h1 className="text-lg font-bold text-neutral-100">Automacoes</h1><p className="text-xs text-neutral-500 mt-1">Webhooks, Filas, Eventos, Agendamentos, Integracoes, Bots e IA</p></div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4"><p className="text-xs text-neutral-500">Webhooks</p><p className="text-xl font-bold text-blue-400">{dash?.webhooks??0}</p></div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4"><p className="text-xs text-neutral-500">Filas</p><p className="text-xl font-bold text-amber-400">{dash?.filas??0}</p></div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4"><p className="text-xs text-neutral-500">Eventos</p><p className="text-xl font-bold text-purple-400">{dash?.eventos??0}</p></div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4"><p className="text-xs text-neutral-500">Agendamentos</p><p className="text-xl font-bold text-emerald-400">{dash?.agendamentos??0}</p></div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4"><p className="text-xs text-neutral-500">Integracoes</p><p className="text-xl font-bold text-indigo-400">{dash?.integracoes??0}</p></div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4"><p className="text-xs text-neutral-500">Bots</p><p className="text-xl font-bold text-pink-400">{dash?.bots??0}</p></div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4"><p className="text-xs text-neutral-500">IA</p><p className="text-xl font-bold text-teal-400">{dash?.ia??0}</p></div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4"><p className="text-xs text-neutral-500">Execucoes</p><p className="text-xl font-bold text-orange-400">{dash?.total_execucoes??0}</p></div>
      </div>
      <div><h2 className="text-sm font-semibold text-neutral-300 mb-3">Modulos</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[{href:"/automacoes/webhooks",label:"Webhooks",c:"bg-blue-600",h:"Notificacoes HTTP em tempo real — receba eventos externos"},{href:"/automacoes/filas",label:"Filas",c:"bg-amber-600",h:"Filas de processamento assincrono — enfileire tarefas"},{href:"/automacoes/eventos",label:"Eventos",c:"bg-purple-600"},{href:"/automacoes/agendamentos",label:"Agendamentos",c:"bg-emerald-600",h:"Tarefas agendadas com cron — execute periodicamente"},{href:"/automacoes/integracoes",label:"Integracoes",c:"bg-indigo-600"},{href:"/automacoes/bots",label:"Bots",c:"bg-pink-600"},{href:"/automacoes/ia",label:"IA",c:"bg-teal-600"}].map(m=>(
            <Link key={m.href} href={m.href} className={m.c+" hover:opacity-90 text-white rounded-lg p-4"}><p className="text-sm font-semibold">{m.label}<span className="opacity-0 group-hover:opacity-100 transition-opacity text-[9px] bg-white/20 rounded-full w-4 h-4 flex items-center justify-center ml-1.5">?</span></p></Link>
          ))}</div>
      </div>
    </div>
  );
}
