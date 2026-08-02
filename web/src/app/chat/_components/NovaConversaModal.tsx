"use client";
import { useState, useEffect, useMemo } from "react";
import type { ConversaChat } from "@/lib/types/chat";
import { api } from "@/lib/api";

interface UsuarioResumo { id: number; nome: string; }

export default function NovaConversaModal({
  onFechar, onCriada,
}: {
  onFechar: () => void;
  onCriada: (conversa: ConversaChat) => void;
}) {
  const [aba, setAba] = useState<"dm" | "grupo">("dm");
  const [usuarios, setUsuarios] = useState<UsuarioResumo[]>([]);
  const [busca, setBusca] = useState("");
  const [selecionados, setSelecionados] = useState<number[]>([]);
  const [nomeGrupo, setNomeGrupo] = useState("");
  const [descricaoGrupo, setDescricaoGrupo] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api.chat.listarUsuarios().then((r) => setUsuarios(r.data)).catch(() => setUsuarios([]));
  }, []);

  const filtrados = useMemo(() => {
    const q = busca.trim().toLowerCase();
    if (!q) return usuarios;
    return usuarios.filter((u) => u.nome.toLowerCase().includes(q));
  }, [usuarios, busca]);

  const alternarSelecao = (id: number) => {
    if (aba === "dm") { setSelecionados([id]); return; }
    setSelecionados((atual) => (atual.includes(id) ? atual.filter((x) => x !== id) : [...atual, id]));
  };

  const criar = async () => {
    setErro("");
    if (aba === "dm") {
      if (selecionados.length !== 1) { setErro("Escolha uma pessoa para conversar."); return; }
      setSalvando(true);
      try {
        const conversa = await api.chat.criarConversaDm(selecionados[0]);
        onCriada(conversa);
      } catch (e) {
        setErro(e instanceof Error ? e.message : "Erro ao criar conversa");
      } finally {
        setSalvando(false);
      }
      return;
    }
    if (!nomeGrupo.trim()) { setErro("Dê um nome ao grupo."); return; }
    if (selecionados.length === 0) { setErro("Escolha ao menos um participante."); return; }
    setSalvando(true);
    try {
      const conversa = await api.chat.criarConversaGrupo(nomeGrupo.trim(), descricaoGrupo.trim(), selecionados);
      onCriada(conversa);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao criar grupo");
    } finally {
      setSalvando(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={onFechar}>
      <div className="w-full max-w-[420px] max-h-[85vh] overflow-y-auto rounded-xl border border-neutral-700 bg-neutral-800 shadow-xl flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-neutral-700/70 px-5 py-4 shrink-0">
          <h3 className="text-sm font-semibold text-neutral-100">Nova conversa</h3>
          <button onClick={onFechar} className="text-neutral-500 hover:text-neutral-300 text-sm">✕</button>
        </div>

        <div className="flex gap-1 px-5 pt-3 shrink-0">
          <button
            onClick={() => { setAba("dm"); setSelecionados([]); setErro(""); }}
            className={`px-3 py-1.5 text-xs rounded-lg ${aba === "dm" ? "bg-indigo-600 text-white" : "text-neutral-400 hover:bg-neutral-700"}`}
          >
            Mensagem direta
          </button>
          <button
            onClick={() => { setAba("grupo"); setSelecionados([]); setErro(""); }}
            className={`px-3 py-1.5 text-xs rounded-lg ${aba === "grupo" ? "bg-indigo-600 text-white" : "text-neutral-400 hover:bg-neutral-700"}`}
          >
            Grupo
          </button>
        </div>

        <div className="px-5 py-4 space-y-3">
          {aba === "grupo" && (
            <>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Nome do grupo</label>
                <input type="text" value={nomeGrupo} onChange={(e) => setNomeGrupo(e.target.value)}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Descrição (opcional)</label>
                <input type="text" value={descricaoGrupo} onChange={(e) => setDescricaoGrupo(e.target.value)}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none" />
              </div>
            </>
          )}

          <div>
            <label className="mb-1 block text-[11px] font-medium text-neutral-400">
              {aba === "dm" ? "Com quem você quer conversar?" : "Participantes"}
            </label>
            <input type="text" value={busca} onChange={(e) => setBusca(e.target.value)}
              placeholder="Buscar por nome..."
              className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none mb-2" />
            <div className="max-h-48 overflow-y-auto rounded-lg border border-neutral-700 divide-y divide-neutral-700/70">
              {filtrados.length === 0 && (
                <p className="px-3 py-3 text-xs text-neutral-500 text-center">Nenhum usuário encontrado</p>
              )}
              {filtrados.map((u) => {
                const marcado = selecionados.includes(u.id);
                return (
                  <button
                    key={u.id} type="button" onClick={() => alternarSelecao(u.id)}
                    className={`w-full text-left px-3 py-2 text-xs flex items-center justify-between ${marcado ? "bg-indigo-600/20 text-indigo-300" : "text-neutral-300 hover:bg-neutral-700/50"}`}
                  >
                    {u.nome}
                    {marcado && <span className="text-indigo-400">✓</span>}
                  </button>
                );
              })}
            </div>
          </div>

          {erro && (
            <div className="text-xs px-3 py-2 rounded-lg border bg-red-950/40 border-red-900/50 text-red-400">{erro}</div>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-neutral-700/70 px-5 py-4 shrink-0">
          <button onClick={onFechar} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 hover:text-neutral-200">Cancelar</button>
          <button onClick={criar} disabled={salvando}
            className="rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
            {salvando ? "Criando..." : "Criar"}
          </button>
        </div>
      </div>
    </div>
  );
}
