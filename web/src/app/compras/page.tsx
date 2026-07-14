"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

const SUBMENU = [
  { href: "/compras/fornecedores", label: "Fornecedores", color: "bg-blue-600" },
  { href: "/compras/solicitacoes", label: "Solicitacoes", color: "bg-amber-600" },
  { href: "/compras/cotacoes", label: "Cotacoes", color: "bg-purple-600" },
  { href: "/compras/pedidos", label: "Pedidos Compra", color: "bg-emerald-600" },
  { href: "/compras/recebimentos", label: "Recebimento", color: "bg-teal-600" },
  { href: "/compras/notas", label: "Notas Entrada", color: "bg-pink-600" },
];

export default function ComprasPage() {
  const [dash, setDash] = useState<{pendentes:number;pedidos_abertos:number;total_recebido:number} | null>(null);

  useEffect(() => {
    fetch("/api/compras/dashboard")
      .then(r => r.json())
      .then(d => setDash(d))
      .catch(() => {});
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div><h1 className="text-lg font-bold text-neutral-100">Compras</h1><p className="text-xs text-neutral-500 mt-1">Solicitacoes, cotacoes, pedidos e recebimento</p></div>
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Solicitacoes Pendentes</p>
          <p className="text-xl font-bold text-amber-400">{dash?.pendentes ?? 0}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Pedidos Abertos</p>
          <p className="text-xl font-bold text-emerald-400">{dash?.pedidos_abertos ?? 0}</p>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
          <p className="text-xs text-neutral-500">Total Recebido</p>
          <p className="text-xl font-bold text-blue-400">R$ {(dash?.total_recebido ?? 0).toLocaleString("pt-BR",{minimumFractionDigits:2})}</p>
        </div>
      </div>
      <div>
        <h2 className="text-sm font-semibold text-neutral-300 mb-3">Modulos</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {SUBMENU.map(m => (
            <Link key={m.href} href={m.href} className={m.color + " hover:opacity-90 text-white rounded-lg p-4 transition-opacity"}>
              <p className="text-sm font-semibold">{m.label}</p>
              <p className="text-[10px] opacity-80 mt-1">Gerenciar {m.label.toLowerCase()}</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
