"use client";
import { useState, useEffect } from "react";
import Link from "next/link";

export default function SegurancaPage() {
  const [audit, setAudit] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);

  useEffect(() => {
    fetch("/api/auditoria?limit=5").then(r=>r.json()).then(d=>setAudit(d.auditoria||[])).catch(()=>{});
    fetch("/api/logs?level=ERROR&limit=5").then(r=>r.json()).then(d=>setLogs(d.logs||[])).catch(()=>{});
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div><h1 className="text-lg font-bold text-neutral-100">Seguranca e Governanca</h1><p className="text-xs text-neutral-500 mt-1">Auditoria, logs, historico e controle de acesso</p></div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Link href="/seguranca/auditoria" className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 hover:bg-neutral-750">
          <p className="text-sm font-semibold text-neutral-200">Auditoria</p> <p className="text-xs text-neutral-500 mt-1">{audit.length} registros recentes</p>
        </Link>
        <Link href="/seguranca/logs" className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 hover:bg-neutral-750">
          <p className="text-sm font-semibold text-neutral-200">Logs</p> <p className="text-xs text-neutral-500 mt-1">{logs.length} erros recentes</p>
        </Link>
        <Link href="/seguranca/historico" className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 hover:bg-neutral-750">
          <p className="text-sm font-semibold text-neutral-200">Historico</p> <p className="text-xs text-neutral-500 mt-1">Alteracoes</p>
        </Link>
        <Link href="/seguranca/rbac" className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 hover:bg-neutral-750">
          <p className="text-sm font-semibold text-neutral-200">RBAC</p> <p className="text-xs text-neutral-500 mt-1">Papeis e permissoes</p>
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-neutral-200 mb-2">Ultimas Acoes</h3>
          <div className="space-y-1 text-xs">
            {audit.slice(0,5).map((a,i) => (
              <div key={i} className="flex justify-between py-1 border-b border-neutral-700/30">
                <span className="text-neutral-400">{a.acao}</span>
                <span className="text-neutral-500">{a.email||"—"}</span>
                <span className="text-neutral-600">{String(a.created_at||"").slice(0,19)}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-neutral-200 mb-2">Logs de Erro</h3>
          <div className="space-y-1 text-xs">
            {logs.slice(0,5).map((l,i) => (
              <div key={i} className="flex justify-between py-1 border-b border-neutral-700/30">
                <span className="text-red-400">{l.level}</span>
                <span className="text-neutral-500">{l.mensagem?.slice(0,50)}</span>
                <span className="text-neutral-600">{String(l.created_at||"").slice(0,19)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
