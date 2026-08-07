"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type LeadFiltro } from "@/lib/api";
import { fmtBRL } from "@/lib/format";
import { Can } from "@/lib/auth";
import Icon from "../../../_components/Icon";
import CrudFormModal, { type FieldDef } from "../../../_components/CrudFormModal";

const ETAPAS_FUNIL = ["captacao", "qualificacao", "prospeccao", "proposta", "negociacao", "fechamento"];

const STATUS_CORES: Record<string, string> = {
  novo: "bg-indigo-500/20 text-indigo-400",
  contatado: "bg-amber-500/20 text-amber-400",
  qualificado: "bg-sky-500/20 text-sky-400",
  convertido: "bg-emerald-500/20 text-emerald-400",
  perdido: "bg-red-500/20 text-red-400",
};

const PAGE_SIZES = [25, 50, 100] as const;
type SortField = "id" | "valor_potencial" | "status" | "funil_etapa";

const LEADS_COLUNAS_EXPORT = ["id", "nome", "email", "telefone", "empresa_id", "origem", "funil_etapa", "valor_potencial", "status", "observacoes"];

function normalizarPayloadLead(data: Record<string, unknown>) {
  const bruto = data.empresa_id;
  const empresa_id = bruto === "" || bruto == null ? null : Number(bruto);
  return { ...data, empresa_id };
}

