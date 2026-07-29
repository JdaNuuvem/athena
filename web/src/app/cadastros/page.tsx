"use client";

import { useState } from "react";
import Icon from "../_components/Icon";
import EmpresasTab from "./_components/EmpresasTab";
import UsuariosTab from "./_components/UsuariosTab";
import ClientesTab from "./_components/ClientesTab";
import FornecedoresTab from "./_components/FornecedoresTab";
import TransportadorasTab from "./_components/TransportadorasTab";
import VendedoresTab from "./_components/VendedoresTab";

const TABS = [
  { key: "empresas", label: "Empresas", icon: "building", Component: EmpresasTab },
  { key: "usuarios", label: "Usuários", icon: "user", Component: UsuariosTab },
  { key: "clientes", label: "Clientes", icon: "crm", Component: ClientesTab },
  { key: "fornecedores", label: "Fornecedores", icon: "compras", Component: FornecedoresTab },
  { key: "transportadoras", label: "Transportadoras", icon: "truck", Component: TransportadorasTab },
  { key: "vendedores", label: "Vendedores", icon: "userStar", Component: VendedoresTab },
];

export default function CadastrosPage() {
  const [activeTab, setActiveTab] = useState("empresas");
  const active = TABS.find((t) => t.key === activeTab) ?? TABS[0];

  return (
    <div className="p-6 space-y-5 max-w-[1400px]">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400">
          <Icon name="cadastros" size={20} />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-neutral-100">Cadastros</h1>
          <p className="text-xs text-neutral-500">Empresas, usuários, clientes, fornecedores, transportadoras e vendedores</p>
        </div>
      </div>

      <nav className="flex flex-wrap gap-1 rounded-xl border border-neutral-800 bg-neutral-900/50 p-1.5" aria-label="Categorias de cadastro">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            aria-current={activeTab === tab.key ? "page" : undefined}
            className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-medium transition-colors ${
              activeTab === tab.key
                ? "bg-indigo-600 text-white shadow-sm"
                : "text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200"
            }`}
          >
            <Icon name={tab.icon} size={15} />
            {tab.label}
          </button>
        ))}
      </nav>

      <active.Component key={active.key} />
    </div>
  );
}
