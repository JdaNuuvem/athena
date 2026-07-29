"use client";
import type { ConversaChat } from "@/lib/types/chat";

const ICONE_TIPO: Record<string, string> = {
  dm: "💬", grupo: "👥", canal_departamento: "🏢", ticket: "🎫",
};

const COR_PRESENCA: Record<string, string> = {
  online: "bg-emerald-500", ausente: "bg-amber-500", ocupado: "bg-red-500",
};

export default function ConversaSidebar({
  conversas, conversaSelecionadaId, onSelecionar, presencas = {},
}: {
  conversas: ConversaChat[];
  conversaSelecionadaId: number | null;
  onSelecionar: (conversa: ConversaChat) => void;
  /** user_id -> status. Simplificacao da Fase 1: o dot so aparece em DM e usa
   * `criado_por` como referencia — `ConversaChat` nao carrega a lista de
   * participantes, entao nao da pra identificar "o outro" da DM sem uma chamada
   * extra. Fica para a Fase 2 junto com o avatar do participante. */
  presencas?: Record<number, string>;
}) {
  return (
    <div className="w-72 shrink-0 border-r border-neutral-800 bg-neutral-900 overflow-y-auto">
      <div className="px-4 py-3 border-b border-neutral-800">
        <h1 className="text-sm font-bold text-neutral-200">Chat</h1>
      </div>
      {conversas.map((c) => {
        const titulo = c.tipo === "ticket" ? `${c.cliente || "Cliente"} — ${c.canal_externo || ""}` : (c.nome || "Conversa");
        const status = c.tipo === "dm" && c.criado_por != null ? presencas[c.criado_por] : undefined;
        return (
          <button
            key={`${c.tipo}-${c.id}`}
            onClick={() => onSelecionar(c)}
            className={`w-full text-left px-4 py-3 border-b border-neutral-800/50 hover:bg-neutral-800 ${
              conversaSelecionadaId === c.id ? "bg-neutral-800" : ""
            }`}
          >
            <div className="flex items-center gap-2">
              <span className="relative">
                {ICONE_TIPO[c.tipo]}
                {c.tipo === "dm" && (
                  <span
                    title={status || "offline"}
                    className={`absolute -bottom-0.5 -right-0.5 w-2 h-2 rounded-full ring-1 ring-neutral-900 ${
                      COR_PRESENCA[status || ""] || "bg-neutral-600"
                    }`}
                  />
                )}
              </span>
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
