"use client";
import { useState, useEffect } from "react";
import { api } from "@/lib/api";

export default function MemoryPage() {
  const [stats, setStats] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [recallQuery, setRecallQuery] = useState("");
  const [recallResults, setRecallResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    Promise.all([
      api.memoryStats().catch(() => ({})),
      api.memoryHistory().catch(() => ({ history: [] })),
    ]).then(([s, h]) => {
      setStats(s);
      setHistory((h as any).history || []);
    }).finally(() => setLoading(false));
  }, []);

  const handleRecall = async () => {
    if (!recallQuery.trim()) return;
    setSearching(true);
    try {
      const r = await api.memoryRecall(recallQuery);
      setRecallResults((r as any).results || []);
    } catch { setRecallResults([]); }
    finally { setSearching(false); }
  };

  if (loading) return <div className="p-6 text-neutral-500">Carregando...</div>;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">Memoria Corporativa</h1>
        <p className="text-xs text-neutral-500 mt-1">Stats, historico e busca semantica na memoria dos agentes</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Registros</p>
          <p className="text-xl font-bold text-blue-400">{stats?.total_entries ?? "—"}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Agentes</p>
          <p className="text-xl font-bold text-purple-400">{stats?.total_agents ?? "—"}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Categorias</p>
          <p className="text-xl font-bold text-emerald-400">{stats?.total_categories ?? "—"}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Ultima entrada</p>
          <p className="text-sm text-neutral-400 mt-1">{stats?.last_entry ? new Date(stats.last_entry).toLocaleDateString("pt-BR") : "—"}</p>
        </div>
      </div>

      <section>
        <h2 className="text-sm font-semibold text-neutral-300 mb-3">Buscar na Memoria</h2>
        <div className="flex gap-2">
          <input
            value={recallQuery}
            onChange={e => setRecallQuery(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleRecall()}
            placeholder="Digite para buscar memorias semanticamente..."
            className="flex-1 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-xs text-neutral-200 placeholder:text-neutral-600 focus:outline-none focus:border-neutral-600"
          />
          <button
            onClick={handleRecall}
            disabled={searching}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs px-4 py-2 rounded-lg"
          >
            {searching ? "..." : "Buscar"}
          </button>
        </div>
        {recallResults.length > 0 && (
          <div className="mt-3 space-y-2">
            {recallResults.map((r: any, i: number) => (
              <div key={i} className="bg-neutral-900 border border-neutral-800 rounded-lg px-4 py-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="bg-blue-500/10 text-blue-400 border border-blue-500/30 px-1.5 py-0.5 rounded text-[10px]">{r.category || r.agent_id || "—"}</span>
                  <span className="text-[10px] text-neutral-500">{r.timestamp ? new Date(r.timestamp).toLocaleString("pt-BR") : ""}</span>
                </div>
                <p className="text-xs text-neutral-300">{r.content || r.text || r.prompt || JSON.stringify(r).slice(0, 200)}</p>
              </div>
            ))}
          </div>
        )}
      </section>

      {history.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-neutral-300 mb-3">Historico Recente</h2>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead><tr className="border-b border-neutral-800 text-neutral-500">
                <th className="text-left p-2">Agente</th><th className="text-left p-2">Categoria</th><th className="text-left p-2">Prompt</th><th className="text-left p-2">Data</th>
              </tr></thead>
              <tbody>
                {history.map((h: any, i: number) => (
                  <tr key={i} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                    <td className="p-2 text-neutral-300">{h.agent_id || h.agente || "—"}</td>
                    <td className="p-2 text-neutral-400">{h.category || h.categoria || "—"}</td>
                    <td className="p-2 text-neutral-400 max-w-xs truncate">{h.prompt || h.content || "—"}</td>
                    <td className="p-2 text-neutral-500">{h.timestamp ? new Date(h.timestamp).toLocaleDateString("pt-BR") : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {!history.length && !recallResults.length && (
        <div className="text-neutral-600 text-sm text-center py-20">Nenhuma memoria registrada.</div>
      )}
    </div>
  );
}
