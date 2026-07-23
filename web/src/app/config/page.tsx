"use client";

import { useState, useEffect } from "react";

export default function ConfigPage() {
  const [config, setConfig] = useState<any>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/config").then(r => r.json()).then(d => { setConfig(d); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  const salvar = async (section: string, data: Record<string, string>) => {
    try {
      await fetch("/api/config/" + section, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      alert("Salvo com sucesso");
    } catch { alert("Erro ao salvar"); }
  };

  if (loading) return <div className="p-6 text-neutral-500 text-sm">Carregando...</div>;

  return (
    <div className="p-6 space-y-6 max-w-2xl">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">Configuracoes</h1>
        <p className="text-xs text-neutral-500 mt-1">Ajustes do sistema</p>
      </div>

      <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3">
        <h2 className="text-sm font-semibold text-neutral-300">Margem Minima</h2>
        <p className="text-xs text-neutral-500">Percentual minimo de margem para alertas de produtos com baixa rentabilidade.</p>
        <div className="flex gap-2">
          <input type="number" defaultValue={config.margem_minima_pct || 15}
            id="margem" className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 w-24" />
          <span className="text-neutral-400 text-sm self-center">%</span>
          <button onClick={() => {
            const v = (document.getElementById("margem") as HTMLInputElement).value;
            salvar("geral", { margem_minima_pct: v });
          }} className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm px-4 py-2 rounded-lg">Salvar</button>
        </div>
      </div>

      <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3">
        <h2 className="text-sm font-semibold text-neutral-300">Integracoes</h2>
        <p className="text-xs text-neutral-500">Configure as integracoes com marketplaces e ERPs nas paginas especificas:</p>
        <div className="flex gap-2 flex-wrap">
          <a href="/integracoes/bling" className="text-xs text-indigo-400 hover:text-indigo-300 bg-neutral-800 px-3 py-1.5 rounded-lg">Bling</a>
          <a href="/integracoes/shopee" className="text-xs text-indigo-400 hover:text-indigo-300 bg-neutral-800 px-3 py-1.5 rounded-lg">Shopee</a>
          <a href="/lojas" className="text-xs text-indigo-400 hover:text-indigo-300 bg-neutral-800 px-3 py-1.5 rounded-lg">Lojas</a>
        </div>
      </div>
    </div>
  );
}
