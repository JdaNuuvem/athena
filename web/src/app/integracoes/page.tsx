"use client";

import { useState, useEffect } from "react";
import { api, type Integration } from "@/lib/api";

const INTEGRATION_LINKS: Record<string, string> = {
  bling: "/integracoes/bling",
  shopee: "/integracoes/shopee",
  hermes: "/integracoes/hermes",
  "shopee-ads": "/integracoes/shopee-ads",
};

export default function IntegracoesPage() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);

  useEffect(() => {
    api.integrations().then(setIntegrations).catch(console.error);
  }, []);

  const grouped = integrations.reduce(
    (acc, i) => {
      const cat = i.category;
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(i);
      return acc;
    },
    {} as Record<string, Integration[]>,
  );

  const categoryLabels: Record<string, string> = {
    erp: "ERP",
    ecommerce: "E-commerce",
    ai: "AI",
    payment: "Pagamento",
    logistics: "Logística",
    communication: "Comunicação",
    analytics: "Analytics",
  };

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <h1 className="text-lg font-light text-neutral-300">Integrações</h1>

      {Object.entries(grouped).map(([cat, items]) => (
        <section key={cat}>
          <h2 className="text-xs text-neutral-500 uppercase tracking-wider mb-3">{categoryLabels[cat] || cat}</h2>
          <div className="grid gap-3">
            {items.map((i) => {
              const link = INTEGRATION_LINKS[i.id];
              const content = (
                <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 hover:border-neutral-700 transition-colors">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-medium text-neutral-200">{i.name}</h3>
                      <span className="text-[10px] text-neutral-500">{i.id}</span>
                    </div>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full ${
                        i.status === "connected" ? "bg-green-900/50 text-green-400" : "bg-neutral-800 text-neutral-400"
                      }`}
                    >
                      {i.status === "connected" ? "Conectado" : "Desconectado"}
                    </span>
                  </div>
                </div>
              );

              return link ? (
                <a key={i.id} href={link}>
                  {content}
                </a>
              ) : (
                <div key={i.id}>{content}</div>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
