"use client";

import { useState, useEffect, useCallback } from "react";
import { api, type EstoqueTransferencia } from "@/lib/api";
import { useStore } from "@/lib/store-context";
import { useAuth } from "@/lib/auth";

const LABEL_MOTIVO: Record<string, string> = {
  reposicao_entre_lojas: "Reposição entre lojas",
  redistribuicao_estoque_parado: "Redistribuição de estoque parado",
  solicitacao_loja_destino: "Solicitação da loja destino",
  outro: "Outro",
};

const LABEL_STATUS: Record<string, { label: string; cls: string }> = {
  pendente_aprovacao: { label: "Pendente aprovação", cls: "bg-amber-900/40 text-amber-400" },
  aprovada: { label: "Aprovada", cls: "bg-blue-900/40 text-blue-400" },
  rejeitada: { label: "Rejeitada", cls: "bg-red-900/40 text-red-400" },
  em_transito: { label: "Em trânsito", cls: "bg-indigo-900/40 text-indigo-400" },
  confirmada: { label: "Confirmada", cls: "bg-emerald-900/40 text-emerald-400" },
  com_discrepancia: { label: "Com discrepância", cls: "bg-orange-900/40 text-orange-400" },
};

export default function TransferenciasEstoquePage() {
  const { lojas } = useStore();
  const { user } = useAuth();
  const podeAprovar = ["gerente", "admin"].includes((user?.role || "").toLowerCase());

  const [transferencias, setTransferencias] = useState<EstoqueTransferencia[]>([]);
  const [filtroStatus, setFiltroStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");

  const [motivos, setMotivos] = useState<string[]>(Object.keys(LABEL_MOTIVO));
  const [sku, setSku] = useState("");
  const [origem, setOrigem] = useState("");
  const [destino, setDestino] = useState("");
  const [quantidade, setQuantidade] = useState("1");
  const [motivo, setMotivo] = useState("reposicao_entre_lojas");
  const [enviando, setEnviando] = useState(false);
  const [confirmando, setConfirmando] = useState<Record<number, string>>({});

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.estoqueListarTransferencias(filtroStatus || undefined);
      setTransferencias(r.transferencias || []);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar transferencias");
    } finally {
      setLoading(false);
    }
  }, [filtroStatus]);

  useEffect(() => { carregar(); }, [carregar]);
  useEffect(() => {
    api.estoqueMotivos().then(r => { if (r.transferencia?.length) setMotivos(r.transferencia); }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!origem && lojas.length > 0) setOrigem(lojas[0].nome);
    if (!destino && lojas.length > 1) setDestino(lojas[1].nome);
  }, [lojas, origem, destino]);

  const solicitar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sku.trim() || !origem || !destino) return;
    const qtd = parseFloat(quantidade);
    if (!qtd || qtd <= 0) { setErro("Quantidade invalida"); return; }
    setEnviando(true); setErro(""); setSucesso("");
    try {
      const r = await api.estoqueTransferir(sku.trim(), origem, destino, qtd, motivo);
      if (r.erro) { setErro(r.erro); return; }
      setSucesso(r.pendente_aprovacao
        ? `Transferencia #${r.transferencia_id} pendente de aprovacao (acima do limite livre).`
        : `Transferencia #${r.transferencia_id} criada — em transito, aguardando confirmacao da loja destino.`);
      setSku(""); setQuantidade("1");
      carregar();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro ao solicitar transferencia");
    } finally {
      setEnviando(false);
    }
  };

  const aprovar = async (id: number) => {
    setErro(""); setSucesso("");
    try {
      const r = await api.estoqueTransferenciaAprovar(id);
      if (r.erro) { setErro(r.erro); return; }
      setSucesso(`Transferencia #${id} aprovada.`);
      carregar();
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao aprovar"); }
  };

  const rejeitar = async (id: number) => {
    setErro(""); setSucesso("");
    try {
      const r = await api.estoqueTransferenciaRejeitar(id);
      if (r.erro) { setErro(r.erro); return; }
      setSucesso(`Transferencia #${id} rejeitada.`);
      carregar();
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao rejeitar"); }
  };

  const confirmarRecebimento = async (id: number) => {
    const qtd = parseFloat(confirmando[id] || "");
    if (!qtd && qtd !== 0) { setErro("Informe a quantidade recebida"); return; }
    setErro(""); setSucesso("");
    try {
      const r = await api.estoqueTransferenciaConfirmar(id, qtd);
      if (r.erro) { setErro(r.erro); return; }
      setSucesso(r.discrepancia
        ? `Transferencia #${id} confirmada com discrepancia (recebido diferente do enviado).`
        : `Transferencia #${id} confirmada.`);
      setConfirmando(c => { const n = { ...c }; delete n[id]; return n; });
      carregar();
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao confirmar"); }
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-light text-neutral-300">Transferências entre Lojas</h1>
        <p className="text-xs text-neutral-500 mt-0.5">
          Toda transferência exige confirmação de quem recebe. Acima do limite livre, exige aprovação de Gerente/Admin antes de sair da origem.
        </p>
      </div>

      {erro && <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">{erro}</div>}
      {sucesso && <div className="text-emerald-400 text-sm bg-emerald-950/30 border border-emerald-900/50 rounded-lg px-4 py-3">{sucesso}</div>}

      <form onSubmit={solicitar} className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3">
        <h2 className="text-sm font-medium text-neutral-300">Nova transferência</h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className="space-y-1">
            <label className="text-[10px] text-neutral-500 uppercase tracking-wider">SKU</label>
            <input value={sku} onChange={e => setSku(e.target.value)} placeholder="Codigo do produto"
              className="w-full bg-neutral-950 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-indigo-500" />
          </div>
          <div className="space-y-1">
            <label className="text-[10px] text-neutral-500 uppercase tracking-wider">Origem</label>
            <select value={origem} onChange={e => setOrigem(e.target.value)}
              className="w-full bg-neutral-950 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-indigo-500">
              {lojas.map(l => <option key={l.id} value={l.nome}>{l.nome}</option>)}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-[10px] text-neutral-500 uppercase tracking-wider">Destino</label>
            <select value={destino} onChange={e => setDestino(e.target.value)}
              className="w-full bg-neutral-950 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-indigo-500">
              {lojas.map(l => <option key={l.id} value={l.nome}>{l.nome}</option>)}
            </select>
          </div>
          <div className="space-y-1">
            <label className="text-[10px] text-neutral-500 uppercase tracking-wider">Quantidade</label>
            <input type="number" step="1" min="1" value={quantidade} onChange={e => setQuantidade(e.target.value)}
              className="w-full bg-neutral-950 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-indigo-500" />
          </div>
          <div className="space-y-1">
            <label className="text-[10px] text-neutral-500 uppercase tracking-wider">Motivo</label>
            <select value={motivo} onChange={e => setMotivo(e.target.value)}
              className="w-full bg-neutral-950 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-100 focus:outline-none focus:border-indigo-500">
              {motivos.map(m => <option key={m} value={m}>{LABEL_MOTIVO[m] || m}</option>)}
            </select>
          </div>
        </div>
        <button type="submit" disabled={enviando} className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors">
          {enviando ? "Enviando..." : "Solicitar Transferência"}
        </button>
      </form>

      <div className="flex items-center gap-2">
        <label className="text-xs text-neutral-500">Filtrar status:</label>
        <select value={filtroStatus} onChange={e => setFiltroStatus(e.target.value)}
          className="bg-neutral-900 border border-neutral-800 rounded-lg px-2 py-1 text-xs text-neutral-300">
          <option value="">Todas</option>
          {Object.entries(LABEL_STATUS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
      </div>

      {loading ? (
        <div className="text-neutral-500 text-sm">Carregando...</div>
      ) : transferencias.length === 0 ? (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-8 text-center text-neutral-500 text-xs">Nenhuma transferência encontrada</div>
      ) : (
        <div className="space-y-2">
          {transferencias.map(t => {
            const st = LABEL_STATUS[t.status] || { label: t.status, cls: "bg-neutral-800 text-neutral-400" };
            return (
              <div key={t.id} className="bg-neutral-900 border border-neutral-800 rounded-lg p-3 space-y-2">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div>
                    <span className="font-mono text-xs text-neutral-400">#{t.id}</span>
                    <span className="text-sm text-neutral-200 font-medium ml-2">{t.produto_nome || t.sku}</span>
                    <span className="text-xs text-neutral-500 ml-2">({t.sku})</span>
                  </div>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full ${st.cls}`}>{st.label}</span>
                </div>
                <div className="text-xs text-neutral-500">
                  {t.loja_origem} → {t.loja_destino} · {t.quantidade_solicitada} un solicitadas
                  {t.quantidade_recebida != null && ` · ${t.quantidade_recebida} un recebidas`}
                  {" · "}{LABEL_MOTIVO[t.motivo] || t.motivo}
                </div>
                <div className="text-[10px] text-neutral-600">
                  Solicitado por {t.usuario_solicitante_nome || "—"}
                  {t.usuario_aprovador_nome && ` · Aprovado por ${t.usuario_aprovador_nome}`}
                  {t.usuario_confirmador_nome && ` · Confirmado por ${t.usuario_confirmador_nome}`}
                </div>
                {t.status === "pendente_aprovacao" && podeAprovar && (
                  <div className="flex gap-2">
                    <button onClick={() => aprovar(t.id)} className="text-xs bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-1 rounded-lg">Aprovar</button>
                    <button onClick={() => rejeitar(t.id)} className="text-xs bg-red-600 hover:bg-red-500 text-white px-3 py-1 rounded-lg">Rejeitar</button>
                  </div>
                )}
                {t.status === "em_transito" && (
                  <div className="flex items-center gap-2">
                    <input
                      type="number" step="1" min="0" placeholder="Qtd recebida"
                      value={confirmando[t.id] ?? ""}
                      onChange={e => setConfirmando(c => ({ ...c, [t.id]: e.target.value }))}
                      className="w-28 bg-neutral-950 border border-neutral-700 rounded-lg px-2 py-1 text-xs text-neutral-100"
                    />
                    <button onClick={() => confirmarRecebimento(t.id)} className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1 rounded-lg">
                      Confirmar Recebimento
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
