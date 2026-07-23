"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { ShopeePedido } from "@/lib/api";

interface LojaShopee {
  id: number;
  nome: string;
  shopee_shop_id: string;
  tem_token: boolean;
}

const STATUS_LABEL: Record<string, string> = {
  UNPAID: "Aguardando pagamento",
  READY_TO_SHIP: "Pronto para envio",
  PROCESSED: "Processado",
  SHIPPED: "Enviado",
  COMPLETED: "Concluído",
  CANCELLED: "Cancelado",
  IN_CANCEL: "Cancelamento em andamento",
  TO_RETURN: "Em devolução",
};

function statusColor(status: string) {
  if (status === "COMPLETED") return "text-green-400";
  if (status === "CANCELLED" || status === "IN_CANCEL") return "text-red-400";
  if (status === "SHIPPED" || status === "READY_TO_SHIP") return "text-blue-400";
  return "text-amber-400";
}

function formatarData(unixSeconds: number) {
  if (!unixSeconds) return "—";
  return new Date(unixSeconds * 1000).toLocaleString("pt-BR");
}

export default function ShopeePedidosPage() {
  const [lojas, setLojas] = useState<LojaShopee[]>([]);
  const [lojaId, setLojaId] = useState<number | "">("");
  const [dias, setDias] = useState(7);
  const [pedidos, setPedidos] = useState<ShopeePedido[]>([]);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [expandido, setExpandido] = useState<string | null>(null);

  useEffect(() => {
    api.shopeeLojas().then(r => {
      const lojasComToken = (r.lojas || []).filter(l => l.tem_token);
      setLojas(lojasComToken);
      if (lojasComToken.length > 0) setLojaId(lojasComToken[0].id);
    }).catch(() => {});
  }, []);

  const buscar = useCallback(async () => {
    if (!lojaId) return;
    setLoading(true);
    setErro(null);
    try {
      const r = await api.shopeePedidos(Number(lojaId), dias);
      if (r.error) { setErro(r.error); setPedidos([]); }
      else setPedidos(r.pedidos || []);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao buscar pedidos");
    } finally {
      setLoading(false);
    }
  }, [lojaId, dias]);

  useEffect(() => { if (lojaId) buscar(); }, [lojaId, buscar]);

  return (
    <div className="p-6 space-y-4 max-w-4xl">
      <div>
        <Link href="/integracoes/shopee" className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors">← Shopee</Link>
        <h1 className="text-lg font-light text-neutral-300 mt-1">Pedidos Shopee</h1>
        <p className="text-xs text-neutral-500 mt-0.5">Pedidos recebidos em cada loja Shopee conectada.</p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <select
          value={lojaId}
          onChange={(e) => setLojaId(e.target.value ? Number(e.target.value) : "")}
          className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200"
        >
          {lojas.length === 0 && <option value="">Nenhuma loja com token ativo</option>}
          {lojas.map(l => <option key={l.id} value={l.id}>{l.nome}</option>)}
        </select>
        <select
          value={dias}
          onChange={(e) => setDias(Number(e.target.value))}
          className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200"
        >
          <option value={1}>Último dia</option>
          <option value={7}>Últimos 7 dias</option>
          <option value={15}>Últimos 15 dias</option>
          <option value={30}>Últimos 30 dias</option>
        </select>
        <button
          onClick={buscar}
          disabled={loading || !lojaId}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors"
        >
          {loading ? "Buscando..." : "Atualizar"}
        </button>
      </div>

      {erro && (
        <div className="text-xs px-3 py-2 rounded-lg border bg-red-950/40 border-red-900/50 text-red-400">{erro}</div>
      )}

      {!loading && lojas.length === 0 && (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 text-center text-neutral-500 text-sm">
          Nenhuma loja Shopee com token ativo. Conecte uma loja na tela de Integrações antes de ver pedidos.
        </div>
      )}

      {!loading && lojas.length > 0 && pedidos.length === 0 && !erro && (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 text-center text-neutral-500 text-sm">
          Nenhum pedido encontrado no período selecionado.
        </div>
      )}

      <div className="space-y-2">
        {pedidos.map((p) => (
          <div key={p.order_sn} className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden">
            <button
              onClick={() => setExpandido(expandido === p.order_sn ? null : p.order_sn)}
              className="w-full flex items-center justify-between p-3 hover:bg-neutral-800/50 transition-colors text-left"
            >
              <div>
                <p className="text-sm text-neutral-200 font-mono">{p.order_sn}</p>
                <p className="text-xs text-neutral-500">
                  {p.recipient_nome || p.buyer_username || "Cliente não identificado"} · {formatarData(p.create_time)}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-sm text-emerald-400 numeric">R$ {Number(p.total_amount || 0).toFixed(2)}</span>
                <span className={`text-xs font-medium ${statusColor(p.status)}`}>{STATUS_LABEL[p.status] || p.status}</span>
              </div>
            </button>
            {expandido === p.order_sn && (
              <div className="border-t border-neutral-800 p-3">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-neutral-500 uppercase tracking-wider text-[10px]">
                      <th className="text-left pb-1">SKU</th>
                      <th className="text-left pb-1">Produto</th>
                      <th className="text-right pb-1">Qtd</th>
                      <th className="text-right pb-1">Preço</th>
                    </tr>
                  </thead>
                  <tbody>
                    {p.itens.map((item, idx) => (
                      <tr key={idx} className="border-t border-neutral-800/50">
                        <td className="py-1 text-neutral-400 font-mono">{item.sku}</td>
                        <td className="py-1 text-neutral-300">{item.nome}</td>
                        <td className="py-1 text-right text-neutral-300 numeric">{item.quantidade}</td>
                        <td className="py-1 text-right text-neutral-300 numeric">R$ {Number(item.preco || 0).toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