function csvEscape(v: unknown): string {
  const s = String(v ?? "");
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

export default function LeadsPanel() {
  const [empresas, setEmpresas] = useState<{ id: number; nome: string }[]>([]);
  const [data, setData] = useState<Record<string, unknown>[]>([]);
  const [meta, setMeta] = useState({ total: 0, page: 1, page_size: 25, pages: 1 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<25 | 50 | 100>(25);
  const [sort, setSort] = useState<SortField>("id");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [status, setStatus] = useState("");
  const [funilEtapa, setFunilEtapa] = useState("");
  const [empresaId, setEmpresaId] = useState("");
  const [origem, setOrigem] = useState("");
  const [origemDebounced, setOrigemDebounced] = useState("");
  const [comTelefone, setComTelefone] = useState<"" | "true" | "false">("");
  const [busca, setBusca] = useState("");
  const [buscaDebounced, setBuscaDebounced] = useState("");

  const [modal, setModal] = useState<{ open: boolean; mode: "create" | "edit"; row?: Record<string, unknown> }>({ open: false, mode: "create" });
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
  const [exportando, setExportando] = useState(false);

  useEffect(() => {
    api.crmList("empresas")
      .then(res => setEmpresas((res.data || []) as { id: number; nome: string }[]))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const t = setTimeout(() => setBuscaDebounced(busca), 300);
    return () => clearTimeout(t);
  }, [busca]);

  useEffect(() => {
    const t = setTimeout(() => setOrigemDebounced(origem), 300);
    return () => clearTimeout(t);
  }, [origem]);

  useEffect(() => {
    setPage(1);
  }, [status, funilEtapa, empresaId, comTelefone, buscaDebounced, origemDebounced, pageSize]);

  const filtro = useMemo<LeadFiltro>(() => ({
    page, pageSize, sort, order,
    status: status || undefined,
    funilEtapa: funilEtapa || undefined,
    origem: origemDebounced || undefined,
    empresaId: empresaId ? Number(empresaId) : undefined,
    comTelefone: comTelefone === "" ? undefined : comTelefone === "true",
    q: buscaDebounced || undefined,
  }), [page, pageSize, sort, order, status, funilEtapa, origemDebounced, empresaId, comTelefone, buscaDebounced]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.crmLeadsListar(filtro);
      setData(res.data || []);
      setMeta(res.meta || { total: 0, page: 1, page_size: pageSize, pages: 1 });
    } catch (e) { setError(String(e)); }
    finally { setLoading(false); }
  }, [filtro, pageSize]);

  useEffect(() => { fetchData(); }, [fetchData, reloadKey]);

  const empresaOptions = useMemo(() => empresas.map(e => ({ label: e.nome, value: String(e.id) })), [empresas]);
  const empresaNomePorId = useMemo(() => Object.fromEntries(empresas.map(e => [String(e.id), e.nome])), [empresas]);

  const leadsFields = useMemo<FieldDef[]>(() => [
    { key: "nome", label: "Nome" },
    { key: "empresa_id", label: "Empresa", type: "select", options: empresaOptions },
    { key: "email", label: "E-mail" },
    { key: "telefone", label: "Telefone" },
    { key: "origem", label: "Origem" },
    { key: "funil_etapa", label: "Etapa do funil", type: "select", options: ETAPAS_FUNIL.map(e => ({ label: e.replace(/_/g, " "), value: e })) },
    { key: "valor_potencial", label: "Valor potencial (R$)", type: "number", step: "0.01" },
    { key: "status", label: "Status", type: "select", options: Object.keys(STATUS_CORES).map(s => ({ label: s, value: s })) },
    { key: "observacoes", label: "Observações" },
  ], [empresaOptions]);

  const temFiltroAtivo = !!(status || funilEtapa || empresaId || origem || comTelefone || busca);
  const limparFiltros = () => {
    setStatus(""); setFunilEtapa(""); setEmpresaId(""); setOrigem(""); setComTelefone(""); setBusca("");
  };

  const openCreate = () => { setFormData({}); setModal({ open: true, mode: "create" }); };

  const openEdit = (row: Record<string, unknown>) => {
    const fd: Record<string, string> = {};
    for (const f of leadsFields) fd[f.key] = String(row[f.key] ?? "");
    setFormData(fd);
    setModal({ open: true, mode: "edit", row });
  };

  const handleSave = async () => {
    const payload: Record<string, unknown> = {};
    for (const f of leadsFields) {
      const val = formData[f.key] ?? "";
      payload[f.key] = f.type === "number" ? (parseFloat(val) || 0) : val;
    }
    const normalizado = normalizarPayloadLead(payload);
    try {
      if (modal.mode === "create") await api.crmCreate("leads", normalizado);
      else await api.crmUpdate("leads", Number(modal.row?.id), normalizado);
      setModal({ open: false, mode: "create" });
      setReloadKey(k => k + 1);
    } catch (e) { alert(String(e)); }
  };

  const handleDelete = async (id: number) => {
    try { await api.crmDelete("leads", id); setConfirmDelete(null); setReloadKey(k => k + 1); }
    catch (e) { alert(String(e)); }
  };

  const toggleSort = (field: SortField) => {
    if (sort === field) setOrder(o => (o === "asc" ? "desc" : "asc"));
    else { setSort(field); setOrder("desc"); }
    setPage(1);
  };

  const handleExportar = async () => {
    setExportando(true);
    try {
      const res = await api.crmLeadsExportar(filtro);
      const linhas = res.data || [];
      const header = LEADS_COLUNAS_EXPORT.join(",");
      const body = linhas.map(row => LEADS_COLUNAS_EXPORT.map(c => {
        if (c === "empresa_id") return csvEscape(row[c] ? (empresaNomePorId[String(row[c])] || row[c]) : "");
        return csvEscape(row[c]);
      }).join(",")).join("\n");
      const csv = `${header}\n${body}`;
      const blob = new Blob([`﻿${csv}`], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `leads_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) { alert(String(e)); }
    finally { setExportando(false); }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {!loading && !error && (
            <span className="rounded-full bg-neutral-800 px-2 py-0.5 text-[10px] font-medium text-neutral-400">
              {meta.total} lead{meta.total === 1 ? "" : "s"}
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Icon name="search" size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-500" />
            <input
              type="text"
              placeholder="Buscar nome, e-mail, telefone..."
              value={busca}
              onChange={e => setBusca(e.target.value)}
              className="w-52 rounded-lg border border-neutral-700 bg-neutral-800 py-1.5 pl-8 pr-3 text-xs text-neutral-200 placeholder-neutral-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
            />
          </div>
          <button
            onClick={handleExportar}
            disabled={exportando}
            className="flex items-center gap-1.5 rounded-lg border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs font-medium text-neutral-300 transition-colors hover:bg-neutral-700 disabled:opacity-50"
          >
            <Icon name="download" size={13} /> {exportando ? "Exportando..." : "Exportar CSV"}
          </button>
          <Can permission="crm.criar">
            <button
              onClick={openCreate}
              className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-500"
            >
              <span className="text-sm leading-none">+</span> Novo
            </button>
          </Can>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <select value={status} onChange={e => setStatus(e.target.value)}
          className="rounded-lg border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
          <option value="">Status: todos</option>
          {Object.keys(STATUS_CORES).map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={funilEtapa} onChange={e => setFunilEtapa(e.target.value)}
          className="rounded-lg border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
          <option value="">Etapa: todas</option>
          {ETAPAS_FUNIL.map(e => <option key={e} value={e}>{e.replace(/_/g, " ")}</option>)}
        </select>
        <select value={empresaId} onChange={e => setEmpresaId(e.target.value)}
          className="rounded-lg border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
          <option value="">Empresa: todas</option>
          {empresas.map(emp => <option key={emp.id} value={emp.id}>{emp.nome}</option>)}
        </select>
        <input
          type="text"
          placeholder="Origem contém..."
          value={origem}
          onChange={e => setOrigem(e.target.value)}
          className="w-36 rounded-lg border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs text-neutral-200 placeholder-neutral-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
        />
        <select value={comTelefone} onChange={e => setComTelefone(e.target.value as "" | "true" | "false")}
          className="rounded-lg border border-neutral-700 bg-neutral-800 px-2.5 py-1.5 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50">
          <option value="">Telefone: qualquer</option>
          <option value="true">Com telefone</option>
          <option value="false">Sem telefone</option>
        </select>
        {temFiltroAtivo && (
          <button onClick={limparFiltros} className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-[11px] text-neutral-500 hover:text-neutral-300">
            <Icon name="close" size={11} /> Limpar filtros
          </button>
        )}
      </div>

      {loading ? (
        <div className="overflow-hidden rounded-xl border border-neutral-800">
          <div className="divide-y divide-neutral-800/70">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex gap-4 px-4 py-3">
                {Array.from({ length: 9 }).map((_, j) => (
                  <div key={j} className="h-3 flex-1 animate-pulse rounded bg-neutral-800" />
                ))}
              </div>
            ))}
          </div>
        </div>
      ) : error ? (
        <div className="flex items-center gap-2 rounded-xl border border-red-900/50 bg-red-950/30 px-4 py-3 text-xs text-red-400">
          <Icon name="alert" size={15} className="shrink-0" />
          {error}
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-neutral-800">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-neutral-800 bg-neutral-900/60 text-left text-neutral-400">
                  <th className="cursor-pointer select-none whitespace-nowrap px-4 py-2.5 font-medium" onClick={() => toggleSort("id")}>
                    <span className="inline-flex items-center gap-1">ID {sort === "id" && <Icon name="chevronDown" size={11} className={order === "asc" ? "rotate-180" : ""} />}</span>
                  </th>
                  <th className="whitespace-nowrap px-4 py-2.5 font-medium">Nome</th>
                  <th className="whitespace-nowrap px-4 py-2.5 font-medium">Empresa</th>
                  <th className="whitespace-nowrap px-4 py-2.5 font-medium">E-mail</th>
                  <th className="whitespace-nowrap px-4 py-2.5 font-medium">Telefone</th>
                  <th className="whitespace-nowrap px-4 py-2.5 font-medium">Origem</th>
                  <th className="cursor-pointer select-none whitespace-nowrap px-4 py-2.5 font-medium" onClick={() => toggleSort("funil_etapa")}>
                    <span className="inline-flex items-center gap-1">Etapa do funil {sort === "funil_etapa" && <Icon name="chevronDown" size={11} className={order === "asc" ? "rotate-180" : ""} />}</span>
                  </th>
                  <th className="cursor-pointer select-none whitespace-nowrap px-4 py-2.5 font-medium" onClick={() => toggleSort("valor_potencial")}>
                    <span className="inline-flex items-center gap-1">Valor potencial {sort === "valor_potencial" && <Icon name="chevronDown" size={11} className={order === "asc" ? "rotate-180" : ""} />}</span>
                  </th>
                  <th className="cursor-pointer select-none whitespace-nowrap px-4 py-2.5 font-medium" onClick={() => toggleSort("status")}>
                    <span className="inline-flex items-center gap-1">Status {sort === "status" && <Icon name="chevronDown" size={11} className={order === "asc" ? "rotate-180" : ""} />}</span>
                  </th>
                  <th className="px-4 py-2.5 font-medium text-right">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-800/70">
                {data.map((row, i) => (
                  <tr key={String(row.id)} className={`text-neutral-300 transition-colors hover:bg-neutral-800/50 ${i % 2 === 1 ? "bg-neutral-900/30" : ""}`}>
                    <td className="whitespace-nowrap px-4 py-2.5">{String(row.id ?? "—")}</td>
                    <td className="whitespace-nowrap px-4 py-2.5">{String(row.nome ?? "—")}</td>
                    <td className="whitespace-nowrap px-4 py-2.5">{row.empresa_id ? (empresaNomePorId[String(row.empresa_id)] || `#${row.empresa_id}`) : "—"}</td>
                    <td className="whitespace-nowrap px-4 py-2.5">{String(row.email ?? "—")}</td>
                    <td className="whitespace-nowrap px-4 py-2.5">{String(row.telefone ?? "—")}</td>
                    <td className="whitespace-nowrap px-4 py-2.5">{String(row.origem ?? "—")}</td>
                    <td className="whitespace-nowrap px-4 py-2.5">{String(row.funil_etapa ?? "—")}</td>
                    <td className="whitespace-nowrap px-4 py-2.5">{fmtBRL(Number(row.valor_potencial) || 0)}</td>
                    <td className="whitespace-nowrap px-4 py-2.5">
                      {(() => {
                        const s = String(row.status ?? "novo");
                        return <span className={`px-2 py-0.5 rounded text-[10px] ${STATUS_CORES[s] || "bg-neutral-500/20 text-neutral-400"}`}>{s}</span>;
                      })()}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex justify-end items-center gap-1">
                        <Can permission="crm.editar">
                          <button onClick={() => openEdit(row)} title="Editar"
                            className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-indigo-500/10 hover:text-indigo-400">
                            <Icon name="pencil" size={13} />
                          </button>
                        </Can>
                        <Can permission="crm.excluir">
                          <button onClick={() => setConfirmDelete(Number(row.id))} title="Excluir"
                            className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-red-500/10 hover:text-red-400">
                            <Icon name="trash" size={13} />
                          </button>
                        </Can>
                      </div>
                    </td>
                  </tr>
                ))}
                {data.length === 0 && (
                  <tr>
                    <td colSpan={10} className="px-4 py-10">
                      <div className="flex flex-col items-center gap-2 text-neutral-500">
                        <Icon name="inbox" size={22} />
                        <span className="text-xs">{temFiltroAtivo ? "Nenhum lead corresponde aos filtros" : "Nenhum lead cadastrado"}</span>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-neutral-800 px-4 py-2.5 text-[11px] text-neutral-400">
            <span>
              {meta.total === 0
                ? "Nenhum registro"
                : `Mostrando ${(meta.page - 1) * meta.page_size + 1}–${Math.min(meta.page * meta.page_size, meta.total)} de ${meta.total}`}
            </span>
            <div className="flex items-center gap-2">
              <select value={pageSize} onChange={e => setPageSize(Number(e.target.value) as 25 | 50 | 100)}
                className="rounded-lg border border-neutral-700 bg-neutral-800 px-2 py-1 text-[11px] text-neutral-300 focus:border-indigo-500 focus:outline-none">
                {PAGE_SIZES.map(n => <option key={n} value={n}>{n} / página</option>)}
              </select>
              <button disabled={meta.page <= 1} onClick={() => setPage(p => p - 1)}
                className="rounded-lg p-1.5 text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200 disabled:opacity-30 disabled:hover:bg-transparent">
                <Icon name="chevronLeft" size={14} />
              </button>
              <span>Página {meta.page} de {meta.pages}</span>
              <button disabled={meta.page >= meta.pages} onClick={() => setPage(p => p + 1)}
                className="rounded-lg p-1.5 text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200 disabled:opacity-30 disabled:hover:bg-transparent">
                <Icon name="chevronRight" size={14} />
              </button>
            </div>
          </div>
        </div>
      )}

      {modal.open && (
        <CrudFormModal
          mode={modal.mode}
          fields={leadsFields}
          formData={formData}
          onChange={(key, value) => setFormData(prev => ({ ...prev, [key]: value }))}
          onSave={handleSave}
          onClose={() => setModal({ open: false, mode: "create" })}
        />
      )}

      {confirmDelete !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setConfirmDelete(null)}>
          <div className="w-full max-w-[340px] rounded-xl border border-neutral-700 bg-neutral-800 p-5 shadow-xl" onClick={e => e.stopPropagation()}>
            <div className="mb-3 flex items-center gap-2 text-red-400">
              <Icon name="alert" size={17} />
              <h3 className="text-sm font-semibold text-neutral-100">Confirmar exclusão</h3>
            </div>
            <p className="mb-4 text-xs text-neutral-400">Tem certeza que deseja excluir este lead? Essa ação não pode ser desfeita.</p>
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
