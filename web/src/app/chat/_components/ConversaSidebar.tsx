"use client";
import type { ConversaChat } from "@/lib/types/chat";

const ICONE_TIPO: Record<string, string> = {
  dm: "💬", grupo: "👥", canal_departamento: "🏢", ticket: "🎫",
};

export default function ConversaSidebar({
  conversas, conversaSelecionadaId, onSelecionar,
}: {
  conversas: ConversaChat[];
  conversaSelecionadaId: number | null;
  onSelecionar: (conversa: ConversaChat) => void;
}) {
  return (
    <div className="w-72 shrink-0 border-r border-neutral-800 bg-neutral-900 overflow-y-auto">
      <div className="px-4 py-3 border-b border-neutral-800">
        <h1 className="text-sm font-bold text-neutral-200">Chat</h1>
      </div>
      {conversas.map((c) => {
        const titulo = c.tipo === "ticket" ? `${c.cliente || "Cliente"} — ${c.canal_externo || ""}` : (c.nome || "Conversa");
        return (
          <button
            key={`${c.tipo}-${c.id}`}
            onClick={() => onSelecionar(c)}
            className={`w-full text-left px-4 py-3 border-b border-neutral-800/50 hover:bg-neutral-800 ${
              conversaSelecionadaId === c.id ? "bg-neutral-800" : ""
            }`}
          >
            <div className="flex items-center gap-2">
              <span>{ICONE_TIPO[c.tipo]}</span>
              <span className="text-sm text-neutral-200 truncate">{titulo}</span>
            </div>
            {c.tipo === "ticket" && c.assunto && (
              <p className="text-[11px] text-neutral-500 mt-0.5 truncate">{c.assunto}</p>
            )}
          </button>
        );
      })}
    </div>
  );
}
