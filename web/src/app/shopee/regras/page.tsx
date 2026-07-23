"use client";

import { useState, useEffect } from "react";

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

export default function RegrasPrecoPage() {
  const [regras, setRegras] = useState<RegraPreco[]>([]);
  const [lojas, setLojas] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<{ open: boolean; edit?: RegraPreco }>({ open: false });
  const [form, setForm] = useState({ nome: "", tipo: "manual", desconto_pct: 0, markup_ajuste_pct: 0, loja_id: "", dias_ativo: "", condicao_estoque_dias: "", data_inicio: "", data_fim: "", prioridade: 0 });

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
          <p className="text-xs text-neutral-500 mt-1">Ajustes automáticos de markup e desconto aplicados na replicação</p>
        </div>
        <button onClick={abrirNovo} className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm px-4 py-2 rounded-lg">+ Nova Regra</button>
      </div>

      {loading ? <p className="text-neutral-500 text-sm">Carregando...</p> : regras.length === 0 ? (
        <p className="text-neutral-500 text-sm">Nenhuma regra cadastrada.</p>
      ) : (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden">
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
