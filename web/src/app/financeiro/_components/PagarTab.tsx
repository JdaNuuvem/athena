"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { fmtBRL as fmt, fmtDataBR } from "@/lib/format";
import { AutorizacaoGerencial, type AutorizacaoGerencialValue } from "../../_components/AutorizacaoGerencial";
import ExportButtons from "@/app/_components/ExportButtons";

interface Conta { id: number; fornecedor: string; descricao: string; valor: number; vencimento: string; data_pagamento?: string; status: string; forma_pagamento: string; }

const AUTORIZACAO_VAZIA: AutorizacaoGerencialValue = { usuario_pin_id: null, pin: "", codigo_barras: "" };
const FORMAS = ["boleto", "pix", "ted", "dinheiro", "cartao"];

export default function PagarTab() {
  const [data, setData] = useState<Conta[]>([]);
  const [loading, setLoading] = useState(true);
  const [criando, setCriando] = useState(false);
  const [novaConta, setNovaConta] = useState({ fornecedor: "", descricao: "", valor: "", vencimento: "", forma_pagamento: "boleto" });
  const [erroCriar, setErroCriar] = useState("");

  const [pagando, setPagando] = useState<Conta | null>(null);
  const [formaPagamento, setFormaPagamento] = useState("boleto");
  const [autorizacao, setAutorizacao] = useState<AutorizacaoGerencialValue>(AUTORIZACAO_VAZIA);
  const [erroPagar, setErroPagar] = useState("");

  const load = () => { api.finList("contas_pagar").then((r) => setData((r.data || []) as Conta[])).catch(() => {}).finally(() => setLoading(false)); };
  useEffect(() => { load(); }, []);

  const abrirCriar = () => {
    setNovaConta({ fornecedor: "", descricao: "", valor: "", vencimento: "", forma_pagamento: "boleto" });
    setErroCriar("");
    setCriando(true);
  };

  const confirmarCriar = async () => {
    if (!novaConta.fornecedor.trim() || !novaConta.valor) { setErroCriar("Fornecedor e valor são obrigatórios"); return; }
    try {
      const r = await api.finCreate("contas_pagar", {
        fornecedor: novaConta.fornecedor.trim(),
        descricao: novaConta.descricao.trim(),
        valor: Number(novaConta.valor),
        vencimento: novaConta.vencimento || null,
        forma_pagamento: novaConta.forma_pagamento,
      });
      if ((r as { error?: string }).error) { setErroCriar((r as { error?: string }).error || "Erro ao criar"); return; }
      setCriando(false);
      load();
    } catch {
      setErroCriar("Erro ao criar conta");
    }
  };

  const abrirPagar = (c: Conta) => {
    setPagando(c);
    setFormaPagamento(c.forma_pagamento || "boleto");
    setAutorizacao(AUTORIZACAO_VAZIA);
    setErroPagar("");
  };

  const confirmarPagar = async () => {
    if (!pagando) return;
    try {
      const r = await api.finUpdate("contas_pagar", pagando.id, {
        status: "pago",
        forma_pagamento: formaPagamento,
        data_pagamento: new Date().toISOString().slice(0, 10),
        usuario_pin_id: autorizacao.usuario_pin_id,
        pin: autorizacao.pin,
        codigo_barras: autorizacao.codigo_barras,
      });
      if ((r as { error?: string }).error) { setErroPagar((r as { error?: string }).error || "Erro ao confirmar pagamento"); return; }
      setPagando(null);
      load();
    } catch {
      setErroPagar("Erro ao confirmar pagamento");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <button onClick={abrirCriar} className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">+ Nova Conta</button>
        <ExportButtons
          columns={["Fornecedor", "Descrição", "Valor", "Vencimento", "Forma Pag.", "Status"]}
          rows={data.map(c => [c.fornecedor, c.descricao, fmt(c.valor), c.vencimento ? fmtDataBR(c.vencimento) : "—", c.forma_pagamento, c.status])}
          filename="contas-pagar" title="Contas a Pagar"
        />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[{ label: "Total Pendente", v: data.filter(c => c.status !== "pago").reduce((s, c) => s + c.valor, 0), c: "text-amber-400" }, { label: "Total Pago", v: data.filter(c => c.status === "pago").reduce((s, c) => s + c.valor, 0), c: "text-emerald-400" }, { label: "Vencidas", v: data.filter(c => c.status !== "pago" && c.vencimento && new Date(c.vencimento) < new Date(new Date().toDateString())).length, c: "text-red-400" }, { label: "Total", v: data.length, c: "text-neutral-200" }].map((c) => (
          <div key={c.label} className="bg-neutral-800 border border-neutral-700 rounded-lg p-3"><p className="text-[10px] text-neutral-500">{c.label}</p><p className={`text-sm font-semibold mt-0.5 ${c.c}`}>{c.label === "Vencidas" || c.label === "Total" ? c.v : fmt(c.v)}</p></div>
        ))}</div>
      {loading ? <p className="text-xs text-neutral-500">Carregando...</p> : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden"><table className="w-full text-xs">
          <thead><tr className="border-b border-neutral-700 text-neutral-400 text-left"><th className="px-4 py-2 font-medium">Fornecedor</th><th className="px-4 py-2 font-medium">Descrição</th><th className="px-4 py-2 font-medium">Valor</th><th className="px-4 py-2 font-medium">Vencimento</th><th className="px-4 py-2 font-medium">Forma Pag.</th><th className="px-4 py-2 font-medium">Status</th><th className="px-4 py-2 font-medium"></th></tr></thead>
          <tbody>{data.map((c) => {
            const sc = c.status === "pago" ? "bg-emerald-500/20 text-emerald-400" : c.status === "atrasado" ? "bg-red-500/20 text-red-400" : "bg-amber-500/20 text-amber-400";
            return <tr key={c.id} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300"><td className="px-4 py-2.5">{c.fornecedor}</td><td className="px-4 py-2.5">{c.descricao}</td><td className="px-4 py-2.5">{fmt(c.valor)}</td><td className="px-4 py-2.5">{c.vencimento ? new Date(c.vencimento + "T00:00:00").toLocaleDateString("pt-BR") : "—"}</td><td className="px-4 py-2.5">{c.forma_pagamento}</td><td className="px-4 py-2.5"><span className={`px-2 py-0.5 rounded text-[10px] ${sc}`}>{c.status}</span></td>
              <td className="px-4 py-2.5">{c.status !== "pago" && <button onClick={() => abrirPagar(c)} className="text-indigo-400 hover:text-indigo-300 text-[11px]">Marcar como pago</button>}</td>
            </tr>;
          })}</tbody>
        </table></div>
      )}

      {criando && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setCriando(false)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-96" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Nova Conta a Pagar</h3>
            {erroCriar && <div className="text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2 mb-3">{erroCriar}</div>}
            <div className="space-y-2">
              <input value={novaConta.fornecedor} onChange={e => setNovaConta({ ...novaConta, fornecedor: e.target.value })}
                placeholder="Fornecedor" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input value={novaConta.descricao} onChange={e => setNovaConta({ ...novaConta, descricao: e.target.value })}
                placeholder="Descrição" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input type="number" step="0.01" value={novaConta.valor} onChange={e => setNovaConta({ ...novaConta, valor: e.target.value })}
                placeholder="Valor" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input type="date" value={novaConta.vencimento} onChange={e => setNovaConta({ ...novaConta, vencimento: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <select value={novaConta.forma_pagamento} onChange={e => setNovaConta({ ...novaConta, forma_pagamento: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200">
                {FORMAS.map(f => <option key={f} value={f}>{f}</option>)}
              </select>
            </div>
            <div className="flex gap-2 mt-4">
              <button onClick={() => setCriando(false)} className="flex-1 py-2 text-sm text-neutral-400">Cancelar</button>
              <button onClick={confirmarCriar} className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg">Criar</button>
            </div>
          </div>
        </div>
      )}

      {pagando && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setPagando(null)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-96" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-1">Confirmar Pagamento</h3>
            <p className="text-xs text-neutral-400 mb-3">{pagando.fornecedor} — {fmt(pagando.valor)}</p>
            {erroPagar && (
              <div className="text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2 mb-3">
                {erroPagar}
                {erroPagar.toLowerCase().includes("exige aprovacao") && (
                  <p className="mt-1 text-neutral-400">Pagamento acima do limite — peça autorização abaixo.</p>
                )}
              </div>
            )}
            <select value={formaPagamento} onChange={e => setFormaPagamento(e.target.value)}
              className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200 mb-3">
              {FORMAS.map(f => <option key={f} value={f}>{f}</option>)}
            </select>
            <div className="mb-3">
              <AutorizacaoGerencial permissao="financeiro.aprovar" onChange={setAutorizacao} />
            </div>
            <div className="flex gap-2">
              <button onClick={() => setPagando(null)} className="flex-1 py-2 text-sm text-neutral-400">Cancelar</button>
              <button onClick={confirmarPagar} className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg">Confirmar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
