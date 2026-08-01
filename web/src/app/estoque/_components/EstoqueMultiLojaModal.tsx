"use client";

import { useState } from "react";
import { atualizarEstoqueDeposito, type BlingDeposito } from "@/lib/api";

interface EstoqueMultiLojaModalProps {
  produtoId: number;
  sku: string;
  nome: string;
  depositos: BlingDeposito[];
  estoqueAtual: Record<number, number>;
  onClose: () => void;
  onSucesso: () => void;
}

type SaveStatus = "enviando" | "ok" | "erro";

export default function EstoqueMultiLojaModal({
  produtoId, sku, nome, depositos, estoqueAtual, onClose, onSucesso,
}: EstoqueMultiLojaModalProps) {
  const [etapa, setEtapa] = useState<"selecao" | "edicao">("selecao");
  const [selecionados, setSelecionados] = useState<Set<number>>(new Set());
  const [valores, setValores] = useState<Record<number, string>>({});
  const [salvando, setSalvando] = useState(false);
  const [status, setStatus] = useState<Record<number, SaveStatus>>({});
  const [concluido, setConcluido] = useState(false);

  const toggleDeposito = (id: number) => {
    setSelecionados(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const avancarParaEdicao = () => {
    if (selecionados.size === 0) return;
    const iniciais: Record<number, string> = {};
    selecionados.forEach(id => { iniciais[id] = String(estoqueAtual[id] ?? 0); });
    setValores(iniciais);
    setEtapa("edicao");
  };

  const handleSalvar = async () => {
    setSalvando(true);
    setConcluido(false);
    const ids = Array.from(selecionados);
    const statusInicial: Record<number, SaveStatus> = {};
    ids.forEach(id => { statusInicial[id] = "enviando"; });
    setStatus(statusInicial);

    await Promise.all(ids.map(async (id) => {
      const atual = estoqueAtual[id] ?? 0;
      const novo = Number(valores[id]);
      if (!Number.isFinite(novo) || novo === atual) {
        setStatus(prev => ({ ...prev, [id]: "ok" }));
        return;
      }
      const delta = novo - atual;
      try {
        await atualizarEstoqueDeposito({
          idDeposito: id, idProduto: produtoId,
          operacao: delta > 0 ? "E" : "S", quantidade: Math.abs(delta),
        });
        setStatus(prev => ({ ...prev, [id]: "ok" }));
      } catch {
        setStatus(prev => ({ ...prev, [id]: "erro" }));
      }
    }));
    setSalvando(false);
    setConcluido(true);
    onSucesso();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-neutral-900 border border-neutral-700 rounded-xl p-6 w-full max-w-lg mx-4 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-medium text-neutral-200">Estoque por loja</h2>
            <p className="text-xs font-mono text-neutral-500 mt-0.5">{sku} — {nome}</p>
          </div>
          <button onClick={onClose} className="text-neutral-500 hover:text-neutral-300 text-lg">&times;</button>
        </div>

        {etapa === "selecao" ? (
          <div className="space-y-4">
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs text-neutral-500 uppercase tracking-wider">
                  Lojas ({selecionados.size} de {depositos.length})
                </label>
                <div className="flex items-center gap-2">
                  <button onClick={() => setSelecionados(new Set(depositos.map(d => d.id)))} className="text-[10px] text-indigo-400 hover:text-indigo-300">Selecionar todas</button>
                  <span className="text-neutral-700">·</span>
                  <button onClick={() => setSelecionados(new Set())} className="text-[10px] text-neutral-500 hover:text-neutral-300">Limpar</button>
                </div>
              </div>
              {depositos.length === 0 ? (
                <p className="text-xs text-amber-400">Nenhum depósito Bling encontrado.</p>
              ) : (
                <div className="max-h-56 overflow-y-auto space-y-1 border border-neutral-800 rounded-lg p-2">
                  {depositos.map(d => (
                    <label key={d.id} className="flex items-center justify-between gap-2 text-xs text-neutral-300 px-1 py-1 hover:bg-neutral-800/50 rounded cursor-pointer">
                      <span className="flex items-center gap-2">
                        <input type="checkbox" checked={selecionados.has(d.id)} onChange={() => toggleDeposito(d.id)} className="accent-indigo-600" />
                        {d.descricao}
                      </span>
                      <span className="font-mono numeric text-neutral-500">{estoqueAtual[d.id] ?? 0}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={onClose} className="text-xs text-neutral-500 hover:text-neutral-300 px-3 py-1.5">Cancelar</button>
              <button
                onClick={avancarParaEdicao}
                disabled={selecionados.size === 0}
                className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs px-4 py-1.5 rounded-lg transition-colors"
              >
                Continuar
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-800 text-neutral-500 text-xs uppercase">
                  <th className="text-left px-2 py-1.5 font-medium">Loja</th>
                  <th className="text-right px-2 py-1.5 font-medium">Estoque</th>
                  {concluido && <th className="text-right px-2 py-1.5 font-medium">Status</th>}
                </tr>
              </thead>
              <tbody>
                {Array.from(selecionados).map((id) => {
                  const deposito = depositos.find(d => d.id === id);
                  return (
                    <tr key={id} className="border-b border-neutral-800/30">
                      <td className="px-2 py-1.5 text-neutral-300 text-xs">{deposito?.descricao}</td>
                      <td className="px-2 py-1.5 text-right">
                        <input
                          type="number"
                          value={valores[id] ?? ""}
                          onChange={(e) => setValores(v => ({ ...v, [id]: e.target.value }))}
                          disabled={salvando || concluido}
                          className="w-20 bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-right text-neutral-200 numeric disabled:opacity-60"
                        />
                      </td>
                      {concluido && (
                        <td className="px-2 py-1.5 text-right text-xs">
                          {status[id] === "ok" && <span className="text-emerald-400">salvo</span>}
                          {status[id] === "erro" && <span className="text-red-400">falhou</span>}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div className="flex justify-end gap-2 pt-2">
              {!concluido && (
                <button onClick={() => setEtapa("selecao")} disabled={salvando} className="text-xs text-neutral-500 hover:text-neutral-300 px-3 py-1.5">
                  Voltar
                </button>
              )}
              <button onClick={onClose} className="text-xs text-neutral-500 hover:text-neutral-300 px-3 py-1.5">
                {concluido ? "Fechar" : "Cancelar"}
              </button>
              {!concluido && (
                <button
                  onClick={handleSalvar}
                  disabled={salvando}
                  className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs px-4 py-1.5 rounded-lg transition-colors"
                >
                  {salvando ? "Salvando..." : "Salvar"}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
