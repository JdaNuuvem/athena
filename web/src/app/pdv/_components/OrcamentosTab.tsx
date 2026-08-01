"use client";

import { useState, useEffect } from "react";
import { Operador, FORMAS } from "./types";
import { AutorizacaoGerencial, type AutorizacaoGerencialValue } from "./AutorizacaoGerencial";

const AUTORIZACAO_VAZIA: AutorizacaoGerencialValue = { gerente_pin_id: null, pin: "", codigo_barras: "" };

export function OrcamentosTab({ caixa, operador, operadorSenha, onVendaCriada }: { caixa: any; operador: Operador; operadorSenha: string; onVendaCriada: () => void }) {
  const [orcamentos, setOrcamentos] = useState<any[]>([]);
  const [pgtoForma, setPgtoForma] = useState("dinheiro");
  const [convertendo, setConvertendo] = useState<{ id: number; total: number } | null>(null);
  const [autorizacao, setAutorizacao] = useState<AutorizacaoGerencialValue>(AUTORIZACAO_VAZIA);
  const [erro, setErro] = useState("");

  const load = () => {
    fetch("/api/pdv/vendas?limit=30").then(r => r.json()).then(d => {
      setOrcamentos((d.data || []).filter((v: any) => v.status === "orcamento"));
    }).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const abrirConversao = (id: number, total: number) => {
    if (!caixa) { alert("Abra o caixa primeiro!"); return; }
    setConvertendo({ id, total });
    setAutorizacao(AUTORIZACAO_VAZIA);
    setErro("");
  };

  const confirmarConversao = async () => {
    if (!convertendo) return;
    try {
      const r = await fetch("/api/pdv/orcamento/" + convertendo.id + "/converter", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ caixa_id: caixa.id, pagamentos: [{ forma: pgtoForma, valor: convertendo.total }],
          operador: operador.nome, operador_id: operador.id,
          gerente_pin_id: autorizacao.gerente_pin_id, pin: autorizacao.pin, codigo_barras: autorizacao.codigo_barras }),
      });
      const d = await r.json();
      if (d.error) { setErro(d.error); return; }
      setConvertendo(null);
      load(); onVendaCriada();
    } catch { setErro("Erro ao converter"); }
  };

  return (
    <div className="overflow-auto p-4">
      <h3 className="text-sm font-semibold text-neutral-200 mb-3">Orcamentos Pendentes</h3>
      {orcamentos.length === 0 && <p className="text-neutral-600 text-sm">Nenhum orcamento pendente.</p>}
      {orcamentos.map(o => (
        <div key={o.id} className="bg-neutral-800 border border-neutral-700 rounded-lg p-3 mb-2 flex items-center justify-between">
          <div>
            <span className="text-indigo-400 font-mono text-sm">#{o.id}</span>
            <span className="text-neutral-400 text-xs ml-3">{o.cliente || "Sem cliente"}</span>
            <span className="text-neutral-500 text-xs ml-3">{String(o.data || "").slice(0, 16)}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-emerald-400 font-medium text-sm">R$ {Number(o.total || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
            <select value={pgtoForma} onChange={e => setPgtoForma(e.target.value)}
              className="bg-neutral-900 rounded px-2 py-1 text-xs text-neutral-200">
              {FORMAS.map(f => <option key={f} value={f}>{f.replace(/_/g, " ")}</option>)}
            </select>
            <button onClick={() => abrirConversao(o.id, o.total)}
              className="px-3 py-1 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">Converter em Venda</button>
          </div>
        </div>
      ))}

      {convertendo && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setConvertendo(null)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-96" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Converter Orçamento #{convertendo.id}</h3>
            <p className="text-xs text-neutral-400 mb-3">Total: R$ {convertendo.total.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} — forma: {pgtoForma.replace(/_/g, " ")}</p>
            {erro && (
              <div className="text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2 mb-3">
                {erro}
                {erro.toLowerCase().includes("desconto") && (
                  <p className="mt-1 text-neutral-400">O desconto deste orçamento excede seu limite — peça autorização abaixo.</p>
                )}
              </div>
            )}
            <div className="mb-3">
              <AutorizacaoGerencial onChange={setAutorizacao} />
            </div>
            <div className="flex gap-2">
              <button onClick={() => setConvertendo(null)} className="flex-1 py-2 text-sm text-neutral-400">Cancelar</button>
              <button onClick={confirmarConversao} className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg">Confirmar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
