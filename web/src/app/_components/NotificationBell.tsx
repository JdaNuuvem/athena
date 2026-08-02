"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Notificacao } from "@/lib/types/atendimento";
import { useChatSocket, type EventoChatSocket } from "@/lib/useChatSocket";
import Icon from "./Icon";

export default function NotificationBell() {
  const router = useRouter();
  const { on } = useChatSocket();
  const [notificacoes, setNotificacoes] = useState<Notificacao[]>([]);
  const [aberto, setAberto] = useState(false);

  const carregar = () => { api.notificacoes.listar().then(r => setNotificacoes(r.data || [])).catch(() => {}); };

  useEffect(() => { carregar(); }, []);

  useEffect(() => {
    return on((evento: EventoChatSocket) => {
      if (evento.evento === "notificacao") carregar();
    });
  }, [on]);

  const naoLidas = notificacoes.filter(n => !n.lida).length;

  const abrir = async (n: Notificacao) => {
    if (!n.lida) await api.notificacoes.marcarLida(n.id);
    setAberto(false);
    carregar();
    if (n.link) router.push(n.link);
  };

  const marcarTodas = async () => {
    await api.notificacoes.marcarTodasLidas();
    carregar();
  };

  return (
    <div className="relative">
      <button
        onClick={() => setAberto(v => !v)}
        aria-label="Notificações"
        className="relative p-1.5 rounded shrink-0 transition-colors hover:bg-white/5"
        style={{ color: "var(--ink-700)" }}
      >
        <Icon name="bell" size={14} />
        {naoLidas > 0 && (
          <span className="absolute -top-0.5 -right-0.5 bg-red-600 text-white text-[9px] rounded-full min-w-[14px] h-[14px] flex items-center justify-center px-0.5">
            {naoLidas > 9 ? "9+" : naoLidas}
          </span>
        )}
      </button>
      {aberto && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setAberto(false)} />
          <div className="absolute bottom-full right-0 mb-2 w-72 max-h-96 overflow-y-auto bg-neutral-900 border border-neutral-700 rounded-lg shadow-xl z-50">
            <div className="flex items-center justify-between px-3 py-2 border-b border-neutral-800">
              <span className="text-xs font-semibold text-neutral-300">Notificações</span>
              {naoLidas > 0 && <button onClick={marcarTodas} className="text-[10px] text-indigo-400 hover:text-indigo-300">Marcar todas lidas</button>}
            </div>
            {notificacoes.length === 0 ? (
              <p className="text-xs text-neutral-500 text-center py-6">Nenhuma notificação</p>
            ) : (
              notificacoes.map(n => (
                <button key={n.id} onClick={() => abrir(n)}
                  className={`w-full text-left px-3 py-2 border-b border-neutral-800/50 hover:bg-neutral-800 ${!n.lida ? "bg-neutral-800/40" : ""}`}>
                  <p className="text-xs text-neutral-200">{n.titulo}</p>
                  {n.mensagem && <p className="text-[10px] text-neutral-500 mt-0.5">{n.mensagem}</p>}
                  <p className="text-[9px] text-neutral-600 mt-0.5">{new Date(n.created_at).toLocaleString("pt-BR")}</p>
                </button>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}
