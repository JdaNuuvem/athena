"use client";

import { useEffect, useState, useMemo } from "react";
import { api } from "@/lib/api";
import type {
  RankingProdutoItem, ProdutoTendenciaItem, CurvaAbcItem, EstoqueParadoItem, RiscoRupturaItem,
} from "@/lib/api";
import TabBar from "./TabBar";
import LoadingState from "./LoadingState";
import ErrorAlert from "./ErrorAlert";
import Icon from "./Icon";

type Categoria = "vendas" | "lucratividade" | "estoque";
type Aba =
  | "vendidos" | "menos_vendidos" | "em_alta" | "em_queda"
  | "lucro" | "menos_lucro" | "margem" | "abc"
  | "parado" | "ruptura";

const CATEGORIAS: { key: Categoria; label: string }[] = [
  { key: "vendas", label: "Vendas" },
  { key: "lucratividade", label: "Lucratividade" },
  { key: "estoque", label: "Estoque" },
];

const ABAS_POR_CATEGORIA: Record<Categoria, { key: Aba; label: string }[]> = {
  vendas: [
    { key: "vendidos", label: "Mais vendidos" },
    { key: "menos_vendidos", label: "Menos vendidos" },
    { key: "em_alta", label: "Em alta" },
    { key: "em_queda", label: "Em queda" },
  ],
  lucratividade: [
    { key: "lucro", label: "Mais lucro" },
    { key: "menos_lucro", label: "Menos lucro" },
    { key: "margem", label: "Maior margem %" },
    { key: "abc", label: "Curva ABC" },
  ],
  estoque: [
    { key: "parado", label: "Parado em estoque" },
    { key: "ruptura", label: "Risco de ruptura" },
  ],
};

const ABA_PADRAO: Record<Categoria, Aba> = { vendas: "vendidos", lucratividade: "lucro", estoque: "parado" };

