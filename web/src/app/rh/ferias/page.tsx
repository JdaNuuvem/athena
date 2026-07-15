"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import StatusBadge from "@/app/_components/StatusBadge";
import LoadingState from "@/app/_components/LoadingState";

interface FeriasRow { id: number; funcionario_id: number; dias: number; inicio: string; fim: string; status: string; periodo_aquisitivo: string; }

const VARIANTS: Record<string, "success"|"warning"|"neutral"> = { concluida: "success", andamento: "warning", agendada: "neutral" };

export default function FeriasPage() {
  const [ferias, setFerias] = useState<FeriasRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.rhList("ferias").then(r => setFerias((r.data || []) as FeriasRow[])).finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 space-y-4">
      <div><h1 className="text-lg font-bold text-neutral-100">Férias</h1><p className="text-xs text-neutral-500 mt-1">{ferias.length} registros</p></div>

      {loading ? <LoadingState /> : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {ferias.map(f => (
            <div key={f.id} className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-2">
              <div className="flex justify-between"><span className="text-sm font-semibold text-neutral-200">{f.dias} dias</span><StatusBadge label={f.status} variant={VARIANTS[f.status] || "neutral"} /></div>
              <div className="text-xs text-neutral-500 space-y-1">
                <p>Período: {f.periodo_aquisitivo}</p>
                <p>{f.inicio?.slice(0,10)} → {f.fim?.slice(0,10)}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
