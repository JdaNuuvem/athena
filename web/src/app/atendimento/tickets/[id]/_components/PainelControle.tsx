"use client";
import type { Ticket, Atendente } from "@/lib/types/atendimento";
import StatusBadge from "@/app/_components/StatusBadge";
import { Can } from "@/lib/auth";
import type { StatusBadgeVariant } from "@/lib/types/ui";

const PRIORIDADE_VARIANT: Record<string, StatusBadgeVariant> = {
  urgente: "danger", alta: "warning", normal: "neutral", baixa: "neutral",
};

const TRANSICOES: Record<string, { status: string; label: string }[]> = {
  aberto: [{ status: "pendente", label: "Marcar pendente" }, { status: "fechado", label: "Fechar" }],
  pendente: [{ status: "aberto", label: "Reabrir" }, { status: "fechado", label: "Fechar" }],
  fechado: [{ status: "aberto", label: "Reabrir" }],
};

export default function PainelControle({
  ticket, atendentes, onMudarStatus, onAtribuir,
}: {
  ticket: Ticket;
  atendentes: Atendente[];
  onMudarStatus: (status: string) => void;
  onAtribuir: (atendenteId: number) => void;
}) {
  const slaVencido = ticket.status !== "fechado" && !!ticket.sla_vencimento && new Date(ticket.sla_vencimento) < new Date();
  const atendenteAtual = atendentes.find(a => a.id === ticket.atendente_id);

  return (
    <div className="w-72 shrink-0 border-l border-neutral-800 p-4 space-y-4 overflow-y-auto">
      <div>
        <p className="text-[10px] uppercase text-neutral-500 mb-1">Status</p>
        <StatusBadge label={ticket.status} variant={ticket.status === "aberto" ? "success" : ticket.status === "pendente" ? "warning" : "neutral"} />
        <Can permission="atendimento.editar">
          <div className="flex flex-col gap-1.5 mt-2">
            {(TRANSICOES[ticket.status] || []).map(t => (
              <button key={t.status} onClick={() => onMudarStatus(t.status)}
                className="text-xs px-2 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-left">
                {t.label}
              </button>
            ))}
          </div>
        </Can>
      </div>

      <div>
        <p className="text-[10px] uppercase text-neutral-500 mb-1">Prioridade</p>
        <StatusBadge label={ticket.prioridade} variant={PRIORIDADE_VARIANT[ticket.prioridade] || "neutral"} />
      </div>

      <div>
        <p className="text-[10px] uppercase text-neutral-500 mb-1">Atendente</p>
        <Can permission="atendimento.editar" fallback={<p className="text-xs text-neutral-300">{atendenteAtual?.nome || "Não atribuído"}</p>}>
          <select
            value={ticket.atendente_id ?? ""}
            onChange={e => e.target.value && onAtribuir(Number(e.target.value))}
            className="w-full bg-neutral-800 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200"
          >
            <option value="">Não atribuído</option>
            {atendentes.map(a => <option key={a.id} value={a.id}>{a.nome}</option>)}
          </select>
        </Can>
      </div>

      <div>
        <p className="text-[10px] uppercase text-neutral-500 mb-1">SLA</p>
        <StatusBadge label={ticket.sla_vencimento ? (slaVencido ? "Vencido" : "No prazo") : "—"} variant={slaVencido ? "danger" : "success"} />
        {ticket.sla_vencimento && <p className="text-[10px] text-neutral-500 mt-1">{new Date(ticket.sla_vencimento).toLocaleString("pt-BR")}</p>}
      </div>

      <div className="space-y-1 pt-2 border-t border-neutral-800">
        <p className="text-[10px] uppercase text-neutral-500">Cliente</p>
        <p className="text-xs text-neutral-300">{ticket.cliente}</p>
        {ticket.email && <p className="text-xs text-neutral-500">{ticket.email}</p>}
        {ticket.telefone && <p className="text-xs text-neutral-500">{ticket.telefone}</p>}
        <p className="text-xs text-neutral-500">Canal: {ticket.canal}</p>
      </div>

      <div className="space-y-1 pt-2 border-t border-neutral-800 text-[10px] text-neutral-500">
        <p>Aberto em: {new Date(ticket.data_abertura).toLocaleString("pt-BR")}</p>
        {ticket.data_fechamento && <p>Fechado em: {new Date(ticket.data_fechamento).toLocaleString("pt-BR")}</p>}
        {ticket.tempo_resposta_min != null && <p>SLA resposta: {ticket.tempo_resposta_min} min</p>}
      </div>
    </div>
  );
}
