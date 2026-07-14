"use client";

import { useEffect, useState, useCallback } from "react";
import Spinner from "./shared/Spinner";
import Alert from "./shared/Alert";
import EmptyState from "./shared/EmptyState";
import { listarBlingPedidos, sincronizarBlingPedidos } from "@/lib/api";
import type { Pedido } from "@/lib/types/domain";
import { PEDIDO_SITUACOES, PEDIDO_SIT_COLORS } from "@/lib/types/domain";

export default function BlingOrdersTab() {
  const [pedidos, setPedidos] = useState<Pedido[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [pagina, setPagina] = useState(1);

  // Filtros
  const [busca, setBusca] = useState("");
  const [statusFilter, setStatusFilter] = useState<number>(0);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const carregar = useCallback(async (p = 1) => {
    try {
      setLoading(true);
      setErro(null);
      const r = await listarBlingPedidos(p, 100);
      if (r.error) throw new Error(String(r.error));
      setPedidos((r.data || []) as Pedido[]);
      setPagina(p);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar pedidos");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  const handleSync = async () => {
    try {
      setLoading(true);
      const r = await sincronizarBlingPedidos();
      setSucesso(`${r.sincronizados || 0} pedidos sincronizados`);
      carregar(pagina);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro na sincronização");
    } finally {
      setLoading(false);
    }
  };

  const situacaoId = (s: any) => (typeof s === "object" && s?.id) ? s.id : 0;

  const filtered = pedidos.filter((p) => {
    if (statusFilter && situacaoId(p.situacao) !== statusFilter) return false;
    if (!busca) return true;
    const term = busca.toLowerCase();
    return String(p.numero).includes(term) || (p.contato?.nome || "").toLowerCase().includes(term);
  });

  if (loading && pedidos.length === 0) return <Spinner />;

  return (
    <div className="space-y-4">
      <Alert message={erro} type="error" />
      <Alert message={sucesso} type="success" />

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <button onClick={handleSync} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500 transition-colors">
          🔄 Sincronizar
        </button>

        <input
          type="text"
          placeholder="Buscar por nº ou cliente..."
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="flex-1 min-w-[180px] bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500"
        />

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(Number(e.target.value))}
          className="bg-neutral-800 border border-neutral-700 rounded-lg px-2 py-1.5 text-xs text-neutral-200"
        >
          <option value={0}>Todos status</option>
          {Object.entries(PEDIDO_SITUACOES).map(([id, label]) => (
            <option key={id} value={id}>{label}</option>
          ))}
        </select>

        <span className="text-xs text-neutral-500 ml-auto">{filtered.length} pedidos</span>

        <button onClick={() => carregar(Math.max(1, pagina - 1))} disabled={pagina <= 1} className="px-2 py-1 bg-neutral-700 text-neutral-300 text-xs rounded disabled:opacity-40">←</button>
        <button onClick={() => carregar(pagina + 1)} disabled={pedidos.length < 100} className="px-2 py-1 bg-neutral-700 text-neutral-300 text-xs rounded disabled:opacity-40">→</button>
      </div>

      {/* Summary */}
      <div className="flex gap-3 text-xs text-neutral-400">
        <span>Total: <strong className="text-neutral-200">{filtered.length}</strong> pedidos</span>
        <span>| Receita: <strong className="text-emerald-400">R$ {filtered.reduce((s, p) => s + (p.total ?? 0), 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</strong></span>
      </div>

      {filtered.length === 0 ? (
        <EmptyState icon="📋" title={busca || statusFilter ? "Nenhum pedido encontrado" : "Nenhum pedido"} description={busca || statusFilter ? "Ajuste os filtros." : "Sincronize pedidos do Bling para começar."} action={!busca && !statusFilter ? { label: "Sincronizar Agora", onClick: handleSync } : undefined} />
      ) : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="text-left p-3 w-[80px]">Nº</th>
                <th className="text-left p-3">Cliente</th>
                <th className="text-left p-3 w-[90px]">Data</th>
                <th className="text-right p-3 w-[100px]">Total</th>
                <th className="text-center p-3 w-[100px]">Status</th>
                <th className="text-center p-3 w-[70px]">Detalhes</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((p, i) => {
                const sid = situacaoId(p.situacao);
                const isExpanded = expandedId === p.id;
                return (
                  <>
                    <tr key={p.id} className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"} ${isExpanded ? "!bg-neutral-750" : ""} cursor-pointer hover:bg-neutral-750`} onClick={() => setExpandedId(isExpanded ? null : p.id)}>
                      <td className="p-3 text-indigo-400 font-mono">{p.numero}</td>
                      <td className="p-3 text-neutral-200">
                        <div className="font-medium">{p.contato?.nome || "—"}</div>
                        {p.contato?.numeroDocumento && <div className="text-[10px] text-neutral-500">{p.contato.numeroDocumento}</div>}
                      </td>
                      <td className="p-3 text-neutral-400">
                        <div>{String(p.data ?? "—").slice(0, 10)}</div>
                        {p.dataSaida && <div className="text-[10px] text-neutral-500">🚚 {String(p.dataSaida).slice(0, 10)}</div>}
                      </td>
                      <td className="p-3 text-right">
                        <div className="text-emerald-400 font-medium">R$ {(p.total ?? 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</div>
                        {p.totalProdutos && <div className="text-[10px] text-neutral-500">itens: R$ {(p.totalProdutos ?? 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</div>}
                      </td>
                      <td className="p-3 text-center">
                        <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-medium ${PEDIDO_SIT_COLORS[sid] || "bg-neutral-700 text-neutral-400"}`}>
                          {PEDIDO_SITUACOES[sid] || `#${sid}`}
                        </span>
                      </td>
                      <td className="p-3 text-center">
                        <button
                          onClick={(e) => { e.stopPropagation(); setExpandedId(isExpanded ? null : p.id); }}
                          className="text-indigo-400 hover:text-indigo-300 text-lg leading-none"
                        >
                          {isExpanded ? "▲" : "▼"}
                        </button>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr key={`${p.id}-detail`} className="border-b border-neutral-700/50 bg-neutral-850">
                        <td colSpan={6} className="p-4">
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                            <div>
                              <h4 className="text-neutral-400 font-medium mb-2">Cliente</h4>
                              <p className="text-neutral-200">{p.contato?.nome || "—"}</p>
                              {p.contato?.numeroDocumento && <p className="text-neutral-500">CPF/CNPJ: {p.contato.numeroDocumento}</p>}
                              {p.contato?.tipoPessoa && <p className="text-neutral-500">Tipo: {p.contato.tipoPessoa === "F" ? "Física" : "Jurídica"}</p>}
                              <p className="text-neutral-500 mt-1">Loja: {p.loja?.id || "—"}</p>
                            </div>
                            <div>
                              <h4 className="text-neutral-400 font-medium mb-2">Datas</h4>
                              <p className="text-neutral-200">Emissão: {String(p.data ?? "—").slice(0, 10)}</p>
                              {p.dataSaida && <p className="text-neutral-200">Saída: {String(p.dataSaida).slice(0, 10)}</p>}
                            </div>
                            <div>
                              <h4 className="text-neutral-400 font-medium mb-2">Valores</h4>
                              <p className="text-emerald-400">Total: R$ {(p.total ?? 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</p>
                              {p.totalProdutos && <p className="text-neutral-200">Produtos: R$ {p.totalProdutos.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</p>}
                              <p className="text-neutral-500 mt-1">Status: {PEDIDO_SITUACOES[sid] || `#${sid}`}</p>
                            </div>
                          </div>
                          {p.itens && p.itens.length > 0 && (
                            <div className="mt-4">
                              <h4 className="text-neutral-400 font-medium mb-2 text-xs">Itens ({p.itens.length})</h4>
                              <div className="bg-neutral-900 rounded-lg overflow-hidden border border-neutral-700/50">
                                <table className="w-full text-[10px]">
                                  <thead>
                                    <tr className="border-b border-neutral-700 text-neutral-500">
                                      <th className="text-left p-2 font-medium">Código</th>
                                      <th className="text-left p-2 font-medium">Descrição</th>
                                      <th className="text-right p-2 font-medium">Qtd</th>
                                      <th className="text-right p-2 font-medium">Unit.</th>
                                      <th className="text-right p-2 font-medium">Total</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {p.itens.map((item, j) => (
                                      <tr key={j} className="border-b border-neutral-800/50 last:border-0">
                                        <td className="p-2 text-neutral-400 font-mono">{item.codigo}</td>
                                        <td className="p-2 text-neutral-300">{item.descricao || "—"}</td>
                                        <td className="p-2 text-right text-neutral-300">{item.quantidade}</td>
                                        <td className="p-2 text-right text-neutral-400">R$ {(item.valor ?? 0).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
                                        <td className="p-2 text-right text-emerald-400">R$ {((item.valor ?? 0) * (item.quantidade ?? 1)).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
