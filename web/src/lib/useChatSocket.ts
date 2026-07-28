"use client";
import { useEffect, useRef, useState, useCallback } from "react";

export interface EventoChatSocket {
  evento: "nova_mensagem" | "mensagem_editada" | "mensagem_excluida" | "usuario_digitando" | "presenca_atualizada" | "confirmacao_leitura";
  [chave: string]: unknown;
}

type Listener = (evento: EventoChatSocket) => void;

export function useChatSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const listenersRef = useRef<Set<Listener>>(new Set());
  const tentativasRef = useRef(0);
  const [conectado, setConectado] = useState(false);

  const conectar = useCallback(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) return;
    const protocolo = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocolo}//${window.location.host}/ws/chat?token=${encodeURIComponent(token)}`);

    ws.onopen = () => { setConectado(true); tentativasRef.current = 0; };
    ws.onmessage = (ev) => {
      try {
        const dados = JSON.parse(ev.data) as EventoChatSocket;
        listenersRef.current.forEach((fn) => fn(dados));
      } catch {
        // ignora payload invalido
      }
    };
    ws.onclose = () => {
      setConectado(false);
      const espera = Math.min(30000, 1000 * 2 ** tentativasRef.current);
      tentativasRef.current += 1;
      setTimeout(conectar, espera);
    };
    ws.onerror = () => ws.close();
    wsRef.current = ws;
  }, []);

  useEffect(() => {
    conectar();
    return () => { wsRef.current?.close(); };
  }, [conectar]);

  const enviar = useCallback((dados: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(dados));
    }
  }, []);

  const on = useCallback((fn: Listener) => {
    listenersRef.current.add(fn);
    return () => { listenersRef.current.delete(fn); };
  }, []);

  const enviarMensagem = useCallback(
    (conversaId: number, texto: string, anexoId?: number, threadPaiId?: number) => {
      enviar({ tipo: "enviar_mensagem", conversa_id: conversaId, texto, anexo_id: anexoId, thread_pai_id: threadPaiId });
    },
    [enviar]
  );

  const marcarDigitando = useCallback(
    (conversaId: number) => enviar({ tipo: "digitando", conversa_id: conversaId }),
    [enviar]
  );

  const marcarLido = useCallback(
    (conversaId: number, ultimaMensagemId: number) =>
      enviar({ tipo: "lido", conversa_id: conversaId, ultima_mensagem_id: ultimaMensagemId }),
    [enviar]
  );

  return { conectado, on, enviarMensagem, marcarDigitando, marcarLido };
}
