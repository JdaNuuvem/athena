"use client";

import { useState, useEffect } from "react";
import { Operador, FORMAS } from "./types";

export function OrcamentosTab({ caixa, operador, operadorSenha, onVendaCriada }: { caixa: any; operador: Operador; operadorSenha: string; onVendaCriada: () => void }) {
  const [orcamentos, setOrcamentos] = useState<any[]>([]);
  const [pgtoForma, setPgtoForma] = useState("dinheiro");

  const load = () => {
    fetch("/api/pdv/vendas?limit=30").then(r => r.json()).then(d => {
      setOrcamentos((d.data || []).filter((v: any) => v.status === "orcamento"));
    }).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const converter = async (id: number, total: number) => {
    if (!caixa) return alert("Abra o caixa primeiro!");
    try {
      const r = await fetch("/api/pdv/orcamento/" + id + "/converter", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ caixa_id: caixa.id, pagamentos: [{ forma: pgtoForma, valor: total }],
          operador: operador.nome, operador_id: operador.id }),
      });
      const d = await r.json();
      if (d.error) { alert(d.error); return; }
      alert(`Orcamento #${id} convertido em venda!`);
      load(); onVendaCriada();
    } catch { alert("Erro ao converter"); }
  };

  return (
    <div className="overflow-auto p-4">
      <h3 className="text-sm font-semibold text-neutral-200 mb-3">Orcamentos Pendentes</h3>
      {orcamentos.length === 0 && <p className="text-neutral-600 text-sm">Nenhum orcamento pendente.</p>}
      {orcamentos.map(o => (
        <div key={o.id} className="bg-neutral-800 border border-neutral-700 rounded-lg p-3 mb-2 flex items-center justify-between">
          <div>
            <span className="text-indigo-400 font-mono text-sm">#{o.id}</span>
            <span className="text-neutral-400 text-xs ml-3">{o.cliente || "Sem cliente"}</span>
            <span className="text-neutral-500 text-xs ml-3">{String(o.data || "").slice(0, 16)}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-emerald-400 font-medium text-sm">R$ {Number(o.total || 0).toFixed(2)}</span>
            <select value={pgtoForma} onChange={e => setPgtoForma(e.target.value)}
              className="bg-neutral-900 rounded px-2 py-1 text-xs text-neutral-200">
              {FORMAS.map(f => <option key={f} value={f}>{f.replace(/_/g, " ")}</option>)}
            </select>
            <button onClick={() => converter(o.id, o.total)}
              className="px-3 py-1 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">Converter em Venda</button>
          </div>
        </div>
      ))}
    </div>
  );
}
