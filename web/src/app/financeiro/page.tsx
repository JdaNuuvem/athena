"use client";

import Icon from "../_components/Icon";
import SidebarLayout from "../_components/SidebarLayout";
import VisaoGeralTab from "./_components/VisaoGeralTab";
import FluxoCaixaTab from "./_components/FluxoCaixaTab";
import ReceberTab from "./_components/ReceberTab";
import PagarTab from "./_components/PagarTab";
import BoletosTab from "./_components/BoletosTab";
import PIXTab from "./_components/PIXTab";
import ConciliacaoTab from "./_components/ConciliacaoTab";
import BancoTab from "./_components/BancoTab";
import DRETab from "./_components/DRETab";
import CofreTab from "./_components/CofreTab";
import VendasPorLojaTab from "./_components/VendasPorLojaTab";
import MovimentoDiarioTab from "./_components/MovimentoDiarioTab";

export default function FinanceiroPage() {
  return (
    <div className="max-w-[1400px] space-y-5 p-6">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400">
          <Icon name="financeiro" size={20} />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-neutral-100">Financeiro</h1>
          <p className="text-xs text-neutral-500">Fluxo de caixa, cofre por loja, contas a pagar/receber, relatórios e DRE</p>
        </div>
      </div>

      <SidebarLayout
        subItems={[
          { key: "visao_geral", label: "Visão Geral" },
          { key: "fluxo_caixa", label: "Fluxo Caixa" },
          { key: "cofre", label: "Cofre" },
          {
            key: "relatorios", label: "Relatórios",
            children: [
              { key: "vendas_por_loja", label: "Vendas por Loja" },
              { key: "movimento_diario", label: "Movimento Diário" },
            ],
          },
          { key: "receber", label: "Receber" },
          { key: "pagar", label: "Pagar" },
          { key: "boletos", label: "Boletos" },
          { key: "pix", label: "PIX" },
          { key: "conciliacao", label: "Conciliação" },
          { key: "banco", label: "Banco" },
          { key: "dre", label: "DRE" },
        ]}
        renderContent={(key) => {
          switch (key) {
            case "visao_geral": return <VisaoGeralTab />;
            case "fluxo_caixa": return <FluxoCaixaTab />;
            case "cofre": return <CofreTab />;
            case "vendas_por_loja": return <VendasPorLojaTab />;
            case "movimento_diario": return <MovimentoDiarioTab />;
            case "receber": return <ReceberTab />;
            case "pagar": return <PagarTab />;
            case "boletos": return <BoletosTab />;
            case "pix": return <PIXTab />;
            case "conciliacao": return <ConciliacaoTab />;
            case "banco": return <BancoTab />;
            case "dre": return <DRETab />;
            default: return null;
          }
        }}
      />
    </div>
  );
}
