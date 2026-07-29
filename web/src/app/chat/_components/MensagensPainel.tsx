"use client";
import { useState, useEffect, useRef } from "react";
import type { ConversaChat, MensagemChat, ParticipanteChat } from "@/lib/types/chat";
import { api } from "@/lib/api";
import { TextoComMencoes } from "@/lib/chatMencoes";
import MencaoAutocomplete from "./MencaoAutocomplete";

export default function MensagensPainel({
  conversa, mensagens, usuarioIdAtual, digitandoUserId, onEnviar, onAbrirThread, onUpload,
}: {
  conversa: ConversaChat;
  mensagens: MensagemChat[];
  usuarioIdAtual: number | null;
  digitandoUserId: number | null;
  onEnviar: (texto: string, anexoId?: number) => void;
  onAbrirThread: (mensagem: MensagemChat) => void;
  onUpload: (arquivo: File) => Promise<number>;
}) {
  const [texto, setTexto] = useState("");
  const [enviandoArquivo, setEnviandoArquivo] = useState(false);
  const [participantes, setParticipantes] = useState<ParticipanteChat[]>([]);
  const [mencaoAtiva, setMencaoAtiva] = useState<{ inicio: number; fim: number; filtro: string } | null>(null);
  const fimRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { fimRef.current?.scrollIntoView({ behavior: "smooth" }); }, [mensagens]);

  useEffect(() => {
    let cancelado = false;
    api.chat.listarParticipantes(conversa.id).then((r) => {
      if (!cancelado) setParticipantes(r.data);
    }).catch(() => {
      if (!cancelado) setParticipantes([]);
    });
    return () => { cancelado = true; };
  }, [conversa.id]);

  const enviar = () => {
    if (!texto.trim()) return;
    onEnviar(texto);
    setTexto("");
    setMencaoAtiva(null);
  };

  const aoDigitar = (e: React.ChangeEvent<HTMLInputElement>) => {
    const valor = e.target.value;
    setTexto(valor);
    const posicaoCursor = e.target.selectionStart ?? valor.length;
    const antesDoCursor = valor.slice(0, posicaoCursor);
    const indiceArroba = antesDoCursor.lastIndexOf("@");
    if (indiceArroba === -1) { setMencaoAtiva(null); return; }
    const trecho = antesDoCursor.slice(indiceArroba + 1);
    if (/\s/.test(trecho)) { setMencaoAtiva(null); return; }
    setMencaoAtiva({ inicio: indiceArroba, fim: posicaoCursor, filtro: trecho });
  };

  const selecionarMencao = (marcador: string) => {
    if (!mencaoAtiva) return;
    const novoTexto = `${texto.slice(0, mencaoAtiva.inicio)}${marcador} ${texto.slice(mencaoAtiva.fim)}`;
    setTexto(novoTexto);
    setMencaoAtiva(null);
    inputRef.current?.focus();
  };

  const selecionarArquivo = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const arquivo = e.target.files?.[0];
    if (!arquivo) return;
    setEnviandoArquivo(true);
    try {
      const anexoId = await onUpload(arquivo);
      onEnviar(`📎 ${arquivo.name}`, anexoId);
    } catch {
      // falha de upload — usuario ve que a mensagem nao apareceu e tenta de novo
    } finally {
      setEnviandoArquivo(false);
      e.target.value = "";
    }
  };

  return (
    <div className="flex-1 flex flex-col">
      <div className="bg-neutral-900 border-b border-neutral-800 px-4 py-3 shrink-0">
        <h2 className="text-sm font-bold text-neutral-200">{conversa.nome || conversa.cliente || "Conversa"}</h2>
        {digitandoUserId && <p className="text-[11px] text-neutral-500">digitando...</p>}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {mensagens.map((m) => (
          <div
            key={m.id}
            className={`max-w-[70%] rounded-lg px-3 py-2 text-sm ${
              m.remetente_id === usuarioIdAtual ? "bg-indigo-700 text-white ml-auto" : "bg-neutral-700 text-neutral-200"
            }`}
          >
            <p>
              {m.excluido_em
                ? "[mensagem excluída]"
                : <TextoComMencoes texto={m.texto ?? ""} participantes={participantes} />}
            </p>
            <div className="flex items-center gap-2 mt-1">
              <p className="text-[10px] opacity-60">{(m.created_at || "").slice(11, 16)}</p>
              {!m.excluido_em && (
                <button onClick={() => onAbrirThread(m)} className="text-[10px] underline opacity-70">
                  responder em thread
                </button>
              )}
            </div>
          </div>
        ))}
        <div ref={fimRef} />
      </div>

      <div className="p-3 border-t border-neutral-800 shrink-0 flex gap-2 relative">
        {mencaoAtiva && (
          <MencaoAutocomplete
            participantes={participantes}
            filtro={mencaoAtiva.filtro}
            mostrarTodos
            departamento={conversa.tipo === "canal_departamento" ? conversa.departamento : null}
            onSelecionar={selecionarMencao}
          />
        )}
        <label className="cursor-pointer text-neutral-400 px-2 flex items-center">
          📎
          <input type="file" className="hidden" onChange={selecionarArquivo} disabled={enviandoArquivo} />
        </label>
        <input
          ref={inputRef}
          type="text" value={texto} onChange={aoDigitar}
          onKeyDown={(e) => e.key === "Enter" && enviar()}
          placeholder="Digite sua mensagem..." autoFocus
          className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200"
        />
        <button onClick={enviar} className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm px-4 py-2 rounded-lg">
          Enviar
        </button>
      </div>
    </div>
  );
}
