"use client";

import { useState } from "react";
import BlingDashboard from "./_components/BlingDashboard";
import BlingProductsTab from "./_components/BlingProductsTab";
import BlingVendasTab from "./_components/BlingVendasTab";
import BlingOrdersTab from "./_components/BlingOrdersTab";
import BlingFinancialTab from "./_components/BlingFinancialTab";
import BlingConfigTab from "./_components/BlingConfigTab";
import ProductFormModal from "./_components/ProductFormModal";
import BulkStockModal from "./_components/BulkStockModal";

const TABS = [
  { key: "dashboard", label: "📊 Dashboard" },
  { key: "produtos", label: "📦 Produtos" },
  { key: "vendas", label: "📈 Vendas" },
  { key: "pedidos", label: "📋 Pedidos" },
  { key: "financeiro", label: "💳 Financeiro" },
  { key: "config", label: "⚙️ Config" },
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
            className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
              activeTab === tab.key
                ? "bg-indigo-600 text-white"
                : "text-neutral-400 hover:text-neutral-200"
            }`}
          >
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
