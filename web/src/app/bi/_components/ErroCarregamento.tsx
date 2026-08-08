"use client";

import Icon from "@/app/_components/Icon";

interface ErroCarregamentoProps {
  onRetry: () => void;
  mensagem?: string;
}

// Estado de erro explicito pra chamada de API do BI — nunca cair silenciosamente
// para dado mockado quando o fetch falha (rede/sessao/500 temporario), pra nao
// mostrar numero fictício como se fosse metrica real do negocio.
export default function ErroCarregamento({ onRetry, mensagem }: ErroCarregamentoProps) {
  return (
    <div className="p-6">
      <div className="rounded-lg border border-red-800/50 bg-red-950/20 p-8 text-center space-y-3">
        <Icon name="alert" size={22} className="mx-auto text-red-400" />
        <p className="text-sm text-red-400">{mensagem || "Não foi possível carregar os dados do BI agora."}</p>
        <button
          onClick={onRetry}
          className="rounded-lg bg-neutral-800 border border-neutral-700 px-4 py-2 text-xs text-neutral-200 hover:bg-neutral-700 transition-colors"
        >
          Tentar novamente
        </button>
      </div>
    </div>
  );
}