function fmtBRL(v: number) {
  return "R$ " + v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function ItemCard({ rank, titulo, subtitulo, children }: { rank: number; titulo: string; subtitulo: React.ReactNode; children: React.ReactNode }) {
  return (
    <div
      className="instrument-hover flex items-center gap-3 px-3 py-2 rounded-lg"
      style={{ background: "var(--panel-850)", border: "1px solid var(--panel-border)" }}
    >
      <span className="numeric text-xs w-5 text-right shrink-0" style={{ color: "var(--ink-700)" }}>{rank}</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm truncate" style={{ color: "var(--ink-100)" }}>{titulo}</p>
        <p className="font-mono text-xs" style={{ color: "var(--ink-500)" }}>{subtitulo}</p>
      </div>
      <div className="text-right shrink-0">{children}</div>
    </div>
  );
}

export default function RankingProdutosModal({ onClose, lojaId }: { onClose: () => void; lojaId?: string }) {
  const [dias, setDias] = useState(30);
  const [categoria, setCategoria] = useState<Categoria>("vendas");
  const [aba, setAba] = useState<Aba>("vendidos");
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const [ranking, setRanking] = useState<RankingProdutoItem[]>([]);
  const [tendencia, setTendencia] = useState<ProdutoTendenciaItem[]>([]);
  const [abc, setAbc] = useState<CurvaAbcItem[]>([]);
  const [parado, setParado] = useState<EstoqueParadoItem[]>([]);
  const [ruptura, setRuptura] = useState<RiscoRupturaItem[]>([]);

  useEffect(() => {
    setLoading(true);
    setErro(null);
    const tarefas: Promise<unknown>[] =
      categoria === "vendas"
        ? [
            api.relatorioRankingProdutos(dias, lojaId).then((r) => setRanking(r.itens || [])),
            api.relatorioProdutosTendencia(dias, lojaId).then(setTendencia),
          ]
        : categoria === "lucratividade"
        ? [
            api.relatorioRankingProdutos(dias, lojaId).then((r) => setRanking(r.itens || [])),
            api.relatorioCurvas(dias, lojaId).then((r) => setAbc(r.itens || [])),
          ]
        : [
            api.relatorioEstoqueParado(dias, 15, lojaId).then(setParado),
            api.relatorioRiscoRuptura(dias, lojaId).then(setRuptura),
          ];
    Promise.all(tarefas)
      .catch((e) => setErro(e instanceof Error ? e.message : "Erro ao carregar ranking"))
      .finally(() => setLoading(false));
  }, [categoria, dias, lojaId]);

  const trocarCategoria = (novaCategoria: string) => {
    const cat = novaCategoria as Categoria;
    setCategoria(cat);
    setAba(ABA_PADRAO[cat]);
  };

  const vendidos = useMemo(() => ranking.filter((i) => i.quantidade > 0), [ranking]);

  const listaVendas = useMemo(() => {
    if (aba === "vendidos") return [...vendidos].sort((a, b) => b.quantidade - a.quantidade).slice(0, 15);
    if (aba === "menos_vendidos") return [...vendidos].sort((a, b) => a.quantidade - b.quantidade).slice(0, 15);
    return [];
  }, [vendidos, aba]);

  const listaTendencia = useMemo(() => {
    if (aba === "em_alta") {
      return [...tendencia]
        .filter((t) => t.crescimento_pct === null || t.crescimento_pct > 0)
        .sort((a, b) => {
          if (a.crescimento_pct === null && b.crescimento_pct === null) return b.quantidade_atual - a.quantidade_atual;
          if (a.crescimento_pct === null) return -1;
          if (b.crescimento_pct === null) return 1;
          return b.crescimento_pct - a.crescimento_pct;
        })
        .slice(0, 15);
    }
    if (aba === "em_queda") {
      return [...tendencia]
        .filter((t) => t.crescimento_pct !== null && t.crescimento_pct < 0)
        .sort((a, b) => (a.crescimento_pct as number) - (b.crescimento_pct as number))
        .slice(0, 15);
    }
    return [];
  }, [tendencia, aba]);

  const listaLucratividade = useMemo(() => {
    if (aba === "lucro") return [...vendidos].sort((a, b) => b.lucro - a.lucro).slice(0, 15);
    if (aba === "menos_lucro") return [...vendidos].sort((a, b) => a.lucro - b.lucro).slice(0, 15);
    if (aba === "margem")
      return [...vendidos].filter((i) => i.custo_cadastrado).sort((a, b) => b.margem_pct - a.margem_pct).slice(0, 15);
    return [];
  }, [vendidos, aba]);

  const listaAbc = useMemo(() => (aba === "abc" ? abc : []), [abc, aba]);
  const listaParado = useMemo(() => (aba === "parado" ? parado : []), [parado, aba]);
  const listaRuptura = useMemo(() => (aba === "ruptura" ? ruptura : []), [ruptura, aba]);

  const vazio =
    (categoria === "vendas" && (aba === "vendidos" || aba === "menos_vendidos") && listaVendas.length === 0) ||
    (categoria === "vendas" && (aba === "em_alta" || aba === "em_queda") && listaTendencia.length === 0) ||
    (categoria === "lucratividade" && aba !== "abc" && listaLucratividade.length === 0) ||
    (categoria === "lucratividade" && aba === "abc" && listaAbc.length === 0) ||
    (categoria === "estoque" && aba === "parado" && listaParado.length === 0) ||
    (categoria === "estoque" && aba === "ruptura" && listaRuptura.length === 0);

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
              Todos os canais — Shopee (virtual) e i9Logic (física) — últimos {dias} dias
            </p>
          </div>
          <button onClick={onClose} style={{ color: "var(--ink-500)" }} aria-label="Fechar">
            <Icon name="close" size={16} />
          </button>
        </div>

        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <TabBar tabs={CATEGORIAS} active={categoria} onChange={trocarCategoria} />
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

        <div className="mb-4">
          <TabBar tabs={ABAS_POR_CATEGORIA[categoria]} active={aba} onChange={(k) => setAba(k as Aba)} />
        </div>

        {loading ? (
          <div className="py-8 text-center"><LoadingState message="Calculando ranking..." /></div>
        ) : erro ? (
          <ErrorAlert message={erro} />
        ) : vazio ? (
          <p className="text-xs py-8 text-center" style={{ color: "var(--ink-500)" }}>
            {categoria === "estoque" && aba === "ruptura"
              ? "Nenhum produto vendendo com estoque em risco de acabar no período."
              : "Nenhum dado no período."}
          </p>
        ) : (
          <div className="space-y-1.5">
            {(aba === "vendidos" || aba === "menos_vendidos") &&
              listaVendas.map((item, i) => (
                <ItemCard
                  key={item.sku}
                  rank={i + 1}
                  titulo={item.descricao}
                  subtitulo={
                    <>
                      {item.sku} · {item.quantidade} un
                      {!item.custo_cadastrado && <span style={{ color: "var(--status-warn)" }}> · custo não cadastrado</span>}
                    </>
                  }
                >
                  <p className="numeric text-sm font-medium" style={{ color: "var(--ink-100)" }}>{item.quantidade} un</p>
                  <p className="numeric text-xs" style={{ color: "var(--ink-700)" }}>{fmtBRL(item.receita)}</p>
                </ItemCard>
              ))}

            {(aba === "em_alta" || aba === "em_queda") &&
              listaTendencia.map((item, i) => (
                <ItemCard
                  key={item.sku}
                  rank={i + 1}
                  titulo={item.descricao}
                  subtitulo={`${item.sku} · ${item.quantidade_atual} un (era ${item.quantidade_anterior})`}
                >
                  {item.crescimento_pct === null ? (
                    <p className="numeric text-sm font-medium" style={{ color: "var(--status-ok)" }}>Novo</p>
                  ) : (
                    <p
                      className="numeric text-sm font-medium"
                      style={{ color: item.crescimento_pct >= 0 ? "var(--status-ok)" : "var(--status-crit)" }}
                    >
                      {item.crescimento_pct >= 0 ? "+" : ""}
                      {item.crescimento_pct}%
                    </p>
                  )}
                </ItemCard>
              ))}

            {(aba === "lucro" || aba === "menos_lucro" || aba === "margem") &&
              listaLucratividade.map((item, i) => (
                <ItemCard
                  key={item.sku}
                  rank={i + 1}
                  titulo={item.descricao}
                  subtitulo={
                    <>
                      {item.sku} · {item.quantidade} un
                      {!item.custo_cadastrado && <span style={{ color: "var(--status-warn)" }}> · custo não cadastrado</span>}
                    </>
                  }
                >
                  <p className="numeric text-sm font-medium" style={{ color: item.lucro >= 0 ? "var(--status-ok)" : "var(--status-crit)" }}>
                    {fmtBRL(item.lucro)}
                  </p>
                  <p className="numeric text-xs" style={{ color: "var(--ink-700)" }}>{item.margem_pct}% margem</p>
                </ItemCard>
              ))}

            {aba === "abc" &&
              listaAbc.map((item, i) => (
                <ItemCard key={`${item.sku}-${i}`} rank={i + 1} titulo={item.descricao} subtitulo={`${item.sku} · ${item.qtd} un · ${item.pct_acum}% acumulado`}>
                  <p className="numeric text-sm font-medium" style={{ color: "var(--ink-100)" }}>{fmtBRL(item.valor_total)}</p>
                  <span
                    className="numeric text-[10px] font-semibold px-1.5 py-0.5 rounded"
                    style={{
                      color: item.classe === "A" ? "var(--status-ok)" : item.classe === "B" ? "var(--status-warn)" : "var(--ink-500)",
                      border: "1px solid currentColor",
                    }}
                  >
                    Classe {item.classe}
                  </span>
                </ItemCard>
              ))}

            {aba === "parado" &&
              listaParado.map((item, i) => (
                <ItemCard key={item.sku} rank={i + 1} titulo={item.nome} subtitulo={`${item.sku} · ${item.quantidade} un paradas`}>
                  <p className="numeric text-sm font-medium" style={{ color: "var(--status-warn)" }}>{fmtBRL(item.valor_imobilizado)}</p>
                  <p className="numeric text-xs" style={{ color: "var(--ink-700)" }}>sem venda há {item.dias_sem_venda}d</p>
                </ItemCard>
              ))}

            {aba === "ruptura" &&
              listaRuptura.map((item, i) => (
                <ItemCard key={item.sku} rank={i + 1} titulo={item.descricao} subtitulo={`${item.sku} · ${item.estoque_atual} un em estoque`}>
                  <p className="numeric text-sm font-medium" style={{ color: item.dias_restantes <= 7 ? "var(--status-crit)" : "var(--status-warn)" }}>
                    {item.dias_restantes}d restantes
                  </p>
                  <p className="numeric text-xs" style={{ color: "var(--ink-700)" }}>{item.velocidade_diaria}/dia</p>
                </ItemCard>
              ))}
          </div>
        )}
      </div>
    </div>
  );
}
