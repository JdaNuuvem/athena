"use client";

import { useState, useEffect } from "react";

interface DreLoja {
  loja_id: number; loja_nome: string;
  receita: number; qtd_vendas: number;
  comissao_pct: number; comissao_valor: number;
  frete: number; custos_producao: number;
  lucro: number; margem_pct: number;
  periodo_dias: number;
}

export default function DreLojasPage() {
  const [data, setData] = useState<DreLoja[]>([]);
  const [dias, setDias] = useState(30);
  const [loading, setLoading] = useState(true);

  const carregar = (d: number) => {
    setLoading(true);
    fetch(`/api/relatorios/dre-por-loja?dias=${d}`)
      .then(r => r.json()).then(r => setData(r.data || []))
      .finally(() => setLoading(false));
  };

  useEffect(() => { carregar(dias); }, [dias]);

  const total = data.reduce((s, l) => ({
    receita: s.receita + l.receita,
    lucro: s.lucro + l.lucro,
    comissao: s.comissao + l.comissao_valor,
    frete: s.frete + l.frete,
  }), { receita: 0, lucro: 0, comissao: 0, frete: 0 });

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-lg font-bold text-neutral-100">DRE por Loja</h1>
          <p className="text-xs text-neutral-500 mt-1">Receita, custos e lucro real de cada canal</p>
        </div>
        <select value={dias} onChange={e => setDias(Number(e.target.value))}
          className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200">
          {[7, 15, 30, 60, 90].map(d => <option key={d} value={d}>Últimos {d} dias</option>)}
        </select>
      </div>

      {!loading && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
            <p className="text-xs text-neutral-500">Receita Total</p>
            <p className="text-xl font-bold text-emerald-400">R$ {total.receita.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</p>
          </div>
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
            <p className="text-xs text-neutral-500">Comissão Total</p>
            <p className="text-xl font-bold text-amber-400">R$ {total.comissao.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</p>
          </div>
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
            <p className="text-xs text-neutral-500">Frete Total</p>
            <p className="text-xl font-bold text-blue-400">R$ {total.frete.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</p>
          </div>
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4">
            <p className="text-xs text-neutral-500">Lucro Líquido</p>
            <p className={"text-xl font-bold " + (total.lucro >= 0 ? "text-emerald-400" : "text-red-400")}>
              R$ {total.lucro.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
            </p>
          </div>
        </div>
      )}

      {loading ? (
        <p className="text-neutral-500 text-sm">Carregando...</p>
      ) : data.length === 0 ? (
        <p className="text-neutral-500 text-sm">Nenhuma loja com dados no período.</p>
      ) : (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-800 text-neutral-500 text-xs">
                <th className="text-left p-3">Loja</th>
                <th className="text-right p-3">Vendas</th>
                <th className="text-right p-3">Receita</th>
                <th className="text-right p-3">Comissão</th>
                <th className="text-right p-3">Frete</th>
                <th className="text-right p-3">Custos</th>
                <th className="text-right p-3">Lucro</th>
                <th className="text-right p-3">Margem</th>
              </tr>
            </thead>
            <tbody>
              {data.map(l => (
                <tr key={l.loja_id} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                  <td className="p-3 text-neutral-200 font-medium">{l.loja_nome}</td>
                  <td className="p-3 text-right text-neutral-400">{l.qtd_vendas}</td>
                  <td className="p-3 text-right text-emerald-400">R$ {l.receita.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
                  <td className="p-3 text-right text-amber-400">R$ {l.comissao_valor.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
                  <td className="p-3 text-right text-blue-400">R$ {l.frete.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
                  <td className="p-3 text-right text-neutral-400">R$ {l.custos_producao.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
                  <td className={"p-3 text-right font-bold " + (l.lucro >= 0 ? "text-emerald-400" : "text-red-400")}>
                    R$ {l.lucro.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="p-3 text-right">
                    <span className={"px-2 py-0.5 rounded text-xs " + (l.margem_pct >= 20 ? "bg-emerald-900/30 text-emerald-400" : l.margem_pct >= 0 ? "bg-amber-900/30 text-amber-400" : "bg-red-900/30 text-red-400")}>
                      {l.margem_pct}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
