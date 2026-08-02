"use client";
import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useChatSocket, type EventoChatSocket } from "@/lib/useChatSocket";
import type { ConversaChat, MensagemChat } from "@/lib/types/chat";
import ConversaSidebar from "./_components/ConversaSidebar";
import MensagensPainel from "./_components/MensagensPainel";
import ThreadPainel from "./_components/ThreadPainel";
import NovaConversaModal from "./_components/NovaConversaModal";

export default function ChatPage() {
  const { user } = useAuth();
  const usuarioIdAtual = user ? parseInt(user.id, 10) : null;
  const { conectado, on, enviarMensagem, marcarDigitando, marcarLido } = useChatSocket();

  const [conversas, setConversas] = useState<ConversaChat[]>([]);
  const [conversaSelecionada, setConversaSelecionada] = useState<ConversaChat | null>(null);
  const [mensagens, setMensagens] = useState<MensagemChat[]>([]);
  const [threadAberta, setThreadAberta] = useState<MensagemChat | null>(null);
  const [digitandoUserId, setDigitandoUserId] = useState<number | null>(null);
  const [presencas, setPresencas] = useState<Record<number, string>>({});
  const [novaConversaAberta, setNovaConversaAberta] = useState(false);
  const [carregandoConversas, setCarregandoConversas] = useState(true);
  const [erroConversas, setErroConversas] = useState("");

  const carregarConversas = useCallback(() => {
    api.chat.listarConversas()
      .then((r) => { setConversas(r.data); setErroConversas(""); })
      .catch((e) => setErroConversas(e instanceof Error ? e.message : "Erro ao carregar conversas"))
      .finally(() => setCarregandoConversas(false));
  }, []);

  useEffect(() => { carregarConversas(); }, [carregarConversas]);

  const selecionarConversa = useCallback((conversa: ConversaChat) => {
    setConversaSelecionada(conversa);
    setThreadAberta(null);
    api.chat.listarMensagens(conversa.id).then((r) => setMensagens(r.data)).catch(() => {});
  }, []);

  const aoCriarConversa = useCallback((conversa: ConversaChat) => {
    setNovaConversaAberta(false);
    setConversas((atual) => (atual.some((c) => c.id === conversa.id && c.tipo === conversa.tipo) ? atual : [conversa, ...atual]));
    selecionarConversa(conversa);
  }, [selecionarConversa]);

  useEffect(() => {
    return on((evento: EventoChatSocket) => {
      if (evento.evento === "nova_mensagem") {
        const mensagem = evento.mensagem as MensagemChat;
        if (conversaSelecionada && mensagem.conversa_id === conversaSelecionada.id) {
          setMensagens((atual) => [...atual, mensagem]);
        }
        carregarConversas();
      }
      if (evento.evento === "presenca_atualizada") {
        setPresencas((atual) => ({ ...atual, [evento.user_id as number]: evento.status as string }));
      }
      if (evento.evento === "mensagem_editada" || evento.evento === "mensagem_excluida") {
        const mensagem = evento.mensagem as MensagemChat;
        if (conversaSelecionada && mensagem.conversa_id === conversaSelecionada.id) {
          setMensagens((atual) => atual.map((m) => (m.id === mensagem.id ? mensagem : m)));
        }
      }
      if (evento.evento === "usuario_digitando" && conversaSelecionada && evento.conversa_id === conversaSelecionada.id) {
        setDigitandoUserId(evento.user_id as number);
        setTimeout(() => setDigitandoUserId(null), 3000);
      }
    });
  }, [on, conversaSelecionada, carregarConversas]);

  const enviar = (texto: string, anexoId?: number) => {
    if (!conversaSelecionada) return;
    if (conversaSelecionada.tipo === "ticket") {
      api.chat.enviarMensagem(conversaSelecionada.id, texto, anexoId)
        .catch((e) => alert(e instanceof Error ? e.message : "Erro ao enviar mensagem"));
      return;
    }
    enviarMensagem(conversaSelecionada.id, texto, anexoId);
  };

  const enviarRespostaThread = (texto: string, threadPaiId: number) => {
    if (!conversaSelecionada) return;
    enviarMensagem(conversaSelecionada.id, texto, undefined, threadPaiId);
  };

  const upload = async (arquivo: File) => {
    const anexo = await api.chat.uploadAnexo(arquivo);
    return anexo.id;
  };

  useEffect(() => {
    if (!conversaSelecionada) return;
    const ultima = mensagens[mensagens.length - 1];
    if (ultima) marcarLido(conversaSelecionada.id, ultima.id);
  }, [mensagens, conversaSelecionada, marcarLido]);

  return (
    <div className="h-screen flex">
      <ConversaSidebar
        conversas={conversas}
        conversaSelecionadaId={conversaSelecionada?.id ?? null}
        onSelecionar={selecionarConversa}
        presencas={presencas}
        onNovaConversa={() => setNovaConversaAberta(true)}
        carregando={carregandoConversas}
        erro={erroConversas}
      />
      {novaConversaAberta && (
        <NovaConversaModal onFechar={() => setNovaConversaAberta(false)} onCriada={aoCriarConversa} />
      )}
      {conversaSelecionada ? (
        <MensagensPainel
          conversa={conversaSelecionada}
          mensagens={mensagens}
          usuarioIdAtual={usuarioIdAtual}
          digitandoUserId={digitandoUserId}
          onEnviar={enviar}
          onAbrirThread={setThreadAberta}
          onUpload={upload}
        />
      ) : (
        <div className="flex-1 flex items-center justify-center text-neutral-500 text-sm">
          Selecione uma conversa
        </div>
      )}
      {threadAberta && (
        <ThreadPainel
          mensagemPai={threadAberta}
          onFechar={() => setThreadAberta(null)}
          onEnviarResposta={enviarRespostaThread}
        />
      )}
      {!conectado && (
        <div className="fixed bottom-3 right-3 bg-amber-600 text-white text-xs px-3 py-1.5 rounded-lg">
          Reconectando...
        </div>
      )}
    </div>
  );
}
