"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { fmtBRL as fmt } from "@/lib/format";
import SidebarLayout from "../../cadastros/_components/SidebarLayout";

const SUB_ITEMS = [
  { key: "conta", label: "Conta" },
  { key: "centro_custo", label: "Centro Custo" },
  { key: "plano_contas", label: "Plano Contas" },
];

interface Banco { id: number; nome: string; agencia: string; conta: string; saldo: number; status: string; }
interface CentroCusto { id: number; nome: string; codigo: string; descricao: string; status: string; }
interface PlanoContas { id: number; codigo: string; nome: string; tipo: string; natureza: string; }

export default function BancoTab() {
  const [bancos, setBancos] = useState<Banco[]>([]);
  const [centros, setCentros] = useState<CentroCusto[]>([]);
  const [plano, setPlano] = useState<PlanoContas[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.finList("bancos"), api.finList("centro_custo"), api.finList("plano_contas")])
      .then(([b, c, p]) => { setBancos((b.data || []) as Banco[]); setCentros((c.data || []) as CentroCusto[]); setPlano((p.data || []) as PlanoContas[]); })
      .catch(() => {}).finally(() => setLoading(false));
  }, []);

  function renderContent(key: string) {
    if (loading) return <p className="text-xs text-neutral-500">Carregando...</p>;
    switch (key) {
      case "conta":
        return (
          <div className="space-y-3">
            <div className="flex items-center justify-between"><h3 className="text-sm font-semibold text-neutral-200">Contas Bancárias</h3><button className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">+ Nova Conta</button></div>
            <table className="w-full text-xs"><thead><tr className="border-b border-neutral-700 text-neutral-400 text-left"><th className="px-3 py-2 font-medium">Banco</th><th className="px-3 py-2 font-medium">Agência</th><th className="px-3 py-2 font-medium">Conta</th><th className="px-3 py-2 font-medium">Saldo</th><th className="px-3 py-2 font-medium">Status</th></tr></thead>
              <tbody>{bancos.map((b) => (
                <tr key={b.id} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300"><td className="px-3 py-2">{b.nome}</td><td className="px-3 py-2">{b.agencia}</td><td className="px-3 py-2">{b.conta}</td><td className="px-3 py-2 text-emerald-400 font-medium">{fmt(b.saldo)}</td><td className="px-3 py-2"><span className={`px-2 py-0.5 rounded text-[10px] ${b.status === "ativa" ? "bg-emerald-500/20 text-emerald-400" : "bg-neutral-500/20 text-neutral-400"}`}>{b.status}</span></td></tr>
              ))}</tbody>
            </table>
          </div>
        );
      case "centro_custo":
        return (
          <div className="space-y-3">
            <div className="flex items-center justify-between"><h3 className="text-sm font-semibold text-neutral-200">Centros de Custo</h3><button className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">+ Novo</button></div>
            <table className="w-full text-xs"><thead><tr className="border-b border-neutral-700 text-neutral-400 text-left"><th className="px-3 py-2 font-medium">Código</th><th className="px-3 py-2 font-medium">Nome</th><th className="px-3 py-2 font-medium">Descrição</th><th className="px-3 py-2 font-medium">Status</th></tr></thead>
              <tbody>{centros.map((c) => (
                <tr key={c.id} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300"><td className="px-3 py-2">{c.codigo}</td><td className="px-3 py-2">{c.nome}</td><td className="px-3 py-2 text-neutral-400">{c.descricao || "—"}</td><td className="px-3 py-2"><span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-400">{c.status}</span></td></tr>
              ))}</tbody>
            </table>
          </div>
        );
      case "plano_contas":
        return (
          <div className="space-y-3">
            <div className="flex items-center justify-between"><h3 className="text-sm font-semibold text-neutral-200">Plano de Contas</h3><button className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">+ Nova Conta</button></div>
            <table className="w-full text-xs"><thead><tr className="border-b border-neutral-700 text-neutral-400 text-left"><th className="px-3 py-2 font-medium">Código</th><th className="px-3 py-2 font-medium">Nome</th><th className="px-3 py-2 font-medium">Tipo</th><th className="px-3 py-2 font-medium">Natureza</th></tr></thead>
              <tbody>{plano.map((p) => (
                <tr key={p.id} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300"><td className="px-3 py-2 font-medium">{p.codigo}</td><td className={`px-3 py-2 ${p.tipo === "sintetica" ? "font-bold text-indigo-300" : "text-neutral-300"}`}>{p.nome}</td><td className="px-3 py-2 text-neutral-400">{p.tipo}</td><td className="px-3 py-2 text-neutral-400">{p.natureza}</td></tr>
              ))}</tbody>
            </table>
          </div>
        );
      default: return <p className="text-xs text-neutral-500">Selecione um item</p>;
    }
  }

  return <SidebarLayout subItems={SUB_ITEMS} renderContent={renderContent} />;
}
