"use client";

import { useState } from "react";
import EmpresasTab from "./_components/EmpresasTab";
import UsuariosTab from "./_components/UsuariosTab";
import ClientesTab from "./_components/ClientesTab";
import FornecedoresTab from "./_components/FornecedoresTab";
import TransportadorasTab from "./_components/TransportadorasTab";
import VendedoresTab from "./_components/VendedoresTab";

const TABS = [
  { key: "empresas", label: "Empresas" },
  { key: "usuarios", label: "Usuários" },
  { key: "clientes", label: "Clientes" },
  { key: "fornecedores", label: "Fornecedores" },
  { key: "transportadoras", label: "Transportadoras" },
  { key: "vendedores", label: "Vendedores" },
];

export default function CadastrosPage() {
  const [activeTab, setActiveTab] = useState("empresas");

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">Cadastros</h1>
        <p className="text-xs text-neutral-500 mt-1">Gerencie empresas, usuários, clientes, fornecedores, transportadoras e vendedores</p>
      </div>

      <nav className="flex border-b border-neutral-700 gap-0">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-xs font-medium transition-colors border-b-2 -mb-[1px] ${
              activeTab === tab.key
                ? "border-indigo-500 text-indigo-300"
                : "border-transparent text-neutral-400 hover:text-neutral-200 hover:border-neutral-500"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div>
        {activeTab === "empresas" && <EmpresasTab />}
        {activeTab === "usuarios" && <UsuariosTab />}
        {activeTab === "clientes" && <ClientesTab />}
        {activeTab === "fornecedores" && <FornecedoresTab />}
        {activeTab === "transportadoras" && <TransportadorasTab />}
        {activeTab === "vendedores" && <VendedoresTab />}
      </div>
    </div>
  );
}
