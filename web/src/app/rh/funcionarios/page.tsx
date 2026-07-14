"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import StatusBadge from "@/app/_components/StatusBadge";
import LoadingState from "@/app/_components/LoadingState";

interface FuncRow { id: number; nome: string; cargo: string; departamento: string; email: string; status: string; data_admissao: string; }
interface FuncDetail { funcionario: FuncRow; ponto: unknown[]; ferias: unknown[]; folha: unknown[]; beneficios: unknown[]; escala: Record<string, unknown> | null; }

const COLORS: Record<string, "success"|"warning"|"danger"|"neutral"> = { ativo:"success", ferias:"warning", afastado:"danger" };

export default function FuncionariosPage() {
  const [funcs, setFuncs] = useState<FuncRow[]>([]);
  const [detail, setDetail] = useState<FuncDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { api.rhList("funcionarios").then(r => setFuncs((r.data || []) as FuncRow[])).finally(() => setLoading(false)); }, []);

  const openDetail = async (id: number) => {
    const r = await fetch(`/api/rh/funcionario/${id}`).then(r => r.json());
    setDetail(r as FuncDetail);
  };

  return (
    <div className="p-6 space-y-4">
      <div><h1 className="text-lg font-bold text-neutral-100">Funcionários</h1><p className="text-xs text-neutral-500 mt-1">{funcs.length} colaboradores</p></div>

      {loading ? <LoadingState /> : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-3 content-start">
            {funcs.map(f => (
              <div key={f.id} onClick={() => openDetail(f.id)} className="bg-neutral-800 border border-neutral-700 rounded-lg p-3 cursor-pointer hover:border-blue-600 transition-colors">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="text-sm font-semibold text-neutral-200">{f.nome}</h3>
                    <p className="text-xs text-neutral-500">{f.cargo} · {f.departamento}</p>
                  </div>
                  <StatusBadge label={f.status} variant={COLORS[f.status] || "neutral"} />
                </div>
              </div>
            ))}
          </div>

          {detail && (
            <div className="bg-neutral-800 border border-blue-700 rounded-lg p-4 space-y-3">
              <div className="flex justify-between">
                <h3 className="text-sm font-semibold text-neutral-200">{detail.funcionario.nome}</h3>
                <button onClick={() => setDetail(null)} className="text-xs text-neutral-500 hover:text-neutral-300">✕</button>
              </div>
              <div className="text-xs text-neutral-400 space-y-1">
                <p>Cargo: {detail.funcionario.cargo}</p>
                <p>Depto: {detail.funcionario.departamento}</p>
                <p>Email: {detail.funcionario.email}</p>
                <p>Admissão: {detail.funcionario.data_admissao}</p>
              </div>

              {detail.escala && <div className="text-xs text-neutral-500">Escala: {String(detail.escala.turno)} · {String(detail.escala.horario)}</div>}

              <div><h4 className="text-xs font-semibold text-neutral-400 mb-1">Benefícios</h4>
                <div className="flex flex-wrap gap-1">{(detail.beneficios as Array<{nome:string}>).map((b,i) => <span key={i} className="bg-neutral-700 rounded px-1.5 py-0.5 text-[10px] text-neutral-300">{b.nome}</span>)}</div>
              </div>

              <div><h4 className="text-xs font-semibold text-neutral-400 mb-1">Folha recente</h4>
                {(detail.folha as Array<{mes:string;liquido:number}>).slice(0,3).map((f,i) => <div key={i} className="flex justify-between text-[10px] text-neutral-300"><span>{f.mes}</span><span className="text-emerald-400">R$ {Number(f.liquido).toFixed(2)}</span></div>)}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
