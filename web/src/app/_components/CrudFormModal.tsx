"use client";

import { useState } from "react";
import Icon from "./Icon";
import FkPicker from "./FkPicker";
import { emailValido, documentoValido } from "@/lib/validacao";
import { buscarCNPJ, buscarCEP, aplicarCNPJ, aplicarCEP } from "@/lib/lookup";

export interface FieldDef {
  key: string;
  label: string;
  type?: "text" | "number" | "select" | "date" | "datetime" | "fk";
  options?: { label: string; value: string }[];
  step?: string;
  min?: number;
  max?: number;
  // Campo "select" cujo valor deve ser enviado como numero (ex.: FK de id) em vez de string.
  numeric?: boolean;
  // type: "fk" — tabela de cadastros referenciada (ex.: "clientes") e campo
  // usado como rotulo no picker (default "nome").
  fkTabela?: string;
  fkLabelField?: string;
  // forca o campo a ocupar as 2 colunas do grid do modal.
  wide?: boolean;
  // bloqueia salvar se vazio.
  required?: boolean;
  // validacao de formato — "documento" aceita CPF (11 digitos) ou CNPJ (14).
  validate?: "email" | "documento";
  // botao de autolookup ao lado do campo — "cnpj" preenche razao_social/
  // endereco/telefone/email via BrasilAPI, "cep" preenche endereco via ViaCEP.
  lookup?: "cnpj" | "cep";
}

interface CrudFormModalProps {
  mode: "create" | "edit";
  fields: FieldDef[];
  formData: Record<string, string>;
  onChange: (key: string, value: string) => void;
  onSave: () => void;
  onClose: () => void;
}

const MENSAGEM_ERRO: Record<NonNullable<FieldDef["validate"]>, string> = {
  email: "Email inválido",
  documento: "CPF/CNPJ inválido",
};

function campoValido(f: FieldDef, valor: string): boolean {
  if (!valor) return true;
  if (f.validate === "email") return emailValido(valor);
  if (f.validate === "documento") return documentoValido(valor);
  return true;
}

export default function CrudFormModal({ mode, fields, formData, onChange, onSave, onClose }: CrudFormModalProps) {
  const [erros, setErros] = useState<Record<string, string>>({});
  const [buscando, setBuscando] = useState<Record<string, boolean>>({});

  const handleLookup = async (f: FieldDef) => {
    const valor = (formData[f.key] ?? "").trim();
    if (!valor || !f.lookup) return;
    setBuscando(prev => ({ ...prev, [f.key]: true }));
    const keys = new Set(fields.map(x => x.key));
    try {
      if (f.lookup === "cnpj") {
        const dados = await buscarCNPJ(valor);
        if (dados) aplicarCNPJ(dados, onChange, keys); else alert("CNPJ não encontrado");
      } else {
        const dados = await buscarCEP(valor);
        if (dados) aplicarCEP(dados, onChange, keys); else alert("CEP não encontrado");
      }
    } finally {
      setBuscando(prev => ({ ...prev, [f.key]: false }));
    }
  };

  const validar = (): boolean => {
    const novosErros: Record<string, string> = {};
    for (const f of fields) {
      if (f.key === "id") continue;
      const valor = (formData[f.key] ?? "").trim();
      if (f.required && !valor) { novosErros[f.key] = "Obrigatório"; continue; }
      if (valor && f.validate && !campoValido(f, valor)) novosErros[f.key] = MENSAGEM_ERRO[f.validate];
    }
    setErros(novosErros);
    return Object.keys(novosErros).length === 0;
  };

  const handleSalvar = () => { if (validar()) onSave(); };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={onClose}>
      <div className="w-full max-w-[440px] max-h-[85vh] overflow-y-auto rounded-xl border border-neutral-700 bg-neutral-800 shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-neutral-700/70 px-5 py-4">
          <h3 className="text-sm font-semibold text-neutral-100">{mode === "create" ? "Novo registro" : "Editar registro"}</h3>
          <button onClick={onClose} className="rounded-md p-1 text-neutral-500 hover:bg-neutral-700 hover:text-neutral-300">
            <Icon name="close" size={15} />
          </button>
        </div>
        <div className="grid grid-cols-2 gap-3 px-5 py-4">
          {fields.filter(f => f.key !== "id").map(f => {
            const erro = erros[f.key];
            const borda = erro ? "border-red-500/70 focus:border-red-500 focus:ring-red-500/50" : "border-neutral-600 focus:border-indigo-500 focus:ring-indigo-500/50";
            return (
              <div key={f.key} className={f.type === "select" || f.type === "fk" || f.wide ? "col-span-2" : "col-span-2 sm:col-span-1"}>
                <label className="mb-1 block text-[11px] font-medium text-neutral-400">
                  {f.label}{f.required && <span className="ml-0.5 text-red-400">*</span>}
                </label>
                {f.type === "select" && f.options ? (
                  <select value={formData[f.key] ?? ""} onChange={e => onChange(f.key, e.target.value)}
                    className={`w-full rounded-lg border bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:ring-1 ${borda}`}>
                    <option value="">Selecione...</option>
                    {f.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                ) : f.type === "fk" && f.fkTabela ? (
                  <FkPicker tabela={f.fkTabela} labelField={f.fkLabelField} value={formData[f.key] ?? ""} onChange={v => onChange(f.key, v)} />
                ) : f.lookup ? (
                  <div className="flex gap-1.5">
                    <input type="text" value={formData[f.key] ?? ""} onChange={e => onChange(f.key, e.target.value)}
                      className={`w-full min-w-0 flex-1 rounded-lg border bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:ring-1 ${borda}`} />
                    <button type="button" onClick={() => handleLookup(f)} disabled={buscando[f.key]} title={f.lookup === "cnpj" ? "Buscar dados pelo CNPJ" : "Buscar endereço pelo CEP"}
                      className="shrink-0 rounded-lg border border-neutral-600 bg-neutral-700 px-2.5 text-neutral-300 transition-colors hover:bg-neutral-600 disabled:opacity-50">
                      <Icon name="search" size={13} className={buscando[f.key] ? "animate-pulse" : ""} />
                    </button>
                  </div>
                ) : (
                  <input type={f.type === "number" ? "number" : f.type === "date" ? "date" : f.type === "datetime" ? "datetime-local" : "text"}
                    step={f.type === "number" ? (f.step ?? "any") : undefined} min={f.min} max={f.max}
                    value={formData[f.key] ?? ""} onChange={e => onChange(f.key, e.target.value)}
                    className={`w-full rounded-lg border bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:ring-1 ${borda}`} />
                )}
                {erro && <p className="mt-1 text-[10px] text-red-400">{erro}</p>}
              </div>
            );
          })}
        </div>
        <div className="flex justify-end gap-2 border-t border-neutral-700/70 px-5 py-4">
          <button onClick={onClose} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 transition-colors hover:text-neutral-200">Cancelar</button>
          <button onClick={handleSalvar} className="rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-500">Salvar</button>
        </div>
      </div>
    </div>
  );
}
