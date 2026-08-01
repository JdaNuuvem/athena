"use client";

import { useState } from "react";
import Icon from "@/app/_components/Icon";
import BlingDashboard from "./_components/BlingDashboard";
import BlingProductsTab from "./_components/BlingProductsTab";
import BlingVendasTab from "./_components/BlingVendasTab";
import BlingOrdersTab from "./_components/BlingOrdersTab";
import BlingFinancialTab from "./_components/BlingFinancialTab";
import BlingConfigTab from "./_components/BlingConfigTab";
import ProductFormModal from "./_components/ProductFormModal";
import BulkStockModal from "./_components/BulkStockModal";

const TABS = [
  { key: "dashboard", label: "Dashboard", icon: "dashboard" },
  { key: "produtos", label: "Produtos", icon: "produtos" },
  { key: "vendas", label: "Vendas", icon: "vendas" },
  { key: "pedidos", label: "Pedidos", icon: "inbox" },
  { key: "financeiro", label: "Financeiro", icon: "financeiro" },
  { key: "config", label: "Config", icon: "__gear__" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export default function BlingPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("dashboard");
  const [showProductForm, setShowProductForm] = useState(false);
  const [showStockModal, setShowStockModal] = useState(false);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">Bling</h1>
        <p className="text-xs text-neutral-500">Integração ERP — Produtos, Vendas, Estoque</p>
      </div>

      <div className="flex flex-wrap gap-1 bg-neutral-800 rounded-lg p-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md transition-colors ${
              activeTab === tab.key
                ? "bg-indigo-600 text-white"
                : "text-neutral-400 hover:text-neutral-200"
            }`}
          >
            {tab.icon === "__gear__" ? (
              <svg xmlns="http://www.w3.org/2000/svg" width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
                <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            ) : (
              <Icon name={tab.icon} size={14} />
            )}
            {tab.label}
          </button>
        ))}
      </div>

      <div>
        {activeTab === "dashboard" && <BlingDashboard />}
        {activeTab === "produtos" && <BlingProductsTab onNewProduct={() => setShowProductForm(true)} onStockManage={() => setShowStockModal(true)} />}
        {activeTab === "vendas" && <BlingVendasTab />}
        {activeTab === "pedidos" && <BlingOrdersTab />}
        {activeTab === "financeiro" && <BlingFinancialTab />}
        {activeTab === "config" && <BlingConfigTab />}
      </div>

      {showProductForm && (
        <ProductFormModal
          onClose={() => setShowProductForm(false)}
          onSaved={() => setShowProductForm(false)}
        />
      )}
      {showStockModal && (
        <BulkStockModal onClose={() => setShowStockModal(false)} />
      )}
    </div>
  );
}
