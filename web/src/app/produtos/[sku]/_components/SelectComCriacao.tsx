"use client";

import { useState } from "react";
import Icon from "@/app/_components/Icon";

interface Opcao { id: number; nome: string; }

export default function SelectComCriacao({
  label, value, options, onChange, onCriar, onCriado, disabled,
}: {
  label: string;
  value: string;
  options: Opcao[];
  onChange: (id: string) => void;
  onCriar: (nome: string) => Promise<Opcao | { error: string }>;
  onCriado: (novo: Opcao) => void;
  disabled?: boolean;
}) {
  const [criando, setCriando] = useState(false);
  const [novoNome, setNovoNome] = useState("");
  const [erro, setErro] = useState("");

  const confirmarCriacao = async () => {
    const nome = novoNome.trim();
    if (!nome) return;
    let resultado: Opcao | { error: string };
    try {
      resultado = await onCriar(nome);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao criar");
      return;
    }
    if ("error" in resultado) {
      setErro(resultado.error);
      return;
    }
    onCriado(resultado);
    onChange(String(resultado.id));
    setCriando(false);
    setNovoNome("");
    setErro("");
  };

  if (criando) {
    return (
      <div className="space-y-1">
        <label className="text-[10px] text-neutral-500 uppercase tracking-wider">{label}</label>
        <div className="flex gap-1">
          <input
            type="text" autoFocus value={novoNome}
            onChange={e => setNovoNome(e.target.value)}
            onKeyDown={e => e.key === "Enter" && confirmarCriacao()}
            placeholder="Nome novo..."
            className="flex-1 bg-neutral-900 border border-indigo-600 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none"
          />
          <button onClick={confirmarCriacao} className="px-2 bg-indigo-600 text-white text-xs rounded-lg">OK</button>
          <button onClick={() => { setCriando(false); setErro(""); }} className="px-2 text-neutral-400 text-xs flex items-center">
            <Icon name="close" size={12} />
          </button>
        </div>
        {erro && <p className="text-[10px] text-red-400">{erro}</p>}
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <label className="text-[10px] text-neutral-500 uppercase tracking-wider">{label}</label>
      <select
        value={value}
        disabled={disabled}
        onChange={e => {
          if (e.target.value === "__novo__") { setCriando(true); return; }
          onChange(e.target.value);
        }}
        className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500"
      >
        <option value="">— Nenhum —</option>
        {options.map(o => <option key={o.id} value={o.id}>{o.nome}</option>)}
        <option value="__novo__">+ Criar novo...</option>
      </select>
    </div>
  );
}
