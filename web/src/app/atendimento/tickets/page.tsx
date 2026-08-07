"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Ticket, Atendente } from "@/lib/types/atendimento";
import PageHeader from "@/app/_components/PageHeader";
import StatusBadge from "@/app/_components/StatusBadge";
import DataTable from "@/app/_components/DataTable";
import TabBar from "@/app/_components/TabBar";
import DateFilter, { type DateFilterValue } from "@/app/_components/DateFilter";
import ErrorAlert from "@/app/_components/ErrorAlert";
import LoadingState from "@/app/_components/LoadingState";
import Icon from "@/app/_components/Icon";
import { Can } from "@/lib/auth";
import { fmtDataBR } from "@/lib/format";
import type { Column, StatusBadgeVariant } from "@/lib/types/ui";

const STATUS_VARIANT: Record<string, StatusBadgeVariant> = {
  aberto: "success", pendente: "warning", fechado: "neutral",
};
const PRIORIDADE_VARIANT: Record<string, StatusBadgeVariant> = {
  urgente: "danger", alta: "warning", normal: "neutral", baixa: "neutral",
};
const TABS = [
  { key: "", label: "Todos" },
  { key: "aberto", label: "Aberto" },
  { key: "pendente", label: "Pendente" },
  { key: "fechado", label: "Fechado" },
];

function slaVariant(t: Ticket): StatusBadgeVariant {
  if (t.status === "fechado" || !t.sla_vencimento) return "neutral";
  return new Date(t.sla_vencimento) < new Date() ? "danger" : "success";
}
function slaLabel(t: Ticket): string {
  if (t.status === "fechado" || !t.sla_vencimento) return "—";
  return new Date(t.sla_vencimento) < new Date() ? "Vencido" : "No prazo";
}

