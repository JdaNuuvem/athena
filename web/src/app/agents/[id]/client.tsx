"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, type Agent } from "@/lib/api";

export default function AgentClientPage() {
  const { id } = useParams<{ id: string }>();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [response, setResponse] = useState<string>("");
  const [input, setInput] = useState("");

  useEffect(() => {
    api.agentsList().then((r) => {
      const found = r.agents.find((a) => a.id === id || a.id === `ag-${id}`);
      if (found) setAgent(found);
    });
  }, [id]);

  const executeAction = async (action: string) => {
    setResponse("Executando...");
    try {
      const r = await api.hermesExecute(id, action);
      setResponse(JSON.stringify(r.data || r, null, 2));
    } catch (err) {
      setResponse(String(err));
    }
  };

  const sendChat = async () => {
    if (!input.trim()) return;
    setResponse("Processando...");
    try {
      const r = await api.chat(input);
      setResponse(r.resposta);
    } catch (err) {
      setResponse(String(err));
    }
    setInput("");
  };

  const agentName = agent?.name || id;

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <div>
        <Link href="/agents" className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors">
          ← Agentes
        </Link>
        <h1 className="text-lg font-light text-neutral-300 mt-1">{agentName}</h1>
        {agent && (
          <div className="flex items-center gap-3 mt-2">
            <span
              aria-hidden="true"
              className={`inline-block w-2 h-2 rounded-full shrink-0 ${
                agent.status === "running" ? "bg-green-500" : "bg-yellow-500"
              }`}
            />
            <span className="text-xs text-neutral-400">{agent.status}</span>
            <span className="text-xs text-neutral-500">{agent.role}</span>
            <span className="text-xs text-neutral-500">{agent.context}</span>
          </div>
        )}
      </div>

      <section>
        <h2 className="text-sm font-medium text-neutral-400 mb-2">Ações rápidas</h2>
        <div className="flex flex-wrap gap-2">
          {["executar_cacada", "relatorio_diario", "verificar_alertas", "processar_mensagem"].map((action) => (
            <button
              key={action}
              onClick={() => executeAction(action)}
              className="bg-neutral-800 hover:bg-neutral-700 text-xs text-neutral-300 px-3 py-1.5 rounded-lg border border-neutral-700 transition-colors"
            >
              {action.replace(/_/g, " ")}
            </button>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-medium text-neutral-400 mb-2">Chat com o agente</h2>
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendChat()}
            placeholder="Digite sua mensagem..."
            className="flex-1 bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-transparent"
          />
          <button
            onClick={sendChat}
            className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 rounded-lg text-sm transition-colors"
          >
            Enviar
          </button>
        </div>
      </section>

      {response && (
        <section>
          <h2 className="text-xs text-neutral-500 uppercase tracking-wider mb-2">Resposta</h2>
          <pre className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 text-xs text-neutral-300 overflow-auto max-h-96 font-mono whitespace-pre-wrap">
            {response}
          </pre>
        </section>
      )}
    </div>
  );
}
