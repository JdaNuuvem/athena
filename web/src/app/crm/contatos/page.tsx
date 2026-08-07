"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { Can } from "@/lib/auth";
import Icon from "@/app/_components/Icon";
import PageHeader from "@/app/_components/PageHeader";
import { fmtBRL, fmtDataBR } from "@/lib/format";

interface Cliente {
  id: number;
  nome: string;
  tipo: string;
  documento: string | null;
  email: string | null;
  telefone: string | null;
  status: string;
  whatsapp: boolean;
  data_nascimento: string | null;
  ultima_compra: string | null;
  total_gasto: number;
  qtd_pedidos: number;
  tags: string[];
}

type Sort = "id" | "nome" | "ultima_compra" | "total_gasto";
type Order = "asc" | "desc";

function extrairErro(res: unknown): string | null {
  if (res && typeof res === "object" && "error" in res && (res as { error?: unknown }).error) {
    return String((res as { error: unknown }).error);
  }
  return null;
}

function janelaPaginas(atual: number, total: number): number[] {
  const inicio = Math.max(1, Math.min(atual - 2, total - 4));
  const fim = Math.min(total, inicio + 4);
  const janela: number[] = [];
  for (let i = Math.max(1, inicio); i <= fim; i++) janela.push(i);
  return janela;
}