export default function TicketsPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [atendentes, setAtendentes] = useState<Atendente[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");
  const [statusTab, setStatusTab] = useState("");
  const [prioridade, setPrioridade] = useState("");
  const [canal, setCanal] = useState("");
  const [atendenteId, setAtendenteId] = useState("");
  const [busca, setBusca] = useState("");
  const [dateFilter, setDateFilter] = useState<DateFilterValue>({});
  const [showModal, setShowModal] = useState(false);
  const [novo, setNovo] = useState({ cliente: "", email: "", telefone: "", assunto: "", canal: "whatsapp", prioridade: "normal" });

  const carregar = useCallback(() => {
    const filtros: Record<string, string> = {};
    if (statusTab) filtros.status = statusTab;
    if (prioridade) filtros.prioridade = prioridade;
    if (canal) filtros.canal = canal;
    if (atendenteId) filtros.atendente_id = atendenteId;
    if (busca) filtros.q = busca;
    if (dateFilter.data_inicio) filtros.de = dateFilter.data_inicio;
    if (dateFilter.data_fim) filtros.ate = dateFilter.data_fim;
    setLoading(true);
    api.atendimento.listar(filtros)
      .then(r => setTickets(r.data || []))
      .catch(e => setErro(e instanceof Error ? e.message : "Erro ao carregar tickets"))
      .finally(() => setLoading(false));
  }, [statusTab, prioridade, canal, atendenteId, busca, dateFilter]);

  useEffect(() => { carregar(); }, [carregar]);
  useEffect(() => { api.atendimento.listarAtendentes().then(r => setAtendentes(r.data || [])).catch(() => {}); }, []);

  const criar = async () => {
    if (!novo.cliente.trim() || !novo.assunto.trim()) return;
    setErro("");
    try {
      const r = await api.atendimento.criar(novo);
      if (r.error) { setErro(r.error); return; }
      setShowModal(false);
      setNovo({ cliente: "", email: "", telefone: "", assunto: "", canal: "whatsapp", prioridade: "normal" });
      carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao criar ticket");
    }
  };

  const columns: Column<Ticket>[] = [
    { key: "numero", label: "Número", render: (v, row) => <Link href={`/atendimento/tickets/${row.id}`} className="text-indigo-400 hover:text-indigo-300">{String(v ?? row.id)}</Link> },
    { key: "cliente", label: "Cliente" },
    { key: "assunto", label: "Assunto" },
    { key: "canal", label: "Canal", align: "center" },
    { key: "prioridade", label: "Prioridade", align: "center", render: (v) => <StatusBadge label={String(v)} variant={PRIORIDADE_VARIANT[String(v)] || "neutral"} /> },
    { key: "status", label: "Status", align: "center", render: (v) => <StatusBadge label={String(v)} variant={STATUS_VARIANT[String(v)] || "neutral"} /> },
    { key: "sla_vencimento", label: "SLA", align: "center", render: (_v, row) => <StatusBadge label={slaLabel(row)} variant={slaVariant(row)} /> },
    { key: "data_abertura", label: "Aberto em", align: "center", render: (v) => v ? fmtDataBR(v) : "—" },
  ];

  return (
    <div className="p-6 space-y-4">
      <div className="flex justify-between items-end flex-wrap gap-3">
        <PageHeader title="Tickets" subtitle="Atendimento ao cliente — chamados multicanal" />
        <div className="flex items-center gap-2 flex-wrap">
          <DateFilter value={dateFilter} onChange={setDateFilter} />
          <Can permission="atendimento.criar">
            <button onClick={() => setShowModal(true)} className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg">
              + Novo Ticket
            </button>
          </Can>
        </div>
      </div>

      <ErrorAlert message={erro || null} />

      <TabBar tabs={TABS} active={statusTab} onChange={setStatusTab} />

      <div className="flex gap-2 flex-wrap">
        <select value={prioridade} onChange={e => setPrioridade(e.target.value)} className="bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200">
          <option value="">Toda prioridade</option>
          {["baixa", "normal", "alta", "urgente"].map(p => <option key={p} value={p}>{p}</option>)}
        </select>
        <select value={canal} onChange={e => setCanal(e.target.value)} className="bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200">
          <option value="">Todo canal</option>
          {["whatsapp", "telegram", "instagram", "facebook", "chat", "email"].map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={atendenteId} onChange={e => setAtendenteId(e.target.value)} className="bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200">
          <option value="">Todo atendente</option>
          {atendentes.map(a => <option key={a.id} value={String(a.id)}>{a.nome}</option>)}
        </select>
        <input type="text" value={busca} onChange={e => setBusca(e.target.value)} placeholder="Buscar cliente, assunto, número..."
          className="bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200 placeholder-neutral-500 w-56" />
      </div>

      {loading ? <LoadingState /> : (
        <DataTable
          columns={columns}
          data={tickets}
          keyExtractor={t => t.id}
          emptyMessage="Nenhum ticket encontrado"
        />
      )}

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setShowModal(false)}>
          <div className="bg-neutral-900 border border-neutral-700 rounded-xl p-6 w-full max-w-md space-y-3" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-neutral-200">Novo Ticket</h3>
              <button onClick={() => setShowModal(false)} className="text-neutral-500 hover:text-neutral-300"><Icon name="close" size={16} /></button>
            </div>
            <input type="text" value={novo.cliente} onChange={e => setNovo(p => ({ ...p, cliente: e.target.value }))} placeholder="Nome do cliente"
              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500" autoFocus />
            <input type="email" value={novo.email} onChange={e => setNovo(p => ({ ...p, email: e.target.value }))} placeholder="Email (opcional)"
              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500" />
            <input type="text" value={novo.telefone} onChange={e => setNovo(p => ({ ...p, telefone: e.target.value }))} placeholder="Telefone (opcional)"
              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500" />
            <input type="text" value={novo.assunto} onChange={e => setNovo(p => ({ ...p, assunto: e.target.value }))} placeholder="Assunto"
              className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500" />
            <div className="flex gap-2">
              <select value={novo.canal} onChange={e => setNovo(p => ({ ...p, canal: e.target.value }))} className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200">
                {["whatsapp", "telegram", "instagram", "facebook", "chat", "email"].map(c => <option key={c} value={c}>{c}</option>)}
              </select>
              <select value={novo.prioridade} onChange={e => setNovo(p => ({ ...p, prioridade: e.target.value }))} className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200">
                {["baixa", "normal", "alta", "urgente"].map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <button onClick={criar} className="w-full bg-emerald-600 hover:bg-emerald-500 text-white text-sm py-2 rounded-lg">Criar Ticket</button>
          </div>
        </div>
      )}
    </div>
  );
}
