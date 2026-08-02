"use client";

import { useState, useEffect } from "react";
import { fiscalNFItens, fiscalNFImpostos } from "@/lib/api";
import { formatCurrency } from "../../types";

interface ItemNota {
  id: number;
  numero_item: number;
  codigo: string;
  descricao: string;
  ncm: string;
  cfop: string;
  unidade: string;
  quantidade: number;
  valor_unitario: number;
  valor_total: number;
}

interface ImpostoNota {
  id: number;
  nome: string;
  sigla: string;
  base_calculo: number;
  aliquota: number;
  valor: number;
  retido: boolean;
}

export default function NotaDetalhesModal({
  notaId, numero, onFechar,
}: {
  notaId: number;
  numero: string;
  onFechar: () => void;
}) {
  const [itens, setItens] = useState<ItemNota[]>([]);
  const [impostos, setImpostos] = useState<ImpostoNota[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");

  useEffect(() => {
    let cancelado = false;
    setLoading(true);
    setErro("");
    Promise.all([fiscalNFItens(notaId), fiscalNFImpostos(notaId)])
      .then(([itensRes, impostosRes]) => {
        if (cancelado) return;
        setItens((itensRes.data || []) as ItemNota[]);
        setImpostos((impostosRes.data || []) as ImpostoNota[]);
      })
      .catch((e) => { if (!cancelado) setErro(e instanceof Error ? e.message : "Erro ao carregar detalhes"); })
      .finally(() => { if (!cancelado) setLoading(false); });
    return () => { cancelado = true; };
  }, [notaId]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={onFechar}>
      <div className="w-full max-w-[720px] max-h-[85vh] overflow-y-auto rounded-xl border border-neutral-700 bg-neutral-800 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-neutral-700/70 px-5 py-4">
          <h3 className="text-sm font-semibold text-neutral-100">Nota {numero} — Itens e Impostos</h3>
          <button onClick={onFechar} className="text-neutral-500 hover:text-neutral-300 text-sm">✕</button>
        </div>

        <div className="px-5 py-4 space-y-5">
          {loading ? (
            <p className="text-xs text-neutral-500">Carregando...</p>
          ) : erro ? (
            <div className="text-xs px-3 py-2 rounded-lg border bg-red-950/40 border-red-900/50 text-red-400">{erro}</div>
          ) : (
            <>
              <section>
                <h4 className="text-xs font-medium text-neutral-400 mb-2">Itens ({itens.length})</h4>
                {itens.length === 0 ? (
                  <p className="text-[11px] text-neutral-500">Nenhum item sincronizado para esta nota.</p>
                ) : (
                  <div className="overflow-x-auto border border-neutral-700 rounded-lg">
                    <table className="w-full text-[11px]">
                      <thead>
                        <tr className="bg-neutral-900 text-neutral-400 text-left">
                          <th className="px-2 py-1.5 font-medium">Código</th>
                          <th className="px-2 py-1.5 font-medium">Descrição</th>
                          <th className="px-2 py-1.5 font-medium">NCM</th>
                          <th className="px-2 py-1.5 font-medium">CFOP</th>
                          <th className="px-2 py-1.5 font-medium text-right">Qtd</th>
                          <th className="px-2 py-1.5 font-medium text-right">Vlr. Unit.</th>
                          <th className="px-2 py-1.5 font-medium text-right">Vlr. Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {itens.map((i) => (
                          <tr key={i.id} className="border-t border-neutral-700/50 text-neutral-300">
                            <td className="px-2 py-1.5">{i.codigo || "—"}</td>
                            <td className="px-2 py-1.5">{i.descricao || "—"}</td>
                            <td className="px-2 py-1.5">{i.ncm || "—"}</td>
                            <td className="px-2 py-1.5">{i.cfop || "—"}</td>
                            <td className="px-2 py-1.5 text-right numeric">{i.quantidade}</td>
                            <td className="px-2 py-1.5 text-right numeric">{formatCurrency(Number(i.valor_unitario) || 0)}</td>
                            <td className="px-2 py-1.5 text-right numeric text-emerald-400">{formatCurrency(Number(i.valor_total) || 0)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              <section>
                <h4 className="text-xs font-medium text-neutral-400 mb-2">Impostos ({impostos.length})</h4>
                {impostos.length === 0 ? (
                  <p className="text-[11px] text-neutral-500">Nenhum imposto calculado para esta nota.</p>
                ) : (
                  <div className="overflow-x-auto border border-neutral-700 rounded-lg">
                    <table className="w-full text-[11px]">
                      <thead>
                        <tr className="bg-neutral-900 text-neutral-400 text-left">
                          <th className="px-2 py-1.5 font-medium">Tributo</th>
                          <th className="px-2 py-1.5 font-medium text-right">Base de Cálculo</th>
                          <th className="px-2 py-1.5 font-medium text-right">Alíquota</th>
                          <th className="px-2 py-1.5 font-medium text-right">Valor</th>
                          <th className="px-2 py-1.5 font-medium text-center">Retido</th>
                        </tr>
                      </thead>
                      <tbody>
                        {impostos.map((imp) => (
                          <tr key={imp.id} className="border-t border-neutral-700/50 text-neutral-300">
                            <td className="px-2 py-1.5">{imp.nome || imp.sigla || "—"}</td>
                            <td className="px-2 py-1.5 text-right numeric">{formatCurrency(Number(imp.base_calculo) || 0)}</td>
                            <td className="px-2 py-1.5 text-right numeric">{Number(imp.aliquota) || 0}%</td>
                            <td className="px-2 py-1.5 text-right numeric text-amber-400">{formatCurrency(Number(imp.valor) || 0)}</td>
                            <td className="px-2 py-1.5 text-center">{imp.retido ? "Sim" : "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            </>
          )}
        </div>

        <div className="flex justify-end border-t border-neutral-700/70 px-5 py-4">
          <button onClick={onFechar} className="rounded-lg px-3 py-1.5 text-xs text-neutral-400 hover:text-neutral-200">Fechar</button>
        </div>
      </div>
    </div>
  );
}
