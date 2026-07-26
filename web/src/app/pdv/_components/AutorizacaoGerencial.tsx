"use client";

import { useState, useEffect, useRef } from "react";

interface OperadorGerencial { id: number; nome: string; role: string; }

export interface AutorizacaoGerencialValue {
  gerente_pin_id: number | null;
  pin: string;
  codigo_barras: string;
}

const VAZIO: AutorizacaoGerencialValue = { gerente_pin_id: null, pin: "", codigo_barras: "" };

/** Bloco expansivel: operador comum "chama o gerente" para autorizar uma acao
 * sensivel (cancelamento, devolucao, sangria, desconto acima do limite) de
 * duas formas — selecionar o gerente e digitar o PIN dele, ou bipar o
 * codigo de barras do cracha fisico do gerente (identifica automaticamente
 * quem e', sem selecionar da lista) — sem precisar de logout/login. */
export function AutorizacaoGerencial({ onChange }: { onChange: (v: AutorizacaoGerencialValue) => void }) {
  const [modo, setModo] = useState<"fechado" | "pin" | "cracha">("fechado");
  const [gerentes, setGerentes] = useState<OperadorGerencial[]>([]);
  const [gerenteId, setGerenteId] = useState<string>("");
  const [pin, setPin] = useState("");

  const [codigo, setCodigo] = useState("");
  const [identificado, setIdentificado] = useState<{ nome: string; erro?: string } | null>(null);
  const codigoRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (modo === "pin" && gerentes.length === 0) {
      fetch("/api/pdv/operadores")
        .then(r => r.json())
        .then(d => setGerentes((d.data || []).filter((o: OperadorGerencial) => ["gerente", "admin"].includes(o.role))))
        .catch(() => {});
    }
    if (modo === "cracha") codigoRef.current?.focus();
  }, [modo, gerentes.length]);

  useEffect(() => {
    if (modo === "pin") onChange(gerenteId ? { gerente_pin_id: Number(gerenteId), pin, codigo_barras: "" } : VAZIO);
    else if (modo === "cracha") onChange(identificado && !identificado.erro ? { ...VAZIO, codigo_barras: codigo } : VAZIO);
    else onChange(VAZIO);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modo, gerenteId, pin, codigo, identificado]);

  const resetar = () => {
    setModo("fechado"); setGerenteId(""); setPin(""); setCodigo(""); setIdentificado(null);
  };

  const bipar = async (valorCodigo: string) => {
    if (!valorCodigo.trim()) return;
    try {
      const r = await fetch("/api/pdv/autorizar-codigo-barras", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ codigo: valorCodigo.trim() }),
      }).then(res => res.json());
      if (r.error) { setIdentificado({ nome: "", erro: r.error }); return; }
      setIdentificado({ nome: r.nome });
    } catch {
      setIdentificado({ nome: "", erro: "Erro ao verificar código" });
    }
  };

  if (modo === "fechado") {
    return (
      <div className="flex items-center gap-3">
        <button type="button" onClick={() => setModo("pin")} className="text-[10px] text-amber-400 hover:text-amber-300 underline">
          Não sou gerente — chamar autorização por PIN
        </button>
        <button type="button" onClick={() => setModo("cracha")} className="text-[10px] text-amber-400 hover:text-amber-300 underline">
          Bipar crachá do gerente
        </button>
      </div>
    );
  }

  if (modo === "cracha") {
    return (
      <div className="bg-amber-950/20 border border-amber-900/40 rounded-lg p-3 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-amber-400 uppercase tracking-wider">Bipar crachá do gerente</span>
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
        <span className="text-[10px] text-amber-400 uppercase tracking-wider">Autorização de gerente (PIN)</span>
        <button type="button" onClick={resetar} className="text-[10px] text-neutral-500 hover:text-neutral-300">Cancelar</button>
      </div>
      <select
        value={gerenteId}
        onChange={e => setGerenteId(e.target.value)}
        className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200"
      >
        <option value="">Selecione o gerente</option>
        {gerentes.map(g => <option key={g.id} value={g.id}>{g.nome}</option>)}
      </select>
      <input
        type="password" inputMode="numeric" maxLength={6}
        value={pin}
        onChange={e => setPin(e.target.value.replace(/\D/g, ""))}
        placeholder="PIN do gerente"
        className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200"
      />
    </div>
  );
}
