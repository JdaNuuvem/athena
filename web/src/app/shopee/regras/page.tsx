"use client";

import { useState, useEffect } from "react";
import { fmtBRL } from "@/lib/format";

interface RegraPreco {
  id: number; nome: string; tipo: string;
  desconto_pct: number; markup_ajuste_pct: number;
  loja_id: number | null; dias_ativo: number | null;
  data_inicio: string | null; data_fim: string | null;
  condicao_estoque_dias: number | null;
  prioridade: number; ativo: boolean;
}

const TIPOS = [
  { value: "manual", label: "Manual (sempre ativo)" },
  { value: "sazonal", label: "Sazonal (por data)" },
  { value: "loja_nova", label: "Loja Nova (X dias)" },
  { value: "produto_parado", label: "Produto Parado (X dias)" },
  { value: "estoque_alto", label: "Estoque Alto (X dias)" },
];

interface AplicacaoDetalhe {
  sku: string; anuncio_id: string; loja: string;
  preco_base: number; preco_atual: number; preco_novo: number;
  regras_aplicadas: string[]; simulado?: boolean; erro?: string;
}
interface AplicacaoResultado {
  avaliados: number; atualizados: number; sem_mudanca: number; sem_preco_base: number;
  erros: AplicacaoDetalhe[]; detalhes: AplicacaoDetalhe[];
}

