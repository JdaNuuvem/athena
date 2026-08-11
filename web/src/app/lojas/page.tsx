"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type TipoLoja, type ImpactoExclusaoForcadaLoja } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import StatusBadge from "@/app/_components/StatusBadge";
import LoadingState from "@/app/_components/LoadingState";
import Icon from "@/app/_components/Icon";

interface Loja { id: number; nome: string; ativa: boolean; status?: string; bling_id?: number; bling_descricao?: string; shopee_markup_pct?: number; grupos_publicacao?: string; tipo?: TipoLoja; }

const MENSAGEM_EXCLUSAO_BLOQUEADA =
  "Nao e possivel excluir: existem dados vinculados a esta loja (estoque, vendas, caixas, etc). Desative-a em vez de excluir.";

type ExclusaoForcadaState = {
  lojaId: number; nome: string; modalAberto: boolean;
  impacto: ImpactoExclusaoForcadaLoja | null; carregandoImpacto: boolean;
  nomeDigitado: string; excluindo: boolean; erro: string;
};

const TIPO_LABEL: Record<TipoLoja, string> = {
  fisica: "Física",
  virtual: "Virtual",
  hibrida: "Híbrida",
  marketplace: "Marketplace",
};

export default function LojasPage() {
  const { hasPermission } = useAuth();
  const [lojas, setLojas] = useState<Loja[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [erro, setErro] = useState("");
  const [modal, setModal] = useState<{ open: boolean; nome: string; markup: number; grupos: string; tipo: TipoLoja; editId?: number }>({ open: false, nome: "", markup: 100, grupos: "", tipo: "fisica" });
  const [exclusaoForcada, setExclusaoForcada] = useState<ExclusaoForcadaState | null>(null);

  const carregar = () => {
    api.lojasManage()
      .then(d => setLojas(d.lojas || []))
      .finally(() => setLoading(false));
  };

  useEffect(() => { carregar(); }, []);

  const salvar = async () => {
    const nome = modal.nome.trim();
    if (!nome) return;
    if (modal.editId) await api.lojasAtualizar(modal.editId, nome, modal.markup, modal.grupos || undefined, modal.tipo);
    else await api.lojasCriar(nome, modal.tipo);
    setModal({ open: false, nome: "", markup: 100, grupos: "", tipo: "fisica" });
    carregar();
  };

  const deletar = async (l: Loja) => {
    if (!confirm("Tem certeza que deseja excluir esta loja?")) return;
    setErro("");
    setExclusaoForcada(null);
    try {
      await api.lojasDeletar(l.id);
      carregar();
    } catch (e) {
      const mensagem = (e as Error).message;
      setErro(mensagem);
      if (mensagem === MENSAGEM_EXCLUSAO_BLOQUEADA && l.status === "inativa" && hasPermission("lojas.excluir_forcado")) {
        setExclusaoForcada({ lojaId: l.id, nome: l.nome, modalAberto: false,
          impacto: null, carregandoImpacto: false, nomeDigitado: "", excluindo: false, erro: "" });
      }
    }
  };

  const abrirExclusaoForcada = async () => {
    if (!exclusaoForcada) return;
    setExclusaoForcada(p => p && { ...p, modalAberto: true, carregandoImpacto: true });
    try {
      const impacto = await api.lojasImpactoExclusaoForcada(exclusaoForcada.lojaId);
      setExclusaoForcada(p => p && { ...p, impacto, carregandoImpacto: false });
    } catch (e) {
      setExclusaoForcada(p => p && { ...p, carregandoImpacto: false, erro: (e as Error).message });
    }
  };

  const confirmarExclusaoForcada = async () => {
    if (!exclusaoForcada) return;
    setExclusaoForcada(p => p && { ...p, excluindo: true, erro: "" });
    try {
      await api.lojasExcluirForcado(exclusaoForcada.lojaId, exclusaoForcada.nomeDigitado);
      setExclusaoForcada(null);
      setErro("");
      carregar();
    } catch (e) {
      setExclusaoForcada(p => p && { ...p, excluindo: false, erro: (e as Error).message });
    }
  };

  const alternarAtiva = async (l: Loja) => {
    setErro("");
    try {
      const r = await api.lojasAtualizarGeral(l.id, { status: l.ativa ? "inativa" : "ativa" });
      if (r.error) { setErro(r.error); return; }
      carregar();
    } catch (e) {
      setErro((e as Error).message);
    }
  };

  const syncBling = async () => {
    setSyncing(true);
    try {
      const r = await fetch("/api/lojas/sync/bling", { method: "POST" }).then(r => r.json());
      if (r.error) alert(r.error);
      carregar();
    } catch (e) { alert(String(e)); }
    finally { setSyncing(false); }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-lg font-bold text-neutral-100 flex items-center gap-2">
            <Icon name="building2" size={18} />
            Lojas
          </h1>
          <p className="text-xs text-neutral-500 mt-1">Gerencie os ambientes e filiais do sistema</p>
          {erro && (
            <p className="text-xs text-red-400 mt-1">
              {erro}
              {exclusaoForcada && !exclusaoForcada.modalAberto && (
                <button onClick={abrirExclusaoForcada} className="ml-2 underline hover:text-red-300">
                  Excluir mesmo assim
                </button>
              )}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={syncBling}
            disabled={syncing}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs px-3 py-1.5 rounded-lg"
          >
            {syncing ? "Sincronizando..." : "Sync Bling"}
          </button>
          <button
            onClick={() => setModal({ open: true, nome: "", markup: 100, grupos: "", tipo: "fisica" })}
            className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg"
          >
            + Nova Loja
          </button>
        </div>
      </div>

      {loading ? <LoadingState /> : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {lojas.map(l => (
            <div key={l.id} className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-2">
              <div className="flex justify-between items-start">
                <h3 className="text-sm font-semibold text-neutral-200">{l.nome}</h3>
                <div className="flex gap-1 items-center">
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${l.tipo === "virtual" ? "bg-purple-900/40 text-purple-400" : l.tipo === "hibrida" ? "bg-amber-900/40 text-amber-400" : l.tipo === "marketplace" ? "bg-pink-900/40 text-pink-400" : "bg-sky-900/40 text-sky-400"}`}>
                    {TIPO_LABEL[l.tipo || "fisica"]}
                  </span>
                  <StatusBadge label={l.ativa ? "Ativa" : "Inativa"} variant={l.ativa ? "success" : "neutral"} />
                </div>
              </div>
              <p className="text-[10px] text-neutral-600">ID: {l.id}{l.bling_id ? ` · Bling #${l.bling_id}` : ""}</p>
              {l.shopee_markup_pct && l.shopee_markup_pct !== 100 && (
                <p className="text-[10px] text-amber-400">Shopee markup: {l.shopee_markup_pct}%</p>
              )}
              <div className="flex gap-2">
                <Link href={`/lojas/${l.id}`} className="text-xs text-emerald-400 hover:text-emerald-300 inline-flex items-center gap-0.5">
                  Ver detalhes <Icon name="chevronRight" size={12} />
                </Link>
                <button
                  onClick={() => setModal({ open: true, nome: l.nome, markup: l.shopee_markup_pct || 100, grupos: l.grupos_publicacao || "", tipo: l.tipo || "fisica", editId: l.id })}
                  className="text-xs text-indigo-400 hover:text-indigo-300"
                >Editar rápido</button>
                <button
                  onClick={() => alternarAtiva(l)}
                  className="text-xs text-neutral-400 hover:text-neutral-200"
                >{l.ativa ? "Desativar" : "Ativar"}</button>
                <button
                  onClick={() => deletar(l)}
                  className="text-xs text-red-400 hover:text-red-300"
                >Excluir</button>
              </div>
            </div>
          ))}
          {lojas.length === 0 && <p className="text-xs text-neutral-500 col-span-full text-center py-8">Nenhuma loja cadastrada</p>}
        </div>
      )}

      {modal.open && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setModal({ open: false, nome: "", markup: 100, grupos: "", tipo: "fisica" })}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-6 w-[350px]" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-4">{modal.editId ? "Editar Loja" : "Nova Loja"}</h3>
            <input
              type="text"
              value={modal.nome}
              onChange={e => setModal(p => ({ ...p, nome: e.target.value }))}
              placeholder="Nome da loja"
              className="w-full bg-neutral-700 border border-neutral-600 rounded px-3 py-2 text-xs text-neutral-200 mb-2 focus:outline-none focus:border-indigo-500"
              autoFocus
              onKeyDown={e => e.key === "Enter" && salvar()}
            />
            <div className="mb-4">
              <label className="text-xs text-neutral-400 block mb-1">Tipo de loja:</label>
              <select
                value={modal.tipo}
                onChange={e => setModal(p => ({ ...p, tipo: e.target.value as TipoLoja }))}
                className="w-full bg-neutral-700 border border-neutral-600 rounded px-3 py-2 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500"
              >
                <option value="fisica">Física (PDV, caixa, estoque)</option>
                <option value="virtual">Virtual (marketplace/Shopee)</option>
                <option value="hibrida">Híbrida (física + virtual)</option>
                <option value="marketplace">Marketplace</option>
              </select>
              <p className="text-[10px] text-neutral-600 mt-1">Define quais utilitários aparecem no menu quando esta loja está selecionada.</p>
            </div>
            <div className="flex items-center gap-2 mb-4">
              <label className="text-xs text-neutral-400">Shopee Markup:</label>
              <input
                type="number"
                value={modal.markup}
                onChange={e => setModal(p => ({ ...p, markup: Number(e.target.value) }))}
                className="w-20 bg-neutral-700 border border-neutral-600 rounded px-2 py-1.5 text-xs text-neutral-200 text-right"
                min={50} max={500} step={1}
              />
              <span className="text-xs text-neutral-500">%</span>
            </div>
            <div className="mb-4">
              <label className="text-xs text-neutral-400">Grupos (separados por vírgula):</label>
              <input type="text" value={modal.grupos} onChange={e => setModal(p => ({ ...p, grupos: e.target.value }))}
                placeholder="Ex: Premium, Econômico" className="w-full bg-neutral-700 border border-neutral-600 rounded px-3 py-2 text-xs text-neutral-200 mt-1" />
              <p className="text-[10px] text-neutral-600 mt-1">Vazio = todos. Preenchido = só produtos com grupo correspondente.</p>
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setModal({ open: false, nome: "", markup: 100, grupos: "", tipo: "fisica" })} className="text-xs px-3 py-1.5 rounded-lg text-neutral-400 hover:text-neutral-200">Cancelar</button>
              <button onClick={salvar} className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white">Salvar</button>
            </div>
          </div>
        </div>
      )}

      {exclusaoForcada?.modalAberto && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setExclusaoForcada(null)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-6 w-[420px]" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-red-400 mb-1">Excluir &quot;{exclusaoForcada.nome}&quot; permanentemente</h3>
            <p className="text-[10px] text-neutral-500 mb-4">Esta ação apaga todo o histórico vinculado a esta loja e não pode ser desfeita.</p>
            {exclusaoForcada.carregandoImpacto ? (
              <p className="text-xs text-neutral-400">Calculando impacto...</p>
            ) : exclusaoForcada.impacto ? (
              <div className="max-h-48 overflow-y-auto text-[10px] text-neutral-400 space-y-0.5 mb-4 border border-neutral-700 rounded p-2">
                {Object.entries(exclusaoForcada.impacto.impacto).filter(([, n]) => n > 0).map(([tabela, n]) => (
                  <div key={tabela} className="flex justify-between"><span>{tabela}</span><span>{n}</span></div>
                ))}
                <div className="flex justify-between font-semibold text-neutral-300 pt-1 border-t border-neutral-700">
                  <span>Total de linhas</span><span>{exclusaoForcada.impacto.total_linhas}</span>
                </div>
              </div>
            ) : null}
            {exclusaoForcada.erro && <p className="text-xs text-red-400 mb-2">{exclusaoForcada.erro}</p>}
            <label className="text-xs text-neutral-400 block mb-1">Digite &quot;{exclusaoForcada.nome}&quot; para confirmar:</label>
            <input
              type="text"
              value={exclusaoForcada.nomeDigitado}
              onChange={e => setExclusaoForcada(p => p && { ...p, nomeDigitado: e.target.value })}
              className="w-full bg-neutral-700 border border-neutral-600 rounded px-3 py-2 text-xs text-neutral-200 mb-4 focus:outline-none focus:border-red-500"
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setExclusaoForcada(null)} className="text-xs px-3 py-1.5 rounded-lg text-neutral-400 hover:text-neutral-200">Cancelar</button>
              <button
                onClick={confirmarExclusaoForcada}
                disabled={exclusaoForcada.nomeDigitado !== exclusaoForcada.nome || exclusaoForcada.excluindo}
                className="text-xs px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 disabled:opacity-40 disabled:cursor-not-allowed text-white"
              >{exclusaoForcada.excluindo ? "Excluindo..." : "Excluir permanentemente"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
