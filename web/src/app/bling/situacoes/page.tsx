"use client";

import { useCallback, useEffect, useState } from "react";
import Icon from "@/app/_components/Icon";
import Spinner from "../_components/shared/Spinner";
import Alert from "../_components/shared/Alert";
import EmptyState from "../_components/shared/EmptyState";
import SyncToolbar from "../_components/shared/SyncToolbar";
import SituacaoFormModal from "../_components/SituacaoFormModal";
import {
  listarBlingSituacoes,
  criarBlingSituacao,
  atualizarBlingSituacao,
  deletarBlingSituacao,
  sincronizarBlingSituacoes,
} from "@/lib/api";
import type { BlingSituacao } from "@/lib/api";

export default function BlingSituacoesPage() {
  const [situacoes, setSituacoes] = useState<BlingSituacao[]>([]);
  const [loading, setLoading] = useState(true);
  const [sincronizando, setSincronizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [editando, setEditando] = useState<BlingSituacao | null>(null);
  const [criando, setCriando] = useState(false);

  const carregar = useCallback(async () => {
    setLoading(true);
    setErro(null);
    const r = await listarBlingSituacoes();
    if (r.error) setErro(r.error);
    setSituacoes(r.data);
    setLoading(false);
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar]);

  const handleSync = async () => {
    setSincronizando(true);
    setErro(null);
    setSucesso(null);
    const r = await sincronizarBlingSituacoes();
    if (r.error) setErro(r.error);
    else setSucesso(`${r.sync ?? 0} situações sincronizadas`);
    setSincronizando(false);
    carregar();
  };

  // PUT/DELETE /situacoes/<id> propagam a operacao pro Bling e limpam o cache
  // local por bling_id — entao o id da rota e' o do Bling, nao o local.
  const handleSalvar = async (dados: Partial<BlingSituacao>) => {
    setErro(null);
    setSucesso(null);
    const r = editando
      ? await atualizarBlingSituacao(editando.bling_id || editando.id, dados)
      : await criarBlingSituacao(dados);
    if (r.error) {
      setErro(r.error);
      return;
    }
    setSucesso(editando ? "Situação atualizada." : "Situação criada.");
    setEditando(null);
    setCriando(false);
    carregar();
  };

  const handleExcluir = async (s: BlingSituacao) => {
    if (!window.confirm(`Excluir a situação "${s.nome}"? Isso remove a situação no Bling também.`)) return;
    setErro(null);
    setSucesso(null);
    const r = await deletarBlingSituacao(s.bling_id || s.id);
    if (r.error) {
      setErro(r.error);
      return;
    }
    setSucesso("Situação excluída.");
    carregar();
  };

  if (loading && situacoes.length === 0) return <Spinner />;

  return (
    <div className="space-y-4">
      <Alert message={erro} type="error" />
      <Alert message={sucesso} type="success" />

      <SyncToolbar
        onSync={handleSync}
        sincronizando={sincronizando}
        total={situacoes.length}
        unidade="situações"
      >
        <button
          onClick={() => {
            setEditando(null);
            setCriando(true);
          }}
          className="px-3 py-1.5 bg-neutral-700 text-neutral-200 text-xs rounded-lg hover:bg-neutral-600 transition-colors"
        >
          + Nova
        </button>
      </SyncToolbar>

      {situacoes.length === 0 ? (
        <EmptyState
          icon="🏷️"
          title="Nenhuma situação"
          description="Sincronize as situações do Bling ou crie uma nova."
          action={{ label: "Sincronizar Agora", onClick: handleSync }}
        />
      ) : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="text-left p-3">Nome</th>
                <th className="text-left p-3 w-[120px]">Módulo</th>
                <th className="text-center p-3 w-[110px]">Cor</th>
                <th className="text-center p-3 w-[110px]">ID Bling</th>
                <th className="text-center p-3 w-[110px]">Ações</th>
              </tr>
            </thead>
            <tbody>
              {situacoes.map((s, i) => (
                <tr
                  key={s.id}
                  className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}
                >
                  <td className="p-3 text-neutral-200">{s.nome}</td>
                  <td className="p-3 text-neutral-400">{s.modulo || "—"}</td>
                  <td className="p-3 text-center">
                    {s.cor ? (
                      <span className="inline-flex items-center gap-1.5 text-[10px] text-neutral-400">
                        <span
                          className="w-3 h-3 rounded-sm border border-neutral-600"
                          style={{ backgroundColor: `#${s.cor.replace("#", "")}` }}
                        />
                        {s.cor}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="p-3 text-center text-neutral-500 font-mono text-[10px]">
                    {s.bling_id || "—"}
                  </td>
                  <td className="p-3">
                    <div className="flex items-center justify-center gap-1">
                      <button
                        onClick={() => {
                          setCriando(false);
                          setEditando(s);
                        }}
                        title="Editar"
                        className="p-1 text-neutral-400 hover:text-indigo-400 transition-colors"
                      >
                        <Icon name="pencil" size={14} />
                      </button>
                      <button
                        onClick={() => handleExcluir(s)}
                        title="Excluir"
                        className="p-1 text-neutral-400 hover:text-red-400 transition-colors"
                      >
                        <Icon name="trash" size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(criando || editando) && (
        <SituacaoFormModal
          situacao={editando}
          onClose={() => {
            setCriando(false);
            setEditando(null);
          }}
          onSalvar={handleSalvar}
        />
      )}
    </div>
  );
}
