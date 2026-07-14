"use client";

import { useState } from "react";

const WORKFLOWS = [
  { id: "lote_para_estoque", label: "Lote → Inspeção → Estoque", input: "lote_id" },
  { id: "defeito_para_capa", label: "Defeito → CAPA", input: "inspecao_id" },
  { id: "manutencao_molde", label: "Manutenção → Produção", input: "molde_id" },
  { id: "agenda_manutencao", label: "Alertas → Agenda", input: null },
  { id: "ag07_para_ag04", label: "AG-07 → AG-04 (Aprovação → Produção)", input: "pipeline_id" },
  { id: "ag06_para_ag04", label: "AG-06 → AG-04 (Pedido → Produção)", input: "pedido_id" },
  { id: "cnc_concluido", label: "CNC Job → Molde", input: "job_id" },
];

export default function WorkflowsPage() {
  const [results, setResults] = useState<Record<string, string>>({});
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});

  const execute = async (wfId: string) => {
    const wf = WORKFLOWS.find((w) => w.id === wfId);
    if (!wf) return;

    if (wf.input && !inputs[wfId]?.trim()) {
      setResults((r) => ({ ...r, [wfId]: `Campo "${wf.input.replace(/_/g, " ")}" é obrigatório` }));
      return;
    }

    const token = localStorage.getItem("token");
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    setLoading((l) => ({ ...l, [wfId]: true }));
    setResults((r) => ({ ...r, [wfId]: "Executando..." }));

    try {
      const url = wf.input
        ? `/api/workflows/${wfId}/${inputs[wfId].trim()}`
        : `/api/workflows/${wfId}`;

      const res = await fetch(url, { method: "POST", headers, body: wf.input ? undefined : "{}" });
      const data = await res.json();
      setResults((r) => ({ ...r, [wfId]: JSON.stringify(data, null, 2) }));
    } catch (err) {
      setResults((r) => ({ ...r, [wfId]: String(err) }));
    } finally {
      setLoading((l) => ({ ...l, [wfId]: false }));
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <h1 className="text-lg font-light text-neutral-300">Workflows</h1>

      <div className="grid gap-3">
        {WORKFLOWS.map((wf) => (
          <div key={wf.id} className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-medium text-neutral-200">{wf.label}</h3>
                <span className="text-[10px] text-neutral-500 font-mono mt-0.5 block">{wf.id}</span>

                {wf.input && (
                  <div className="mt-3">
                    <label
                      htmlFor={`wf-input-${wf.id}`}
                      className="text-[10px] text-neutral-500 uppercase tracking-wider block mb-1"
                    >
                      {wf.input.replace(/_/g, " ")}
                    </label>
                    <input
                      id={`wf-input-${wf.id}`}
                      type="text"
                      value={inputs[wf.id] || ""}
                      onChange={(e) => setInputs((prev) => ({ ...prev, [wf.id]: e.target.value }))}
                      onKeyDown={(e) => e.key === "Enter" && execute(wf.id)}
                      placeholder={`ID do ${wf.input.replace(/_/g, " ")}`}
                      className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-transparent"
                    />
                  </div>
                )}
              </div>

              <button
                onClick={() => execute(wf.id)}
                disabled={loading[wf.id]}
                className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs px-4 py-2 rounded-lg transition-colors shrink-0 mt-0.5"
              >
                {loading[wf.id] ? "..." : "Executar"}
              </button>
            </div>

            {results[wf.id] && (
              <pre className="mt-3 bg-neutral-950 border border-neutral-800 rounded-lg p-3 text-xs text-neutral-400 font-mono overflow-auto max-h-40">
                {results[wf.id]}
              </pre>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
