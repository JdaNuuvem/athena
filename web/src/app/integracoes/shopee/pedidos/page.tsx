"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { api } from "@/lib/api";
import { useTheme, chartAxisColors } from "@/lib/theme-context";
import type { ShopeePedidoSincronizado, ShopeePedidosEstatisticas } from "@/lib/api";
import Icon from "@/app/_components/Icon";
import PainelFulfillment from "./_components/PainelFulfillment";
import MapaBrasilPedidos from "./_components/MapaBrasilPedidos";

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

const STATUS_ORDEM = Object.keys(STATUS_LABEL);

function statusColor(status: string) {
  if (status === "COMPLETED") return "text-green-400";
  if (status === "CANCELLED" || status === "IN_CANCEL") return "text-red-400";
  if (status === "SHIPPED" || status === "READY_TO_SHIP") return "text-blue-400";
  return "text-amber-400";
}

function statusHex(status: string) {
  if (status === "COMPLETED") return "#4ade80";
  if (status === "CANCELLED" || status === "IN_CANCEL") return "#f87171";
  if (status === "SHIPPED" || status === "READY_TO_SHIP") return "#60a5fa";
  return "#fbbf24";
}

function fmtHoras(h: number | null) {
  if (h === null || h === undefined) return "—";
  if (h < 24) return `${h.toFixed(1)}h`;
  return `${Math.floor(h / 24)}d ${Math.round(h % 24)}h`;
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-2 text-xs shadow-lg">
      <div className="text-neutral-500">{label}</div>
      <div className="numeric text-neutral-200 mt-0.5">{payload[0].value}</div>
    </div>
  );
}

