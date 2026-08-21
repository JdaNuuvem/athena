"use client";

import { useCallback, useEffect, useState } from "react";
import Spinner from "../_components/shared/Spinner";
import Alert from "../_components/shared/Alert";
import EmptyState from "../_components/shared/EmptyState";
import SyncToolbar from "../_components/shared/SyncToolbar";
import { listarBlingCanais, sincronizarBlingCanais } from "@/lib/api";
import type { BlingCanal } from "@/lib/api";

export default function BlingCanaisPage() {
  const [canais, setCanais] = useState<BlingCanal[]>([]);
  const [loading, setLoading] = useState(true);
  const [sincronizando, setSincronizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);

  const carregar = useCallback(async () => {
    setLoading(true);
    setErro(null);
    const r = await listarBlingCanais();
    if (r.error) setErro(r.error);
    setCanais(r.data);
    setLoading(false);
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar]);

  const handleSync = async () => {
    setSincronizando(true);
    setErro(null);
    setSucesso(null);
    const r = await sincronizarBlingCanais();
    if (r.error) setErro(r.error);
    else setSucesso(`${r.sync ?? 0} canais sincronizados`);
    setSincronizando(false);
    carregar();
  };

  if (loading && canais.length === 0) return <Spinner />;

  return (
    <div className="space-y-4">
      <Alert message={erro} type="error" />
      <Alert message={sucesso} type="success" />

      <SyncToolbar
        onSync={handleSync}
        sincronizando={sincronizando}
        total={canais.length}
        unidade="canais"
      />

      {canais.length === 0 ? (
        <EmptyState
          icon="🛍️"
          title="Nenhum canal"
          description="Sincronize as lojas/canais do Bling para começar."
          action={{ label: "Sincronizar Agora", onClick: handleSync }}
        />
      ) : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="text-left p-3">Nome</th>
                <th className="text-left p-3 w-[160px]">Situação</th>
                <th className="text-center p-3 w-[110px]">ID Bling</th>
              </tr>
            </thead>
            <tbody>
              {canais.map((c, i) => (
                <tr
                  key={c.id}
                  className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}
                >
                  <td className="p-3 text-neutral-200">{c.nome}</td>
                  <td className="p-3 text-neutral-400">{c.situacao || "—"}</td>
                  <td className="p-3 text-center text-neutral-500 font-mono text-[10px]">
                    {c.bling_id || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
