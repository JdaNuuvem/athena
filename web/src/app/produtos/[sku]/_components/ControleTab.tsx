"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";

interface EstoquePorLoja { loja: string; quantidade: number; data_atualizacao?: string | null; }
interface AnuncioShopee { marketplace: string; shop_id?: string; anuncio_id?: string; preco: number; status: string; }
interface LojaShopee { id: number; nome: string; shopee_shop_id?: string; }
interface Variacao { model_id: number; model_name: string; model_sku: string; price_info?: Array<{ current_price: number }>; stock_info_v2?: { summary_info?: { total_available_stock: number } }; }

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

  const [lojasShopee, setLojasShopee] = useState<LojaShopee[]>([]);
  const [enviando, setEnviando] = useState<string | null>(null);
  const [msg, setMsg] = useState("");

  const anunciosShopee: AnuncioShopee[] = Array.isArray(p?.estoque_lojas)
    ? p.estoque_lojas.filter((a: AnuncioShopee) => a.marketplace === "shopee" && a.anuncio_id)
    : [];

  const [precos, setPrecos] = useState<Record<string, string>>({});
  const [atualizandoPreco, setAtualizandoPreco] = useState<string | null>(null);
  const [pausando, setPausando] = useState<string | null>(null);
  const [variacoesAbertas, setVariacoesAbertas] = useState<string | null>(null);
  const [variacoes, setVariacoes] = useState<Variacao[]>([]);
  const [carregandoVariacoes, setCarregandoVariacoes] = useState<string | null>(null);

  useEffect(() => {
    api.shopeeLojas().then(r => setLojasShopee(r.lojas || [])).catch(() => {});
  }, []);

  const lojaIdPorShopId = (shopId?: string) => lojasShopee.find(l => l.shopee_shop_id === shopId)?.id;

  const atualizarPreco = async (anuncio: AnuncioShopee) => {
    const itemId = Number(anuncio.anuncio_id);
    const lojaId = lojaIdPorShopId(anuncio.shop_id);
    const novoPreco = Number(precos[anuncio.anuncio_id || ""]);
    if (!itemId || !lojaId || !novoPreco) { setMsg("Preço inválido ou loja não vinculada"); return; }
    setAtualizandoPreco(anuncio.anuncio_id || null); setMsg("");
    try {
      const r = await api.shopeeAtualizarPreco(itemId, lojaId, novoPreco);
      setMsg(r.error ? `Erro: ${r.error}` : "Preço atualizado na Shopee");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Erro ao atualizar preço");
    } finally {
      setAtualizandoPreco(null);
      setTimeout(() => setMsg(""), 4000);
    }
  };

  const alternarPausa = async (anuncio: AnuncioShopee) => {
    const itemId = Number(anuncio.anuncio_id);
    const lojaId = lojaIdPorShopId(anuncio.shop_id);
    if (!itemId || !lojaId) { setMsg("Loja não vinculada"); return; }
    const pausar = anuncio.status !== "unlist" && anuncio.status !== "pausado";
    setPausando(anuncio.anuncio_id || null); setMsg("");
    try {
      const r = await api.shopeeUnlistProduto(itemId, lojaId, pausar);
      setMsg(r.error ? `Erro: ${r.error}` : pausar ? "Anúncio pausado na Shopee" : "Anúncio reativado na Shopee");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Erro ao alterar status do anúncio");
    } finally {
      setPausando(null);
      setTimeout(() => setMsg(""), 4000);
    }
  };

  const verVariacoes = async (anuncio: AnuncioShopee) => {
    const itemId = Number(anuncio.anuncio_id);
    if (!itemId) return;
    if (variacoesAbertas === anuncio.anuncio_id) { setVariacoesAbertas(null); return; }
    const lojaId = lojaIdPorShopId(anuncio.shop_id);
    setCarregandoVariacoes(anuncio.anuncio_id || null);
    try {
      const r = await api.shopeeVariacoes(itemId, lojaId);
      setVariacoes((r.response?.model as Variacao[]) || []);
      setVariacoesAbertas(anuncio.anuncio_id || null);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Erro ao buscar variações");
    } finally {
      setCarregandoVariacoes(null);
    }
  };

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

      {anunciosShopee.length > 0 && (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3">
          <h3 className="text-sm font-medium text-neutral-200">Anúncios na Shopee</h3>
          <div className="space-y-3">
            {anunciosShopee.map((a) => {
              const anuncioId = a.anuncio_id || "";
              const pausado = a.status === "unlist" || a.status === "pausado";
              const lojaId = lojaIdPorShopId(a.shop_id);
              return (
                <div key={anuncioId} className="bg-neutral-800/50 rounded-lg p-3 space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-xs text-neutral-300">item_id: <span className="font-mono">{anuncioId}</span></p>
                      <p className="text-[10px] text-neutral-500">Preço atual: R$ {Number(a.preco || 0).toFixed(2)} · Status: {a.status}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        step="0.01"
                        placeholder="Novo preço"
                        value={precos[anuncioId] || ""}
                        onChange={(e) => setPrecos({ ...precos, [anuncioId]: e.target.value })}
                        className="w-24 bg-neutral-900 border border-neutral-700 rounded-lg px-2 py-1 text-xs text-neutral-200"
                      />
                      <button
                        onClick={() => atualizarPreco(a)}
                        disabled={atualizandoPreco === anuncioId || !lojaId}
                        className="text-[10px] bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-2.5 py-1.5 rounded-lg"
                      >
                        {atualizandoPreco === anuncioId ? "Atualizando..." : "Atualizar preço"}
                      </button>
                      <button
                        onClick={() => alternarPausa(a)}
                        disabled={pausando === anuncioId || !lojaId}
                        className={`text-[10px] disabled:opacity-50 text-white px-2.5 py-1.5 rounded-lg ${pausado ? "bg-emerald-700 hover:bg-emerald-600" : "bg-amber-700 hover:bg-amber-600"}`}
                      >
                        {pausando === anuncioId ? "Aguarde..." : pausado ? "Reativar" : "Pausar"}
                      </button>
                      <button
                        onClick={() => verVariacoes(a)}
                        disabled={carregandoVariacoes === anuncioId}
                        className="text-[10px] bg-neutral-700 hover:bg-neutral-600 disabled:opacity-50 text-white px-2.5 py-1.5 rounded-lg"
                      >
                        {carregandoVariacoes === anuncioId ? "Carregando..." : variacoesAbertas === anuncioId ? "Ocultar variações" : "Ver variações"}
                      </button>
                    </div>
                  </div>
                  {variacoesAbertas === anuncioId && (
                    variacoes.length === 0 ? (
                      <p className="text-[10px] text-neutral-500">Este item não possui variações (produto simples).</p>
                    ) : (
                      <table className="w-full text-xs mt-2">
                        <thead>
                          <tr className="text-neutral-500 text-[10px] uppercase tracking-wider">
                            <th className="text-left py-1">Variação</th>
                            <th className="text-left py-1">SKU</th>
                            <th className="text-right py-1">Preço</th>
                            <th className="text-right py-1">Estoque</th>
                          </tr>
                        </thead>
                        <tbody>
                          {variacoes.map((v) => (
                            <tr key={v.model_id} className="border-t border-neutral-700/50">
                              <td className="py-1 text-neutral-300">{v.model_name}</td>
                              <td className="py-1 text-neutral-500 font-mono">{v.model_sku}</td>
                              <td className="py-1 text-right text-neutral-200 numeric">R$ {Number(v.price_info?.[0]?.current_price || 0).toFixed(2)}</td>
                              <td className="py-1 text-right text-neutral-200 numeric">{v.stock_info_v2?.summary_info?.total_available_stock ?? "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
