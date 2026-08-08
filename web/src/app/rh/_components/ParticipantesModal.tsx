"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import Icon from "@/app/_components/Icon";
import FkPicker from "@/app/_components/FkPicker";
import { fkRhService } from "./rhService";

interface Participante {
  id: number;
  funcionario_id: number;
  funcionario_nome?: string;
  presenca: string;
  nota_avaliacao?: number;
  certificado_emitido: boolean;
}

interface ParticipantesModalProps {
  treinamentoId: number;
  treinamentoNome?: string;
  onClose: () => void;
}

const PRESENCA_LABEL: Record<string, string> = { pendente: "Pendente", presente: "Presente", ausente: "Ausente" };
const PRESENCA_COR: Record<string, string> = {
  pendente: "bg-amber-500/20 text-amber-400",
  presente: "bg-emerald-500/20 text-emerald-400",
  ausente: "bg-red-500/20 text-red-400",
};

// Participantes de um treinamento — controla presenca, nota de avaliacao e
// emissao de certificado por funcionario.
export default function ParticipantesModal({ treinamentoId, treinamentoNome, onClose }: ParticipantesModalProps) {
  const [participantes, setParticipantes] = useState<Participante[]>([]);
  const [loading, setLoading] = useState(true);
  const [novoFuncionarioId, setNovoFuncionarioId] = useState("");
  const [adicionando, setAdicionando] = useState(false);

  const fetchParticipantes = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.rhTreinamentoDetalhe(treinamentoId);
      setParticipantes((r.participantes || []) as unknown as Participante[]);
    } catch { setParticipantes([]); }
    finally { setLoading(false); }
  }, [treinamentoId]);

  useEffect(() => { fetchParticipantes(); }, [fetchParticipantes]);

  const handleAdicionar = async () => {
    if (!novoFuncionarioId) return;
    try {
      await api.rhCreate("treinamento_participantes", { treinamento_id: treinamentoId, funcionario_id: Number(novoFuncionarioId) });
      setNovoFuncionarioId("");
      setAdicionando(false);
      fetchParticipantes();
    } catch (e) { alert(String(e)); }
  };

  const atualizarParticipante = async (id: number, campo: string, valor: unknown) => {
    try {
      await api.rhUpdate("treinamento_participantes", id, { [campo]: valor });
      fetchParticipantes();
    } catch (e) { alert(String(e)); }
  };

  const handleRemover = async (id: number) => {
    try { await api.rhDelete("treinamento_participantes", id); fetchParticipantes(); }
    catch (e) { alert(String(e)); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={onClose}>
      <div className="w-full max-w-[640px] max-h-[85vh] overflow-y-auto rounded-xl border border-neutral-700 bg-neutral-800 shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-neutral-700/70 px-5 py-4">
          <h3 className="text-sm font-semibold text-neutral-100">Participantes{treinamentoNome ? ` — ${treinamentoNome}` : ""}</h3>
          <button onClick={onClose} className="rounded-md p-1 text-neutral-500 hover:bg-neutral-700 hover:text-neutral-300">
            <Icon name="close" size={15} />
          </button>
        </div>

        <div className="space-y-3 px-5 py-4">
          {loading ? (
            <p className="text-xs text-neutral-500">Carregando...</p>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-neutral-700">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-neutral-700 bg-neutral-900/60 text-left text-neutral-400">
                    <th className="px-3 py-2 font-medium">Funcionário</th>
                    <th className="px-3 py-2 font-medium">Presença</th>
                    <th className="px-3 py-2 font-medium">Nota</th>
                    <th className="px-3 py-2 font-medium">Certificado</th>
                    <th className="px-3 py-2 font-medium text-right">Ações</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-800/70">
                  {participantes.map(p => (
                    <tr key={p.id} className="text-neutral-300">
                      <td className="whitespace-nowrap px-3 py-2">{p.funcionario_nome}</td>
                      <td className="whitespace-nowrap px-3 py-2">
                        <select value={p.presenca} onChange={e => atualizarParticipante(p.id, "presenca", e.target.value)}
                          className={`rounded px-1.5 py-1 text-[10px] ${PRESENCA_COR[p.presenca] ?? "bg-neutral-500/20 text-neutral-400"}`}>
                          {Object.entries(PRESENCA_LABEL).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
                        </select>
                      </td>
                      <td className="whitespace-nowrap px-3 py-2">
                        <input type="number" step="0.1" min={0} max={10} defaultValue={p.nota_avaliacao ?? ""}
                          onBlur={e => atualizarParticipante(p.id, "nota_avaliacao", e.target.value ? parseFloat(e.target.value) : null)}
                          className="w-16 rounded border border-neutral-600 bg-neutral-700 px-2 py-1 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none" />
                      </td>
                      <td className="whitespace-nowrap px-3 py-2">
                        <input type="checkbox" checked={p.certificado_emitido} onChange={e => atualizarParticipante(p.id, "certificado_emitido", e.target.checked)}
                          className="rounded border-neutral-600 bg-neutral-700 accent-indigo-600" />
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button onClick={() => handleRemover(p.id)} title="Remover" className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-red-500/10 hover:text-red-400">
                          <Icon name="trash" size={13} />
                        </button>
                      </td>
                    </tr>
                  ))}
                  {participantes.length === 0 && (
                    <tr><td colSpan={5} className="px-3 py-6 text-center text-neutral-500">Nenhum participante ainda</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {adicionando ? (
            <div className="flex items-center gap-2 rounded-lg border border-indigo-700/50 bg-neutral-900/40 p-3">
              <div className="flex-1">
                <FkPicker tabela="funcionarios" service={fkRhService} value={novoFuncionarioId} onChange={setNovoFuncionarioId} />
              </div>
              <button onClick={() => { setAdicionando(false); setNovoFuncionarioId(""); }} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 transition-colors hover:text-neutral-200">Cancelar</button>
              <button onClick={handleAdicionar} className="rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-500">Adicionar</button>
            </div>
          ) : (
            <button onClick={() => setAdicionando(true)} className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-neutral-700 px-3 py-2 text-xs text-neutral-500 transition-colors hover:bg-neutral-800 hover:text-neutral-300">
              <span className="text-sm leading-none">+</span> Adicionar participante
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
