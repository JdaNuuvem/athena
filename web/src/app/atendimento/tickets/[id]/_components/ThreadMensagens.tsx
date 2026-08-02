"use client";
import { useEffect, useRef, useState } from "react";
import type { Ticket, MensagemTicket } from "@/lib/types/atendimento";
import { Can } from "@/lib/auth";

export default function ThreadMensagens({
  ticket, mensagens, onEnviar, onUpload,
}: {
  ticket: Ticket;
  mensagens: MensagemTicket[];
  onEnviar: (texto: string) => void;
  onUpload: (arquivo: File) => Promise<void>;
}) {
  const [texto, setTexto] = useState("");
  const [enviandoArquivo, setEnviandoArquivo] = useState(false);
  const fimRef = useRef<HTMLDivElement>(null);

  useEffect(() => { fimRef.current?.scrollIntoView({ behavior: "smooth" }); }, [mensagens]);

  const enviar = () => {
    if (!texto.trim()) return;
    onEnviar(texto);
    setTexto("");
  };

  const selecionarArquivo = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const arquivo = e.target.files?.[0];
    if (!arquivo) return;
    setEnviandoArquivo(true);
    try { await onUpload(arquivo); }
    finally { setEnviandoArquivo(false); e.target.value = ""; }
  };

  return (
    <div className="flex-1 flex flex-col min-w-0">
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {mensagens.length === 0 && <p className="text-xs text-neutral-500 text-center mt-8">Nenhuma mensagem ainda</p>}
        {mensagens.map(m => (
          <div key={m.id} className="max-w-[70%] rounded-lg px-3 py-2 text-sm bg-neutral-700 text-neutral-200">
            <p className="text-[10px] text-neutral-400 mb-0.5">{m.remetente_nome || "—"}</p>
            {m.anexo_url ? (
              <a href={`/api/atendimento/tickets/${ticket.id}/anexo/${m.anexo_url}`} target="_blank" rel="noreferrer" className="text-indigo-300 underline">
                📎 {m.texto}
              </a>
            ) : (
              <p>{m.texto}</p>
            )}
            <p className="text-[10px] opacity-60 mt-1">{(m.created_at || "").slice(11, 16)}</p>
          </div>
        ))}
        <div ref={fimRef} />
      </div>

      <Can permission="atendimento.criar">
        <div className="p-3 border-t border-neutral-800 shrink-0 flex gap-2">
          <label className="cursor-pointer text-neutral-400 px-2 flex items-center">
            <svg xmlns="http://www.w3.org/2000/svg" width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
              <path d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
            </svg>
            <input type="file" className="hidden" onChange={selecionarArquivo} disabled={enviandoArquivo} />
          </label>
          <input
            type="text" value={texto} onChange={e => setTexto(e.target.value)}
            onKeyDown={e => e.key === "Enter" && enviar()}
            placeholder="Digite sua mensagem..."
            className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200"
          />
          <button onClick={enviar} className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm px-4 py-2 rounded-lg">Enviar</button>
        </div>
      </Can>
    </div>
  );
}
