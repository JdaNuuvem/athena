"use client";

import { useEffect, useState } from "react";
import Spinner from "./shared/Spinner";
import Alert from "./shared/Alert";
import { listarBlingDepositos, obterSaldoDeposito, atualizarEstoqueDeposito, BlingDeposito } from "@/lib/api";

interface StockModalProps {
  produto: { id: number; codigo: string; nome: string; preco: number };
  onClose: () => void;
  onSaved: () => void;
}

interface SaldoDeposito {
  idDeposito: number;
  nome: string;
  saldo: number;
  ajuste: number;
}

export default function StockModal({ produto, onClose, onSaved }: StockModalProps) {
  const [saldos, setSaldos] = useState<SaldoDeposito[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);

  useEffect(() => {
    async function carregar() {
      try {
        const [depositos] = await Promise.all([listarBlingDepositos()]);
        const deps = (depositos.data || []) as BlingDeposito[];
        
        const rows: SaldoDeposito[] = [];
        for (const d of deps) {
          try {
            const r = await obterSaldoDeposito(d.id, [produto.id]);
            const item = (r.data || []).find((x: any) => x.idProduto === produto.id);
            rows.push({
              idDeposito: d.id,
              nome: d.descricao,
              saldo: item ? (item.saldo ?? item.saldoFisico ?? item.saldoVirtual ?? 0) : 0,
              ajuste: 0,
            });
          } catch {
            rows.push({ idDeposito: d.id, nome: d.descricao, saldo: 0, ajuste: 0 });
          }
        }
        setSaldos(rows);
      } catch (e) {
        setErro(e instanceof Error ? e.message : "Erro ao carregar estoque");
      } finally {
        setLoading(false);
      }
    }
    carregar();
  }, [produto.id]);

  const totalGeral = saldos.reduce((s, d) => s + d.saldo, 0);

  const handleAjuste = (idx: number, delta: number) => {
    setSaldos((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], ajuste: Math.max(-next[idx].saldo, next[idx].ajuste + delta) };
      return next;
    });
  };

  const handleSplit = () => {
    const count = saldos.length || 1;
    const perDeposit = Math.floor(totalGeral / count);
    setSaldos((prev) => prev.map((d) => ({
      ...d,
      ajuste: perDeposit - d.saldo,
    })));
  };

  const handleSave = async (idx: number) => {
    const s = saldos[idx];
    if (s.ajuste === 0) return;
    try {
      setSaving(true);
      await atualizarEstoqueDeposito({
        idDeposito: s.idDeposito,
        idProduto: produto.id,
        operacao: s.ajuste > 0 ? "E" : "S",
        quantidade: Math.abs(s.ajuste),
      });
      setSaldos((prev) => {
        const next = [...prev];
        next[idx] = { ...next[idx], saldo: next[idx].saldo + next[idx].ajuste, ajuste: 0 };
        return next;
      });
      setSucesso(`${s.nome}: ${s.ajuste > 0 ? "+" : ""}${s.ajuste}`);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao salvar");
    } finally {
      setSaving(false);
      setTimeout(() => setSucesso(null), 2000);
    }
  };

  const saldoColor = (q: number) => q <= 0 ? "text-red-400" : q < 10 ? "text-yellow-400" : "text-emerald-400";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-neutral-850 border border-neutral-700 rounded-xl w-full max-w-lg mx-4 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b border-neutral-700">
          <div>
            <h3 className="text-sm font-semibold text-neutral-100">Estoque — {produto.codigo}</h3>
            <p className="text-[10px] text-neutral-500">{produto.nome}</p>
          </div>
          <button onClick={onClose} className="text-neutral-500 hover:text-neutral-300 text-lg leading-none">✕</button>
        </div>

        <div className="p-4 space-y-3 max-h-[60vh] overflow-y-auto">
          <Alert message={erro} type="error" />
          <Alert message={sucesso} type="success" />

          {loading ? (
            <Spinner />
          ) : saldos.length === 0 ? (
            <p className="text-xs text-neutral-500 text-center py-4">Nenhum depósito encontrado</p>
          ) : (
            <>
              {/* Cabeçalho total */}
              <div className="flex items-center justify-between bg-neutral-900 rounded-lg px-3 py-2">
                <span className="text-xs text-neutral-400">Total Geral</span>
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-bold ${saldoColor(totalGeral)}`}>{totalGeral}</span>
                  <button
                    onClick={handleSplit}
                    className="text-[10px] bg-indigo-600 hover:bg-indigo-500 text-white px-2 py-0.5 rounded transition-colors"
                    title="Dividir estoque igualmente entre todos os depósitos"
                  >
                    Dividir Igualmente
                  </button>
                </div>
              </div>

              {saldos.map((s, i) => (
                <div key={s.idDeposito} className="bg-neutral-800 border border-neutral-700/50 rounded-lg px-3 py-2.5 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-neutral-300 font-medium truncate max-w-[180px]">{s.nome}</span>
                    <div className="flex items-center gap-2">
                      {s.ajuste !== 0 && (
                        <button
                          onClick={() => handleSave(i)}
                          disabled={saving}
                          className="text-[10px] bg-emerald-600 hover:bg-emerald-500 text-white px-2 py-0.5 rounded transition-colors"
                        >
                          Salvar
                        </button>
                      )}
                      <span className={`text-sm font-mono font-bold ${saldoColor(s.saldo)}`}>
                        {s.saldo}
                      </span>
                      {s.ajuste !== 0 && (
                        <span className={`text-[10px] font-bold ${s.ajuste > 0 ? "text-emerald-400" : "text-red-400"}`}>
                          {s.ajuste > 0 ? "+" : ""}{s.ajuste}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => handleAjuste(i, -10)}
                      className="text-[10px] bg-neutral-700 hover:bg-neutral-600 text-neutral-300 px-1.5 py-0.5 rounded"
                    >−10</button>
                    <button
                      onClick={() => handleAjuste(i, -1)}
                      className="text-[10px] bg-neutral-700 hover:bg-neutral-600 text-neutral-300 px-1.5 py-0.5 rounded"
                    >−1</button>
                    <input
                      type="number"
                      value={s.ajuste}
                      onChange={(e) => {
                        const v = Number(e.target.value);
                        setSaldos((prev) => {
                          const next = [...prev];
                          next[i] = { ...next[i], ajuste: Math.max(-next[i].saldo, v || 0) };
                          return next;
                        });
                      }}
                      className="flex-1 bg-neutral-900 border border-neutral-600 rounded px-2 py-1 text-xs text-neutral-200 text-center w-16"
                      placeholder="Ajuste"
                    />
                    <button
                      onClick={() => handleAjuste(i, 1)}
                      className="text-[10px] bg-neutral-700 hover:bg-neutral-600 text-neutral-300 px-1.5 py-0.5 rounded"
                    >+1</button>
                    <button
                      onClick={() => handleAjuste(i, 10)}
                      className="text-[10px] bg-neutral-700 hover:bg-neutral-600 text-neutral-300 px-1.5 py-0.5 rounded"
                    >+10</button>
                  </div>
                </div>
              ))}

              {/* Salvar todos */}
              {saldos.some((s) => s.ajuste !== 0) && (
                <button
                  onClick={async () => {
                    for (let i = 0; i < saldos.length; i++) {
                      if (saldos[i].ajuste !== 0) await handleSave(i);
                    }
                    onSaved();
                  }}
                  disabled={saving}
                  className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs rounded-lg transition-colors"
                >
                  Salvar Todos os Ajustes
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
