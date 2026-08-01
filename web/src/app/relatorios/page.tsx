"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import Icon from "@/app/_components/Icon";

type ReportIconSpec = { kind: "nav"; name: string } | { kind: "custom"; name: string };

const REPORTS: { href: string; label: string; desc: string; icon: ReportIconSpec; color: string }[] = [
  {href:"/relatorios/vendas",label:"Vendas",desc:"Total, quantidade e vendas diarias",icon:{kind:"nav",name:"vendas"},color:"bg-blue-500"},
  {href:"/relatorios/lucro",label:"Lucro e Margem",desc:"Receita, custos, lucro e margem %",icon:{kind:"custom",name:"trendingUp"},color:"bg-emerald-500"},
  {href:"/relatorios/ticket-medio",label:"Ticket Medio",desc:"Valor medio por venda",icon:{kind:"custom",name:"target"},color:"bg-indigo-500"},
  {href:"/relatorios/estoque",label:"Estoque",desc:"Itens, baixo estoque e rupturas",icon:{kind:"nav",name:"estoque"},color:"bg-amber-500"},
  {href:"/relatorios/clientes",label:"Clientes",desc:"Total, novos e top compradores",icon:{kind:"custom",name:"users"},color:"bg-purple-500"},
  {href:"/relatorios/fornecedores",label:"Fornecedores",desc:"Total, ativos e top por valor",icon:{kind:"nav",name:"building2"},color:"bg-teal-500"},
  {href:"/relatorios/dre",label:"DRE",desc:"Receita bruta, CMV, lucro bruto",icon:{kind:"nav",name:"bi"},color:"bg-emerald-500"},
  {href:"/relatorios/fluxo-caixa",label:"Fluxo de Caixa",desc:"Entradas, saidas e saldo",icon:{kind:"custom",name:"banknote"},color:"bg-blue-500"},
  {href:"/relatorios/aging",label:"Aging Financeiro",desc:"Contas a vencer e faixas",icon:{kind:"custom",name:"clock"},color:"bg-red-500"},
  {href:"/relatorios/previsao",label:"Previsao",desc:"Media diaria e projecao 30 dias",icon:{kind:"custom",name:"sparkles"},color:"bg-pink-500"},
  {href:"/relatorios/compras",label:"Compras",desc:"Pedidos, fornecedores e valores",icon:{kind:"nav",name:"compras"},color:"bg-orange-500"},
  {href:"/relatorios/impostos",label:"Impostos",desc:"Tributos por periodo",icon:{kind:"nav",name:"documentos"},color:"bg-red-500"},
  {href:"/relatorios/comissao",label:"Comissao",desc:"Comissoes por vendedor",icon:{kind:"custom",name:"percent"},color:"bg-yellow-500"},
  {href:"/relatorios/marketplaces",label:"Marketplaces",desc:"Vendas por canal",icon:{kind:"custom",name:"shoppingBag"},color:"bg-violet-500"},
  {href:"/relatorios/devolucoes",label:"Devolucoes",desc:"Taxa de devolucao e motivos",icon:{kind:"custom",name:"undo"},color:"bg-red-500"},
  {href:"/relatorios/rupturas",label:"Rupturas",desc:"Produtos sem estoque",icon:{kind:"nav",name:"alert"},color:"bg-orange-500"},
  {href:"/relatorios/curvas",label:"Curva ABC",desc:"Classificacao de produtos",icon:{kind:"custom",name:"ruler"},color:"bg-sky-500"},
  {href:"/relatorios/produtos",label:"Produtos",desc:"Mais vendidos e margem",icon:{kind:"nav",name:"produtos"},color:"bg-green-500"},
  {href:"/relatorios/financeiro",label:"Financeiro",desc:"Contas a pagar e receber",icon:{kind:"nav",name:"financeiro"},color:"bg-cyan-500"},
];

function ReportIcon({ name, size = 16 }: { name: string; size?: number }) {
  const common = {
    xmlns: "http://www.w3.org/2000/svg" as const,
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.5,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  switch (name) {
    case "trendingUp":
      return <svg {...common}><path d="M3 17l6-6 4 4 8-8" /><path d="M15 7h6v6" /></svg>;
    case "target":
      return <svg {...common}><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1" /></svg>;
    case "users":
      return <svg {...common}><path d="M16 19v-1.5a3.5 3.5 0 00-3.5-3.5h-5A3.5 3.5 0 004 17.5V19" /><circle cx="9" cy="8" r="3" /><path d="M20 19v-1.5a3.5 3.5 0 00-2.5-3.36" /><path d="M14.5 4.6a3 3 0 010 5.8" /></svg>;
    case "banknote":
      return <svg {...common}><rect x="2.5" y="6" width="19" height="12" rx="2" /><circle cx="12" cy="12" r="2.5" /><path d="M6 12h.01M18 12h.01" /></svg>;
    case "clock":
      return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3.5 2" /></svg>;
    case "sparkles":
      return <svg {...common}><path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3z" /><path d="M19 14l.8 2.2L22 17l-2.2.8L19 20l-.8-2.2L16 17l2.2-.8L19 14z" /></svg>;
    case "percent":
      return <svg {...common}><path d="M19 5L5 19" /><circle cx="7" cy="7" r="2.5" /><circle cx="17" cy="17" r="2.5" /></svg>;
    case "shoppingBag":
      return <svg {...common}><path d="M6 9V7a3 3 0 016 0v2" /><path d="M4.8 9h9.4l.9 11a1 1 0 01-1 1.1H4.9a1 1 0 01-1-1.1l.9-11z" /></svg>;
    case "undo":
      return <svg {...common}><path d="M9 5L4 10l5 5" /><path d="M4 10h11a5 5 0 010 10h-2" /></svg>;
    case "ruler":
      return <svg {...common}><rect x="3" y="8" width="18" height="8" rx="1" /><path d="M7 8v3M11 8v3M15 8v3" /></svg>;
    default:
      return null;
  }
}

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
      else if (d.ticket_medio !== undefined) setVal("R$ "+Number(d.ticket_medio).toLocaleString("pt-BR",{minimumFractionDigits:2,maximumFractionDigits:2}));
      else if (d.entradas !== undefined) setVal("R$ "+Number(d.saldo).toLocaleString("pt-BR",{minimumFractionDigits:2}));
      else if (d.contratos_pendentes !== undefined) setVal(d.contratos_pendentes+" pendentes");
      else if (d.media_diaria !== undefined) setVal("R$ "+Number(d.media_diaria).toLocaleString("pt-BR",{minimumFractionDigits:2,maximumFractionDigits:2})+"/dia");
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
          <Link key={r.href} href={r.href} className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 hover:bg-neutral-750 transition-colors">
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-2">
                <span className={`inline-block w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${r.color}`} />
                <div>
                  <p className="text-sm font-semibold text-neutral-200 flex items-center gap-1.5">
                    {r.icon.kind === "nav" ? <Icon name={r.icon.name} size={16} /> : <ReportIcon name={r.icon.name} size={16} />}
                    {r.label}
                  </p>
                  <p className="text-xs text-neutral-500 mt-0.5">{r.desc}</p>
                </div>
              </div>
            </div>
            <KpiPreview href={r.href} label={r.label} />
          </Link>
        ))}
      </div>
    </div>
  );
}
