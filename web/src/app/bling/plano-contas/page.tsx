"use client";

import { useCallback, useEffect, useState } from "react";
import Spinner from "../_components/shared/Spinner";
import Alert from "../_components/shared/Alert";
import EmptyState from "../_components/shared/EmptyState";
import SyncToolbar from "../_components/shared/SyncToolbar";
import { listarBlingPlanoContas, sincronizarBlingPlanoContas } from "@/lib/api";
import type { BlingContaContabil } from "@/lib/api";

export default function BlingPlanoContasPage() {
  const [contas, setContas] = useState<BlingContaContabil[]>([]);
  const [loading, setLoading] = useState(true);
  const [sincronizando, setSincronizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [busca, setBusca] = useState("");

  const carregar = useCallback(async () => {
    setLoading(true);
    setErro(null);
    const r = await listarBlingPlanoContas();
    if (r.error) setErro(r.error);
    setContas(r.data);
    setLoading(false);
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar]);

  const handleSync = async () => {
    setSincronizando(true);
    setErro(null);
    setSucesso(null);
    const r = await sincronizarBlingPlanoContas();
    if (r.error) setErro(r.error);
    else setSucesso(`${r.sync ?? 0} contas sincronizadas`);
    setSincronizando(false);
    carregar();
  };

  const filtradas = contas.filter((c) => {
    if (!busca) return true;
    const t = busca.toLowerCase();
    return (c.nome || "").toLowerCase().includes(t) || (c.codigo || "").toLowerCase().includes(t);
  });

  if (loading && contas.length === 0) return <Spinner />;

  return (
    <div className="space-y-4">
      <Alert message={erro} type="error" />
      <Alert message={sucesso} type="success" />

      <SyncToolbar
        onSync={handleSync}
        sincronizando={sincronizando}
        total={filtradas.length}
        unidade="contas"
      >
        <input
          type="text"
          placeholder="Buscar por código ou nome..."
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="flex-1 min-w-[180px] bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500"
        />
      </SyncToolbar>

      {filtradas.length === 0 ? (
        <EmptyState
          icon="📊"
          title={busca ? "Nenhuma conta encontrada" : "Nenhuma conta contábil"}
          description={
            busca ? "Ajuste a busca." : "Sincronize o plano de contas do Bling para começar."
          }
          action={busca ? undefined : { label: "Sincronizar Agora", onClick: handleSync }}
        />
      ) : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="text-left p-3 w-[130px]">Código</th>
                <th className="text-left p-3">Nome</th>
                <th className="text-left p-3 w-[120px]">Tipo</th>
                <th className="text-left p-3 w-[120px]">Natureza</th>
                <th className="text-center p-3 w-[110px]">ID Bling</th>
              </tr>
            </thead>
            <tbody>
              {filtradas.map((c, i) => (
                <tr
                  key={c.id}
                  className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}
                >
                  <td className="p-3 text-indigo-400 font-mono">{c.codigo || "—"}</td>
                  <td className="p-3 text-neutral-200">{c.nome}</td>
                  <td className="p-3 text-neutral-400">{c.tipo || "—"}</td>
                  <td className="p-3 text-neutral-400">{c.natureza || "—"}</td>
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