function fmtBRL(v: number | string) {
  return "R$ " + Number(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// A Shopee mascara nome/endereco do destinatario como "****" (protecao de dados
// do comprador) — buyer_username nao vem mascarado, entao e' o identificador
// mais confiavel do cliente quando isso acontece.
function mascarado(v: string | null | undefined) {
  return !v || /^\*+$/.test(v);
}

function nomeCliente(p: { recipient_nome: string; buyer_username: string }) {
  if (!mascarado(p.recipient_nome)) return p.recipient_nome;
  if (!mascarado(p.buyer_username)) return `@${p.buyer_username}`;
  return "Cliente não identificado";
}

function formatarData(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR");
}

const POR_PAGINA = 30;

export default function ShopeePedidosPage() {
  const { theme } = useTheme();
  const { grid: gridColor, axis: axisColor } = chartAxisColors(theme);
  const [lojas, setLojas] = useState<LojaShopee[]>([]);
  const [lojaId, setLojaId] = useState<number | "">("");
  const [pedidos, setPedidos] = useState<ShopeePedidoSincronizado[]>([]);
  const [total, setTotal] = useState(0);
  const [valorTotal, setValorTotal] = useState(0);
  const [atrasados, setAtrasados] = useState(0);
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [expandido, setExpandido] = useState<number | null>(null);
  const [statusFiltro, setStatusFiltro] = useState("");
  const [buscaInput, setBuscaInput] = useState("");
  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState(1);
  const [diasSync, setDiasSync] = useState(30);
  const [sincronizando, setSincronizando] = useState(false);
  const [diasEstatisticas, setDiasEstatisticas] = useState(90);
  const [estatisticas, setEstatisticas] = useState<ShopeePedidosEstatisticas | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    api.shopeeLojas().then(r => {
      const lojasComToken = (r.lojas || []).filter(l => l.tem_token);
      setLojas(lojasComToken);
      if (lojasComToken.length > 0) setLojaId(lojasComToken[0].id);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setPagina(1);
      setBusca(buscaInput.trim());
    }, 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [buscaInput]);

  const carregar = useCallback(async () => {
    if (!lojaId) return;
    setLoading(true);
    setErro(null);
    try {
      const r = await api.shopeePedidosSincronizados(Number(lojaId), {
        status: statusFiltro || undefined,
        busca: busca || undefined,
        pagina,
      });
      if (r.error) { setErro(r.error); setPedidos([]); }
      else {
        setPedidos(r.pedidos || []);
        setTotal(r.total || 0);
        setValorTotal(r.valor_total || 0);
        setAtrasados(r.atrasados || 0);
      }
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao buscar pedidos");
    } finally {
      setLoading(false);
    }
  }, [lojaId, statusFiltro, busca, pagina]);

  useEffect(() => { carregar(); }, [carregar]);

  useEffect(() => {
    if (!lojaId) { setEstatisticas(null); return; }
    api.shopeePedidosEstatisticas(Number(lojaId), diasEstatisticas)
      .then((r) => setEstatisticas(r.error ? null : r))
      .catch(() => setEstatisticas(null));
  }, [lojaId, diasEstatisticas]);

  const sincronizar = async () => {
    if (!lojaId) return;
    setSincronizando(true);
    setMsg(null);
    setErro(null);
    try {
      const r = await api.shopeeSincronizarPedidos(Number(lojaId), diasSync);
      setMsg(`${r.total} pedidos sincronizados${r.erros ? ` · ${r.erros} erros` : ""}`);
      await carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao sincronizar pedidos");
    } finally {
      setSincronizando(false);
      setTimeout(() => setMsg(null), 6000);
    }
  };

  const totalPaginas = Math.max(1, Math.ceil(total / POR_PAGINA));

  return (
    <div className="p-6 space-y-4 max-w-5xl">
      <div>
        <Link href="/integracoes/shopee" className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors inline-flex items-center gap-1"><Icon name="chevronLeft" size={14} /> Shopee</Link>
        <h1 className="text-lg font-light text-neutral-300 mt-1">Pedidos Shopee</h1>
        <p className="text-xs text-neutral-500 mt-0.5">Pedidos sincronizados de cada loja Shopee — todos os status, com endereço, pagamento e rastreio.</p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <select
          value={lojaId}
          onChange={(e) => { setLojaId(e.target.value ? Number(e.target.value) : ""); setPagina(1); }}
          className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200"
        >
          {lojas.length === 0 && <option value="">Nenhuma loja com token ativo</option>}
          {lojas.map(l => <option key={l.id} value={l.id}>{l.nome}</option>)}
        </select>
        <select
          value={diasSync}
          onChange={(e) => setDiasSync(Number(e.target.value))}
          title="Período que a sincronização busca na Shopee"
          className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200"
        >
          <option value={7}>Sincronizar últimos 7 dias</option>
          <option value={30}>Sincronizar últimos 30 dias</option>
          <option value={90}>Sincronizar últimos 90 dias</option>
        </select>
        <button
          onClick={sincronizar}
          disabled={sincronizando || !lojaId}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors"
        >
          {sincronizando ? "Sincronizando..." : "Sincronizar com a Shopee"}
        </button>
      </div>

      {msg && <div className="text-xs px-3 py-2 rounded-lg border bg-green-950/40 border-green-900/50 text-green-400">{msg}</div>}
      {erro && <div className="text-xs px-3 py-2 rounded-lg border bg-red-950/40 border-red-900/50 text-red-400">{erro}</div>}

      {!loading && lojas.length === 0 && (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 text-center text-neutral-500 text-sm">
          Nenhuma loja Shopee com token ativo. Conecte uma loja na tela de Integrações antes de ver pedidos.
        </div>
      )}

      {lojas.length > 0 && (
        <>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs text-neutral-500 uppercase tracking-wider">Onde estão os pedidos</p>
              <select
                value={diasEstatisticas}
                onChange={(e) => setDiasEstatisticas(Number(e.target.value))}
                className="bg-neutral-800 border border-neutral-700 rounded-lg px-2 py-1 text-xs text-neutral-200"
              >
                <option value={30}>Últimos 30 dias</option>
                <option value={90}>Últimos 90 dias</option>
                <option value={180}>Últimos 180 dias</option>
              </select>
            </div>
            {estatisticas?.enderecos_mascarados ? (
              <p className="text-sm text-center py-6 text-neutral-500">
                A Shopee não está enviando o estado do destinatário para esta conta (endereço protegido pela API — vem mascarado como &quot;****&quot;). Sem esse dado não há como montar o mapa.
              </p>
            ) : (
              <MapaBrasilPedidos dados={estatisticas?.por_estado || []} />
            )}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
              <p className="text-xs text-neutral-500 uppercase tracking-wider mb-3">Pedidos por dia</p>
              {estatisticas && estatisticas.serie_diaria.length > 0 ? (
                <ResponsiveContainer width="100%" height={180}>
                  <LineChart data={estatisticas.serie_diaria.map((p) => ({ ...p, diaLabel: p.dia.slice(8, 10) + "/" + p.dia.slice(5, 7) }))}>
                    <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                    <XAxis dataKey="diaLabel" stroke={axisColor} tick={{ fontSize: 10, fill: axisColor }} />
                    <YAxis stroke={axisColor} tick={{ fontSize: 10, fill: axisColor }} allowDecimals={false} width={30} />
                    <Tooltip content={<ChartTooltip />} />
                    <Line type="monotone" dataKey="total" stroke={theme === "dark" ? "#34d399" : "#059669"} strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="text-sm text-center py-14 text-neutral-500">Sem dados no período</div>
              )}
            </div>

            <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
              <p className="text-xs text-neutral-500 uppercase tracking-wider mb-3">Distribuição por status</p>
              {estatisticas && estatisticas.por_status.length > 0 ? (
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart
                    data={estatisticas.por_status.map((s) => ({ ...s, label: STATUS_LABEL[s.status] || s.status }))}
                    layout="vertical"
                    margin={{ left: 90 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                    <XAxis type="number" stroke={axisColor} tick={{ fontSize: 10, fill: axisColor }} allowDecimals={false} />
                    <YAxis type="category" dataKey="label" stroke={axisColor} tick={{ fontSize: 10, fill: axisColor }} width={90} />
                    <Tooltip content={<ChartTooltip />} />
                    <Bar dataKey="total" radius={[0, 3, 3, 0]}>
                      {estatisticas.por_status.map((s, i) => <Cell key={i} fill={statusHex(s.status)} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="text-sm text-center py-14 text-neutral-500">Sem dados no período</div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            <div className="lg:col-span-2 bg-neutral-900 border border-neutral-800 rounded-lg p-4">
              <p className="text-xs text-neutral-500 uppercase tracking-wider mb-3">Clientes recorrentes no período</p>
              {estatisticas && estatisticas.clientes_recorrentes.length > 0 ? (
                <div className="space-y-1.5">
                  {estatisticas.clientes_recorrentes.map((c, i) => (
                    <div key={c.cliente + i} className="flex items-center gap-3 text-sm">
                      <span className="text-xs text-neutral-600 w-4 shrink-0">{i + 1}</span>
                      <span className="flex-1 min-w-0 truncate text-neutral-300">{c.cliente}</span>
                      <span className="text-xs text-neutral-500 numeric shrink-0">{c.total} pedidos</span>
                      <span className="text-emerald-400 numeric shrink-0 w-24 text-right">{fmtBRL(c.valor)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-center py-6 text-neutral-500">Nenhum comprador com mais de 1 pedido no período.</p>
              )}
            </div>
            <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-3 flex flex-col justify-center">
              <p className="text-xs text-neutral-500 uppercase tracking-wider">Tempo médio de despacho</p>
              <p className="text-lg text-neutral-200 numeric font-medium mt-1">{fmtHoras(estatisticas?.tempo_medio_despacho_horas ?? null)}</p>
              <p className="text-xs text-neutral-600 mt-1">Do pedido pago até o despacho registrado.</p>
            </div>
          </div>

          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 flex flex-wrap items-center gap-3">
            <input
              type="text"
              value={buscaInput}
              onChange={(e) => setBuscaInput(e.target.value)}
              placeholder="Buscar por pedido, cliente ou SKU..."
              className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 w-60 placeholder:text-neutral-500"
            />
            <select
              value={statusFiltro}
              onChange={(e) => { setStatusFiltro(e.target.value); setPagina(1); }}
              className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200"
            >
              <option value="">Todos os status</option>
              {STATUS_ORDEM.map(s => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
            </select>
            <div className="flex items-center gap-4 ml-auto text-xs">
              <span className="text-neutral-500">{total} pedido{total === 1 ? "" : "s"}</span>
              <span className="text-neutral-300 numeric">{fmtBRL(valorTotal)}</span>
              {atrasados > 0 && (
                <span className="text-amber-400 font-medium">{atrasados} atrasado{atrasados === 1 ? "" : "s"}</span>
              )}
            </div>
          </div>

          {loading ? (
            <p className="text-xs text-neutral-500">Carregando...</p>
          ) : pedidos.length === 0 ? (
            <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 text-center text-neutral-500 text-sm">
              {total === 0 && !statusFiltro && !busca
                ? <>Nenhum pedido sincronizado ainda. Clique em &quot;Sincronizar com a Shopee&quot;.</>
                : <>Nenhum pedido encontrado com esses filtros.</>}
            </div>
          ) : (
            <>
              <div className="instrument-enter space-y-2">
                {pedidos.map((p) => {
                  const atrasado = p.status === "READY_TO_SHIP" && !!p.prazo_envio && new Date(p.prazo_envio) < new Date();
                  return (
                    <div key={p.id} className="instrument-hover bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden">
                      <button
                        onClick={() => setExpandido(expandido === p.id ? null : p.id)}
                        className="w-full flex items-center justify-between p-3 hover:bg-neutral-800/50 transition-colors text-left gap-3"
                      >
                        <div className="min-w-0">
                          <p className="text-sm text-neutral-200 font-mono">{p.order_sn}</p>
                          <p className="text-xs text-neutral-500 truncate">
                            {nomeCliente(p)} · {formatarData(p.create_time)}
                          </p>
                        </div>
                        <div className="flex items-center gap-3 shrink-0">
                          {atrasado && <span className="text-[10px] bg-amber-900/40 text-amber-400 px-1.5 py-0.5 rounded-full">Atrasado</span>}
                          <span className="text-sm text-emerald-400 numeric">{fmtBRL(p.total_amount)}</span>
                          <span className={`text-xs font-medium ${statusColor(p.status)}`}>{STATUS_LABEL[p.status] || p.status}</span>
                        </div>
                      </button>
                      {expandido === p.id && (
                        <div className="border-t border-neutral-800 p-3 space-y-3">
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                            <div>
                              <p className="text-neutral-500 uppercase tracking-wider text-[10px] mb-1">Cliente & entrega</p>
                              <p className="text-neutral-300 font-medium">{nomeCliente(p)}</p>
                              {!mascarado(p.recipient_nome) && !mascarado(p.buyer_username) && (
                                <p className="text-neutral-500">Usuário Shopee: @{p.buyer_username}</p>
                              )}
                              {mascarado(p.recipient_telefone) && mascarado(p.recipient_endereco) ? (
                                <p className="text-neutral-600 italic mt-1">Endereço protegido pela Shopee (não disponível via API)</p>
                              ) : (
                                <>
                                  <p className="text-neutral-400">{p.recipient_telefone || "—"}</p>
                                  <p className="text-neutral-400">{p.recipient_endereco || "—"}</p>
                                  <p className="text-neutral-400">
                                    {[p.recipient_cidade, p.recipient_estado, p.recipient_cep].filter(Boolean).join(" · ") || "—"}
                                  </p>
                                </>
                              )}
                            </div>
                            <div>
                              <p className="text-neutral-500 uppercase tracking-wider text-[10px] mb-1">Pagamento & prazo</p>
                              <p className="text-neutral-300">{p.forma_pagamento || "Não informado"}</p>
                              <p className="text-neutral-400">Prazo de envio: {formatarData(p.prazo_envio)}</p>
                              {p.observacao && <p className="text-neutral-400 mt-1">Obs: {p.observacao}</p>}
                            </div>
                          </div>
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
                              {p.itens.map((item) => (
                                <tr key={item.id} className="border-t border-neutral-800/50">
                                  <td className="py-1 text-neutral-400 font-mono">{item.sku}</td>
                                  <td className="py-1 text-neutral-300">{item.nome}</td>
                                  <td className="py-1 text-right text-neutral-300 numeric">{item.quantidade}</td>
                                  <td className="py-1 text-right text-neutral-300 numeric">{fmtBRL(item.preco)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          <PainelFulfillment orderSn={p.order_sn} lojaId={Number(lojaId)} />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {totalPaginas > 1 && (
                <div className="flex items-center justify-center gap-3 text-xs text-neutral-500">
                  <button
                    onClick={() => setPagina(p => Math.max(1, p - 1))}
                    disabled={pagina <= 1}
                    className="px-3 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 disabled:opacity-40 text-neutral-300"
                  >
                    Anterior
                  </button>
                  <span>Página {pagina} de {totalPaginas}</span>
                  <button
                    onClick={() => setPagina(p => Math.min(totalPaginas, p + 1))}
                    disabled={pagina >= totalPaginas}
                    className="px-3 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 disabled:opacity-40 text-neutral-300"
                  >
                    Próxima
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
