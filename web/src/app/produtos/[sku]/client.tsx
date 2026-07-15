"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import VisaoGeralTab from "./_components/VisaoGeralTab";
import CadastroTab from "./_components/CadastroTab";
import VariacoesTab from "./_components/VariacoesTab";
import KitsBomTab from "./_components/KitsBomTab";
import LotesSeriesTab from "./_components/LotesSeriesTab";
import LocalizacaoTab from "./_components/LocalizacaoTab";
import ControleTab from "./_components/ControleTab";

const TABS = [
  { id: "visao-geral", label: "Visão Geral" },
  { id: "cadastro", label: "Cadastro" },
  { id: "variacoes", label: "Variações" },
  { id: "kits-bom", label: "Kits & BOM" },
  { id: "lotes-series", label: "Lotes & Séries" },
  { id: "localizacao", label: "Localização" },
  { id: "controle", label: "Controle" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function ProdutoClientPage() {
  const { sku } = useParams<{ sku: string }>();
  const [produto, setProduto] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabId>("visao-geral");

  useEffect(() => {
    api.detalheProduto(sku)
      .then((d) => setProduto(d as Record<string, unknown>))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [sku]);

  const formatarMoeda = (v: unknown) => {
    const n = typeof v === "number" ? v : parseFloat(String(v || 0));
    return isNaN(n) ? "0" : n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  };

  if (loading) return <div className="p-6 text-neutral-500">Carregando...</div>;
  if (!produto) return <div className="p-6 text-red-400">Produto não encontrado</div>;

  return (
    <div className="p-6 space-y-6">
      <div>
        <Link href="/produtos" className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors">
          ← Produtos
        </Link>
        <h1 className="text-lg font-light text-neutral-300 mt-1">
          {String(produto.descricao || produto.nome || sku)}
        </h1>
        <p className="text-xs font-mono text-neutral-500 mt-1">{sku}</p>
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

      {tab === "visao-geral" && <VisaoGeralTab produto={produto} formatarMoeda={formatarMoeda} />}
      {tab === "cadastro" && <CadastroTab />}
      {tab === "variacoes" && <VariacoesTab variacoes={(produto?.variacoes as any) || []} />}
      {tab === "kits-bom" && <KitsBomTab />}
      {tab === "lotes-series" && <LotesSeriesTab />}
      {tab === "localizacao" && <LocalizacaoTab />}
      {tab === "controle" && <ControleTab />}
    </div>
  );
}
