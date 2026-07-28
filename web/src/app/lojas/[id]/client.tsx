"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import GeralTab from "./_components/GeralTab";
import OperacionalComercialTab from "./_components/OperacionalComercialTab";
import FiscalFinanceiroTab from "./_components/FiscalFinanceiroTab";
import VirtualDeliveryTab from "./_components/VirtualDeliveryTab";
import ResponsaveisTab from "./_components/ResponsaveisTab";
import IntegracoesTab from "./_components/IntegracoesTab";
import MidiaTab from "./_components/MidiaTab";

const TABS = [
  { id: "geral", label: "Geral" },
  { id: "operacional", label: "Operacional & Comercial" },
  { id: "fiscal", label: "Fiscal & Financeiro" },
  { id: "virtual", label: "Virtual & Delivery" },
  { id: "responsaveis", label: "Responsáveis" },
  { id: "integracoes", label: "Integrações" },
  { id: "midia", label: "Mídia" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function LojaClientPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params?.id || 0);
  const [loja, setLoja] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabId>("geral");

  const carregar = () => {
    if (!id) { setLoading(false); return; }
    api.lojasObter(id)
      .then((d) => setLoja(d.loja))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { carregar(); }, [id]);

  if (loading) return <div className="p-6 text-neutral-500">Carregando...</div>;
  if (!id) return <div className="p-6 text-red-400">Loja inválida</div>;
  if (!loja) return <div className="p-6 text-red-400">Loja não encontrada</div>;

  return (
    <div className="p-6 space-y-6">
      <div>
        <Link href="/lojas" className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors">
          ← Lojas
        </Link>
        <h1 className="text-lg font-light text-neutral-300 mt-1">
          {String(loja.nome_fantasia || loja.nome)}
        </h1>
        <p className="text-xs text-neutral-500 mt-1">ID: {id}</p>
      </div>

      <div className="flex gap-2 overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap ${
              tab === t.id
                ? "bg-indigo-600/20 text-indigo-300 border border-indigo-600/30"
                : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 border border-transparent"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "geral" && <GeralTab id={id} loja={loja} onUpdate={carregar} />}
      {tab === "operacional" && <OperacionalComercialTab id={id} loja={loja} />}
      {tab === "fiscal" && <FiscalFinanceiroTab id={id} loja={loja} />}
      {tab === "virtual" && <VirtualDeliveryTab id={id} loja={loja} />}
      {tab === "responsaveis" && <ResponsaveisTab id={id} />}
      {tab === "integracoes" && <IntegracoesTab id={id} />}
      {tab === "midia" && <MidiaTab id={id} />}
    </div>
  );
}
