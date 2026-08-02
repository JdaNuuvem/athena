"use client";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";
import type { Ticket, Atendente } from "@/lib/types/atendimento";
import Icon from "@/app/_components/Icon";
import LoadingState from "@/app/_components/LoadingState";
import ErrorAlert from "@/app/_components/ErrorAlert";
import PainelControle from "./_components/PainelControle";

export default function TicketDetalheClient() {
  // ponytail: nao usa useParams() — export estatico pre-renderiza com
  // id="placeholder"; usePathname() sempre reflete a URL real do browser.
  // Mesmo padrao de /lojas/[id]/client.tsx.
  const pathname = usePathname();
  const id = Number(pathname?.split("/").filter(Boolean).pop() || 0);

  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [atendentes, setAtendentes] = useState<Atendente[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");

  const carregar = useCallback(() => {
    if (!id) { setLoading(false); return; }
    api.atendimento.obter(id)
      .then(t => setTicket(t))
      .catch(e => setErro(e instanceof Error ? e.message : "Erro ao carregar ticket"))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => { carregar(); }, [carregar]);
  useEffect(() => { api.atendimento.listarAtendentes().then(r => setAtendentes(r.data || [])).catch(() => {}); }, []);

  const mudarStatus = async (status: string) => {
    setErro("");
    try {
      const r = await api.atendimento.mudarStatus(id, status);
      if (r.error) { setErro(r.error); return; }
      carregar();
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao mudar status"); }
  };

  const atribuir = async (atendenteId: number) => {
    setErro("");
    try {
      const r = await api.atendimento.atribuir(id, atendenteId);
      if (r.error) { setErro(r.error); return; }
      carregar();
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao atribuir atendente"); }
  };

  if (loading) return <LoadingState />;
  if (!id) return <div className="p-6 text-red-400">Ticket inválido</div>;
  if (!ticket) return <div className="p-6 text-red-400">Ticket não encontrado</div>;

  return (
    <div className="h-screen flex flex-col">
      <div className="p-4 border-b border-neutral-800 shrink-0 space-y-1">
        <Link href="/atendimento/tickets" className="text-xs text-neutral-500 hover:text-neutral-300 inline-flex items-center gap-0.5">
          <Icon name="chevronLeft" size={12} /> Tickets
        </Link>
        <h1 className="text-sm font-bold text-neutral-100">{ticket.numero || `#${ticket.id}`} — {ticket.assunto}</h1>
        <ErrorAlert message={erro || null} />
      </div>
      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 flex items-center justify-center text-neutral-500 text-sm">
          Thread de mensagens — Task 13
        </div>
        <PainelControle ticket={ticket} atendentes={atendentes} onMudarStatus={mudarStatus} onAtribuir={atribuir} />
      </div>
    </div>
  );
}