export default function Page() {
  const [items, setItems] = useState<Cliente[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busca, setBusca] = useState("");
  const [buscaAtiva, setBuscaAtiva] = useState("");
  const [pagina, setPagina] = useState(1);
  const [porPagina, setPorPagina] = useState(20);
  const [total, setTotal] = useState(0);
  const [totalPaginas, setTotalPaginas] = useState(1);

  const [sort, setSort] = useState<Sort>("id");
  const [order, setOrder] = useState<Order>("desc");
  const [filtroStatus, setFiltroStatus] = useState("");
  const [filtroTag, setFiltroTag] = useState("");
  const [filtroWhatsapp, setFiltroWhatsapp] = useState("");
  const [filtroSemComprarDias, setFiltroSemComprarDias] = useState("");
  const [tagsDisponiveis, setTagsDisponiveis] = useState<string[]>([]);

  const [modal, setModal] = useState<{ open: boolean; mode: "create" | "edit"; row?: Cliente }>({ open: false, mode: "create" });
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  const [statusAlvo, setStatusAlvo] = useState<Cliente | null>(null);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  useEffect(() => {
    api.cadClientesTagsDisponiveis().then(r => setTagsDisponiveis(r.data || [])).catch(() => {});
  }, []);

  const filtrosAtivos = !!(filtroStatus || filtroTag || filtroWhatsapp || filtroSemComprarDias);

  const carregar = useCallback(async (paginaAlvo: number, buscaAlvo: string) => {
    setLoading(true);
    setError("");
    try {
      const filtros: Record<string, string> = { sort, order };
      if (filtroStatus) filtros.status = filtroStatus;
      if (filtroTag) filtros.tag = filtroTag;
      if (filtroWhatsapp) filtros.whatsapp = filtroWhatsapp;
      if (filtroSemComprarDias) filtros.sem_comprar_dias = filtroSemComprarDias;
      const res = await api.cadListPaginado("clientes", paginaAlvo, porPagina, buscaAlvo || undefined, filtros);
      setItems((res.data || []) as Cliente[]);
      setTotal(res.total ?? 0);
      setTotalPaginas(res.total_paginas ?? 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [sort, order, filtroStatus, filtroTag, filtroWhatsapp, filtroSemComprarDias, porPagina]);

  useEffect(() => { carregar(pagina, buscaAtiva); }, [carregar, pagina, buscaAtiva]);

  // debounce: espera parar de digitar antes de disparar a busca no servidor,
  // e volta pra pagina 1 (uma busca nova pode ter menos paginas que a atual).
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setPagina(1);
      setBuscaAtiva(busca.trim());
    }, 350);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [busca]);

  const alternarSort = (coluna: Sort) => {
    if (sort === coluna) {
      setOrder(o => (o === "asc" ? "desc" : "asc"));
    } else {
      setSort(coluna);
      setOrder("desc");
    }
    setPagina(1);
  };

  const limparFiltros = () => {
    setFiltroStatus("");
    setFiltroTag("");
    setFiltroWhatsapp("");
    setFiltroSemComprarDias("");
    setPagina(1);
  };

  const abrirNovo = () => {
    setForm({ tipo: "PF" });
    setSaveError("");
    setModal({ open: true, mode: "create" });
  };

  const abrirEdicao = (row: Cliente) => {
    setForm({
      nome: row.nome || "",
      tipo: row.tipo || "PF",
      documento: row.documento || "",
      email: row.email || "",
      telefone: row.telefone || "",
      whatsapp: row.whatsapp ? "true" : "false",
      data_nascimento: row.data_nascimento || "",
    });
    setSaveError("");
    setModal({ open: true, mode: "edit", row });
  };

  const fecharModal = () => {
    if (saving) return;
    setModal({ open: false, mode: "create" });
  };

  const salvar = async () => {
    if (!form.nome?.trim()) {
      setSaveError("Nome e obrigatorio.");
      return;
    }
    setSaving(true);
    setSaveError("");
    const payload = {
      nome: form.nome.trim(),
      tipo: form.tipo || "PF",
      documento: form.documento?.trim() || "",
      email: form.email?.trim() || "",
      telefone: form.telefone?.trim() || "",
      whatsapp: form.whatsapp === "true",
      data_nascimento: form.data_nascimento || null,
    };
    try {
      const res = modal.mode === "create"
        ? await api.cadCreate("clientes", payload)
        : await api.cadUpdate("clientes", Number(modal.row?.id), payload);
      const erro = extrairErro(res);
      if (erro) { setSaveError(erro); return; }
      setModal({ open: false, mode: "create" });
      await carregar(modal.mode === "create" ? 1 : pagina, buscaAtiva);
      if (modal.mode === "create") setPagina(1);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const alternarStatus = async (row: Cliente) => {
    const novoStatus = row.status === "ativo" ? "inativo" : "ativo";
    setTogglingId(row.id);
    try {
      const res = await api.cadUpdate("clientes", row.id, { status: novoStatus });
      const erro = extrairErro(res);
      if (erro) { setError(erro); return; }
      setStatusAlvo(null);
      await carregar(pagina, buscaAtiva);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setTogglingId(null);
    }
  };

  const inicioItem = total === 0 ? 0 : (pagina - 1) * porPagina + 1;
  const fimItem = Math.min(pagina * porPagina, total);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <PageHeader title="Contatos" subtitle="Agenda de clientes e contatos comerciais" />
        <Can permission="cadastros.criar">
          <button onClick={abrirNovo} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">+ Novo</button>
        </Can>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <div className="relative w-full max-w-xs">
          <Icon name="search" size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-500" />
          <input
            type="text"
            placeholder="Buscar por nome, documento, email ou telefone..."
            value={busca}
            onChange={e => setBusca(e.target.value)}
            className="w-full rounded-lg border border-neutral-700 bg-neutral-800 py-1.5 pl-8 pr-3 text-xs text-neutral-200 placeholder-neutral-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
          />
        </div>

        <select value={filtroStatus} onChange={e => { setFiltroStatus(e.target.value); setPagina(1); }}
          className="rounded-lg border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none">
          <option value="">Status: todos</option>
          <option value="ativo">Ativo</option>
          <option value="inativo">Inativo</option>
        </select>

        <select value={filtroTag} onChange={e => { setFiltroTag(e.target.value); setPagina(1); }}
          className="rounded-lg border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none">
          <option value="">Tag: todas</option>
          {tagsDisponiveis.map(t => <option key={t} value={t}>{t}</option>)}
        </select>

        <select value={filtroWhatsapp} onChange={e => { setFiltroWhatsapp(e.target.value); setPagina(1); }}
          className="rounded-lg border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none">
          <option value="">WhatsApp: qualquer</option>
          <option value="true">Com WhatsApp</option>
          <option value="false">Sem WhatsApp</option>
        </select>

        <select value={filtroSemComprarDias} onChange={e => { setFiltroSemComprarDias(e.target.value); setPagina(1); }}
          className="rounded-lg border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none">
          <option value="">Última compra: qualquer</option>
          <option value="30">Sem comprar há 30+ dias</option>
          <option value="60">Sem comprar há 60+ dias</option>
          <option value="90">Sem comprar há 90+ dias</option>
          <option value="180">Sem comprar há 180+ dias</option>
        </select>

        {filtrosAtivos && (
          <button onClick={limparFiltros} className="text-xs text-neutral-500 hover:text-neutral-300 px-2 py-1.5">
            Limpar filtros
          </button>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-900/50 bg-red-950/30 px-4 py-3 text-xs text-red-400">
          <Icon name="alert" size={15} className="shrink-0" />
          {error}
        </div>
      )}

      {loading ? (
        <div className="overflow-hidden rounded-lg border border-neutral-800">
          <div className="divide-y divide-neutral-800/70">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex gap-4 px-4 py-3">
                {Array.from({ length: 6 }).map((_, j) => <div key={j} className="h-3 flex-1 animate-pulse rounded bg-neutral-800" />)}
              </div>
            ))}
          </div>
        </div>
      ) : items.length === 0 ? (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center">
          <p className="text-neutral-400 text-sm">{buscaAtiva || filtrosAtivos ? "Nenhum contato encontrado para esse filtro." : "Nenhum contato cadastrado."}</p>
        </div>
      ) : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="text-left p-3 cursor-pointer select-none hover:text-neutral-200" onClick={() => alternarSort("nome")}>
                  Nome
                  {sort === "nome" && (
                    <Icon name="chevronDown" size={11} className={"inline ml-0.5" + (order === "asc" ? " rotate-180" : "")} />
                  )}
                </th>
                <th className="text-left p-3">Contato</th>
                <th className="text-left p-3">Tags</th>
                <th className="text-left p-3 cursor-pointer select-none hover:text-neutral-200" onClick={() => alternarSort("ultima_compra")}>
                  Última compra
                  {sort === "ultima_compra" && (
                    <Icon name="chevronDown" size={11} className={"inline ml-0.5" + (order === "asc" ? " rotate-180" : "")} />
                  )}
                </th>
                <th className="text-right p-3 cursor-pointer select-none hover:text-neutral-200" onClick={() => alternarSort("total_gasto")}>
                  Total gasto
                  {sort === "total_gasto" && (
                    <Icon name="chevronDown" size={11} className={"inline ml-0.5" + (order === "asc" ? " rotate-180" : "")} />
                  )}
                </th>
                <th className="text-left p-3">Status</th>
                <th className="text-right p-3">Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, i) => (
                <tr key={item.id} className={"border-b border-neutral-700/50 " + (i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50")}>
                  <td className="p-3 text-neutral-300">{item.nome}</td>
                  <td className="p-3 text-neutral-300">
                    <div>{item.email || "—"}</div>
                    <div className="flex items-center gap-1.5 text-neutral-500">
                      <span>{item.telefone || "—"}</span>
                      {item.whatsapp && (
                        <span className="px-1 py-0.5 rounded text-[9px] font-semibold bg-emerald-500/20 text-emerald-400">WA</span>
                      )}
                    </div>
                  </td>
                  <td className="p-3">
                    <div className="flex flex-wrap gap-1">
                      {item.tags.slice(0, 3).map(t => (
                        <span key={t} className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-indigo-500/20 text-indigo-400">{t}</span>
                      ))}
                      {item.tags.length > 3 && <span className="text-[10px] text-neutral-500">+{item.tags.length - 3}</span>}
                      {item.tags.length === 0 && <span className="text-neutral-600">—</span>}
                    </div>
                  </td>
                  <td className="p-3 text-neutral-300">{fmtDataBR(item.ultima_compra)}</td>
                  <td className="p-3 text-right text-neutral-300">{fmtBRL(item.total_gasto)}</td>
                  <td className="p-3">
                    <span className={"px-2 py-0.5 rounded text-[10px] font-medium " + (item.status === "ativo" ? "bg-emerald-500/20 text-emerald-400" : "bg-neutral-500/20 text-neutral-400")}>
                      {item.status === "ativo" ? "Ativo" : "Inativo"}
                    </span>
                  </td>
                  <td className="p-3">
                    <div className="flex justify-end gap-1">
                      <Can permission="cadastros.editar">
                        <button onClick={() => abrirEdicao(item)} title="Editar" className="rounded-md p-1.5 text-neutral-500 hover:bg-indigo-500/10 hover:text-indigo-400">
                          <Icon name="pencil" size={13} />
                        </button>
                      </Can>
                      <Can permission="cadastros.excluir">
                        <button
                          onClick={() => (item.status === "ativo" ? setStatusAlvo(item) : alternarStatus(item))}
                          disabled={togglingId === item.id}
                          title={item.status === "ativo" ? "Desativar" : "Reativar"}
                          className={"rounded-md p-1.5 disabled:opacity-50 " + (item.status === "ativo" ? "text-neutral-500 hover:bg-red-500/10 hover:text-red-400" : "text-neutral-500 hover:bg-emerald-500/10 hover:text-emerald-400")}
                        >
                          <Icon name="power" size={13} />
                        </button>
                      </Can>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-neutral-500">
          <span>Mostrando {inicioItem}–{fimItem} de {total}</span>
          <div className="flex items-center gap-2">
            <select value={porPagina} onChange={e => { setPorPagina(Number(e.target.value)); setPagina(1); }}
              className="rounded-lg border border-neutral-700 bg-neutral-800 px-2 py-1 text-neutral-300 focus:border-indigo-500 focus:outline-none">
              <option value={20}>20 / página</option>
              <option value={50}>50 / página</option>
              <option value={100}>100 / página</option>
            </select>
            <div className="flex gap-1">
              <button onClick={() => setPagina(1)} disabled={pagina <= 1}
                className="rounded-lg border border-neutral-700 px-2.5 py-1 text-neutral-300 hover:bg-neutral-800 disabled:opacity-40 disabled:hover:bg-transparent">
                «
              </button>
              <button onClick={() => setPagina(p => Math.max(1, p - 1))} disabled={pagina <= 1}
                className="rounded-lg border border-neutral-700 px-2.5 py-1 text-neutral-300 hover:bg-neutral-800 disabled:opacity-40 disabled:hover:bg-transparent">
                ‹
              </button>
              {janelaPaginas(pagina, totalPaginas).map(n => (
                <button key={n} onClick={() => setPagina(n)}
                  className={"rounded-lg border px-2.5 py-1 " + (n === pagina ? "border-indigo-500 bg-indigo-500/20 text-indigo-400" : "border-neutral-700 text-neutral-300 hover:bg-neutral-800")}>
                  {n}
                </button>
              ))}
              <button onClick={() => setPagina(p => Math.min(totalPaginas, p + 1))} disabled={pagina >= totalPaginas}
                className="rounded-lg border border-neutral-700 px-2.5 py-1 text-neutral-300 hover:bg-neutral-800 disabled:opacity-40 disabled:hover:bg-transparent">
                ›
              </button>
              <button onClick={() => setPagina(totalPaginas)} disabled={pagina >= totalPaginas}
                className="rounded-lg border border-neutral-700 px-2.5 py-1 text-neutral-300 hover:bg-neutral-800 disabled:opacity-40 disabled:hover:bg-transparent">
                »
              </button>
            </div>
          </div>
        </div>
      )}

      {modal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={fecharModal}>
          <div className="w-full max-w-[440px] rounded-xl border border-neutral-700 bg-neutral-800 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-neutral-700/70 px-5 py-4">
              <h3 className="text-sm font-semibold text-neutral-100">{modal.mode === "create" ? "Novo contato" : "Editar contato"}</h3>
              <button onClick={fecharModal} className="rounded-md p-1 text-neutral-500 hover:bg-neutral-700 hover:text-neutral-300">
                <Icon name="close" size={15} />
              </button>
            </div>
            <div className="grid grid-cols-2 gap-3 px-5 py-4">
              <div className="col-span-2">
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Nome *</label>
                <input type="text" value={form.nome || ""} onChange={e => setForm({ ...form, nome: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Tipo</label>
                <select value={form.tipo || "PF"} onChange={e => setForm({ ...form, tipo: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
                  <option value="PF">Pessoa Fisica (PF)</option>
                  <option value="PJ">Pessoa Juridica (PJ)</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Documento</label>
                <input type="text" placeholder={form.tipo === "PJ" ? "CNPJ" : "CPF"} value={form.documento || ""} onChange={e => setForm({ ...form, documento: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Email</label>
                <input type="email" value={form.email || ""} onChange={e => setForm({ ...form, email: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Telefone</label>
                <input type="text" value={form.telefone || ""} onChange={e => setForm({ ...form, telefone: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              <div className="flex items-center gap-2 pt-5">
                <input type="checkbox" id="whatsapp" checked={form.whatsapp === "true"} onChange={e => setForm({ ...form, whatsapp: e.target.checked ? "true" : "false" })}
                  className="rounded border-neutral-600 bg-neutral-700 text-indigo-500 focus:ring-indigo-500/50" />
                <label htmlFor="whatsapp" className="text-[11px] font-medium text-neutral-400">Telefone tem WhatsApp</label>
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">Data de nascimento</label>
                <input type="date" value={form.data_nascimento || ""} onChange={e => setForm({ ...form, data_nascimento: e.target.value })}
                  className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50" />
              </div>
              {saveError && (
                <div className="col-span-2 text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2">{saveError}</div>
              )}
            </div>
            <div className="flex justify-end gap-2 border-t border-neutral-700/70 px-5 py-4">
              <button onClick={fecharModal} disabled={saving} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 hover:text-neutral-200 disabled:opacity-50">Cancelar</button>
              <button onClick={salvar} disabled={saving} className="rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50">
                {saving ? "Salvando..." : "Salvar"}
              </button>
            </div>
          </div>
        </div>
      )}

      {statusAlvo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setStatusAlvo(null)}>
          <div className="w-full max-w-[360px] rounded-xl border border-neutral-700 bg-neutral-800 p-5 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="mb-3 flex items-center gap-2 text-amber-400">
              <Icon name="alert" size={17} />
              <h3 className="text-sm font-semibold text-neutral-100">Desativar contato</h3>
            </div>
            <p className="mb-4 text-xs text-neutral-400">
              &quot;{statusAlvo.nome}&quot; ficara marcado como inativo. O registro nao e apagado e pode ser reativado a qualquer momento.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setStatusAlvo(null)} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 hover:text-neutral-200">Cancelar</button>
              <button
                onClick={() => alternarStatus(statusAlvo)}
                disabled={togglingId === statusAlvo.id}
                className="rounded-lg bg-red-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-red-500 disabled:opacity-50"
              >
                {togglingId === statusAlvo.id ? "Aguarde..." : "Desativar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
