"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

export default function BlingIntegrationPage() {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<{ text: string; ok: boolean } | null>(null);

  useEffect(() => {
    api.blingStatus().then(setStatus).catch(() => {});
  }, []);

  const sync = async () => {
    setSyncing(true);
    setSyncMessage(null);
    try {
      const r = await api.blingSync();
      const count = (r as Record<string, unknown>).count ?? 0;
      setSyncMessage({ text: `${count} registros sincronizados`, ok: true });
    } catch {
      setSyncMessage({ text: "Erro ao sincronizar", ok: false });
    } finally {
      setSyncing(false);
      setTimeout(() => setSyncMessage(null), 6000);
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <div>
        <a href="/integracoes" className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors">← Integrações</a>
        <h1 className="text-lg font-light text-neutral-300 mt-1">Bling ERP</h1>
      </div>

      {status && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
            <div className="text-[10px] text-neutral-500 uppercase tracking-wider mb-1">Status</div>
            <div className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className={`w-2 h-2 rounded-full shrink-0 ${status.autenticado ? "bg-green-500" : "bg-red-500"}`}
              />
              <span className="text-sm text-neutral-200">{status.autenticado ? "Conectado" : "Desconectado"}</span>
            </div>
          </div>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
            <div className="text-[10px] text-neutral-500 uppercase tracking-wider mb-1">Callback</div>
            <div className="text-sm text-indigo-400 font-mono truncate">{status.auth_url ? "Configurado" : "—"}</div>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={sync}
          disabled={syncing}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors"
        >
          {syncing ? "Sincronizando..." : "Sincronizar Produtos e Pedidos"}
        </button>

        {syncMessage && (
          <span className={`text-xs px-3 py-1.5 rounded-lg border ${syncMessage.ok ? "bg-green-950/40 border-green-900/50 text-green-400" : "bg-red-950/40 border-red-900/50 text-red-400"}`}>
            {syncMessage.text}
          </span>
        )}
      </div>

      <div className="flex gap-2 flex-wrap">
        <a
          href="/api/bling/auth"
          target="_blank"
          rel="noopener noreferrer"
          className="bg-neutral-800 hover:bg-neutral-700 text-neutral-300 text-xs px-4 py-2 rounded-lg border border-neutral-700 transition-colors"
        >
          Autorizar Bling (OAuth)
        </a>
        <a
          href="/integracoes"
          className="bg-neutral-800 hover:bg-neutral-700 text-neutral-300 text-xs px-4 py-2 rounded-lg border border-neutral-700 transition-colors"
        >
          Voltar
        </a>
      </div>
    </div>
  );
}
