"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { fmtBRL as fmt } from "@/lib/format";
import SidebarLayout from "../../_components/SidebarLayout";

const SUB_ITEMS = [
  { key: "conta", label: "Conta" },
  { key: "centro_custo", label: "Centro Custo" },
  { key: "plano_contas", label: "Plano Contas" },
];

interface Banco { id: number; nome: string; agencia: string; conta: string; saldo: number; status: string; }
interface CentroCusto { id: number; nome: string; codigo: string; descricao: string; status: string; }
interface PlanoContas { id: number; codigo: string; nome: string; tipo: string; natureza: string; }

const TIPOS_PLANO = ["sintetica", "analitica"];
const NATUREZAS_PLANO = ["devedora", "credora"];

export default function BancoTab() {
  const [bancos, setBancos] = useState<Banco[]>([]);
  const [centros, setCentros] = useState<CentroCusto[]>([]);
  const [plano, setPlano] = useState<PlanoContas[]>([]);
  const [loading, setLoading] = useState(true);

  const [criando, setCriando] = useState<"conta" | "centro_custo" | "plano_contas" | null>(null);
  const [novoBanco, setNovoBanco] = useState({ nome: "", agencia: "", conta: "", saldo: "" });
  const [novoCentro, setNovoCentro] = useState({ nome: "", codigo: "", descricao: "" });
  const [novoPlano, setNovoPlano] = useState({ codigo: "", nome: "", tipo: "sintetica", natureza: "devedora" });
  const [erro, setErro] = useState("");

  const load = () => {
    Promise.all([api.finList("bancos"), api.finList("centro_custo"), api.finList("plano_contas")])
      .then(([b, c, p]) => { setBancos((b.data || []) as Banco[]); setCentros((c.data || []) as CentroCusto[]); setPlano((p.data || []) as PlanoContas[]); })
      .catch(() => {}).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const abrirCriar = (tipo: "conta" | "centro_custo" | "plano_contas") => {
    setNovoBanco({ nome: "", agencia: "", conta: "", saldo: "" });
    setNovoCentro({ nome: "", codigo: "", descricao: "" });
    setNovoPlano({ codigo: "", nome: "", tipo: "sintetica", natureza: "devedora" });
    setErro("");
    setCriando(tipo);
  };

  const confirmarCriarConta = async () => {
    if (!novoBanco.nome.trim()) { setErro("Nome do banco é obrigatório"); return; }
    try {
      const r = await api.finCreate("bancos", { nome: novoBanco.nome.trim(), agencia: novoBanco.agencia.trim(), conta: novoBanco.conta.trim(), saldo: Number(novoBanco.saldo) || 0 });
      if ((r as { error?: string }).error) { setErro((r as { error?: string }).error || "Erro ao criar"); return; }
      setCriando(null);
      load();
    } catch {
      setErro("Erro ao criar conta bancária");
    }
  };

  const confirmarCriarCentro = async () => {
    if (!novoCentro.nome.trim() || !novoCentro.codigo.trim()) { setErro("Nome e código são obrigatórios"); return; }
    try {
      const r = await api.finCreate("centro_custo", { nome: novoCentro.nome.trim(), codigo: novoCentro.codigo.trim(), descricao: novoCentro.descricao.trim() });
      if ((r as { error?: string }).error) { setErro((r as { error?: string }).error || "Erro ao criar"); return; }
      setCriando(null);
      load();
    } catch {
      setErro("Erro ao criar centro de custo");
    }
  };

  const confirmarCriarPlano = async () => {
    if (!novoPlano.nome.trim() || !novoPlano.codigo.trim()) { setErro("Nome e código são obrigatórios"); return; }
    try {
      const r = await api.finCreate("plano_contas", { codigo: novoPlano.codigo.trim(), nome: novoPlano.nome.trim(), tipo: novoPlano.tipo, natureza: novoPlano.natureza });
      if ((r as { error?: string }).error) { setErro((r as { error?: string }).error || "Erro ao criar"); return; }
      setCriando(null);
      load();
    } catch {
      setErro("Erro ao criar conta do plano");
    }
  };

  function renderContent(key: string) {
    if (loading) return <p className="text-xs text-neutral-500">Carregando...</p>;
    switch (key) {
      case "conta":
        return (
          <div className="space-y-3">
            <div className="flex items-center justify-between"><h3 className="text-sm font-semibold text-neutral-200">Contas Bancárias</h3><button onClick={() => abrirCriar("conta")} className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">+ Nova Conta</button></div>
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
            <div className="flex items-center justify-between"><h3 className="text-sm font-semibold text-neutral-200">Centros de Custo</h3><button onClick={() => abrirCriar("centro_custo")} className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">+ Novo</button></div>
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
            <div className="flex items-center justify-between"><h3 className="text-sm font-semibold text-neutral-200">Plano de Contas</h3><button onClick={() => abrirCriar("plano_contas")} className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">+ Nova Conta</button></div>
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

  return (
    <>
      <SidebarLayout subItems={SUB_ITEMS} renderContent={renderContent} />

      {criando === "conta" && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setCriando(null)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-96" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Nova Conta Bancária</h3>
            {erro && <div className="text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2 mb-3">{erro}</div>}
            <div className="space-y-2">
              <input value={novoBanco.nome} onChange={e => setNovoBanco({ ...novoBanco, nome: e.target.value })}
                placeholder="Nome do banco" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input value={novoBanco.agencia} onChange={e => setNovoBanco({ ...novoBanco, agencia: e.target.value })}
                placeholder="Agência" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input value={novoBanco.conta} onChange={e => setNovoBanco({ ...novoBanco, conta: e.target.value })}
                placeholder="Conta" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input type="number" step="0.01" value={novoBanco.saldo} onChange={e => setNovoBanco({ ...novoBanco, saldo: e.target.value })}
                placeholder="Saldo inicial" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
            </div>
            <div className="flex gap-2 mt-4">
              <button onClick={() => setCriando(null)} className="flex-1 py-2 text-sm text-neutral-400">Cancelar</button>
              <button onClick={confirmarCriarConta} className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg">Criar</button>
            </div>
          </div>
        </div>
      )}

      {criando === "centro_custo" && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setCriando(null)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-96" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Novo Centro de Custo</h3>
            {erro && <div className="text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2 mb-3">{erro}</div>}
            <div className="space-y-2">
              <input value={novoCentro.codigo} onChange={e => setNovoCentro({ ...novoCentro, codigo: e.target.value })}
                placeholder="Código" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input value={novoCentro.nome} onChange={e => setNovoCentro({ ...novoCentro, nome: e.target.value })}
                placeholder="Nome" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input value={novoCentro.descricao} onChange={e => setNovoCentro({ ...novoCentro, descricao: e.target.value })}
                placeholder="Descrição" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
            </div>
            <div className="flex gap-2 mt-4">
              <button onClick={() => setCriando(null)} className="flex-1 py-2 text-sm text-neutral-400">Cancelar</button>
              <button onClick={confirmarCriarCentro} className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg">Criar</button>
            </div>
          </div>
        </div>
      )}

      {criando === "plano_contas" && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setCriando(null)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-96" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Nova Conta do Plano</h3>
            {erro && <div className="text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2 mb-3">{erro}</div>}
            <div className="space-y-2">
              <input value={novoPlano.codigo} onChange={e => setNovoPlano({ ...novoPlano, codigo: e.target.value })}
                placeholder="Código" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input value={novoPlano.nome} onChange={e => setNovoPlano({ ...novoPlano, nome: e.target.value })}
                placeholder="Nome" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <select value={novoPlano.tipo} onChange={e => setNovoPlano({ ...novoPlano, tipo: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200">
                {TIPOS_PLANO.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <select value={novoPlano.natureza} onChange={e => setNovoPlano({ ...novoPlano, natureza: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200">
                {NATUREZAS_PLANO.map(n => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
            <div className="flex gap-2 mt-4">
              <button onClick={() => setCriando(null)} className="flex-1 py-2 text-sm text-neutral-400">Cancelar</button>
              <button onClick={confirmarCriarPlano} className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg">Criar</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
