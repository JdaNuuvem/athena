"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import DateFilter, { type DateFilterValue } from "@/app/_components/DateFilter";
import LoadingState from "@/app/_components/LoadingState";

interface PontoRow { id: number; funcionario: string; data: string; entrada: string; saida_almoco: string; volta_almoco: string; saida: string; }

export default function PontoPage() {
  const [pontos, setPontos] = useState<PontoRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [dateFilter] = useState<DateFilterValue>({});

  const today = new Date().toISOString().slice(0, 10);

  useEffect(() => {
    fetch(`/api/rh/ponto/data/${today}`)
      .then(r => r.json())
      .then(d => setPontos((d.data || d || []) as PontoRow[]))
      .finally(() => setLoading(false));
  }, [today]);

  return (
    <div className="p-6 space-y-4">
      <div><h1 className="text-lg font-bold text-neutral-100">Ponto Eletrônico</h1><p className="text-xs text-neutral-500 mt-1">Registros de {new Date().toLocaleDateString("pt-BR")}</p></div>

      {loading ? <LoadingState /> : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead><tr className="border-b border-neutral-700 text-neutral-400">
              <th className="text-left p-2">Funcionário</th><th className="text-center p-2">Entrada</th><th className="text-center p-2">Saída Almoço</th><th className="text-center p-2">Volta</th><th className="text-center p-2">Saída</th>
            </tr></thead>
            <tbody>
              {pontos.length === 0 ? <tr><td colSpan={5} className="p-4 text-center text-neutral-500">Nenhum registro hoje</td></tr> :
              pontos.map(p => (
                <tr key={p.id} className="border-b border-neutral-700/50">
                  <td className="p-2 text-neutral-200">{p.funcionario || `#${p.id}`}</td>
                  <td className="p-2 text-center text-neutral-300">{p.entrada?.slice(0,5) || "—"}</td>
                  <td className="p-2 text-center text-neutral-300">{p.saida_almoco?.slice(0,5) || "—"}</td>
                  <td className="p-2 text-center text-neutral-300">{p.volta_almoco?.slice(0,5) || "—"}</td>
                  <td className="p-2 text-center text-neutral-300">{p.saida?.slice(0,5) || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
