"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import CrudPanel, { type Column, type FieldDef, type CrudService } from "../../_components/CrudPanel";
import Icon from "../../_components/Icon";
import { Can } from "@/lib/auth";
import { api } from "@/lib/api";

const STATUS_CORES: Record<string, string> = {
  pendente: "bg-amber-500/20 text-amber-400",
  concluida: "bg-emerald-500/20 text-emerald-400",
  cancelada: "bg-neutral-500/20 text-neutral-400",
};

interface RegistroNome { id: number; nome: string; }
interface Negociacao { id: number; titulo: string; }

function fmtDataHoraBR(v: unknown): string {
  if (!v) return "—";
  const d = new Date(String(v));
  return isNaN(d.getTime()) ? "—" : d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function nowLocalISO(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

const agendaService: CrudService = {
  list: (tabela) => api.crmList(tabela),
  create: (tabela, data) => api.crmCreate(tabela, data),
  update: (tabela, id, data) => api.crmUpdate(tabela, id, data),
  delete: (tabela, id) => api.crmDelete(tabela, id),
};

export default function Page() {
  const [leads, setLeads] = useState<RegistroNome[]>([]);
  const [contatos, setContatos] = useState<RegistroNome[]>([]);
  const [negociacoes, setNegociacoes] = useState<Negociacao[]>([]);
  const [reloadKey, setReloadKey] = useState(0);
  const [processando, setProcessando] = useState<number | null>(null);

  useEffect(() => {
    api.crmList("leads").then(r => setLeads((r.data || []) as RegistroNome[])).catch(() => {});
    api.crmList("contatos").then(r => setContatos((r.data || []) as RegistroNome[])).catch(() => {});
    api.crmList("negociacoes").then(r => setNegociacoes((r.data || []) as Negociacao[])).catch(() => {});
  }, []);

  const leadsMap = useMemo(() => Object.fromEntries(leads.map(l => [l.id, l.nome])), [leads]);
  const contatosMap = useMemo(() => Object.fromEntries(contatos.map(c => [c.id, c.nome])), [contatos]);
  const negociacoesMap = useMemo(() => Object.fromEntries(negociacoes.map(n => [n.id, n.titulo])), [negociacoes]);

  const marcarConcluida = useCallback(async (id: number) => {
    setProcessando(id);
    try {
      await api.crmUpdate("agenda", id, { status: "concluida", data_realizada: nowLocalISO() });
      setReloadKey(k => k + 1);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Erro ao marcar atividade como concluída");
    } finally {
      setProcessando(null);
    }
  }, []);

  const marcarCancelada = useCallback(async (id: number) => {
    if (!confirm("Cancelar esta atividade?")) return;
    setProcessando(id);
    try {
      await api.crmUpdate("agenda", id, { status: "cancelada" });
      setReloadKey(k => k + 1);
    } catch (e) {
      alert(e instanceof Error ? e.message : "Erro ao cancelar atividade");
    } finally {
      setProcessando(null);
    }
  }, []);

  const agendaCols: Column[] = useMemo(() => [
    { key: "tipo", label: "Tipo" },
    { key: "descricao", label: "Descrição" },
    { key: "data_agendada", label: "Data agendada", render: fmtDataHoraBR },
    { key: "lead_id", label: "Lead", render: (v) => v ? (leadsMap[Number(v)] || `#${v}`) : "—" },
    { key: "contato_id", label: "Contato", render: (v) => v ? (contatosMap[Number(v)] || `#${v}`) : "—" },
    { key: "negociacao_id", label: "Negociação", render: (v) => v ? (negociacoesMap[Number(v)] || `#${v}`) : "—" },
    { key: "status", label: "Status", render: (v) => {
      const s = String(v ?? "pendente");
      return <span className={`px-2 py-0.5 rounded text-[10px] ${STATUS_CORES[s] || "bg-neutral-500/20 text-neutral-400"}`}>{s}</span>;
    }},
    { key: "data_realizada", label: "Realizada em", render: fmtDataHoraBR },
  ], [leadsMap, contatosMap, negociacoesMap]);

  const agendaFields: FieldDef[] = useMemo(() => [
    { key: "tipo", label: "Tipo (ligação, reunião, e-mail...)" },
    { key: "descricao", label: "Descrição" },
    { key: "data_agendada", label: "Data agendada", type: "datetime" },
    { key: "lead_id", label: "Lead", type: "select", numeric: true, options: leads.map(l => ({ label: l.nome, value: String(l.id) })) },
    { key: "contato_id", label: "Contato", type: "select", numeric: true, options: contatos.map(c => ({ label: c.nome, value: String(c.id) })) },
    { key: "negociacao_id", label: "Negociação", type: "select", numeric: true, options: negociacoes.map(n => ({ label: n.titulo, value: String(n.id) })) },
    { key: "status", label: "Status", type: "select", options: Object.keys(STATUS_CORES).map(s => ({ label: s, value: s })) },
    { key: "data_realizada", label: "Realizada em", type: "datetime" },
  ], [leads, contatos, negociacoes]);

  const rowActions = useCallback((row: Record<string, unknown>) => {
    if (row.status !== "pendente") return null;
    const id = Number(row.id);
    const busy = processando === id;
    return (
      <>
        <Can permission="crm.editar">
          <button
            onClick={() => marcarConcluida(id)}
            disabled={busy}
            title="Marcar como concluída"
            className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-emerald-500/10 hover:text-emerald-400 disabled:opacity-50"
          >
            <Icon name="check" size={13} />
          </button>
          <button
            onClick={() => marcarCancelada(id)}
            disabled={busy}
            title="Cancelar"
            className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-red-500/10 hover:text-red-400 disabled:opacity-50"
          >
            <Icon name="close" size={13} />
          </button>
        </Can>
      </>
    );
  }, [processando, marcarConcluida, marcarCancelada]);

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">Agenda</h1>
        <p className="text-xs text-neutral-500 mt-1">Atividades e follow-ups vinculados a leads, contatos e negociações</p>
      </div>
      <CrudPanel
        tabela="agenda"
        columns={agendaCols}
        formFields={agendaFields}
        service={agendaService}
        permissionPrefix="crm"
        rowActions={rowActions}
        reloadKey={reloadKey}
      />
    </div>
  );
}
