"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/lib/auth";

interface Aprovacao {
  id: number;
  caixa_id: number;
  caixa_numero?: string;
  valor: number;
  motivo: string;
  status: string;
  usuario_solicitante_nome: string | null;
  usuario_aprovador_nome: string | null;
  motivo_rejeicao: string | null;
  criado_em: string;
  resolvido_em: string | null;
}

const LABEL_MOTIVO: Record<string, string> = {
  troco: "Troco",
  deposito_banco: "Depósito no banco",
  pagamento_fornecedor: "Pagamento a fornecedor",
  despesa_operacional: "Despesa operacional",
  outro: "Outro",
};

export default function AprovacoesPDVPage() {
  const { user } = useAuth();
  const podeAprovar = ["gerente", "admin"].includes((user?.role || "").toLowerCase());

  const [status, setStatus] = useState("pendente");
  const [aprovacoes, setAprovacoes] = useState<Aprovacao[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`/api/pdv/sangria/aprovacoes?status=${status}`).then(res => res.json());
      setAprovacoes(r.aprovacoes || []);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar");
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => { carregar(); }, [carregar]);

  const aprovar = async (id: number) => {
    setErro(""); setSucesso("");
    try {
      const r = await fetch(`/api/pdv/sangria/aprovacoes/${id}/aprovar`, { method: "POST" }).then(res => res.json());
      if (r.error) { setErro(r.error); return; }
      setSucesso(`Sangria #${id} aprovada e aplicada ao caixa.`);
      carregar();
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao aprovar"); }
  };

  const rejeitar = async (id: number) => {
    setErro(""); setSucesso("");
    try {
      const r = await fetch(`/api/pdv/sangria/aprovacoes/${id}/rejeitar`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}),
      }).then(res => res.json());
      if (r.error) { setErro(r.error); return; }
      setSucesso(`Sangria #${id} rejeitada — caixa não foi alterado.`);
      carregar();
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao rejeitar"); }
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-light text-neutral-300">Aprovações de Sangria — PDV</h1>
        <p className="text-xs text-neutral-500 mt-0.5">Sangrias acima do limite configurado ficam aqui até um Gerente/Admin aprovar ou rejeitar.</p>
      </div>

      {!podeAprovar && (
        <div className="text-amber-400 text-sm bg-amber-950/30 border border-amber-900/50 rounded-lg px-4 py-3">
          Apenas Gerente/Admin pode aprovar ou rejeitar. Você pode visualizar as pendências abaixo.
        </div>
      )}
      {erro && <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">{erro}</div>}
      {sucesso && <div className="text-emerald-400 text-sm bg-emerald-950/30 border border-emerald-900/50 rounded-lg px-4 py-3">{sucesso}</div>}

      <div className="flex items-center gap-2">
        <label className="text-xs text-neutral-500">Status:</label>
        <select value={status} onChange={e => setStatus(e.target.value)}
          className="bg-neutral-900 border border-neutral-800 rounded-lg px-2 py-1 text-xs text-neutral-300">
          <option value="pendente">Pendentes</option>
          <option value="aprovada">Aprovadas</option>
          <option value="rejeitada">Rejeitadas</option>
        </select>
      </div>

      {loading ? (
        <div className="text-neutral-500 text-sm">Carregando...</div>
      ) : aprovacoes.length === 0 ? (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-8 text-center text-neutral-500 text-xs">Nenhuma aprovação encontrada</div>
      ) : (
        <div className="space-y-2">
          {aprovacoes.map(a => (
            <div key={a.id} className="bg-neutral-900 border border-neutral-800 rounded-lg p-3 space-y-2">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <span className="font-mono text-xs text-neutral-400">#{a.id}</span>
                  <span className="text-sm text-neutral-200 font-medium ml-2">Caixa {a.caixa_numero || `#${a.caixa_id}`}</span>
                </div>
                <span className="text-xs text-amber-400 font-medium">R$ {Number(a.valor).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
              </div>
              <div className="text-xs text-neutral-500">Motivo: {LABEL_MOTIVO[a.motivo] || a.motivo}</div>
              <div className="text-[10px] text-neutral-600">
                Solicitado por {a.usuario_solicitante_nome || "—"} em {new Date(a.criado_em).toLocaleString("pt-BR")}
                {a.usuario_aprovador_nome && ` · Resolvido por ${a.usuario_aprovador_nome}`}
              </div>
              {a.status === "pendente" && podeAprovar && (
                <div className="flex gap-2">
                  <button onClick={() => aprovar(a.id)} className="text-xs bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-1 rounded-lg">Aprovar</button>
                  <button onClick={() => rejeitar(a.id)} className="text-xs bg-red-600 hover:bg-red-500 text-white px-3 py-1 rounded-lg">Rejeitar</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
