"use client";

import { useState } from "react";
import { Operador } from "./types";

export function CaixaTab({ operador, operadorSenha, caixa, onAbrirCaixa, onFecharCaixa }: {
  operador: Operador;
  operadorSenha: string;
  caixa: any;
  onAbrirCaixa: (saldoInicial: number) => Promise<void>;
  onFecharCaixa: () => void;
}) {
  const [saldoInicial, setSaldoInicial] = useState(0);

  return (
    <div className="p-4 space-y-3">
      <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 max-w-md">
        <h3 className="text-sm font-semibold text-neutral-200 mb-3">Caixa</h3>
        {caixa ? (
          <div className="space-y-2 text-sm">
            <p className="text-neutral-400">Status: <span className="text-emerald-400">Aberto</span></p>
            <p className="text-neutral-400">Saldo inicial: <span className="text-neutral-200">R$ {(caixa.saldo_inicial || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</span></p>
            <button onClick={onFecharCaixa} className="px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-500">Fechar Caixa</button>
          </div>
        ) : (
          <div className="space-y-2">
            <input type="number" value={saldoInicial} onChange={e => setSaldoInicial(Number(e.target.value))} placeholder="Saldo inicial" className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm text-neutral-200" />
            <button onClick={() => onAbrirCaixa(saldoInicial)} className="w-full py-2 bg-emerald-600 text-white text-sm rounded-lg">Abrir Caixa</button>
          </div>
        )}
      </div>
    </div>
  );
}
