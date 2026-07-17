"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

interface LojaShopee {
  id: number;
  nome: string;
  shopee_shop_id: string;
  shopee_shop_name: string | null;
  shopee_token_expira_em: string | null;
}

interface LojaSimples {
  id: number;
  nome: string;
  ativa: boolean;
}

export default function ShopeeIntegrationPage() {
  const [lojasShopee, setLojasShopee] = useState<LojaShopee[]>([]);
  const [lojasDisponiveis, setLojasDisponiveis] = useState<LojaSimples[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncingId, setSyncingId] = useState<number | "novo" | null>(null);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);
  const [lojaParaConectar, setLojaParaConectar] = useState<string>("");

  const carregar = useCallback(async () => {
    setLoading(true);
    try {
      const [shopeeR, lojasR] = await Promise.all([
        api.shopeeLojas().catch(() => ({ lojas: [] as LojaShopee[] })),
        api.lojasManage().catch(() => ({ lojas: [] as LojaSimples[] })),
      ]);
      setLojasShopee(shopeeR.lojas || []);
      setLojasDisponiveis(lojasR.lojas || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  const conectarNovaLoja = async () => {
    try {
      const lojaId = lojaParaConectar ? Number(lojaParaConectar) : undefined;
      const r = lojaId ? await api.shopeeConectarLoja(lojaId) : await api.shopeeAuthUrl();
      if (r.url) {
        window.open(r.url, "_blank", "noopener,noreferrer");
        setMsg({ text: "Janela de autorização da Shopee aberta. Após autorizar, volte e atualize esta página.", ok: true });
      } else {
        setMsg({ text: "Não foi possível gerar a URL de autorização (Partner ID configurado?)", ok: false });
      }
    } catch (e) {
      setMsg({ text: e instanceof Error ? e.message : "Erro ao conectar", ok: false });
    }
  };

  const sincronizar = async (lojaId?: number) => {
    setSyncingId(lojaId ?? "novo");
    setMsg(null);
    try {
      const r = await api.shopeeSync(lojaId);
      setMsg({ text: `${r.total} itens sincronizados${r.erros ? ` · ${r.erros} erros` : ""}`, ok: true });
      carregar();
    } catch (e) {
      setMsg({ text: e instanceof Error ? e.message : "Erro ao sincronizar", ok: false });
    } finally {
      setSyncingId(null);
    }
  };

  const lojasSemShopee = lojasDisponiveis.filter(l => !lojasShopee.some(s => s.id === l.id));

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <div>
        <Link href="/integracoes" className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors">← Integrações</Link>
        <h1 className="text-lg font-light text-neutral-300 mt-1">Shopee</h1>
        <p className="text-xs text-neutral-500 mt-0.5">Gerencie suas lojas Shopee e sincronize produtos/estoque — suporta múltiplas contas.</p>
      </div>

      {msg && (
        <div className={`text-xs px-3 py-2 rounded-lg border ${msg.ok ? "bg-green-950/40 border-green-900/50 text-green-400" : "bg-red-950/40 border-red-900/50 text-red-400"}`}>
          {msg.text}
        </div>
      )}

      <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3">
        <h2 className="text-sm font-medium text-neutral-300">Lojas Conectadas</h2>
        {loading ? (
          <p className="text-xs text-neutral-500">Carregando...</p>
        ) : lojasShopee.length === 0 ? (
          <p className="text-xs text-neutral-500">Nenhuma loja Shopee conectada ainda.</p>
        ) : (
          <div className="space-y-2">
            {lojasShopee.map((l) => (
              <div key={l.id} className="flex items-center justify-between bg-neutral-800/50 rounded-lg px-3 py-2">
                <div>
                  <p className="text-sm text-neutral-200">{l.nome}</p>
                  <p className="text-[10px] text-neutral-500 font-mono">shop_id: {l.shopee_shop_id}</p>
                </div>
                <button
                  onClick={() => sincronizar(l.id)}
                  disabled={syncingId === l.id}
                  className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs px-3 py-1.5 rounded-lg transition-colors"
                >
                  {syncingId === l.id ? "Sincronizando..." : "Sincronizar"}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3">
        <h2 className="text-sm font-medium text-neutral-300">Conectar Nova Loja</h2>
        <p className="text-xs text-neutral-500">
          Vincule a autorização a uma das suas lojas cadastradas (opcional) ou conecte sem vincular.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={lojaParaConectar}
            onChange={(e) => setLojaParaConectar(e.target.value)}
            className="bg-neutral-800 border border-neutral-700 rounded-lg px-2 py-1.5 text-xs text-neutral-200"
          >
            <option value="">Sem vincular a uma loja específica</option>
            {lojasSemShopee.map((l) => (
              <option key={l.id} value={l.id}>{l.nome}</option>
            ))}
          </select>
          <button
            onClick={conectarNovaLoja}
            className="bg-emerald-600 hover:bg-emerald-500 text-white text-sm px-4 py-2 rounded-lg transition-colors"
          >
            Conectar Loja Shopee
          </button>
        </div>
      </div>

      <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
        <button
          onClick={() => sincronizar()}
          disabled={syncingId === "novo"}
          className="bg-neutral-700 hover:bg-neutral-600 disabled:opacity-50 text-white text-xs px-3 py-1.5 rounded-lg transition-colors"
        >
          {syncingId === "novo" ? "Sincronizando..." : "Sincronizar loja padrão (config legada)"}
        </button>
      </div>
    </div>
  );
}
