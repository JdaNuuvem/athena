"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

export default function ShopeeAdsPage() {
  const [campaigns, setCampaigns] = useState<Record<string, unknown>[]>([]);

  useEffect(() => {
    api.shopeeAdsCampaigns()
      .then((c) => setCampaigns(c as Record<string, unknown>[]))
      .catch(() => {});
  }, []);

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div>
        <a href="/integracoes" className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors">← Integrações</a>
        <h1 className="text-lg font-light text-neutral-300 mt-1">Shopee Ads</h1>
      </div>

      <section>
        <h2 className="text-xs text-neutral-500 uppercase tracking-wider mb-2">Campanhas ({campaigns.length})</h2>
        {campaigns.length === 0 ? (
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 text-center text-neutral-500 text-sm">
            Nenhuma campanha encontrada. Sincronize os anúncios primeiro.
          </div>
        ) : (
          <div className="grid gap-3">
            {campaigns.map((c, i) => (
              <div key={i} className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm text-neutral-200">{c.nome as string}</h3>
                    <span className="text-[10px] text-neutral-500 numeric">{c.campaign_id as string}</span>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-green-900/50 text-green-400">{c.status as string}</span>
                </div>
                {Boolean(c.daily_budget) && (
                  <div className="mt-2 text-xs text-neutral-500">
                    Budget diário: <span className="text-neutral-300 numeric">R$ {Number(c.daily_budget ?? 0).toFixed(2)}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