export default function RegrasPrecoPage() {
  const [regras, setRegras] = useState<RegraPreco[]>([]);
  const [lojas, setLojas] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<{ open: boolean; edit?: RegraPreco }>({ open: false });
  const [form, setForm] = useState({ nome: "", tipo: "manual", desconto_pct: 0, markup_ajuste_pct: 0, loja_id: "", dias_ativo: "", condicao_estoque_dias: "", data_inicio: "", data_fim: "", prioridade: 0 });

  const [lojaAplicar, setLojaAplicar] = useState("");
  const [aplicando, setAplicando] = useState(false);
  const [resultadoAplicacao, setResultadoAplicacao] = useState<AplicacaoResultado | null>(null);
  const [erroAplicacao, setErroAplicacao] = useState("");

  const lojasShopee = lojas.filter(l => l.shopee_shop_id || l.tipo === "virtual");

  const carregar = () => {
    fetch("/api/automacoes/regras_preco").then(r => r.json()).then(d => setRegras(d.data || [])).finally(() => setLoading(false));
    fetch("/api/lojas/manage").then(r => r.json()).then(d => setLojas(d.lojas || [])).catch(() => {});
  };
  useEffect(() => { carregar(); }, []);

  const salvar = async () => {
    const body: any = { ...form, desconto_pct: Number(form.desconto_pct), markup_ajuste_pct: Number(form.markup_ajuste_pct), prioridade: Number(form.prioridade), loja_id: form.loja_id ? Number(form.loja_id) : null, dias_ativo: form.dias_ativo ? Number(form.dias_ativo) : null, condicao_estoque_dias: form.condicao_estoque_dias ? Number(form.condicao_estoque_dias) : null, data_inicio: form.data_inicio || null, data_fim: form.data_fim || null };
    const url = modal.edit ? `/api/automacoes/regras_preco/${modal.edit.id}` : "/api/automacoes/regras_preco";
    await fetch(url, { method: modal.edit ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    setModal({ open: false }); carregar();
  };

  const aplicarRegras = async (dryRun: boolean) => {
    setAplicando(true);
    setErroAplicacao("");
    setResultadoAplicacao(null);
    try {
      const res = await fetch("/api/automacoes/regras_preco/aplicar", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ loja_id: lojaAplicar ? Number(lojaAplicar) : undefined, dry_run: dryRun }),
      });
      const texto = await res.text();
      let d: any;
      try { d = JSON.parse(texto); } catch { throw new Error(`Erro ${res.status} do servidor — resposta inesperada`); }
      if (d.erros?.length && !d.avaliados) { setErroAplicacao(d.erros[0]?.erro || "Erro ao aplicar regras"); return; }
      setResultadoAplicacao(d);
    } catch (e) {
      setErroAplicacao(e instanceof Error ? e.message : "Erro ao aplicar regras");
    } finally {
      setAplicando(false);
    }
  };

  const toggleAtivo = async (id: number, ativo: boolean) => {
    await fetch(`/api/automacoes/regras_preco/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ativo: !ativo }) });
    carregar();
  };

  const abrirNovo = () => { setForm({ nome: "", tipo: "manual", desconto_pct: 0, markup_ajuste_pct: 0, loja_id: "", dias_ativo: "", condicao_estoque_dias: "", data_inicio: "", data_fim: "", prioridade: 0 }); setModal({ open: true }); };
  const abrirEditar = (r: RegraPreco) => { setForm({ nome: r.nome, tipo: r.tipo, desconto_pct: r.desconto_pct, markup_ajuste_pct: r.markup_ajuste_pct, loja_id: r.loja_id ? String(r.loja_id) : "", dias_ativo: r.dias_ativo ? String(r.dias_ativo) : "", condicao_estoque_dias: r.condicao_estoque_dias ? String(r.condicao_estoque_dias) : "", data_inicio: r.data_inicio || "", data_fim: r.data_fim || "", prioridade: r.prioridade }); setModal({ open: true, edit: r }); };

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-lg font-bold text-neutral-100">Regras de Preço</h1>
          <p className="text-xs text-neutral-500 mt-1">Ajustes automáticos de markup e desconto — aplicados ao clonar um anúncio pra loja nova, e sob demanda no catálogo já publicado</p>
        </div>
        <button onClick={abrirNovo} className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm px-4 py-2 rounded-lg">+ Nova Regra</button>
      </div>

      <div className="instrument bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3">
        <div>
          <h2 className="text-sm font-medium text-neutral-200">Aplicar regras ao catálogo Shopee</h2>
          <p className="text-xs text-neutral-500 mt-0.5">
            Recalcula o preço de cada anúncio ativo a partir do preço-base do catálogo e envia pra Shopee de verdade quando ele mudou.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select value={lojaAplicar} onChange={e => setLojaAplicar(e.target.value)}
            className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200">
            <option value="">Todas as lojas Shopee</option>
            {lojasShopee.map(l => <option key={l.id} value={l.id}>{l.nome}</option>)}
          </select>
          <button onClick={() => aplicarRegras(true)} disabled={aplicando}
            className="bg-neutral-700 hover:bg-neutral-600 disabled:opacity-50 text-neutral-200 text-sm px-4 py-2 rounded-lg">
            {aplicando ? "Calculando..." : "Simular (não envia)"}
          </button>
          <button onClick={() => aplicarRegras(false)} disabled={aplicando}
            className="bg-teal-600 hover:bg-teal-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg">
            {aplicando ? "Aplicando..." : "Aplicar e enviar à Shopee"}
          </button>
        </div>

        {erroAplicacao && (
          <div className="text-xs px-3 py-2 rounded-lg border bg-red-950/40 border-red-900/50 text-red-400">{erroAplicacao}</div>
        )}

        {resultadoAplicacao && (
          <div className="space-y-2">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <div className="bg-neutral-800/50 rounded-lg p-2">
                <p className="text-[10px] text-neutral-500 uppercase tracking-wider">Avaliados</p>
                <p className="text-sm text-neutral-200 numeric font-medium">{resultadoAplicacao.avaliados}</p>
              </div>
              <div className="bg-neutral-800/50 rounded-lg p-2">
                <p className="text-[10px] text-neutral-500 uppercase tracking-wider">{resultadoAplicacao.detalhes.some(d => d.simulado) ? "Mudariam" : "Atualizados"}</p>
                <p className="text-sm text-emerald-400 numeric font-medium">{resultadoAplicacao.detalhes.length}</p>
              </div>
              <div className="bg-neutral-800/50 rounded-lg p-2">
                <p className="text-[10px] text-neutral-500 uppercase tracking-wider">Sem mudança</p>
                <p className="text-sm text-neutral-300 numeric font-medium">{resultadoAplicacao.sem_mudanca}</p>
              </div>
              <div className="bg-neutral-800/50 rounded-lg p-2">
                <p className="text-[10px] text-neutral-500 uppercase tracking-wider">Erros</p>
                <p className={`text-sm numeric font-medium ${resultadoAplicacao.erros.length > 0 ? "text-red-400" : "text-neutral-300"}`}>{resultadoAplicacao.erros.length}</p>
              </div>
            </div>
            {resultadoAplicacao.sem_preco_base > 0 && (
              <p className="text-[10px] text-amber-400">{resultadoAplicacao.sem_preco_base} anúncio(s) sem preço-base cadastrado (produtos_loja ou catálogo) — ignorados.</p>
            )}
            {resultadoAplicacao.detalhes.length > 0 && (
              <div className="max-h-48 overflow-y-auto border border-neutral-800 rounded-lg">
                <table className="w-full text-[11px]">
                  <thead><tr className="border-b border-neutral-800 text-neutral-500"><th className="text-left p-2">SKU</th><th className="text-left p-2">Loja</th><th className="text-right p-2">De</th><th className="text-right p-2">Para</th><th className="text-left p-2">Regras</th></tr></thead>
                  <tbody>
                    {resultadoAplicacao.detalhes.map((d, i) => (
                      <tr key={i} className="border-b border-neutral-800/50">
                        <td className="p-2 text-neutral-300 font-mono">{d.sku}</td>
                        <td className="p-2 text-neutral-400">{d.loja}</td>
                        <td className="p-2 text-right text-neutral-400 numeric">{fmtBRL(d.preco_atual)}</td>
                        <td className="p-2 text-right text-emerald-400 numeric">{fmtBRL(d.preco_novo)}</td>
                        <td className="p-2 text-neutral-500">{d.regras_aplicadas.join(", ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {resultadoAplicacao.erros.length > 0 && (
              <div className="text-[10px] text-red-400 space-y-0.5">
                {resultadoAplicacao.erros.slice(0, 5).map((e, i) => <p key={i}>{e.sku}: {e.erro}</p>)}
              </div>
            )}
          </div>
        )}
      </div>

      {loading ? <p className="text-neutral-500 text-sm">Carregando...</p> : regras.length === 0 ? (
        <p className="text-neutral-500 text-sm">Nenhuma regra cadastrada.</p>
      ) : (
        <div className="instrument-enter bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead><tr className="border-b border-neutral-800 text-neutral-500"><th className="text-left p-3">Nome</th><th className="text-left p-3">Tipo</th><th className="text-right p-3">Desconto</th><th className="text-right p-3">Markup</th><th className="text-left p-3">Loja</th><th className="text-center p-3">Ativo</th></tr></thead>
            <tbody>
              {regras.map(r => (
                <tr key={r.id} className="border-b border-neutral-800/50 hover:bg-neutral-800/30 cursor-pointer" onClick={() => abrirEditar(r)}>
                  <td className="p-3 text-neutral-200">{r.nome}</td>
                  <td className="p-3 text-neutral-400">{TIPOS.find(t => t.value === r.tipo)?.label || r.tipo}</td>
                  <td className="p-3 text-right text-red-400">{r.desconto_pct > 0 ? `-${r.desconto_pct}%` : "—"}</td>
                  <td className="p-3 text-right text-emerald-400">{r.markup_ajuste_pct > 0 ? `+${r.markup_ajuste_pct}%` : "—"}</td>
                  <td className="p-3 text-neutral-400">{r.loja_id ? lojas.find(l => l.id === r.loja_id)?.nome || `#${r.loja_id}` : "Todas"}</td>
                  <td className="p-3 text-center" onClick={e => e.stopPropagation()}>
                    <button onClick={() => toggleAtivo(r.id, r.ativo)} className={`text-[10px] px-2 py-0.5 rounded ${r.ativo ? "bg-emerald-900/30 text-emerald-400" : "bg-neutral-700 text-neutral-500"}`}>
                      {r.ativo ? "ON" : "OFF"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {modal.open && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setModal({ open: false })}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-[420px] max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-4">{modal.edit ? "Editar Regra" : "Nova Regra"}</h3>
            <div className="space-y-3 text-sm">
              <input type="text" value={form.nome} onChange={e => setForm(f => ({ ...f, nome: e.target.value }))} placeholder="Nome da regra" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-2 text-neutral-200" autoFocus />
              <select value={form.tipo} onChange={e => setForm(f => ({ ...f, tipo: e.target.value }))} className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-2 text-neutral-200">
                {TIPOS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs text-neutral-500">Desconto %</label>
                  <input type="number" value={form.desconto_pct} onChange={e => setForm(f => ({ ...f, desconto_pct: Number(e.target.value) }))} className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-neutral-200 text-right" min={0} max={100} />
                </div>
                <div>
                  <label className="text-xs text-neutral-500">Markup ajuste %</label>
                  <input type="number" value={form.markup_ajuste_pct} onChange={e => setForm(f => ({ ...f, markup_ajuste_pct: Number(e.target.value) }))} className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-neutral-200 text-right" min={-50} max={500} />
                </div>
              </div>
              {(form.tipo === "loja_nova") && (
                <div>
                  <label className="text-xs text-neutral-500">Aplicar nos primeiros (dias)</label>
                  <input type="number" value={form.dias_ativo} onChange={e => setForm(f => ({ ...f, dias_ativo: e.target.value }))} className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-neutral-200" placeholder="Ex: 30" />
                </div>
              )}
              {(form.tipo === "produto_parado" || form.tipo === "estoque_alto") && (
                <div>
                  <label className="text-xs text-neutral-500">Dias sem venda / parado</label>
                  <input type="number" value={form.condicao_estoque_dias} onChange={e => setForm(f => ({ ...f, condicao_estoque_dias: e.target.value }))} className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-neutral-200" placeholder="Ex: 30" />
                </div>
              )}
              {(form.tipo === "sazonal") && (
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs text-neutral-500">Data início</label>
                    <input type="date" value={form.data_inicio} onChange={e => setForm(f => ({ ...f, data_inicio: e.target.value }))} className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-neutral-200" />
                  </div>
                  <div>
                    <label className="text-xs text-neutral-500">Data fim</label>
                    <input type="date" value={form.data_fim} onChange={e => setForm(f => ({ ...f, data_fim: e.target.value }))} className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-neutral-200" />
                  </div>
                </div>
              )}
              <div>
                <label className="text-xs text-neutral-500">Loja (vazio = todas)</label>
                <select value={form.loja_id} onChange={e => setForm(f => ({ ...f, loja_id: e.target.value }))} className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-2 text-neutral-200">
                  <option value="">Todas as lojas</option>
                  {lojas.map(l => <option key={l.id} value={l.id}>{l.nome}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-neutral-500">Prioridade (maior = aplica primeiro)</label>
                <input type="number" value={form.prioridade} onChange={e => setForm(f => ({ ...f, prioridade: Number(e.target.value) }))} className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-neutral-200" />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button onClick={() => setModal({ open: false })} className="text-sm px-4 py-2 rounded-lg text-neutral-400 hover:text-neutral-200">Cancelar</button>
                <button onClick={salvar} disabled={!form.nome} className="text-sm px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white">Salvar</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
