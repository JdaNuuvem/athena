"use client";

import { useEffect, useState } from "react";
import Spinner from "./shared/Spinner";
import Alert from "./shared/Alert";
import {
  listarBlingDepositos,
  obterSaldoDeposito,
  atualizarEstoqueDeposito,
  BlingDeposito,
  BlingEstoqueSaldo,
} from "@/lib/api";

interface BulkStockModalProps {
  onClose: () => void;
}

export default function BulkStockModal({ onClose }: BulkStockModalProps) {
  const [depositos, setDepositos] = useState<BlingDeposito[]>([]);
  const [depositoSelecionado, setDepositoSelecionado] = useState<number | null>(null);
  const [saldos, setSaldos] = useState<BlingEstoqueSaldo[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingSaldo, setLoadingSaldo] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [operacao, setOperacao] = useState<"B" | "E" | "S">("B");
  const [idProduto, setIdProduto] = useState<number | "">("");
  const [quantidade, setQuantidade] = useState<number>(0);
  const [preco, setPreco] = useState<number>(0);

  useEffect(() => {
    async function carregarDepositos() {
      try {
        const r = await listarBlingDepositos();
        setDepositos(r.data || []);
      } catch (e) {
        setErro(e instanceof Error ? e.message : "Erro ao carregar depósitos");
      } finally {
        setLoading(false);
      }
    }
    carregarDepositos();
  }, []);

  useEffect(() => {
    if (!depositoSelecionado) return;
    async function carregarSaldos() {
      try {
        setLoadingSaldo(true);
        const r = await obterSaldoDeposito(depositoSelecionado!);
        setSaldos(r.data || []);
      } catch (e) {
        setErro(e instanceof Error ? e.message : "Erro ao carregar saldos");
      } finally {
        setLoadingSaldo(false);
      }
    }
    carregarSaldos();
  }, [depositoSelecionado]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!depositoSelecionado || idProduto === "" || quantidade <= 0) {
      setErro("Preencha todos os campos obrigatórios");
      return;
    }
    try {
      setErro(null);
      await atualizarEstoqueDeposito({
        idDeposito: depositoSelecionado,
        idProduto: Number(idProduto),
        operacao,
        quantidade,
        preco: preco || undefined,
      });
      setSucesso("Estoque atualizado com sucesso!");
      const r = await obterSaldoDeposito(depositoSelecionado);
      setSaldos(r.data || []);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro ao atualizar estoque");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-neutral-850 border border-neutral-700 rounded-xl w-full max-w-2xl mx-4 max-h-[80vh] overflow-y-auto shadow-2xl">
        <div className="flex items-center justify-between p-4 border-b border-neutral-700 sticky top-0 bg-neutral-850">
          <h3 className="text-sm font-semibold text-neutral-100">Gestão de Estoque</h3>
          <button onClick={onClose} className="text-neutral-500 hover:text-neutral-300 text-lg">✕</button>
        </div>

        <div className="p-4 space-y-4">
          <Alert message={erro} type="error" />
          <Alert message={sucesso} type="success" />

          {loading ? (
            <Spinner />
          ) : (
            <>
              <div>
                <label className="block text-xs text-neutral-400 mb-1">Depósito</label>
                <select value={depositoSelecionado || ""} onChange={(e) => setDepositoSelecionado(Number(e.target.value) || null)}
                  className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-xs text-neutral-200">
                  <option value="">Selecione um depósito...</option>
                  {depositos.map((d) => (
                    <option key={d.id} value={d.id}>{d.descricao}</option>
                  ))}
                </select>
              </div>

              <form onSubmit={handleSubmit} className="space-y-3 p-3 bg-neutral-800 rounded-lg">
                <h4 className="text-xs font-semibold text-neutral-300">Movimentação</h4>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[10px] text-neutral-500 mb-1">Operação</label>
                    <select value={operacao} onChange={(e) => setOperacao(e.target.value as "B" | "E" | "S")}
                      className="w-full bg-neutral-750 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200">
                      <option value="B">Balanço</option>
                      <option value="E">Entrada</option>
                      <option value="S">Saída</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-[10px] text-neutral-500 mb-1">ID Produto *</label>
                    <input type="number" value={idProduto} onChange={(e) => setIdProduto(Number(e.target.value) || "")}
                      className="w-full bg-neutral-750 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200" placeholder="ID no Bling" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[10px] text-neutral-500 mb-1">Quantidade *</label>
                    <input type="number" step="0.01" min="0" value={quantidade} onChange={(e) => setQuantidade(parseFloat(e.target.value) || 0)}
                      className="w-full bg-neutral-750 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200" />
                  </div>
                  <div>
                    <label className="block text-[10px] text-neutral-500 mb-1">Preço (opcional)</label>
                    <input type="number" step="0.01" min="0" value={preco} onChange={(e) => setPreco(parseFloat(e.target.value) || 0)}
                      className="w-full bg-neutral-750 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200" />
                  </div>
                </div>
                <button type="submit" className="w-full py-2 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500 transition-colors">Atualizar Estoque</button>
              </form>

              {depositoSelecionado && (
                <div>
                  <h4 className="text-xs font-semibold text-neutral-300 mb-2">Saldos Atuais {loadingSaldo && "(carregando...)"}</h4>
                  {saldos.length === 0 && !loadingSaldo ? (
                    <p className="text-xs text-neutral-500">Nenhum saldo disponível</p>
                  ) : (
                    <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden max-h-48 overflow-y-auto">
                      <table className="w-full text-[10px]">
                        <thead>
                          <tr className="border-b border-neutral-700 text-neutral-400">
                            <th className="text-left p-2">Código</th>
                            <th className="text-right p-2">Saldo</th>
                          </tr>
                        </thead>
                        <tbody>
                          {saldos.map((s) => (
                            <tr key={s.idProduto} className="border-b border-neutral-700/30">
                              <td className="p-2 text-neutral-200 font-mono">{s.codigo}</td>
                              <td className="p-2 text-right text-emerald-400">{s.saldo}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
