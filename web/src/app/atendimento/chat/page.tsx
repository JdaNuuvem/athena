"use client";

import { useState, useEffect, useRef } from "react";

interface Mensagem { id: number; texto?: string; descricao?: string; remetente: string; canal: string; data: string; }

export default function ChatPage() {
  const [mensagens, setMensagens] = useState<Mensagem[]>([]);
  const [texto, setTexto] = useState("");
  const [canal, setCanal] = useState("chat");
  const ref = useRef<HTMLDivElement>(null);

  const carregar = () => {
    fetch("/api/atendimento/tickets?tipo=chat&limit=50").then(r => r.json()).then(d => {
      setMensagens(d.data || []);
    }).catch(() => {});
  };

  useEffect(() => { carregar(); const t = setInterval(carregar, 10000); return () => clearInterval(t); }, []);

  useEffect(() => { ref.current?.scrollIntoView({ behavior: "smooth" }); }, [mensagens]);

  const enviar = async () => {
    if (!texto.trim()) return;
    try {
      await fetch("/api/atendimento/tickets", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ descricao: texto, canal, tipo: "chat", prioridade: "normal" }),
      });
      setTexto(""); carregar();
    } catch {}
  };

  return (
    <div className="h-screen flex flex-col">
      <div className="bg-neutral-900 border-b border-neutral-800 px-4 py-3 shrink-0">
        <h1 className="text-sm font-bold text-neutral-200">Chat ao Vivo</h1>
        <select value={canal} onChange={e => setCanal(e.target.value)}
          className="mt-1 bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200">
          {["chat","whatsapp","telegram","instagram","facebook"].map(c => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {mensagens.map(m => (
          <div key={m.id} className={`max-w-[70%] rounded-lg px-3 py-2 text-sm ${m.remetente === "cliente" ? "bg-neutral-700 text-neutral-200 ml-0" : "bg-indigo-700 text-white ml-auto"}`}>
            <p>{m.texto || m.descricao}</p>
            <p className="text-[10px] opacity-60 mt-0.5">{m.data?.slice(11,16) || ""}</p>
          </div>
        ))}
        <div ref={ref} />
      </div>

      <div className="p-3 border-t border-neutral-800 shrink-0 flex gap-2">
        <input type="text" value={texto} onChange={e => setTexto(e.target.value)}
          onKeyDown={e => e.key === "Enter" && enviar()}
          placeholder="Digite sua mensagem..." autoFocus
          className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200" />
        <button onClick={enviar} className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm px-4 py-2 rounded-lg">Enviar</button>
      </div>
    </div>
  );
}
