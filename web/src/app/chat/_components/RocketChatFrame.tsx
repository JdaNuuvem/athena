"use client";

import { useCallback, useEffect, useState } from "react";

const ROCKETCHAT_URL = process.env.NEXT_PUBLIC_ROCKETCHAT_URL;
const TIMEOUT_MS = 5000;

type Status = "nao_configurado" | "carregando" | "indisponivel" | "pronto";

async function estaDisponivel(url: string): Promise<boolean> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    // no-cors: nao precisamos ler a resposta, so' confirmar que o host
    // responde. Evita depender de CORS habilitado no Rocket.Chat — um
    // fetch no-cors resolve pra qualquer resposta HTTP alcancada e so'
    // rejeita em falha real de rede/timeout.
    await fetch(`${url}/api/v1/info`, {
      mode: "no-cors",
      cache: "no-store",
      signal: controller.signal,
    });
    return true;
  } catch {
    return false;
  } finally {
    clearTimeout(timeout);
  }
}

export default function RocketChatFrame() {
  const [status, setStatus] = useState<Status>(ROCKETCHAT_URL ? "carregando" : "nao_configurado");

  const verificar = useCallback(() => {
    if (!ROCKETCHAT_URL) {
      setStatus("nao_configurado");
      return;
    }
    setStatus("carregando");
    estaDisponivel(ROCKETCHAT_URL).then((ok) => setStatus(ok ? "pronto" : "indisponivel"));
  }, []);

  useEffect(() => {
    verificar();
  }, [verificar]);

  if (status === "nao_configurado") {
    return (
      <div className="h-screen w-full flex items-center justify-center text-neutral-500 text-sm">
        Chat não configurado (NEXT_PUBLIC_ROCKETCHAT_URL ausente).
      </div>
    );
  }

  if (status === "carregando") {
    return (
      <div className="h-screen w-full flex items-center justify-center text-neutral-500 text-sm">
        Carregando chat...
      </div>
    );
  }

  if (status === "indisponivel") {
    return (
      <div className="h-screen w-full flex flex-col items-center justify-center gap-3 text-neutral-500 text-sm">
        <span>Chat indisponível no momento.</span>
        <button
          onClick={verificar}
          className="px-3 py-1.5 rounded bg-neutral-800 text-neutral-200 text-xs hover:bg-neutral-750 transition-colors"
        >
          Tentar novamente
        </button>
      </div>
    );
  }

  return (
    <iframe
      src={`${ROCKETCHAT_URL}?layout=embedded`}
      title="Chat"
      className="h-screen w-full border-0"
      allow="camera; microphone; display-capture; clipboard-write"
    />
  );
}
