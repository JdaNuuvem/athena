"use client";

import { useState, useEffect } from "react";

interface OperadorGerencial { id: number; nome: string; role: string; }

export interface AutorizacaoGerencialValue {
  gerente_pin_id: number | null;
  pin: string;
}

/** Bloco expansivel: operador comum "chama o gerente" para autorizar uma acao
 * sensivel (cancelamento, devolucao, sangria, desconto acima do limite) via
 * PIN numerico curto, sem precisar de logout/login no meio do atendimento. */
export function AutorizacaoGerencial({ onChange }: { onChange: (v: AutorizacaoGerencialValue) => void }) {
  const [ativo, setAtivo] = useState(false);
  const [gerentes, setGerentes] = useState<OperadorGerencial[]>([]);
  const [gerenteId, setGerenteId] = useState<string>("");
  const [pin, setPin] = useState("");

  useEffect(() => {
    if (ativo && gerentes.length === 0) {
      fetch("/api/pdv/operadores")
        .then(r => r.json())
        .then(d => setGerentes((d.data || []).filter((o: OperadorGerencial) => ["gerente", "admin"].includes(o.role))))
        .catch(() => {});
    }
  }, [ativo, gerentes.length]);

  useEffect(() => {
    onChange(ativo && gerenteId ? { gerente_pin_id: Number(gerenteId), pin } : { gerente_pin_id: null, pin: "" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ativo, gerenteId, pin]);

  if (!ativo) {
    return (
      <button type="button" onClick={() => setAtivo(true)} className="text-[10px] text-amber-400 hover:text-amber-300 underline">
        Não sou gerente — chamar autorização por PIN
      </button>
    );
  }

  return (
    <div className="bg-amber-950/20 border border-amber-900/40 rounded-lg p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-amber-400 uppercase tracking-wider">Autorização de gerente (PIN)</span>
        <button type="button" onClick={() => { setAtivo(false); setGerenteId(""); setPin(""); }} className="text-[10px] text-neutral-500 hover:text-neutral-300">
          Cancelar
        </button>
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
