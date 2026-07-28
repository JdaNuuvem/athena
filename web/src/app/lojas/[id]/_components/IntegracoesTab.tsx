"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Section, SelectField } from "./shared";

const NOMES: Record<string, string> = {
  bling: "Bling", shopee: "Shopee",
  mercado_livre: "Mercado Livre", amazon: "Amazon", magalu: "Magalu",
  woocommerce: "WooCommerce", shopify: "Shopify", openpix: "OpenPix",
  asaas: "Asaas", mercado_pago: "Mercado Pago", stripe: "Stripe",
  meta_ads: "Meta Ads", google_ads: "Google Ads", tiktok_ads: "TikTok Ads",
  kwai_ads: "Kwai Ads", whatsapp_business: "WhatsApp Business", telegram: "Telegram",
};
const STATUS_OPCOES = [
  { value: "nao_implementada", label: "Não implementada" },
  { value: "ativa", label: "Ativa" },
  { value: "inativa", label: "Inativa" },
];
const LINK_GERENCIAMENTO: Record<string, string> = {
  bling: "/integracoes/bling",
  shopee: "/integracoes/shopee",
};

interface Integracao { integracao: string; status: string; configurado: boolean; }

export default function IntegracoesTab({ id }: { id: number }) {
  const [integracoes, setIntegracoes] = useState<Integracao[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState<string>("");

  const carregar = () => {
    api.lojasIntegracoesListar(id).then((d) => setIntegracoes(d.integracoes || [])).finally(() => setLoading(false));
  };

  useEffect(() => { carregar(); }, [id]);

  const alterarStatus = async (chave: string, status: string) => {
    setSalvando(chave); setErro("");
    const r = await api.lojasIntegracaoAtualizar(id, chave, { status });
    if (r.error) setErro(r.error);
    setSalvando("");
    carregar();
  };

  if (loading) return <p className="text-xs text-neutral-500">Carregando...</p>;

  return (
    <div className="space-y-4">
      {erro && <p className="text-xs text-red-400">{erro}</p>}

      <Section title="Integrações">
        <div className="space-y-2">
          {integracoes.map((i) => {
            const gerenciada = LINK_GERENCIAMENTO[i.integracao];
            return (
              <div key={i.integracao} className="flex items-center justify-between bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2">
                <div>
                  <p className="text-sm text-neutral-200">{NOMES[i.integracao] || i.integracao}</p>
                  {gerenciada && (
                    <Link href={gerenciada} className="text-[10px] text-indigo-400 hover:text-indigo-300">
                      Gerenciado na tela própria →
                    </Link>
                  )}
                </div>
                {gerenciada ? (
                  <span className={`text-[10px] px-2 py-0.5 rounded-full ${i.status === "ativa" ? "bg-emerald-900/40 text-emerald-400" : "bg-neutral-700 text-neutral-400"}`}>
                    {i.status === "ativa" ? "Conectado" : "Não conectado"}
                  </span>
                ) : (
                  <div className="w-48">
                    <SelectField label="" value={i.status} onChange={(v) => alterarStatus(i.integracao, v)} options={STATUS_OPCOES} />
                    {salvando === i.integracao && <p className="text-[10px] text-neutral-500">Salvando...</p>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Section>
    </div>
  );
}
