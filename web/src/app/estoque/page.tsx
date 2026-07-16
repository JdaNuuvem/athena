"use client";

import { useState, useEffect, useCallback } from "react";
import { Can } from "@/lib/auth";

interface LojaItem { id: number; nome: string; ativa: boolean; }
interface EstoqueRow { id: number; sku: string; nome: string; loja: string; quantidade: number; imagem_url: string; situacao: string; data_atualizacao: string; }

export default function EstoquePage() {
  const [rows, setRows] = useState<EstoqueRow[]>([]);
  const [lojas, setLojas] = useState<LojaItem[]>([]);
  const [lojaSel, setLojaSel] = useState("");
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);

  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState(1);
  const [total, setTotal] = useState(0);

  const [grupos, setGrupos] = useState<any[]>([]);
  const [avulsos, setAvulsos] = useState<any[]>([]);
  const [expandedG, setExpandedG] = useState<Set<number>>(new Set());
  const [viewMode, setViewMode] = useState<"agrupado" | "flat">("flat");

  // Modal state
  const [modalRow, setModalRow] = useState<EstoqueRow | null>(null);
  const [modalTipo, setModalTipo] = useState<"editar" | "transferir" | "entrada" | "saida">("editar");
  const [transferDestino, setTransferDestino] = useState("");
  const [transferOrigem, setTransferOrigem] = useState("");

  const carregarLojas = useCallback(async () => {
    try {
      const r = await fetch("/api/lojas/manage");
      const d = await r.json();
      const list: LojaItem[] = d.lojas || [];
      setLojas(list);
      if (!lojaSel && list.length > 0) setLojaSel(String(list[0].id));
    } catch { /* silencioso */ }
  }, []);

  const carregarEstoque = useCallback(async (p: number = 1) => {
    if (!lojaSel) return;
    try {
      setLoading(true); setErro(null);
      const params = new URLSearchParams({ loja: lojaSel, pagina: String(p), por_pagina: "50" });
      if (busca) params.set("busca", busca);
      const r = await fetch(`/api/estoque/lojas?${params}`);
      const d = await r.json();
      setRows(d.estoque || []);
      setTotal(d.total || 0);
      setPagina(p);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar");
    } finally { setLoading(false); }
  }, [lojaSel, busca]);

  const carregarAgrupados = useCallback(async () => {
    try {
      const r = await fetch("/api/bling/produtos/agrupados?limite=100");
      if (r.ok) {
        const d = await r.json();
        setGrupos(d.grupos || []);
        setAvulsos(d.avulsos || []);
      }
    } catch { /* silencioso */ }
  }, []);

  useEffect(() => { carregarLojas(); carregarAgrupados(); }, []);
  useEffect(() => { if (lojaSel) carregarEstoque(1); }, [lojaSel, busca]);

  const handleEntrada = async (sku: string, qtd: number, motivo: string) => {
    const lojaNome = lojas.find(l => String(l.id) === lojaSel)?.nome || lojaSel;
    const r = await fetch("/api/estoque/entrada", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sku, loja: lojaNome, quantidade: qtd, motivo }),
    });
    const d = await r.json();
    if (d.erro) { setErro(d.erro); return false; }
    setSucesso(`+${qtd} ${sku} → ${lojaNome}`);
    carregarEstoque(pagina);
    return true;
  };

  const handleSaida = async (sku: string, qtd: number, motivo: string) => {
    const lojaNome = lojas.find(l => String(l.id) === lojaSel)?.nome || lojaSel;
    const r = await fetch("/api/estoque/saida", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sku, loja: lojaNome, quantidade: qtd, motivo }),
    });
    const d = await r.json();
    if (d.erro) { setErro(d.erro); return false; }
    setSucesso(`-${qtd} ${sku} ← ${lojaNome}`);
    carregarEstoque(pagina);
    return true;
  };

  const handleTransferir = async (sku: string, origem: string, destino: string, qtd: number, motivo: string) => {
    const r = await fetch("/api/estoque/transferir", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sku, origem, destino, quantidade: qtd, motivo }),
    });
    const d = await r.json();
    if (d.erro) { setErro(d.erro); return false; }
    setSucesso(`${qtd} ${sku}: ${origem} → ${destino}`);
    carregarEstoque(pagina);
    return true;
  };

  const handleSyncBling = async () => {
    try {
      setErro(null);
      const r = await fetch("/api/lojas/sync/bling", { method: "POST" });
      const d = await r.json();
      if (d.error) { setErro(d.error); return; }
      setSucesso(`Bling sincronizado: ${d.sync || 0} lojas`);
      carregarLojas();
      carregarEstoque(1);
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro"); }
  };

  const sc = (q: number) => q <= 0 ? "text-red-400" : q < 10 ? "text-yellow-400" : "text-emerald-400";

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-neutral-100">Estoque por Loja</h1>
          <p className="text-xs text-neutral-500 mt-1">
            {lojaSel ? `${rows.length} produtos &middot; ${total} total` : "Selecione uma loja"}
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => carregarEstoque(pagina)} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">Atualizar</button>
          <Can permission="inventory:edit">
            <button onClick={handleSyncBling} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">Sincronizar Bling</button>
          </Can>
        </div>
      </div>

      {erro && <div className="bg-red-900/30 border border-red-800 text-red-400 text-xs px-3 py-2 rounded-lg flex items-center justify-between"><span>{erro}</span><button onClick={() => setErro(null)} className="text-red-300 ml-2">X</button></div>}
      {sucesso && <div className="bg-emerald-900/30 border border-emerald-800 text-emerald-400 text-xs px-3 py-2 rounded-lg flex items-center justify-between"><span>{sucesso}</span><button onClick={() => setSucesso(null)} className="text-emerald-300 ml-2">X</button></div>}

      {/* Store selector */}
      <div className="flex items-center gap-3 bg-neutral-800 border border-neutral-700 rounded-lg p-3">
        <span className="text-xs font-medium text-neutral-300">Loja / Depósito:</span>
        <select value={lojaSel} onChange={e => { setLojaSel(e.target.value); setPagina(1); }}
          className="bg-neutral-700 border border-neutral-600 rounded-lg px-3 py-1.5 text-xs text-neutral-200 focus:outline-none focus:border-indigo-500 min-w-[200px]">
          <option value="">-- Selecionar --</option>
          {lojas.map(l => <option key={l.id} value={String(l.id)}>{l.nome}{!l.ativa ? " (inativa)" : ""}</option>)}
        </select>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <input type="text" value={busca} onChange={e => { setBusca(e.target.value); setPagina(1); }}
          placeholder="Buscar SKU ou nome..." className="flex-1 min-w-[200px] bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500" />
        <span className="text-xs text-neutral-500 py-1.5">{rows.length} resultados</span>
      </div>

      {/* View mode toggle */}
      <div className="flex items-center gap-2">
        <button onClick={() => setViewMode("flat")} className={"px-3 py-1 text-xs rounded-lg " + (viewMode === "flat" ? "bg-indigo-600 text-white" : "bg-neutral-700 text-neutral-400")}>Lista Simples</button>
        <button onClick={() => setViewMode("agrupado")} className={"px-3 py-1 text-xs rounded-lg " + (viewMode === "agrupado" ? "bg-indigo-600 text-white" : "bg-neutral-700 text-neutral-400")}>Agrupado (variações)</button>
      </div>

      {/* Flat view */}
      {viewMode === "flat" && (
        <>
          {loading ? <div className="text-neutral-500 text-sm py-8 text-center">Carregando estoque...</div> : !lojaSel ? (
            <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center"><p className="text-neutral-400 text-sm">Selecione uma loja acima</p></div>
          ) : rows.length === 0 ? (
            <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center"><p className="text-neutral-400 text-sm">Nenhum produto em estoque nesta loja</p></div>
          ) : (
            <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                    <th className="text-left p-2">SKU</th>
                    <th className="text-left p-2">Nome</th>
                    <th className="text-right p-2 w-24">Quantidade</th>
                    <th className="text-center p-2 w-20">Status</th>
                    <th className="text-right p-2 w-28">Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={r.id} className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}>
                      <td className="p-2 text-neutral-200 font-mono text-[11px]">{r.sku}</td>
                      <td className="p-2 text-neutral-200 max-w-[200px] truncate" title={r.nome}>{r.nome}</td>
                      <td className={`p-2 text-right font-bold font-mono ${sc(r.quantidade)}`}>{r.quantidade}</td>
                      <td className="p-2 text-center">
                        <span className={`px-1.5 py-0.5 rounded text-[9px] ${r.situacao === "A" ? "bg-emerald-900/30 text-emerald-400" : "bg-neutral-700 text-neutral-400"}`}>{r.situacao === "A" ? "Ativo" : "Inativo"}</span>
                      </td>
                      <td className="p-1.5 text-right">
                        <div className="flex items-center gap-1 justify-end">
                          <button onClick={() => { setModalRow(r); setModalTipo("editar"); }}
                            className="px-2 py-0.5 bg-neutral-700 text-neutral-300 text-[10px] rounded hover:bg-neutral-600" title="Editar">Editar</button>
                          <button onClick={() => { setModalRow(r); setModalTipo("transferir"); setTransferOrigem(r.loja); setTransferDestino(""); }}
                            className="px-2 py-0.5 bg-neutral-700 text-neutral-300 text-[10px] rounded hover:bg-neutral-600" title="Transferir">Transferir</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* Grouped view */}
      {viewMode === "agrupado" && (
        <div className="space-y-3">
          {grupos.map((g: any, gi: number) => {
            const isExpanded = expandedG.has(gi);
            const pai = g.pai || g;
            const filhos: any[] = g.filhos || g.variacoes || [];
            const totalFilhos = filhos.reduce((s: number, f: any) => s + (f.estoque?.saldoVirtualTotal ?? 0), 0);
            const paiId = pai.id || gi;
            return (
              <div key={gi} className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
                <div className="flex items-center px-3 py-2 cursor-pointer hover:bg-neutral-750" onClick={() => { const s = new Set(expandedG); s.has(gi) ? s.delete(gi) : s.add(gi); setExpandedG(s); }}>
                  <span className="text-neutral-400 text-xs mr-2">{isExpanded ? "▼" : "▶"}</span>
                  {pai.imagemURL ? <img src={pai.imagemURL} alt="" className="w-8 h-8 object-cover rounded mr-3" /> : <div className="w-8 h-8 rounded bg-neutral-700 mr-3 flex items-center justify-center text-[8px] text-neutral-500">IMG</div>}
                  <div className="flex-1">
                    <span className="text-sm font-semibold text-neutral-200">{pai.nome || pai.codigo || "Produto " + paiId}</span>
                    <span className="text-xs text-neutral-500 ml-2">{filhos.length} variações</span>
                  </div>
                  <div className="text-right"><span className="text-xs text-neutral-400">{totalFilhos} total</span></div>
                </div>
                {isExpanded && (
                  <div className="border-t border-neutral-700">
                    <table className="w-full text-xs">
                      <thead><tr className="text-neutral-500 border-b border-neutral-700/50"><th className="text-left p-2 pl-10">SKU</th><th className="text-left p-2">Variação</th><th className="text-right p-2">Estoque</th><th className="text-center p-2">Status</th></tr></thead>
                      <tbody>
                        {filhos.map((f: any, fi: number) => (
                          <tr key={fi} className={"border-b border-neutral-700/30 " + (fi % 2 === 0 ? "bg-neutral-800/50" : "")}>
                            <td className="p-2 pl-10 text-neutral-300 font-mono text-[11px]">{f.codigo}</td>
                            <td className="p-2 text-neutral-400 text-[11px]">{f.nome?.replace(pai.nome || "", "").trim() || f.codigo}</td>
                            <td className="p-2 text-right text-neutral-300">{f.estoque?.saldoVirtualTotal ?? "—"}</td>
                            <td className="p-2 text-center"><span className={"px-1.5 py-0.5 rounded text-[9px] " + (f.situacao === "A" ? "bg-emerald-900/30 text-emerald-400" : "bg-neutral-700 text-neutral-400")}>{f.situacao === "A" ? "Ativo" : "Inativo"}</span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            );
          })}
          {avulsos.length > 0 && (
            <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-3">
              <h3 className="text-xs font-semibold text-neutral-400 mb-2">Produtos sem variação ({avulsos.length})</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {avulsos.map((a: any, ai: number) => (
                  <div key={ai} className="flex items-center gap-2 bg-neutral-750 rounded px-2 py-1.5">
                    {a.imagemURL ? <img src={a.imagemURL} alt="" className="w-6 h-6 rounded" /> : <div className="w-6 h-6 rounded bg-neutral-700" />}
                    <div className="min-w-0"><div className="text-[10px] text-neutral-300 truncate">{a.nome || a.codigo}</div></div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Modal */}
      {modalRow && (
        <StockModal
          row={modalRow}
          tipo={modalTipo}
          lojas={lojas}
          lojaAtual={lojaSel}
          transferOrigem={transferOrigem}
          transferDestino={transferDestino}
          setTransferDestino={setTransferDestino}
          onClose={() => setModalRow(null)}
          onEntrada={handleEntrada}
          onSaida={handleSaida}
          onTransferir={(orig, dest, qtd, motivo) => handleTransferir(modalRow.sku, orig, dest, qtd, motivo)}
        />
      )}
    </div>
  );
}

function StockModal({ row, tipo, lojas, lojaAtual, transferOrigem, transferDestino, setTransferDestino, onClose, onEntrada, onSaida, onTransferir }: {
  row: EstoqueRow; tipo: string; lojas: LojaItem[]; lojaAtual: string;
  transferOrigem: string; transferDestino: string;
  setTransferDestino: (v: string) => void;
  onClose: () => void;
  onEntrada: (sku: string, qtd: number, motivo: string) => Promise<boolean>;
  onSaida: (sku: string, qtd: number, motivo: string) => Promise<boolean>;
  onTransferir: (origem: string, destino: string, qtd: number, motivo: string) => Promise<boolean>;
}) {
  const [qtd, setQtd] = useState(0);
  const [motivo, setMotivo] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const lojaNome = lojas.find(l => String(l.id) === lojaAtual)?.nome || lojaAtual;

  const handleSubmit = async () => {
    if (qtd <= 0) { setMsg("Quantidade deve ser > 0"); return; }
    setSaving(true); setMsg("");
    let ok = false;
    if (tipo === "entrada") ok = await onEntrada(row.sku, qtd, motivo);
    else if (tipo === "saida") ok = await onSaida(row.sku, qtd, motivo);
    else if (tipo === "transferir") {
      if (!transferDestino) { setMsg("Selecione o destino"); setSaving(false); return; }
      ok = await onTransferir(transferOrigem, transferDestino, qtd, motivo);
    }
    setSaving(false);
    if (ok) onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-neutral-850 border border-neutral-700 rounded-xl w-full max-w-sm mx-4 shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between p-3 border-b border-neutral-700">
          <div><h3 className="text-sm font-semibold text-neutral-100">{row.sku}</h3><p className="text-[10px] text-neutral-500">{row.nome}</p></div>
          <button onClick={onClose} className="text-neutral-500 hover:text-neutral-300">✕</button>
        </div>
        <div className="p-3 space-y-3">
          {msg && <div className="bg-red-900/30 text-red-400 text-[10px] px-2 py-1 rounded">{msg}</div>}
          <div className="bg-neutral-800 rounded px-3 py-2 flex items-center justify-between">
            <span className="text-xs text-neutral-400">Estoque atual ({row.loja})</span>
            <span className="text-sm font-bold font-mono text-emerald-400">{row.quantidade}</span>
          </div>

          {tipo === "transferir" ? (
            <>
              <div>
                <span className="text-[10px] text-neutral-500">Origem</span>
                <div className="bg-neutral-700 rounded px-3 py-1.5 text-xs text-neutral-300">{transferOrigem}</div>
              </div>
              <div>
                <span className="text-[10px] text-neutral-500">Destino</span>
                <select value={transferDestino} onChange={e => setTransferDestino(e.target.value)}
                  className="w-full bg-neutral-700 border border-neutral-600 rounded px-3 py-1.5 text-xs text-neutral-200 mt-0.5">
                  <option value="">-- Selecionar --</option>
                  {lojas.filter(l => l.nome !== transferOrigem && l.ativa).map(l => <option key={l.id} value={l.nome}>{l.nome}</option>)}
                </select>
              </div>
            </>
          ) : (
            <div className="bg-neutral-800 rounded px-3 py-2">
              <span className="text-[10px] text-neutral-500">{tipo === "entrada" ? "Loja destino" : "Loja origem"}</span>
              <div className="text-xs text-neutral-300">{lojaNome}</div>
            </div>
          )}

          <div>
            <span className="text-[10px] text-neutral-500">Quantidade</span>
            <input type="number" value={qtd || ""} onChange={e => setQtd(Number(e.target.value))} min={1}
              className="w-full bg-neutral-800 border border-neutral-600 rounded px-3 py-1.5 text-xs text-neutral-200 mt-0.5 focus:outline-none focus:border-indigo-500"
              placeholder="0" autoFocus />
          </div>

          <div>
            <span className="text-[10px] text-neutral-500">Motivo (opcional)</span>
            <input type="text" value={motivo} onChange={e => setMotivo(e.target.value)}
              className="w-full bg-neutral-800 border border-neutral-600 rounded px-3 py-1.5 text-xs text-neutral-200 mt-0.5 focus:outline-none focus:border-indigo-500"
              placeholder="ex: reposição, venda..." />
          </div>

          <div className="flex gap-2 pt-2">
            <Can permission="inventory:edit">
              <button onClick={handleSubmit} disabled={saving}
                className={"flex-1 py-2 text-xs rounded-lg text-white " + (tipo === "saida" ? "bg-red-600 hover:bg-red-500" : tipo === "transferir" ? "bg-amber-600 hover:bg-amber-500" : "bg-emerald-600 hover:bg-emerald-500")}>
                {saving ? "Salvando..." : tipo === "entrada" ? "Registrar Entrada" : tipo === "saida" ? "Registrar Saída" : "Transferir"}
              </button>
            </Can>
          </div>

          {/* Quick action buttons */}
          <div className="flex items-center gap-1 pt-1 border-t border-neutral-700">
            <Can permission="inventory:edit">
              <button onClick={() => onEntrada(row.sku, 1, "entrada rapida").then(ok => ok && onClose())}
                className="flex-1 py-1.5 bg-emerald-900/30 text-emerald-400 text-[10px] rounded hover:bg-emerald-900/50">+1 Entrada</button>
              <button onClick={() => onSaida(row.sku, 1, "saida rapida").then(ok => ok && onClose())}
                className="flex-1 py-1.5 bg-red-900/30 text-red-400 text-[10px] rounded hover:bg-red-900/50">-1 Saída</button>
            </Can>
          </div>
        </div>
      </div>
    </div>
  );
}
