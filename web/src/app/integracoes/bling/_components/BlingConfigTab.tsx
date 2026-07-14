"use client";

import { useEffect, useState, useCallback } from "react";
import Spinner from "./shared/Spinner";
import Alert from "./shared/Alert";
import EmptyState from "./shared/EmptyState";
import {
  getBlingStatus,
  getBlingAuthUrl,
  listarBlingWebhooks,
  criarBlingWebhook,
  deletarBlingWebhook,
  listarBlingNotificacoes,
  listarBlingEventos,
  confirmarLeituraNotificacao,
  BlingWebhook,
} from "@/lib/api";

export default function BlingConfigTab() {
  const [status, setStatus] = useState<{ autenticado: boolean; client_id_setado: boolean } | null>(null);
  const [webhooks, setWebhooks] = useState<BlingWebhook[]>([]);
  const [notificacoes, setNotificacoes] = useState<unknown[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [eventos, setEventos] = useState<string[]>([]);
  const [showWebhookForm, setShowWebhookForm] = useState(false);
  const [novoEvento, setNovoEvento] = useState("");
  const [novaUrl, setNovaUrl] = useState("");

  const carregar = useCallback(async () => {
    try {
      setLoading(true);
      setErro(null);
      const [s, w, n, e] = await Promise.all([
        getBlingStatus(),
        listarBlingWebhooks(),
        listarBlingNotificacoes(),
        listarBlingEventos(),
      ]);
      setStatus(s);
      setWebhooks((w.data || []) as BlingWebhook[]);
      setNotificacoes((n.data || []) as unknown[]);
      setEventos(e.eventos || []);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar configurações");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  const handleAuth = async () => {
    try {
      const { url } = await getBlingAuthUrl();
      if (url) window.open(url, "_blank");
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao obter URL de auth");
    }
  };

  const handleCriarWebhook = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!novoEvento || !novaUrl) return;
    try {
      await criarBlingWebhook(novoEvento, novaUrl);
      setSucesso("Webhook criado!");
      setShowWebhookForm(false);
      setNovoEvento("");
      setNovaUrl("");
      carregar();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro ao criar webhook");
    }
  };

  const handleDeletarWebhook = async (id: number) => {
    if (!confirm("Remover este webhook?")) return;
    try {
      await deletarBlingWebhook(id);
      setSucesso("Webhook removido");
      carregar();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro ao remover webhook");
    }
  };

  if (loading) return <Spinner />;

  return (
    <div className="space-y-6">
      <Alert message={erro} type="error" />
      <Alert message={sucesso} type="success" />

      <section>
        <h3 className="text-sm font-semibold text-neutral-200 mb-3">Conexão OAuth2</h3>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${status?.autenticado ? "bg-emerald-400" : "bg-red-400"}`} />
              <span className="text-xs text-neutral-300">{status?.autenticado ? "Autenticado" : "Não autenticado"}</span>
            </div>
            <button onClick={handleAuth} disabled={!status?.client_id_setado}
              className={`px-4 py-1.5 text-xs rounded-lg transition-colors ${status?.autenticado ? "bg-neutral-700 text-neutral-400" : "bg-indigo-600 text-white hover:bg-indigo-500"}`}>
              {status?.autenticado ? "Reconectar" : "Conectar Bling"}
            </button>
          </div>
          <div className="text-[10px] text-neutral-500">
            Client ID: {status?.client_id_setado ? "✅ Configurado" : "❌ Não configurado"}
          </div>
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-neutral-200">Webhooks ({webhooks.length})</h3>
          <button onClick={() => setShowWebhookForm(!showWebhookForm)}
            className="px-3 py-1 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">+ Novo</button>
        </div>

        {showWebhookForm && (
          <form onSubmit={handleCriarWebhook} className="bg-neutral-800 border border-neutral-700 rounded-lg p-3 mb-3 space-y-2">
            <select value={novoEvento} onChange={(e) => setNovoEvento(e.target.value)}
              className="w-full bg-neutral-750 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200">
              <option value="">Selecione o evento...</option>
              {eventos.map((ev) => (
                <option key={ev} value={ev}>{ev}</option>
              ))}
            </select>
            <input type="url" value={novaUrl} onChange={(e) => setNovaUrl(e.target.value)}
              placeholder="https://exemplo.com/webhook/bling"
              className="w-full bg-neutral-750 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200" />
            <div className="flex gap-2">
              <button type="submit" className="px-3 py-1 bg-emerald-600 text-white text-xs rounded hover:bg-emerald-500">Salvar</button>
              <button type="button" onClick={() => setShowWebhookForm(false)} className="px-3 py-1 text-xs text-neutral-400 hover:text-neutral-200">Cancelar</button>
            </div>
          </form>
        )}

        {webhooks.length === 0 ? (
          <EmptyState icon="🔗" title="Nenhum webhook" description="Crie webhooks para receber eventos do Bling em tempo real." />
        ) : (
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-neutral-700 text-neutral-400">
                  <th className="text-left p-2">Evento</th>
                  <th className="text-left p-2">URL</th>
                  <th className="text-center p-2">Status</th>
                  <th className="text-right p-2">Ações</th>
                </tr>
              </thead>
              <tbody>
                {webhooks.map((w) => (
                  <tr key={w.id} className="border-b border-neutral-700/50">
                    <td className="p-2 text-neutral-200 font-mono text-[10px]">{w.evento}</td>
                    <td className="p-2 text-neutral-400 text-[10px] truncate max-w-[200px]">{w.url}</td>
                    <td className="p-2 text-center">
                      <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-900/30 text-emerald-400">Ativo</span>
                    </td>
                    <td className="p-2 text-right">
                      <button onClick={() => handleDeletarWebhook(w.id)} className="text-red-400 hover:text-red-300">🗑</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h3 className="text-sm font-semibold text-neutral-200 mb-3">Notificações ({notificacoes.length})</h3>
        {notificacoes.length === 0 ? (
          <EmptyState icon="🔔" title="Nenhuma notificação" description="Notificações do Bling aparecerão aqui." />
        ) : (
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden max-h-64 overflow-y-auto">
            {notificacoes.map((n: any, i) => (
              <div key={n.id || i} className="flex items-center justify-between p-2 border-b border-neutral-700/50 text-xs">
                <span className="text-neutral-300">{n.mensagem || n.descricao || `Notificação #${n.id}`}</span>
                <button onClick={async () => { try { await confirmarLeituraNotificacao(n.id); carregar(); } catch {} }}
                  className="text-indigo-400 hover:text-indigo-300">Marcar lida</button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
