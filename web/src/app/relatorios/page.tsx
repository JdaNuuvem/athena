"use client";
import { useState, useEffect } from "react";
import Link from "next/link";

const REPORTS = [
  {href:"/relatorios/vendas",label:"Vendas",desc:"Total, quantidade e vendas diarias",icon:"💰",color:"border-l-blue-500"},
  {href:"/relatorios/lucro",label:"Lucro e Margem",desc:"Receita, custos, lucro e margem %",icon:"📈",color:"border-l-emerald-500"},
  {href:"/relatorios/ticket-medio",label:"Ticket Medio",desc:"Valor medio por venda",icon:"🎯",color:"border-l-indigo-500"},
  {href:"/relatorios/estoque",label:"Estoque",desc:"Itens, baixo estoque e rupturas",icon:"📦",color:"border-l-amber-500"},
  {href:"/relatorios/clientes",label:"Clientes",desc:"Total, novos e top compradores",icon:"👥",color:"border-l-purple-500"},
  {href:"/relatorios/fornecedores",label:"Fornecedores",desc:"Total, ativos e top por valor",icon:"🏭",color:"border-l-teal-500"},
  {href:"/relatorios/dre",label:"DRE",desc:"Receita bruta, CMV, lucro bruto",icon:"📊",color:"border-l-emerald-500"},
  {href:"/relatorios/fluxo-caixa",label:"Fluxo de Caixa",desc:"Entradas, saidas e saldo",icon:"💵",color:"border-l-blue-500"},
  {href:"/relatorios/aging",label:"Aging Financeiro",desc:"Contas a vencer e faixas",icon:"⏰",color:"border-l-red-500"},
  {href:"/relatorios/previsao",label:"Previsao",desc:"Media diaria e projecao 30 dias",icon:"🔮",color:"border-l-pink-500"},
  {href:"/relatorios/compras",label:"Compras",desc:"Pedidos, fornecedores e valores",icon:"🛒",color:"border-l-orange-500"},
  {href:"/relatorios/impostos",label:"Impostos",desc:"Tributos por periodo",icon:"📄",color:"border-l-red-500"},
  {href:"/relatorios/comissao",label:"Comissao",desc:"Comissoes por vendedor",icon:"💸",color:"border-l-yellow-500"},
  {href:"/relatorios/marketplaces",label:"Marketplaces",desc:"Vendas por canal",icon:"🛍️",color:"border-l-violet-500"},
  {href:"/relatorios/devolucoes",label:"Devolucoes",desc:"Taxa de devolucao e motivos",icon:"↩️",color:"border-l-red-500"},
  {href:"/relatorios/rupturas",label:"Rupturas",desc:"Produtos sem estoque",icon:"⚠️",color:"border-l-orange-500"},
  {href:"/relatorios/curvas",label:"Curva ABC",desc:"Classificacao de produtos",icon:"📐",color:"border-l-sky-500"},
  {href:"/relatorios/produtos",label:"Produtos",desc:"Mais vendidos e margem",icon:"🏷️",color:"border-l-green-500"},
  {href:"/relatorios/financeiro",label:"Financeiro",desc:"Contas a pagar e receber",icon:"💳",color:"border-l-cyan-500"},
];

function KpiPreview({ href, label }: { href: string; label: string }) {
  const [val, setVal] = useState<string>("...");
  useEffect(() => {
    const apis: Record<string,string> = {
      vendas:"/api/relatorios/vendas?dias=7",
      lucro:"/api/relatorios/lucro?dias=30",
      "ticket-medio":"/api/relatorios/ticket-medio?dias=30",
      estoque:"/api/relatorios/estoque",
      clientes:"/api/relatorios/clientes?dias=30",
      fornecedores:"/api/relatorios/fornecedores",
      dre:"/api/relatorios/dre?dias=30",
      "fluxo-caixa":"/api/relatorios/fluxo-caixa?dias=30",
      previsao:"/api/relatorios/previsao?dias=30",
      aging:"/api/relatorios/aging",
      compras:"/api/relatorios/compras",
    };
    const api = apis[href.split("/").pop()||""];
    if (!api) return;
    fetch(api).then(r=>r.json()).then(d => {
      if (d.total !== undefined) setVal("R$ "+Number(d.total).toLocaleString("pt-BR",{minimumFractionDigits:2}));
      else if (d.receita !== undefined) setVal("R$ "+Number(d.receita).toLocaleString("pt-BR",{minimumFractionDigits:2}));
      else if (d.total_itens !== undefined) setVal(d.total_itens+" itens");
      else if (d.ticket_medio !== undefined) setVal("R$ "+Number(d.ticket_medio).toFixed(2));
      else if (d.entradas !== undefined) setVal("R$ "+Number(d.saldo).toLocaleString("pt-BR",{minimumFractionDigits:2}));
      else if (d.contratos_pendentes !== undefined) setVal(d.contratos_pendentes+" pendentes");
      else if (d.media_diaria !== undefined) setVal("R$ "+Number(d.media_diaria).toFixed(2)+"/dia");
    }).catch(()=>{});
  }, [href]);
  return <span className="text-[10px] text-neutral-500 mt-0.5">{val}</span>;
}

export default function RelatoriosPage() {
  return (
    <div className="p-6 space-y-6">
      <div><h1 className="text-lg font-bold text-neutral-100">Relatorios</h1><p className="text-xs text-neutral-500 mt-1">20 relatorios gerenciais com dados em tempo real</p></div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {REPORTS.map(r => (
          <Link key={r.href} href={r.href} className={"bg-neutral-800 border border-neutral-700 border-l-4 rounded-lg p-4 hover:bg-neutral-750 transition-colors " + r.color}>
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-semibold text-neutral-200">{r.icon} {r.label}</p>
                <p className="text-xs text-neutral-500 mt-0.5">{r.desc}</p>
              </div>
            </div>
            <KpiPreview href={r.href} label={r.label} />
          </Link>
        ))}
      </div>
    </div>
  );
}
