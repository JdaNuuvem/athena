"use client";

import { useState } from "react";
import FluxoCaixaTab from "./_components/FluxoCaixaTab";
import ReceberTab from "./_components/ReceberTab";
import PagarTab from "./_components/PagarTab";
import BoletosTab from "./_components/BoletosTab";
import PIXTab from "./_components/PIXTab";
import ConciliacaoTab from "./_components/ConciliacaoTab";
import BancoTab from "./_components/BancoTab";
import DRETab from "./_components/DRETab";

const TABS = [
  { key: "fluxo_caixa", label: "Fluxo Caixa" },
  { key: "receber", label: "Receber" },
  { key: "pagar", label: "Pagar" },
  { key: "boletos", label: "Boletos" },
  { key: "pix", label: "PIX" },
  { key: "conciliacao", label: "Conciliação" },
  { key: "banco", label: "Banco" },
  { key: "dre", label: "DRE" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export default function FinanceiroPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("fluxo_caixa");

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">Financeiro</h1>
        <p className="text-xs text-neutral-500 mt-1">Fluxo de caixa, contas a pagar/receber e DRE</p>
      </div>
      <div className="flex flex-wrap gap-1 bg-neutral-800 rounded-lg p-1">
        {TABS.map((tab) => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)}
            className={`px-3 py-1.5 text-xs rounded-md transition-colors ${activeTab === tab.key ? "bg-indigo-600 text-white" : "text-neutral-400 hover:text-neutral-200"}`}>{tab.label}</button>
        ))}</div>
      <div>
        {activeTab === "fluxo_caixa" && <FluxoCaixaTab />}
        {activeTab === "receber" && <ReceberTab />}
        {activeTab === "pagar" && <PagarTab />}
        {activeTab === "boletos" && <BoletosTab />}
        {activeTab === "pix" && <PIXTab />}
        {activeTab === "conciliacao" && <ConciliacaoTab />}
        {activeTab === "banco" && <BancoTab />}
        {activeTab === "dre" && <DRETab />}
      </div>
    </div>
  );
}
