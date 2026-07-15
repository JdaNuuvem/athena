"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import StatusBadge from "@/app/_components/StatusBadge";
import LoadingState from "@/app/_components/LoadingState";

interface Loja { id: number; nome: string; ativa: boolean; bling_id?: number; bling_descricao?: string; }

export default function LojasPage() {
  const [lojas, setLojas] = useState<Loja[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [modal, setModal] = useState<{ open: boolean; nome: string; editId?: number }>({ open: false, nome: "" });

  const carregar = () => {
    api.lojasManage()
      .then(d => setLojas(d.lojas || []))
      .finally(() => setLoading(false));
  };

  useEffect(() => { carregar(); }, []);

  const salvar = async () => {
    const nome = modal.nome.trim();
    if (!nome) return;
    if (modal.editId) await api.lojasAtualizar(modal.editId, nome);
    else await api.lojasCriar(nome);
    setModal({ open: false, nome: "" });
    carregar();
  };

  const deletar = async (id: number) => {
    if (!confirm("Tem certeza que deseja excluir esta loja?")) return;
    await api.lojasDeletar(id);
    carregar();
  };

  const syncBling = async () => {
    setSyncing(true);
    try {
      const r = await fetch("/api/lojas/sync/bling", { method: "POST" }).then(r => r.json());
      if (r.error) alert(r.error);
      carregar();
    } catch (e) { alert(String(e)); }
    finally { setSyncing(false); }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-lg font-bold text-neutral-100">🏪 Lojas</h1>
          <p className="text-xs text-neutral-500 mt-1">Gerencie os ambientes e filiais do sistema</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={syncBling}
            disabled={syncing}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs px-3 py-1.5 rounded-lg"
          >
            {syncing ? "Sincronizando..." : "Sync Bling"}
          </button>
          <button
            onClick={() => setModal({ open: true, nome: "" })}
            className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg"
          >
            + Nova Loja
          </button>
        </div>
      </div>

      {loading ? <LoadingState /> : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {lojas.map(l => (
            <div key={l.id} className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-2">
              <div className="flex justify-between items-start">
                <h3 className="text-sm font-semibold text-neutral-200">{l.nome}</h3>
                <StatusBadge label={l.ativa ? "Ativa" : "Inativa"} variant={l.ativa ? "success" : "neutral"} />
              </div>
              <p className="text-[10px] text-neutral-600">ID: {l.id}{l.bling_id ? ` · Bling #${l.bling_id}` : ""}</p>
              <div className="flex gap-2">
                <button
                  onClick={() => setModal({ open: true, nome: l.nome, editId: l.id })}
                  className="text-xs text-indigo-400 hover:text-indigo-300"
                >Editar</button>
                <button
                  onClick={() => deletar(l.id)}
                  className="text-xs text-red-400 hover:text-red-300"
                >Excluir</button>
              </div>
            </div>
          ))}
          {lojas.length === 0 && <p className="text-xs text-neutral-500 col-span-full text-center py-8">Nenhuma loja cadastrada</p>}
        </div>
      )}

      {modal.open && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setModal({ open: false, nome: "" })}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-6 w-[350px]" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-4">{modal.editId ? "Editar Loja" : "Nova Loja"}</h3>
            <input
              type="text"
              value={modal.nome}
              onChange={e => setModal(p => ({ ...p, nome: e.target.value }))}
              placeholder="Nome da loja"
              className="w-full bg-neutral-700 border border-neutral-600 rounded px-3 py-2 text-xs text-neutral-200 mb-4 focus:outline-none focus:border-indigo-500"
              autoFocus
              onKeyDown={e => e.key === "Enter" && salvar()}
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setModal({ open: false, nome: "" })} className="text-xs px-3 py-1.5 rounded-lg text-neutral-400 hover:text-neutral-200">Cancelar</button>
              <button onClick={salvar} className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white">Salvar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
