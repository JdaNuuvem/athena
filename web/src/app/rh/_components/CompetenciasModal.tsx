"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import Icon from "@/app/_components/Icon";

interface Competencia {
  id: number;
  competencia: string;
  nota?: number;
  comentario?: string;
}

interface CompetenciasModalProps {
  avaliacaoId: number;
  funcionarioNome?: string;
  onClose: () => void;
}

// Competencias avaliadas dentro de uma avaliacao de desempenho (ex: Comunicacao,
// Trabalho em equipe, Entrega) — cada uma com nota 0-10 e comentario opcional.
export default function CompetenciasModal({ avaliacaoId, funcionarioNome, onClose }: CompetenciasModalProps) {
  const [competencias, setCompetencias] = useState<Competencia[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({ competencia: "", nota: "", comentario: "" });
  const [editId, setEditId] = useState<number | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  const fetchCompetencias = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.rhAvaliacaoDetalhe(avaliacaoId);
      setCompetencias((r.competencias || []) as unknown as Competencia[]);
    } catch { setCompetencias([]); }
    finally { setLoading(false); }
  }, [avaliacaoId]);

  useEffect(() => { fetchCompetencias(); }, [fetchCompetencias]);

  const abrirNovo = () => { setForm({ competencia: "", nota: "", comentario: "" }); setEditId(0); };
  const abrirEdicao = (c: Competencia) => {
    setForm({ competencia: c.competencia, nota: String(c.nota ?? ""), comentario: c.comentario || "" });
    setEditId(c.id);
  };

  const handleSalvar = async () => {
    if (!form.competencia.trim()) { alert("Informe a competência"); return; }
    const payload = {
      avaliacao_id: avaliacaoId,
      competencia: form.competencia.trim(),
      nota: form.nota ? parseFloat(form.nota) : null,
      comentario: form.comentario || null,
    };
    try {
      if (editId) await api.rhUpdate("avaliacao_competencias", editId, payload);
      else await api.rhCreate("avaliacao_competencias", payload);
      setEditId(null);
      setForm({ competencia: "", nota: "", comentario: "" });
      fetchCompetencias();
    } catch (e) { alert(String(e)); }
  };

  const handleDelete = async (id: number) => {
    try { await api.rhDelete("avaliacao_competencias", id); setConfirmDelete(null); fetchCompetencias(); }
    catch (e) { alert(String(e)); }
  };

  const mediaNotas = competencias.length > 0
    ? (competencias.reduce((s, c) => s + (Number(c.nota) || 0), 0) / competencias.filter(c => c.nota != null).length || 0)
    : 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={onClose}>
      <div className="w-full max-w-[560px] max-h-[85vh] overflow-y-auto rounded-xl border border-neutral-700 bg-neutral-800 shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-neutral-700/70 px-5 py-4">
          <h3 className="text-sm font-semibold text-neutral-100">Competências{funcionarioNome ? ` — ${funcionarioNome}` : ""}</h3>
          <button onClick={onClose} className="rounded-md p-1 text-neutral-500 hover:bg-neutral-700 hover:text-neutral-300">
            <Icon name="close" size={15} />
          </button>
        </div>

        <div className="space-y-3 px-5 py-4">
          {loading ? (
            <p className="text-xs text-neutral-500">Carregando...</p>
          ) : (
            <div className="overflow-hidden rounded-lg border border-neutral-700">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-neutral-700 bg-neutral-900/60 text-left text-neutral-400">
                    <th className="px-3 py-2 font-medium">Competência</th>
                    <th className="px-3 py-2 font-medium">Nota</th>
                    <th className="px-3 py-2 font-medium">Comentário</th>
                    <th className="px-3 py-2 font-medium text-right">Ações</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-800/70">
                  {competencias.map(c => (
                    <tr key={c.id} className="text-neutral-300">
                      <td className="px-3 py-2">{c.competencia}</td>
                      <td className="whitespace-nowrap px-3 py-2 font-medium text-indigo-300">{c.nota ?? "—"}</td>
                      <td className="px-3 py-2">{c.comentario || "—"}</td>
                      <td className="px-3 py-2">
                        <div className="flex justify-end gap-1">
                          <button onClick={() => abrirEdicao(c)} title="Editar" className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-indigo-500/10 hover:text-indigo-400">
                            <Icon name="pencil" size={13} />
                          </button>
                          <button onClick={() => setConfirmDelete(c.id)} title="Excluir" className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-red-500/10 hover:text-red-400">
                            <Icon name="trash" size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {competencias.length === 0 && (
                    <tr><td colSpan={4} className="px-3 py-6 text-center text-neutral-500">Nenhuma competência avaliada</td></tr>
                  )}
                </tbody>
                {competencias.length > 0 && (
                  <tfoot>
                    <tr className="border-t border-neutral-700 text-neutral-300">
                      <td className="px-3 py-2 text-right font-medium" colSpan={1}>Média</td>
                      <td className="px-3 py-2 font-semibold text-emerald-400">{mediaNotas.toFixed(1)}</td>
                      <td colSpan={2} />
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          )}

          {editId !== null ? (
            <div className="space-y-2 rounded-lg border border-indigo-700/50 bg-neutral-900/40 p-3">
              <div className="grid grid-cols-2 gap-2">
                <input placeholder="Competência (ex: Comunicação)" value={form.competencia} onChange={e => setForm({ ...form, competencia: e.target.value })}
                  className="col-span-2 rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
                <input type="number" step="0.1" min={0} max={10} placeholder="Nota (0-10)" value={form.nota} onChange={e => setForm({ ...form, nota: e.target.value })}
                  className="rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
                <input placeholder="Comentário" value={form.comentario} onChange={e => setForm({ ...form, comentario: e.target.value })}
                  className="rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div className="flex justify-end gap-2">
                <button onClick={() => { setEditId(null); setForm({ competencia: "", nota: "", comentario: "" }); }} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 transition-colors hover:text-neutral-200">Cancelar</button>
                <button onClick={handleSalvar} className="rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-500">Salvar</button>
              </div>
            </div>
          ) : (
            <button onClick={abrirNovo} className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-neutral-700 px-3 py-2 text-xs text-neutral-500 transition-colors hover:bg-neutral-800 hover:text-neutral-300">
              <span className="text-sm leading-none">+</span> Adicionar competência
            </button>
          )}
        </div>
      </div>

      {confirmDelete !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={() => setConfirmDelete(null)}>
          <div className="w-full max-w-[320px] rounded-xl border border-neutral-700 bg-neutral-800 p-5 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="mb-3 flex items-center gap-2 text-red-400">
              <Icon name="alert" size={17} />
              <h3 className="text-sm font-semibold text-neutral-100">Confirmar exclusão</h3>
            </div>
            <p className="mb-4 text-xs text-neutral-400">Excluir esta competência avaliada?</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmDelete(null)} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 transition-colors hover:text-neutral-200">Cancelar</button>
              <button onClick={() => handleDelete(confirmDelete)} className="rounded-lg bg-red-600 px-3.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-500">Excluir</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
