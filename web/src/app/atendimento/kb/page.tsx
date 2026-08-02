"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { api } from "@/lib/api";
import { Can } from "@/lib/auth";
import Icon from "../../_components/Icon";

interface KBArtigo {
  id: number;
  titulo: string;
  categoria: string | null;
  conteudo: string | null;
  tags: string | null;
  visualizacoes: number;
  util_sim: number;
  util_nao: number;
  publicado: boolean;
}

const CAMPOS_FORM: { key: "titulo" | "categoria" | "tags"; label: string }[] = [
  { key: "titulo", label: "Título" },
  { key: "categoria", label: "Categoria" },
  { key: "tags", label: "Tags (separadas por vírgula)" },
];

export default function KBPage() {
  const [items, setItems] = useState<KBArtigo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busca, setBusca] = useState("");
  const [filtroStatus, setFiltroStatus] = useState<"todos" | "publicados" | "rascunhos">("todos");

  const [modal, setModal] = useState<{ open: boolean; mode: "create" | "edit"; row?: KBArtigo }>({ open: false, mode: "create" });
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  const [expandido, setExpandido] = useState<number | null>(null);
  const [votados, setVotados] = useState<Set<number>>(new Set());
  const [votando, setVotando] = useState<number | null>(null);

  const carregar = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.atendList("kb_artigos");
      setItems((res.data || []) as KBArtigo[]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  const abrirNovo = () => {
    setForm({ publicado: "true" });
    setSaveError("");
    setModal({ open: true, mode: "create" });
  };

  const abrirEdicao = (a: KBArtigo) => {
    setForm({
      titulo: a.titulo || "",
      categoria: a.categoria || "",
      tags: a.tags || "",
      conteudo: a.conteudo || "",
      publicado: a.publicado ? "true" : "false",
    });
    setSaveError("");
    setModal({ open: true, mode: "edit", row: a });
  };

  const fecharModal = () => {
    if (saving) return;
    setModal({ open: false, mode: "create" });
  };

  const salvar = async () => {
    if (!form.titulo?.trim()) { setSaveError("Título é obrigatório."); return; }
    setSaving(true);
    setSaveError("");
    const payload = {
      titulo: form.titulo.trim(),
      categoria: form.categoria?.trim() || "",
      tags: form.tags?.trim() || "",
      conteudo: form.conteudo || "",
      publicado: form.publicado !== "false",
    };
    try {
      if (modal.mode === "create") await api.atendCreate("kb_artigos", payload);
      else await api.atendUpdate("kb_artigos", Number(modal.row?.id), payload);
      setModal({ open: false, mode: "create" });
      await carregar();
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const excluir = async (id: number) => {
    try {
      await api.atendDelete("kb_artigos", id);
      setConfirmDelete(null);
      await carregar();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const alternarExpandido = useCallback((a: KBArtigo) => {
    const abrindo = expandido !== a.id;
    setExpandido(abrindo ? a.id : null);
    if (abrindo) {
      api.atendKbVisualizar(a.id).catch(() => {});
      setItems(prev => prev.map(it => it.id === a.id ? { ...it, visualizacoes: (it.visualizacoes || 0) + 1 } : it));
    }
  }, [expandido]);

  const votar = useCallback(async (id: number, util: boolean) => {
    if (votados.has(id) || votando === id) return;
    setVotando(id);
    try {
      await api.atendKbVotar(id, util);
      setVotados(prev => new Set(prev).add(id));
      setItems(prev => prev.map(it => it.id === id
        ? { ...it, util_sim: it.util_sim + (util ? 1 : 0), util_nao: it.util_nao + (util ? 0 : 1) }
        : it));
    } catch {
      // voto e' um sinal de baixo risco — falha silenciosa nao impede o uso do artigo
    } finally {
      setVotando(null);
    }
  }, [votados, votando]);

  const filtrados = useMemo(() => {
    return items.filter(a => {
      if (filtroStatus === "publicados" && !a.publicado) return false;
      if (filtroStatus === "rascunhos" && a.publicado) return false;
      if (!busca.trim()) return true;
      const q = busca.trim().toLowerCase();
      return [a.titulo, a.categoria, a.tags].some(v => String(v ?? "").toLowerCase().includes(q));
    });
  }, [items, busca, filtroStatus]);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-neutral-100">Base de Conhecimento</h1>
          <p className="text-xs text-neutral-500 mt-1">Artigos e documentação</p>
        </div>
        <Can permission="atendimento.criar">
          <button onClick={abrirNovo} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">+ Artigo</button>
        </Can>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[200px]">
          <Icon name="search" size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-500" />
          <input
            type="text"
            value={busca}
            onChange={e => setBusca(e.target.value)}
            placeholder="Buscar por título, categoria ou tags..."
            className="w-full bg-neutral-800 border border-neutral-700 rounded-lg pl-8 pr-3 py-2 text-sm text-neutral-200 placeholder-neutral-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
          />
        </div>
        <select value={filtroStatus} onChange={e => setFiltroStatus(e.target.value as typeof filtroStatus)}
          className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none">
          <option value="todos">Todos os status</option>
          <option value="publicados">Publicados</option>
          <option value="rascunhos">Rascunhos</option>
        </select>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-900/50 bg-red-950/30 px-4 py-3 text-xs text-red-400">
          <Icon name="alert" size={15} className="shrink-0" />
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-neutral-500 text-sm">Carregando...</p>
      ) : filtrados.length === 0 ? (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center">
          <p className="text-neutral-400 text-sm">{busca || filtroStatus !== "todos" ? "Nenhum artigo encontrado para esse filtro." : "Nenhum artigo cadastrado."}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {filtrados.map(a => {
            const aberto = expandido === a.id;
            const jaVotou = votados.has(a.id);
            return (
              <div key={a.id} className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="text-sm font-semibold text-neutral-200">{a.titulo}</h3>
                  <span className={`shrink-0 text-[10px] px-2 py-0.5 rounded ${a.publicado ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-500/20 text-amber-400"}`}>
                    {a.publicado ? "Publicado" : "Rascunho"}
                  </span>
                </div>
                <p className="text-[10px] text-neutral-500 mt-1">{a.categoria || "Sem categoria"} · {a.visualizacoes || 0} visualizações</p>
                <p className={"text-xs text-neutral-400 mt-2 " + (aberto ? "whitespace-pre-wrap" : "line-clamp-3")}>{a.conteudo || "—"}</p>
                {a.conteudo && a.conteudo.length > 160 && (
                  <button onClick={() => alternarExpandido(a)} className="text-[10px] text-indigo-400 hover:text-indigo-300 mt-1">
                    {aberto ? "Ver menos" : "Ver artigo completo"}
                  </button>
                )}
                <div className="flex items-center gap-2 mt-3">
                  {a.tags && <span className="text-[10px] bg-neutral-700 rounded px-2 py-0.5 text-neutral-400">{a.tags}</span>}
                  <div className="flex items-center gap-1 ml-auto">
                    <span className="text-[10px] text-neutral-500">Útil?</span>
                    <button onClick={() => votar(a.id, true)} disabled={jaVotou || votando === a.id} title="Útil"
                      className="rounded p-1 text-neutral-500 hover:text-emerald-400 hover:bg-emerald-500/10 disabled:opacity-40">
                      <Icon name="check" size={12} />
                    </button>
                    <span className="text-[10px] text-neutral-500">{a.util_sim || 0}</span>
                    <button onClick={() => votar(a.id, false)} disabled={jaVotou || votando === a.id} title="Não útil"
                      className="rounded p-1 text-neutral-500 hover:text-red-400 hover:bg-red-500/10 disabled:opacity-40">
                      <Icon name="close" size={12} />
                    </button>
                    <span className="text-[10px] text-neutral-500">{a.util_nao || 0}</span>
                  </div>
                  <Can permission="atendimento.editar">
                    <button onClick={() => abrirEdicao(a)} title="Editar" className="rounded p-1 text-neutral-500 hover:text-indigo-400 hover:bg-indigo-500/10">
                      <Icon name="pencil" size={12} />
                    </button>
                  </Can>
                  <Can permission="atendimento.excluir">
                    <button onClick={() => setConfirmDelete(a.id)} title="Excluir" className="rounded p-1 text-neutral-500 hover:text-red-400 hover:bg-red-500/10">
                      <Icon name="trash" size={12} />
                    </button>
                  </Can>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {modal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={fecharModal}>
          <div className="w-full max-w-[480px] max-h-[85vh] overflow-y-auto rounded-xl border border-neutral-700 bg-neutral-800 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-neutral-700/70 px-5 py-4">
              <h3 className="text-sm font-semibold text-neutral-100">{modal.mode === "create" ? "Novo artigo" : "Editar artigo"}</h3>
              <button onClick={fecharModal} className="rounded-md p-1 text-neutral-500 hover:bg-neutral-700 hover:text-neutral-300">
                <Icon name="close" size={15} />
              </button>
            </div>
            <div className="space-y-3 px-5 py-4">
              {CAMPOS_FORM.map(f => (
                <div key={f.key}>
                  <label className="mb-1 block text-[11px] font-medium text-neutral-400">{f.label}</label>
                  <input type="text" value={form[f.key] || ""} onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                    className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
                </div>
              ))}
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Conteúdo</label>
                <textarea value={form.conteudo || ""} onChange={e => setForm(prev => ({ ...prev, conteudo: e.target.value }))} rows={6}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <label className="flex items-center gap-2 text-xs text-neutral-300">
                <input type="checkbox" checked={form.publicado !== "false"} onChange={e => setForm(prev => ({ ...prev, publicado: e.target.checked ? "true" : "false" }))} />
                Publicado (visível para a equipe)
              </label>
              {saveError && (
                <div className="text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2">{saveError}</div>
              )}
            </div>
            <div className="flex justify-end gap-2 border-t border-neutral-700/70 px-5 py-4">
              <button onClick={fecharModal} disabled={saving} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 hover:text-neutral-200 disabled:opacity-50">Cancelar</button>
              <button onClick={salvar} disabled={saving} className="rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
                {saving ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}

      {confirmDelete !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setConfirmDelete(null)}>
          <div className="w-full max-w-[340px] rounded-xl border border-neutral-700 bg-neutral-800 p-5 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="mb-3 flex items-center gap-2 text-red-400">
              <Icon name="alert" size={17} />
              <h3 className="text-sm font-semibold text-neutral-100">Confirmar exclusão</h3>
            </div>
            <p className="mb-4 text-xs text-neutral-400">Tem certeza que deseja excluir este artigo? Essa ação não pode ser desfeita.</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmDelete(null)} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 hover:text-neutral-200">Cancelar</button>
              <button onClick={() => excluir(confirmDelete)} className="rounded-lg bg-red-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-red-500">Excluir</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
