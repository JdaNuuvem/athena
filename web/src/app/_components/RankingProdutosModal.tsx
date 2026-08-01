"use client";

import { useEffect, useState, useMemo } from "react";
import { api } from "@/lib/api";
import type { RankingProdutoItem } from "@/lib/api";
import TabBar from "./TabBar";
import LoadingState from "./LoadingState";
import ErrorAlert from "./ErrorAlert";
import Icon from "./Icon";

type Aba = "lucro" | "vendidos" | "menos_vendidos";

const ABAS = [
  { key: "lucro", label: "Mais lucro" },
  { key: "vendidos", label: "Mais vendidos" },
  { key: "menos_vendidos", label: "Menos vendidos" },
];

function fmtBRL(v: number) {
  return "R$ " + v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function RankingProdutosModal({ onClose }: { onClose: () => void }) {
  const [itens, setItens] = useState<RankingProdutoItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [dias, setDias] = useState(30);
  const [aba, setAba] = useState<Aba>("lucro");

  useEffect(() => {
    setLoading(true);
    setErro(null);
    api.relatorioRankingProdutos(dias)
      .then(r => setItens(r.itens || []))
      .catch(e => setErro(e instanceof Error ? e.message : "Erro ao carregar ranking"))
      .finally(() => setLoading(false));
  }, [dias]);

  const ordenados = useMemo(() => {
    const vendidos = itens.filter(i => i.quantidade > 0);
    if (aba === "lucro") return [...vendidos].sort((a, b) => b.lucro - a.lucro).slice(0, 15);
    if (aba === "vendidos") return [...vendidos].sort((a, b) => b.quantidade - a.quantidade).slice(0, 15);
    return [...vendidos].sort((a, b) => a.quantidade - b.quantidade).slice(0, 15);
  }, [itens, aba]);

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="instrument-enter instrument w-full max-w-2xl max-h-[85vh] overflow-y-auto p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-sm font-medium" style={{ color: "var(--ink-100)" }}>Ranking de produtos</h2>
            <p className="text-xs mt-0.5" style={{ color: "var(--ink-500)" }}>
              Todos os canais — Shopee, marketplaces via Bling e loja física — últimos {dias} dias
            </p>
          </div>
          <button onClick={onClose} style={{ color: "var(--ink-500)" }} aria-label="Fechar">
            <Icon name="close" size={16} />
          </button>
        </div>

        <div className="flex items-center gap-2 mb-4 flex-wrap">
          <TabBar tabs={ABAS} active={aba} onChange={(k) => setAba(k as Aba)} />
          <select
            value={dias}
            onChange={(e) => setDias(Number(e.target.value))}
            className="text-xs rounded-lg px-2 py-1.5 ml-auto bg-neutral-800 border border-neutral-700 text-neutral-300"
          >
            <option value={7}>7 dias</option>
            <option value={30}>30 dias</option>
            <option value={90}>90 dias</option>
          </select>
        </div>

        {loading ? (
          <div className="py-8 text-center"><LoadingState message="Calculando ranking..." /></div>
        ) : erro ? (
          <ErrorAlert message={erro} />
        ) : ordenados.length === 0 ? (
          <p className="text-xs py-8 text-center" style={{ color: "var(--ink-500)" }}>Nenhuma venda no período.</p>
        ) : (
          <div className="space-y-1.5">
            {ordenados.map((item, i) => (
              <div
                key={item.sku}
                className="instrument-hover flex items-center gap-3 px-3 py-2 rounded-lg"
                style={{ background: "var(--panel-850)", border: "1px solid var(--panel-border)" }}
              >
                <span className="numeric text-xs w-5 text-right shrink-0" style={{ color: "var(--ink-700)" }}>{i + 1}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm truncate" style={{ color: "var(--ink-100)" }}>{item.descricao}</p>
                  <p className="font-mono text-xs" style={{ color: "var(--ink-500)" }}>
                    {item.sku} · {item.quantidade} un
                    {!item.custo_cadastrado && (
                      <span style={{ color: "var(--status-warn)" }}> · custo não cadastrado</span>
                    )}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p className="numeric text-sm font-medium" style={{ color: item.lucro >= 0 ? "var(--status-ok)" : "var(--status-crit)" }}>
                    {fmtBRL(item.lucro)}
                  </p>
                  <p className="numeric text-xs" style={{ color: "var(--ink-700)" }}>{item.margem_pct}% margem</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
