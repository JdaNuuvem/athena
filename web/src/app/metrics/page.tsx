"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

export default function MetricsPage() {
  const [lojas, setLojas] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.lojas(30)])
      .then(([l]) => setLojas(l as Record<string, unknown>[]))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6 text-neutral-500">Carregando...</div>;

  const fisicas = lojas.filter((l) => l.tipo === "fisica");
  const digitais = lojas.filter((l) => l.tipo === "digital");

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <h1 className="text-lg font-light text-neutral-300">Métricas</h1>

      <section>
        <h2 className="text-sm font-medium text-neutral-400 mb-3">Lojas Físicas</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {fisicas.map((loja) => (
            <div key={loja.id as number} className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
              <h3 className="text-sm font-medium text-neutral-200">{loja.nome as string}</h3>
              <div className="mt-3 space-y-1 text-xs text-neutral-400">
                <div className="flex justify-between">
                  <span>Receita</span>
                  <span className="text-neutral-200 numeric">R$ {Number(loja.receita).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="flex justify-between">
                  <span>Pedidos</span>
                  <span className="text-neutral-200 numeric">{String(loja.pedidos)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Ticket médio</span>
                  <span className="text-neutral-200 numeric">R$ {Number(loja.ticket_medio).toFixed(2)}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-medium text-neutral-400 mb-3">Marketplaces</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {digitais.map((mp) => (
            <div key={mp.id as number} className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
              <h3 className="text-sm font-medium text-neutral-200 capitalize">{mp.nome as string}</h3>
              <div className="mt-3 space-y-1 text-xs text-neutral-400">
                <div className="flex justify-between">
                  <span>Receita</span>
                  <span className="text-neutral-200 numeric">R$ {Number(mp.receita).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="flex justify-between">
                  <span>Pedidos</span>
                  <span className="text-neutral-200 numeric">{String(mp.pedidos)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Ticket médio</span>
                  <span className="text-neutral-200 numeric">R$ {Number(mp.ticket_medio).toFixed(2)}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
