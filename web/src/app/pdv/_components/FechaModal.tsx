"use client";

import { useState, useEffect } from "react";
import { Operador } from "./types";
import { AutorizacaoGerencial, type AutorizacaoGerencialValue } from "./AutorizacaoGerencial";

export function FechaModal({ open, caixa, operador, onClose, onFechar }: {
  open: boolean;
  caixa: any;
  operador: Operador;
  onClose: () => void;
  onFechar: (result: any) => void;
}) {
  const [fechaResumo, setFechaResumo] = useState<any>(null);
  const [fechaSaldo, setFechaSaldo] = useState("");
  const [fechaSenha, setFechaSenha] = useState("");
  const [autorizacao, setAutorizacao] = useState<AutorizacaoGerencialValue>({ gerente_pin_id: null, pin: "", codigo_barras: "" });

  useEffect(() => {
    if (!open || !caixa) return;
    setFechaSaldo(""); setFechaSenha(""); setFechaResumo(null);
    fetch("/api/pdv/caixa/" + caixa.id + "/resumo")
      .then(r => r.json()).then(setFechaResumo).catch(() => {});
  }, [open, caixa]);

  const fecharCaixa = async () => {
    const saldo = parseFloat(fechaSaldo);
    if (!saldo && saldo !== 0) { alert("Informe o saldo final"); return; }
    try {
      const r = await fetch("/api/pdv/caixa/" + caixa.id + "/fechar", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ saldo_final: saldo, operador_id: operador.id, senha: fechaSenha,
          gerente_pin_id: autorizacao.gerente_pin_id, pin: autorizacao.pin, codigo_barras: autorizacao.codigo_barras }),
      });
      const d = await r.json();
      if (d.error) { alert(d.error); onClose(); return; }
      if (d.aviso_segregacao) {
        alert("Aviso: você é o único operador que vendeu neste turno. Considere ter uma segunda pessoa conferindo o caixa.");
      }
      onFechar(d);
    } catch { alert("Erro ao fechar"); onClose(); }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-[28rem] max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <h3 className="text-sm font-semibold text-neutral-200 mb-3">Fechar Caixa #{caixa?.id}</h3>
        {fechaResumo && !fechaResumo.error && (
          <div className="mb-4 space-y-2 text-xs">
            <div className="flex justify-between text-neutral-400"><span>Saldo inicial</span><span className="text-neutral-200">R$ {Number(fechaResumo.saldo_inicial).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></div>
            <div className="border-t border-neutral-700 pt-2 mt-2">
              <p className="text-neutral-500 mb-1">Vendas por forma de pgto:</p>
              {Object.entries(fechaResumo.vendas_por_forma || {}).map(([forma, valor]) => (
                <div key={forma} className="flex justify-between"><span className="text-neutral-400 capitalize">{forma.replace(/_/g, " ")}</span><span className="text-neutral-200">R$ {(valor as number).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></div>
              ))}
              {(!fechaResumo.vendas_por_forma || Object.keys(fechaResumo.vendas_por_forma).length === 0) && (
                <p className="text-neutral-600">Nenhuma venda no periodo</p>
              )}
            </div>
            {fechaResumo.sangrias > 0 && <div className="flex justify-between text-red-400"><span>Sangrias</span><span>- R$ {Number(fechaResumo.sangrias).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></div>}
            {fechaResumo.suprimentos > 0 && <div className="flex justify-between text-emerald-400"><span>Suprimentos</span><span>+ R$ {Number(fechaResumo.suprimentos).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></div>}
            <div className="border-t border-neutral-700 pt-2 flex justify-between font-bold text-sm">
              <span className="text-neutral-300">Saldo esperado (dinheiro)</span>
              <span className="text-amber-400">R$ {Number(fechaResumo.saldo_esperado_dinheiro).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
            </div>
          </div>
        )}
        {fechaResumo?.error && <p className="text-red-400 text-xs mb-3">{fechaResumo.error}</p>}
        <input type="number" step="0.01" value={fechaSaldo} onChange={e => setFechaSaldo(e.target.value)}
          placeholder="Saldo conferido (dinheiro em caixa)" autoFocus
          className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200 mb-2" />
        {fechaResumo && !fechaResumo.error && fechaSaldo && (
          <div className={"text-xs mb-2 " + (Math.abs(parseFloat(fechaSaldo) - (fechaResumo.saldo_esperado_dinheiro || 0)) < 0.01 ? "text-emerald-400" : "text-red-400")}>
            Diferença: R$ {(parseFloat(fechaSaldo || "0") - (fechaResumo.saldo_esperado_dinheiro || 0)).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        )}
        <input type="password" value={fechaSenha} onChange={e => setFechaSenha(e.target.value)}
          placeholder="Senha para confirmar"
          onKeyDown={e => { if (e.key === "Enter") fecharCaixa(); }}
          className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-4 py-2 text-sm text-neutral-200 mb-2" />
        <div className="mb-3">
          <AutorizacaoGerencial onChange={setAutorizacao} />
        </div>
        <div className="flex gap-2">
          <button onClick={onClose} className="flex-1 py-2 text-sm text-neutral-400 hover:text-neutral-200">Cancelar</button>
          <button onClick={fecharCaixa} className="flex-1 py-2 bg-red-600 text-white text-sm rounded-lg">Fechar Caixa</button>
        </div>
      </div>
    </div>
  );
}
