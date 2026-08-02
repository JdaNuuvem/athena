"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";
import type { Ticket, Atendente, MensagemTicket } from "@/lib/types/atendimento";
import { useChatSocket, type EventoChatSocket } from "@/lib/useChatSocket";
import { Can } from "@/lib/auth";
import Icon from "@/app/_components/Icon";
import LoadingState from "@/app/_components/LoadingState";
import ErrorAlert from "@/app/_components/ErrorAlert";
import PainelControle from "./_components/PainelControle";
import ThreadMensagens from "./_components/ThreadMensagens";

export default function TicketDetalheClient() {
  // ponytail: nao usa useParams() — export estatico pre-renderiza com
  // id="placeholder"; usePathname() sempre reflete a URL real do browser.
  // Mesmo padrao de /lojas/[id]/client.tsx.
  const pathname = usePathname();
  const id = Number(pathname?.split("/").filter(Boolean).pop() || 0);
  const { conectado, on } = useChatSocket();

  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [atendentes, setAtendentes] = useState<Atendente[]>([]);
  const [mensagens, setMensagens] = useState<MensagemTicket[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");
  const [showEditar, setShowEditar] = useState(false);

  // participantes de uma conversa de ticket sao derivados da permissao
  // atendimento.ver (todo atendente e' "participante" de todo ticket), entao
  // o broadcast de nova_mensagem chega pra quem estiver com QUALQUER ticket
  // aberto — precisa filtrar pelo conversa_id deste ticket, nao so pelo id
  // da mensagem, senao mensagem de outro ticket vaza pra esta thread.
  const conversaIdRef = useRef<number | null>(null);

  const carregarTicket = useCallback(() => {
    if (!id) { setLoading(false); return; }
    api.atendimento.obter(id)
      .then(t => setTicket(t))
      .catch(e => setErro(e instanceof Error ? e.message : "Erro ao carregar ticket"))
      .finally(() => setLoading(false));
  }, [id]);

  const carregarMensagens = useCallback(() => {
    if (!id) return;
    conversaIdRef.current = null;
    api.atendimento.listarMensagens(id).then(r => {
      const dados = r.data || [];
      setMensagens(dados);
      if (dados.length > 0) conversaIdRef.current = dados[0].conversa_id;
    }).catch(() => {});
  }, [id]);

  useEffect(() => { carregarTicket(); }, [carregarTicket]);
  useEffect(() => { carregarMensagens(); }, [carregarMensagens]);
  useEffect(() => { api.atendimento.listarAtendentes().then(r => setAtendentes(r.data || [])).catch(() => {}); }, []);

  useEffect(() => {
    return on((evento: EventoChatSocket) => {
      if (evento.evento === "nova_mensagem") {
        const m = evento.mensagem as MensagemTicket;
        if (conversaIdRef.current !== null && m.conversa_id !== conversaIdRef.current) return;
        if (conversaIdRef.current === null) conversaIdRef.current = m.conversa_id;
        setMensagens(atual => (atual.some(x => x.id === m.id) ? atual : [...atual, m]));
      }
      if (evento.evento === "ticket_status_alterado" && evento.ticket_id === id) {
        setTicket(atual => atual ? { ...atual, status: evento.status as Ticket["status"] } : atual);
      }
      if (evento.evento === "ticket_atendente_alterado" && evento.ticket_id === id) {
        setTicket(atual => atual ? { ...atual, atendente_id: evento.atendente_id as number } : atual);
      }
    });
  }, [on, id]);

  const mudarStatus = async (status: string) => {
    setErro("");
    try {
      const r = await api.atendimento.mudarStatus(id, status);
      if (r.error) { setErro(r.error); return; }
      carregarTicket();
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao mudar status"); }
  };

  const atribuir = async (atendenteId: number) => {
    setErro("");
    try {
      const r = await api.atendimento.atribuir(id, atendenteId);
      if (r.error) { setErro(r.error); return; }
      carregarTicket();
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao atribuir atendente"); }
  };

  const enviarMensagem = async (texto: string) => {
    setErro("");
    try {
      const r = await api.atendimento.enviarMensagem(id, texto);
      if (r.error) setErro(r.error);
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao enviar mensagem"); }
  };

  const uploadAnexo = async (arquivo: File) => {
    setErro("");
    try {
      const r = await api.atendimento.uploadAnexo(id, arquivo);
      if (r.error) setErro(r.error);
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao enviar anexo"); }
  };

  const editar = async (campos: { cliente: string; email: string; telefone: string; assunto: string; canal: string; prioridade: string }) => {
    setErro("");
    try {
      const r = await api.atendimento.atualizar(id, campos);
      if (r.error) { setErro(r.error); return; }
      setShowEditar(false);
      carregarTicket();
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao editar ticket"); }
  };

  if (loading) return <LoadingState />;
  if (!id) return <div className="p-6 text-red-400">Ticket inválido</div>;
  if (!ticket) return <div className="p-6 text-red-400">Ticket não encontrado</div>;

  return (
    <div className="h-screen flex flex-col">
      <div className="p-4 border-b border-neutral-800 shrink-0 space-y-1">
        <div className="flex items-start justify-between gap-3">
          <div>
            <Link href="/atendimento/tickets" className="text-xs text-neutral-500 hover:text-neutral-300 inline-flex items-center gap-0.5">
              <Icon name="chevronLeft" size={12} /> Tickets
            </Link>
            <h1 className="text-sm font-bold text-neutral-100">{ticket.numero || `#${ticket.id}`} — {ticket.assunto}</h1>
          </div>
          <Can permission="atendimento.editar">
            <button onClick={() => setShowEditar(true)} className="text-xs text-indigo-400 hover:text-indigo-300 shrink-0">Editar</button>
          </Can>
        </div>
        <ErrorAlert message={erro || null} />
      </div>
      <div className="flex-1 flex overflow-hidden">
        <ThreadMensagens ticket={ticket} mensagens={mensagens} onEnviar={enviarMensagem} onUpload={uploadAnexo} />
        <PainelControle ticket={ticket} atendentes={atendentes} onMudarStatus={mudarStatus} onAtribuir={atribuir} />
      </div>
      {!conectado && (
        <div className="fixed bottom-3 right-3 bg-amber-600 text-white text-xs px-3 py-1.5 rounded-lg">Reconectando...</div>
      )}
      {showEditar && (
        <EditarTicketModal ticket={ticket} onSalvar={editar} onFechar={() => setShowEditar(false)} />
      )}
    </div>
  );
}

function EditarTicketModal({
  ticket, onSalvar, onFechar,
}: {
  ticket: Ticket;
  onSalvar: (campos: { cliente: string; email: string; telefone: string; assunto: string; canal: string; prioridade: string }) => void;
  onFechar: () => void;
}) {
  const [form, setForm] = useState<{ cliente: string; email: string; telefone: string; assunto: string; canal: string; prioridade: string }>({
    cliente: ticket.cliente, email: ticket.email || "", telefone: ticket.telefone || "",
    assunto: ticket.assunto, canal: ticket.canal, prioridade: ticket.prioridade,
  });
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onFechar}>
      <div className="bg-neutral-900 border border-neutral-700 rounded-xl p-6 w-full max-w-md space-y-3" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-neutral-200">Editar Ticket</h3>
          <button onClick={onFechar} className="text-neutral-500 hover:text-neutral-300"><Icon name="close" size={16} /></button>
        </div>
        <input type="text" value={form.cliente} onChange={e => setForm(p => ({ ...p, cliente: e.target.value }))} placeholder="Nome do cliente"
          className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200" autoFocus />
        <input type="email" value={form.email} onChange={e => setForm(p => ({ ...p, email: e.target.value }))} placeholder="Email"
          className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200" />
        <input type="text" value={form.telefone} onChange={e => setForm(p => ({ ...p, telefone: e.target.value }))} placeholder="Telefone"
          className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200" />
        <input type="text" value={form.assunto} onChange={e => setForm(p => ({ ...p, assunto: e.target.value }))} placeholder="Assunto"
          className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200" />
        <div className="flex gap-2">
          <select value={form.canal} onChange={e => setForm(p => ({ ...p, canal: e.target.value }))} className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200">
            {["whatsapp", "telegram", "instagram", "facebook", "chat", "email"].map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <select value={form.prioridade} onChange={e => setForm(p => ({ ...p, prioridade: e.target.value }))} className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200">
            {["baixa", "normal", "alta", "urgente"].map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <button onClick={() => onSalvar(form)} className="w-full bg-indigo-600 hover:bg-indigo-500 text-white text-sm py-2 rounded-lg">Salvar</button>
      </div>
    </div>
  );
}
