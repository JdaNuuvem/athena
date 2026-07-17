"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

interface EstoquePorLoja { loja: string; quantidade: number; data_atualizacao?: string | null; }

interface Props {
  produto: Record<string, unknown> | null;
}

function Badge({ label, color }: { label: string; color: string }) {
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${color}`}>{label}</span>;
}

function ProgressBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="w-full bg-neutral-800 rounded-full h-2 overflow-hidden">
      <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function SugestaoReposicao({ atual, minimo, maximo }: { atual: number; minimo: number; maximo: number }) {
  if (atual >= minimo) return <span className="text-xs text-green-400">Estoque adequado</span>;
  const necessario = Math.max(maximo - atual, minimo - atual);
  return <span className="text-xs text-amber-400">Comprar ~{necessario} un</span>;
}

export default function ControleTab({ produto }: Props) {
  const p = produto as any;
  const sku = String(p?.sku || "");
  const estoqueMinimo = Number(p?.estoque_minimo ?? 0);
  const estoqueMaximo = Number(p?.estoque_maximo ?? 0);
  const fornecedor = String(p?.fornecedor_nome || "Não informado");
  const localizacao = String(p?.estoque_localizacao || "");
  const porLoja: EstoquePorLoja[] = Array.isArray(p?.estoque_por_loja) ? p.estoque_por_loja : [];
  const totalAtual = porLoja.reduce((s, l) => s + Number(l.quantidade || 0), 0);

  const [lojasShopee, setLojasShopee] = useState<Array<{ id: number; nome: string }>>([]);
  const [enviando, setEnviando] = useState<string | null>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api.shopeeLojas().then(r => setLojasShopee(r.lojas || [])).catch(() => {});
  }, []);

  const enviarParaShopee = async (loja: string, quantidade: number) => {
    const alvo = lojasShopee.find(l => l.nome === loja);
    if (!alvo || !sku) return;
    setEnviando(loja); setMsg("");
    try {
      const r = await api.shopeeAtualizarEstoqueProduto(sku, alvo.id, quantidade);
      setMsg(r.error ? `Erro: ${r.error}` : `${loja}: estoque enviado à Shopee (${quantidade} un)`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Erro ao enviar para Shopee");
    } finally {
      setEnviando(null);
      setTimeout(() => setMsg(""), 4000);
    }
  };

  const enviarParaTodasLojas = async (quantidade: number) => {
    if (!sku) return;
    setEnviando("__todas__"); setMsg("");
    try {
      const r = await api.shopeeEstoqueTodasLojas(sku, quantidade);
      setMsg(r.erro ? `Erro: ${r.erro}` : `Enviado para ${r.sucesso}/${r.total} lojas Shopee (${quantidade} un)`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Erro ao enviar para todas as lojas");
    } finally {
      setEnviando(null);
      setTimeout(() => setMsg(""), 4000);
    }
  };

  if (!estoqueMinimo && !estoqueMaximo && porLoja.length === 0) {
    return (
      <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 text-center text-neutral-500 text-sm">
        Sem dados de controle de estoque para este produto. Sincronize com o Bling ou registre estoque por loja.
      </div>
    );
  }

  const status = totalAtual <= 0 ? "Sem estoque" : estoqueMinimo && totalAtual <= estoqueMinimo ? "Crítico" : "Ativo";
  const barColor = status === "Sem estoque" ? "bg-red-500" : status === "Crítico" ? "bg-amber-500" : "bg-green-500";

  return (
    <div className="space-y-6">
      <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-medium text-neutral-200">Controle Geral (Bling)</h3>
            <p className="text-xs text-neutral-500">Fornecedor: {fornecedor}{localizacao ? ` · Localização: ${localizacao}` : ""}</p>
          </div>
          <Badge label={status} color={status === "Ativo" ? "bg-green-900/50 text-green-400" : status === "Crítico" ? "bg-amber-900/50 text-amber-400" : "bg-red-900/50 text-red-400"} />
        </div>

        {estoqueMaximo > 0 && (
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-neutral-500">Estoque Atual</span>
              <span className={`numeric font-medium ${status === "Sem estoque" ? "text-red-400" : status === "Crítico" ? "text-amber-400" : "text-green-400"}`}>
                {totalAtual} / {estoqueMaximo} un
              </span>
            </div>
            <ProgressBar value={totalAtual} max={estoqueMaximo} color={barColor} />
          </div>
        )}

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-neutral-800/50 rounded-lg p-2.5">
            <p className="text-[10px] text-neutral-500 uppercase tracking-wider">Estoque Mínimo</p>
            <p className="text-sm text-red-400 numeric font-medium">{estoqueMinimo || "—"}</p>
          </div>
          <div className="bg-neutral-800/50 rounded-lg p-2.5">
            <p className="text-[10px] text-neutral-500 uppercase tracking-wider">Estoque Máximo</p>
            <p className="text-sm text-neutral-200 numeric font-medium">{estoqueMaximo || "—"}</p>
          </div>
          <div className="bg-neutral-800/50 rounded-lg p-2.5">
            <p className="text-[10px] text-neutral-500 uppercase tracking-wider">Total Atual</p>
            <p className="text-sm text-neutral-200 numeric font-medium">{totalAtual}</p>
          </div>
          <div className="bg-neutral-800/50 rounded-lg p-2.5">
            <p className="text-[10px] text-neutral-500 uppercase tracking-wider">Sugestão</p>
            {estoqueMinimo > 0
              ? <SugestaoReposicao atual={totalAtual} minimo={estoqueMinimo} maximo={estoqueMaximo} />
              : <span className="text-xs text-neutral-600">—</span>}
          </div>
        </div>
      </div>

      {porLoja.length > 0 && (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
          <div className="flex items-center justify-between px-3 pt-3">
            {msg ? <span className="text-xs text-emerald-400">{msg}</span> : <span />}
            {lojasShopee.length > 1 && (
              <button
                onClick={() => enviarParaTodasLojas(totalAtual)}
                disabled={enviando === "__todas__"}
                className="text-[10px] bg-orange-700 hover:bg-orange-600 disabled:opacity-50 text-white px-2.5 py-1.5 rounded-lg"
              >
                {enviando === "__todas__" ? "Enviando..." : `Enviar ${totalAtual} un para todas as lojas Shopee`}
              </button>
            )}
          </div>
          <table className="w-full text-sm min-w-[400px]">
            <thead>
              <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
                <th className="text-left p-3 font-medium">Loja / Depósito</th>
                <th className="text-right p-3 font-medium">Quantidade</th>
                <th className="text-left p-3 font-medium">Atualizado em</th>
                <th className="text-center p-3 font-medium">Shopee</th>
              </tr>
            </thead>
            <tbody>
              {porLoja.map((l) => {
                const shopeeVinculada = lojasShopee.some(s => s.nome === l.loja);
                return (
                  <tr key={l.loja} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                    <td className="p-3 text-neutral-300">{l.loja}</td>
                    <td className="p-3 text-right text-neutral-200 numeric">{l.quantidade}</td>
                    <td className="p-3 text-neutral-500 text-xs">{l.data_atualizacao ? new Date(l.data_atualizacao).toLocaleString("pt-BR") : "—"}</td>
                    <td className="p-3 text-center">
                      {shopeeVinculada ? (
                        <button
                          onClick={() => enviarParaShopee(l.loja, l.quantidade)}
                          disabled={enviando === l.loja}
                          className="text-[10px] bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white px-2 py-1 rounded"
                        >
                          {enviando === l.loja ? "Enviando..." : "Enviar"}
                        </button>
                      ) : (
                        <span className="text-[10px] text-neutral-600">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
