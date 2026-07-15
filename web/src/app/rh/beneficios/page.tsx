"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtBRL } from "@/lib/format";
import LoadingState from "@/app/_components/LoadingState";

interface BenefRow { id: number; nome: string; tipo: string; valor_empresa: number; valor_funcionario: number; funcionarios_ativos: number; }

export default function BeneficiosPage() {
  const [beneficios, setBeneficios] = useState<BenefRow[]>([]);
  const [totais, setTotais] = useState({ total_empresa: 0, total_funcionario: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.rhBeneficiosResumo().then(d => {
      setBeneficios((d.beneficios || []) as BenefRow[]);
      setTotais({ total_empresa: Number(d.total_empresa), total_funcionario: Number(d.total_funcionario) });
    }).finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 space-y-4">
      <div><h1 className="text-lg font-bold text-neutral-100">Benefícios</h1><p className="text-xs text-neutral-500 mt-1">Empresa: {fmtBRL(totais.total_empresa)} · Func.: {fmtBRL(totais.total_funcionario)}</p></div>

      {loading ? <LoadingState /> : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {beneficios.map(b => (
            <div key={b.id} className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-2">
              <h3 className="text-sm font-semibold text-neutral-200">{b.nome}</h3>
              <span className="text-[10px] text-neutral-500 bg-neutral-700 rounded px-1.5 py-0.5">{b.tipo}</span>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div><p className="text-neutral-500">Empresa</p><p className="text-emerald-400">{fmtBRL(b.valor_empresa)}</p></div>
                <div><p className="text-neutral-500">Funcionário</p><p className="text-amber-400">{fmtBRL(b.valor_funcionario)}</p></div>
              </div>
              <p className="text-[10px] text-neutral-600">{b.funcionarios_ativos} funcionários ativos</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
