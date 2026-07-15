"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtBRL } from "@/lib/format";
import StatusBadge from "@/app/_components/StatusBadge";
import LoadingState from "@/app/_components/LoadingState";

interface FolhaRow { id: number; funcionario_id: number; mes: string; salario: number; beneficios: number; descontos: number; liquido: number; status: string; }
interface FolhaResumo { total_funcionarios: number; total_salarios: number; total_beneficios: number; total_descontos: number; total_liquido: number; }

const mesAtual = new Date().toISOString().slice(0, 7);

export default function FolhaPage() {
  const [folha, setFolha] = useState<FolhaRow[]>([]);
  const [resumo, setResumo] = useState<FolhaResumo | null>(null);
  const [loading, setLoading] = useState(true);
  const [mes, setMes] = useState(mesAtual);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.rhList("folha"),
      fetch(`/api/rh/folha/resumo/${mes}`).then(r => r.json()),
    ]).then(([r1, r2]) => {
      setFolha((r1.data || []) as FolhaRow[]);
      setResumo(r2 as FolhaResumo);
    }).finally(() => setLoading(false));
  }, [mes]);

  return (
    <div className="p-6 space-y-4">
      <div className="flex justify-between items-end">
        <div><h1 className="text-lg font-bold text-neutral-100">Folha de Pagamento</h1><p className="text-xs text-neutral-500 mt-1">Competência {mes}</p></div>
        <input type="month" value={mes} onChange={e => setMes(e.target.value)} className="bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200 [color-scheme:dark]" />
      </div>

      {loading ? <LoadingState /> : (
        <>
          {resumo && (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-4">
              {[["Funcionários", resumo.total_funcionarios],["Salários",fmtBRL(resumo.total_salarios)],["Benefícios",fmtBRL(resumo.total_beneficios)],["Descontos",fmtBRL(resumo.total_descontos)],["Líquido",fmtBRL(resumo.total_liquido)]].map(([l,v],i) => (
                <div key={i} className="bg-neutral-800 border border-neutral-700 rounded p-2 text-center">
                  <p className="text-[10px] text-neutral-500">{l}</p>
                  <p className="text-sm font-bold text-neutral-200">{v}</p>
                </div>
              ))}
            </div>
          )}

          <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead><tr className="border-b border-neutral-700 text-neutral-400"><th className="text-left p-2">Mês</th><th className="text-right p-2">Salário</th><th className="text-right p-2">Benef.</th><th className="text-right p-2">Desc.</th><th className="text-right p-2">Líquido</th><th className="text-center p-2">Status</th></tr></thead>
              <tbody>
                {folha.map(f => (
                  <tr key={f.id} className="border-b border-neutral-700/50">
                    <td className="p-2 text-neutral-200">{f.mes}</td>
                    <td className="p-2 text-right text-neutral-300">{fmtBRL(f.salario)}</td>
                    <td className="p-2 text-right text-neutral-300">{fmtBRL(f.beneficios)}</td>
                    <td className="p-2 text-right text-red-400">{fmtBRL(f.descontos)}</td>
                    <td className="p-2 text-right text-emerald-400">{fmtBRL(f.liquido)}</td>
                    <td className="p-2 text-center"><StatusBadge label={f.status} variant={f.status==="pago"?"success":"warning"} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
