"use client";

import { useState, useRef, useEffect } from "react";

interface Message {
  id: string;
  role: "user" | "hermes";
  text: string;
  agent?: string;
}

export default function HermesPage() {
  const [messages, setMessages] = useState<Message[]>([
    { id: "0", role: "hermes", text: "Olá! Sou o Hermes, seu assistente de IA. Pergunte sobre produtos, vendas, finanças, produção ou qualquer análise do seu negócio.", agent: "diretor" },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");

    const userMsg: Message = { id: Date.now().toString(), role: "user", text };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await fetch("/api/hermes/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mensagem: text, user_id: "web", nome: "Admin" }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const hermesMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "hermes",
        text: data.resposta || "Sem resposta.",
        agent: data.agente,
      };
      setMessages((prev) => [...prev, hermesMsg]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { id: (Date.now() + 1).toString(), role: "hermes", text: `Erro: ${e instanceof Error ? e.message : "Falha na comunicação"}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-60px)]">
      {/* Header */}
      <div className="border-b border-neutral-800 px-6 py-3 flex items-center gap-3 shrink-0">
        <span className="text-lg">◈</span>
        <div>
          <h1 className="text-sm font-semibold text-neutral-200">Hermes</h1>
          <p className="text-[10px] text-neutral-500">Assistente IA — agentes de produto, finanças e marketing</p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : ""}`}>
            {msg.role === "hermes" && (
              <div className="w-8 h-8 rounded-full bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center shrink-0">
                <span className="text-xs">◈</span>
              </div>
            )}
            <div className={`max-w-[75%] ${msg.role === "user" ? "order-first" : ""}`}>
              {msg.agent && msg.role === "hermes" && (
                <div className="text-[10px] text-neutral-500 mb-1 ml-1">Agente: {msg.agent}</div>
              )}
              <div className={`rounded-xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-indigo-600 text-white rounded-br-md"
                  : "bg-neutral-800 border border-neutral-700 text-neutral-200 rounded-bl-md"
              }`}>
                {msg.text}
              </div>
            </div>
            {msg.role === "user" && (
              <div className="w-8 h-8 rounded-full bg-neutral-700 flex items-center justify-center shrink-0">
                <span className="text-xs text-neutral-400">A</span>
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center shrink-0">
              <span className="text-xs">◈</span>
            </div>
            <div className="bg-neutral-800 border border-neutral-700 rounded-xl px-4 py-2.5">
              <div className="flex gap-1.5">
                <div className="w-2 h-2 rounded-full bg-neutral-500 animate-bounce" style={{ animationDelay: "0ms" }} />
                <div className="w-2 h-2 rounded-full bg-neutral-500 animate-bounce" style={{ animationDelay: "150ms" }} />
                <div className="w-2 h-2 rounded-full bg-neutral-500 animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Sugestões */}
      {messages.length <= 1 && (
        <div className="px-6 pb-2">
          <div className="flex flex-wrap gap-2">
            {[
              "Qual produto devo lançar?",
              "Onde estamos perdendo dinheiro?",
              "Produtos em alta",
              "Preços dos concorrentes",
              "Melhor sequência de produção",
              "Margem dos produtos",
            ].map((q) => (
              <button
                key={q}
                onClick={() => { setInput(q); }}
                className="text-[10px] bg-neutral-800 border border-neutral-700 text-neutral-400 hover:text-neutral-200 hover:border-neutral-600 px-3 py-1.5 rounded-full transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="border-t border-neutral-800 px-4 py-3 shrink-0">
        <div className="flex gap-2 max-w-3xl mx-auto">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Pergunte algo para o Hermes..."
            disabled={loading}
            className="flex-1 bg-neutral-800 border border-neutral-700 rounded-xl px-4 py-2.5 text-sm text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500 disabled:opacity-50"
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white px-5 rounded-xl text-sm font-medium transition-colors"
          >
            Enviar
          </button>
        </div>
      </div>
    </div>
  );
}
