"use client";

import Icon from "../_components/Icon";
import SidebarLayout from "../_components/SidebarLayout";
import VisaoGeralTab from "./_components/VisaoGeralTab";
import FuncionariosTab from "./_components/FuncionariosTab";
import PontoTab from "./_components/PontoTab";
import FeriasTab from "./_components/FeriasTab";
import FolhaTab from "./_components/FolhaTab";
import BeneficiosTab from "./_components/BeneficiosTab";
import ValeTab from "./_components/ValeTab";
import ComissoesTab from "./_components/ComissoesTab";
import AvaliacoesTab from "./_components/AvaliacoesTab";
import TreinamentosTab from "./_components/TreinamentosTab";

export default function RHPage() {
  return (
    <div className="max-w-[1400px] space-y-5 p-6">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400">
          <Icon name="rh" size={20} />
        </div>
        <div>
          <h1 className="text-lg font-semibold text-neutral-100">RH</h1>
          <p className="text-xs text-neutral-500">Funcionários, ponto, férias, folha, benefícios, avaliações de desempenho e treinamentos</p>
        </div>
      </div>

      <SidebarLayout
        subItems={[
          { key: "visao_geral", label: "Visão Geral" },
          { key: "funcionarios", label: "Funcionários" },
          { key: "ponto", label: "Ponto" },
          { key: "ferias", label: "Férias" },
          { key: "folha", label: "Folha" },
          { key: "beneficios", label: "Benefícios" },
          { key: "vale", label: "Vale" },
          { key: "comissoes", label: "Comissões" },
          { key: "avaliacoes", label: "Avaliações" },
          { key: "treinamentos", label: "Treinamentos" },
        ]}
        renderContent={(key) => {
          switch (key) {
            case "visao_geral": return <VisaoGeralTab />;
            case "funcionarios": return <FuncionariosTab />;
            case "ponto": return <PontoTab />;
            case "ferias": return <FeriasTab />;
            case "folha": return <FolhaTab />;
            case "beneficios": return <BeneficiosTab />;
            case "vale": return <ValeTab />;
            case "comissoes": return <ComissoesTab />;
            case "avaliacoes": return <AvaliacoesTab />;
            case "treinamentos": return <TreinamentosTab />;
            default: return null;
          }
        }}
      />
    </div>
  );
}
