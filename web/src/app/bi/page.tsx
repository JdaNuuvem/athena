"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import type { KpiMetric, SubmenuItem, AcoesDoMes, VariacaoMensal } from "./types";
import { formatCurrency } from "./types";
import PageHeader from "@/app/_components/PageHeader";
import KpiCard from "@/app/_components/KpiCard";
import Icon from "@/app/_components/Icon";
import ErroCarregamento from "./_components/ErroCarregamento";
import ExportButtons from "@/app/_components/ExportButtons";

interface DashboardKpiRaw { label: string; value: string; color: string; variacao?: VariacaoMensal | null }

const DEFAULT_SUBMENU: SubmenuItem[] = [
  { href: "/bi/vendas", label: "Vendas & Drill-down", color: "bg-blue-600" },
  { href: "/bi/indicadores", label: "Indicadores", color: "bg-amber-600" },
  { href: "/bi/forecast", label: "Forecast", color: "bg-purple-600" },
  { href: "/bi/ml", label: "Machine Learning", color: "bg-emerald-600" },
  { href: "/bi/lojas", label: "Lojas", color: "bg-rose-600" },
];

export default function BiPage() {
  const [kpis, setKpis] = useState<KpiMetric[]>([]);
  const [acoes, setAcoes] = useState<AcoesDoMes | null>(null);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState(false);

  const load = useCallback(() => {
    setLoading(true); setErro(false);
    Promise.all([
      fetch("/api/bi/dashboard").then(r => r.ok ? r.json() : Promise.reject()),
      fetch("/api/bi/acoes-mes").then(r => r.ok ? r.json() : Promise.reject()),
    ]).then(([dash, ac]: [{ kpis: DashboardKpiRaw[] }, AcoesDoMes]) => {
      setKpis(dash.kpis.map(k => ({
        label: k.label, value: k.value, color: k.color,
        sub: k.variacao?.label,
      })));
      setAcoes(ac);
    }).catch(() => setErro(true))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="p-6 text-neutral-400">Carregando...</div>;
  if (erro) return <ErroCarregamento onRetry={load} />;

  const temAcoes = acoes && (acoes.capital_parado || acoes.inadimplencia || acoes.clientes_em_risco || acoes.maior_anomalia);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between gap-3">
        <PageHeader title="BI" subtitle="Business Intelligence, dashboards e análises" />
        <ExportButtons
          columns={["Indicador", "Valor", "Variação"]}
          rows={kpis.map(k => [k.label, k.value, k.sub || ""])}
          filename="bi-dashboard" title="Dashboard BI"
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {kpis.map(kpi => <KpiCard key={kpi.label} metric={kpi} />)}
      </div>

      {temAcoes && (
        <div>
          <h2 className="text-sm font-semibold text-neutral-300 mb-3">Ações do Mês</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {acoes?.capital_parado && (
              <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <Icon name="estoque" size={15} className="text-amber-400" />
                  <h3 className="text-xs font-semibold text-neutral-200">Capital parado em estoque</h3>
                </div>
                <p className="text-lg font-bold text-amber-400">{formatCurrency(acoes.capital_parado.total_valor)}</p>
                <p className="text-[11px] text-neutral-500">
                  {acoes.capital_parado.itens.length} produto(s) sem venda nos últimos 60 dias, parados no estoque.
                </p>
                <ul className="text-[11px] text-neutral-400 space-y-0.5">
                  {acoes.capital_parado.itens.slice(0, 3).map(i => (
                    <li key={i.sku} className="flex justify-between">
                      <span className="truncate">{i.nome}</span>
                      <span className="font-mono text-neutral-300 shrink-0 ml-2">{formatCurrency(i.valor_imobilizado)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {acoes?.inadimplencia && (
              <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <Icon name="alert" size={15} className="text-red-400" />
                  <h3 className="text-xs font-semibold text-neutral-200">Inadimplência</h3>
                </div>
                <p className="text-lg font-bold text-red-400">{formatCurrency(acoes.inadimplencia.total_valor)}</p>
                <p className="text-[11px] text-neutral-500">
                  {acoes.inadimplencia.total_qtd} conta(s) a receber vencidas.
                </p>
                <ul className="text-[11px] text-neutral-400 space-y-0.5">
                  {acoes.inadimplencia.maiores_devedores.slice(0, 3).map((d, i) => (
                    <li key={i} className="flex justify-between">
                      <span className="truncate">{d.cliente} ({d.dias_vencido}d)</span>
                      <span className="font-mono text-neutral-300 shrink-0 ml-2">{formatCurrency(d.valor)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {acoes?.clientes_em_risco && (
              <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <Icon name="user" size={15} className="text-purple-400" />
                  <h3 className="text-xs font-semibold text-neutral-200">Clientes de alto valor em risco</h3>
                </div>
                <p className="text-lg font-bold text-purple-400">{acoes.clientes_em_risco.qtd_clientes} cliente(s)</p>
                <p className="text-[11px] text-neutral-500">Compraram bastante, mas sumiram nos últimos meses — considere reengajar.</p>
                <ul className="text-[11px] text-neutral-400 space-y-0.5">
                  {acoes.clientes_em_risco.clientes.slice(0, 3).map((c, i) => (
                    <li key={i} className="flex justify-between">
                      <span className="truncate">{c.nome}</span>
                      <span className="font-mono text-neutral-300 shrink-0 ml-2">{formatCurrency(c.valor)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {acoes?.maior_anomalia && (
              <div className="space-y-2">
                <div className="flex items-center gap-2 px-1">
                  <Icon name="bi" size={15} className="text-blue-400" />
                  <h3 className="text-xs font-semibold text-neutral-200">Anomalia de destaque</h3>
                </div>
                <Link href="/bi/ml" className="block">
                  <div className="text-xs text-neutral-500 hover:text-neutral-300">
                    {acoes.maior_anomalia.descricao}
                  </div>
                </Link>
              </div>
            )}
          </div>
        </div>
      )}

      <div>
        <h2 className="text-sm font-semibold text-neutral-300 mb-3">Módulos</h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {DEFAULT_SUBMENU.map(item => (
            <Link
              key={item.href}
              href={item.href}
              className={`${item.color} hover:opacity-90 text-white rounded-lg p-4 transition-opacity`}
            >
              <p className="text-sm font-semibold">{item.label}</p>
              <p className="text-[10px] opacity-80 mt-1">Acessar {item.label.toLowerCase()}</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
