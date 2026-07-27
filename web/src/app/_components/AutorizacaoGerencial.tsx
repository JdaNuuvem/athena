"use client";

import { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";

interface UsuarioRBAC { id: number; nome: string; email: string; ativo: boolean; }

export interface AutorizacaoGerencialValue {
  usuario_pin_id: number | null;
  pin: string;
  codigo_barras: string;
}

const VAZIO: AutorizacaoGerencialValue = { usuario_pin_id: null, pin: "", codigo_barras: "" };

/** Versao generica do componente de autorizacao gerencial criado para o PDV
 * (PIN ou cracha fisico), para uso em qualquer modulo que precise de dupla
 * autorizacao — ex: aprovar pagamento acima do limite no financeiro sem
 * precisar de logout/login. `permissao` e' o codigo RBAC que quem autoriza
 * precisa ter (validado no backend em /api/rbac/autorizar). */
export function AutorizacaoGerencial({ permissao, onChange }: { permissao: string; onChange: (v: AutorizacaoGerencialValue) => void }) {
  const [modo, setModo] = useState<"fechado" | "pin" | "cracha">("fechado");
  const [usuarios, setUsuarios] = useState<UsuarioRBAC[]>([]);
  const [usuarioId, setUsuarioId] = useState<string>("");
  const [pin, setPin] = useState("");

  const [codigo, setCodigo] = useState("");
  const [identificado, setIdentificado] = useState<{ nome: string; erro?: string } | null>(null);
  const codigoRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (modo === "pin" && usuarios.length === 0) {
      api.rbacListUsuarios()
        .then(d => setUsuarios((d.usuarios || []).filter(u => u.ativo)))
        .catch(() => {});
    }
    if (modo === "cracha") codigoRef.current?.focus();
  }, [modo, usuarios.length]);

  useEffect(() => {
    if (modo === "pin") onChange(usuarioId ? { usuario_pin_id: Number(usuarioId), pin, codigo_barras: "" } : VAZIO);
    else if (modo === "cracha") onChange(identificado && !identificado.erro ? { ...VAZIO, codigo_barras: codigo } : VAZIO);
    else onChange(VAZIO);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modo, usuarioId, pin, codigo, identificado]);

  const resetar = () => {
    setModo("fechado"); setUsuarioId(""); setPin(""); setCodigo(""); setIdentificado(null);
  };

  const bipar = async (valorCodigo: string) => {
    if (!valorCodigo.trim()) return;
    try {
      const r = await api.rbacAutorizar({ permissao, codigo_barras: valorCodigo.trim() });
      if (r.error) { setIdentificado({ nome: "", erro: r.error }); return; }
      setIdentificado({ nome: r.nome || "" });
    } catch {
      setIdentificado({ nome: "", erro: "Erro ao verificar código" });
    }
  };

  if (modo === "fechado") {
    return (
      <div className="flex items-center gap-3">
        <button type="button" onClick={() => setModo("pin")} className="text-[10px] text-amber-400 hover:text-amber-300 underline">
          Não tenho permissão — chamar autorização por PIN
        </button>
        <button type="button" onClick={() => setModo("cracha")} className="text-[10px] text-amber-400 hover:text-amber-300 underline">
          Bipar crachá de quem autoriza
        </button>
      </div>
    );
  }

  if (modo === "cracha") {
    return (
      <div className="bg-amber-950/20 border border-amber-900/40 rounded-lg p-3 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-amber-400 uppercase tracking-wider">Bipar crachá de autorização</span>
          <button type="button" onClick={resetar} className="text-[10px] text-neutral-500 hover:text-neutral-300">Cancelar</button>
        </div>
        <input
          ref={codigoRef}
          type="text"
          value={codigo}
          onChange={e => { setCodigo(e.target.value); setIdentificado(null); }}
          onBlur={() => bipar(codigo)}
          onKeyDown={e => { if (e.key === "Enter") bipar(codigo); }}
          placeholder="Aguardando leitura do crachá..."
          className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200 font-mono"
        />
        {identificado?.erro && <p className="text-[10px] text-red-400">{identificado.erro}</p>}
        {identificado && !identificado.erro && <p className="text-[10px] text-emerald-400">Autorizado por: {identificado.nome}</p>}
      </div>
    );
  }

  return (
    <div className="bg-amber-950/20 border border-amber-900/40 rounded-lg p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-amber-400 uppercase tracking-wider">Autorização (PIN)</span>
        <button type="button" onClick={resetar} className="text-[10px] text-neutral-500 hover:text-neutral-300">Cancelar</button>
      </div>
      <select
        value={usuarioId}
        onChange={e => setUsuarioId(e.target.value)}
        className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200"
      >
        <option value="">Selecione quem autoriza</option>
        {usuarios.map(u => <option key={u.id} value={u.id}>{u.nome}</option>)}
      </select>
      <input
        type="password" inputMode="numeric" maxLength={6}
        value={pin}
        onChange={e => setPin(e.target.value.replace(/\D/g, ""))}
        placeholder="PIN de quem autoriza"
        className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200"
      />
    </div>
  );
}
