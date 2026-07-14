import type { Obrigacao, ObrigacaoStatus } from "../types";
import StatusBadge from "@/app/_components/StatusBadge";
import type { StatusBadgeVariant } from "../types";

const STATUS_LABEL: Record<ObrigacaoStatus, string> = {
  entregue: "Entregue",
  pendente: "Pendente",
  andamento: "Em andamento",
};

const STATUS_VARIANT: Record<ObrigacaoStatus, StatusBadgeVariant> = {
  entregue: "success",
  pendente: "danger",
  andamento: "warning",
};

interface ObligacaoCardProps {
  obrigacao: Obrigacao;
}

export default function ObligacaoCard({ obrigacao }: ObligacaoCardProps) {
  return (
    <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-neutral-100">{obrigacao.nome}</h3>
        <StatusBadge label={STATUS_LABEL[obrigacao.status]} variant={STATUS_VARIANT[obrigacao.status]} />
      </div>
      <p className="text-xs text-neutral-500">{obrigacao.descricao}</p>
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <div>
          <p className="text-neutral-500">Última Entrega</p>
          <p className="text-neutral-300">{obrigacao.ultimaEntrega}</p>
        </div>
        <div>
          <p className="text-neutral-500">Próximo Venc.</p>
          <p className="text-neutral-300">{obrigacao.proximoVencimento}</p>
        </div>
        <div className="col-span-2">
          <p className="text-neutral-500">Periodicidade</p>
          <p className="text-neutral-300">{obrigacao.periodicidade}</p>
        </div>
      </div>
    </div>
  );
}
