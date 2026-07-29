"use client";
import { useState, useEffect } from "react";
import type { MensagemChat } from "@/lib/types/chat";
import { api } from "@/lib/api";

export default function ThreadPainel({
  mensagemPai, onFechar, onEnviarResposta,
}: {
  mensagemPai: MensagemChat;
  onFechar: () => void;
  onEnviarResposta: (texto: string, threadPaiId: number) => void;
}) {
  const [respostas, setRespostas] = useState<MensagemChat[]>([]);
  const [texto, setTexto] = useState("");

  useEffect(() => {
    api.chat.listarMensagens(mensagemPai.conversa_id).then((r) => {
      setRespostas(r.data.filter((m) => m.thread_pai_id === mensagemPai.id));
    }).catch(() => {});
  }, [mensagemPai.id, mensagemPai.conversa_id]);

  const enviar = () => {
    if (!texto.trim()) return;
    onEnviarResposta(texto, mensagemPai.id);
    setTexto("");
  };

  return (
    <div className="w-80 shrink-0 border-l border-neutral-800 bg-neutral-900 flex flex-col">
      <div className="px-4 py-3 border-b border-neutral-800 flex items-center justify-between">
        <h3 className="text-sm font-bold text-neutral-200">Thread</h3>
        <button onClick={onFechar} className="text-neutral-500 text-xs">fechar</button>
      </div>
      <div className="p-3 border-b border-neutral-800 bg-neutral-800/50">
        <p className="text-sm text-neutral-300">{mensagemPai.texto}</p>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {respostas.map((r) => (
          <div key={r.id} className="bg-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200">
            {r.texto}
          </div>
        ))}
      </div>
      <div className="p-3 border-t border-neutral-800 flex gap-2">
        <input
          type="text" value={texto} onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && enviar()}
          placeholder="Responder na thread..."
          className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200"
        />
        <button onClick={enviar} className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs px-3 py-2 rounded-lg">
          Enviar
        </button>
      </div>
    </div>
  );
}
