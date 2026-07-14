"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

export default function ShopeeIntegrationPage() {
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<{ text: string; ok: boolean } | null>(null);

  const sync = async () => {
    setSyncing(true);
    setSyncMessage(null);
    try {
      const r = await api.shopeeSync();
      const total = (r as Record<string, unknown>).total ?? 0;
      setSyncMessage({ text: `${total} itens sincronizados`, ok: true });
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
        <Link href="/integracoes" className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors">← Integrações</Link>
        <h1 className="text-lg font-light text-neutral-300 mt-1">Shopee</h1>
      </div>

      <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
        <p className="text-sm text-neutral-400 mb-4">
          Configure as chaves da Shopee na página de configuração para sincronizar produtos e pedidos.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={sync}
            disabled={syncing}
            className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors"
          >
            {syncing ? "Sincronizando..." : "Sincronizar Produtos"}
          </button>

          {syncMessage && (
            <span className={`text-xs px-3 py-1.5 rounded-lg border ${syncMessage.ok ? "bg-green-950/40 border-green-900/50 text-green-400" : "bg-red-950/40 border-red-900/50 text-red-400"}`}>
              {syncMessage.text}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
