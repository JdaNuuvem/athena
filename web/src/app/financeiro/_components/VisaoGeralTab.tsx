"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { fmtBRL, fmtDataBR } from "@/lib/format";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

interface Conta {
  id: number;
  cliente?: string;
  fornecedor?: string;
  descricao?: string;
  valor: number;
  vencimento: string;
  status: string;
}

interface FluxoDia { data: string; entradas: number; saidas: number; }

// Dashboard de visao geral do modulo Financeiro — consolida bancos+cofres,
// vencimentos proximos, fluxo de caixa e DRE do mes numa unica tela.
export default function VisaoGeralTab() {
  const [saldoBancos, setSaldoBancos] = useState(0);
  const [saldoCofres, setSaldoCofres] = useState(0);
  const [receberVencendo, setReceberVencendo] = useState<Conta[]>([]);
  const [pagarVencendo, setPagarVencendo] = useState<Conta[]>([]);
  const [atrasadas, setAtrasadas] = useState<{ receber: Conta[]; pagar: Conta[] }>({ receber: [], pagar: [] });
  const [fluxoDiario, setFluxoDiario] = useState<FluxoDia[]>([]);
  const [dre, setDre] = useState<{ receitas: number; despesas: number; resultado: number; lucro: boolean } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const [bancos, cofre, receber, pagar, fluxo, dreResp] = await Promise.all([
          api.finList("bancos"),
          api.cofreSaldoTotal(),
          api.finList("contas_receber"),
          api.finList("contas_pagar"),
          api.finFluxoResumo(30),
          api.finDREResumo(),
        ]);

        const bancosList = (bancos.data || []) as { saldo?: number }[];
        setSaldoBancos(bancosList.reduce((s, b) => s + (Number(b.saldo) || 0), 0));
        setSaldoCofres(cofre.saldo_total || 0);

        const hoje = new Date(); hoje.setHours(0, 0, 0, 0);
        const em7dias = new Date(hoje); em7dias.setDate(em7dias.getDate() + 7);

        const receberList = (receber.data || []) as Conta[];
        const pagarList = (pagar.data || []) as Conta[];

        setReceberVencendo(receberList.filter(c => c.status === "pendente" && c.vencimento && new Date(c.vencimento) >= hoje && new Date(c.vencimento) <= em7dias));
        setPagarVencendo(pagarList.filter(c => c.status === "pendente" && c.vencimento && new Date(c.vencimento) >= hoje && new Date(c.vencimento) <= em7dias));
        setAtrasadas({
          receber: receberList.filter(c => c.status !== "pago" && c.vencimento && new Date(c.vencimento) < hoje),
          pagar: pagarList.filter(c => c.status !== "pago" && c.vencimento && new Date(c.vencimento) < hoje),
        });

        const diario = (fluxo.diario || []) as { data: string; entradas: number; saidas: number }[];
        setFluxoDiario(diario.map(d => ({ data: fmtDataBR(d.data), entradas: Number(d.entradas) || 0, saidas: Number(d.saidas) || 0 })));
        setDre(dreResp);
      } catch { /* mantem estado zerado — telas individuais mostram o erro real */ }
      finally { setLoading(false); }
    })();
  }, []);

  if (loading) return <p className="text-xs text-neutral-500">Carregando...</p>;

  const saldoTotal = saldoBancos + saldoCofres;
  const totalReceberVencendo = receberVencendo.reduce((s, c) => s + Number(c.valor || 0), 0);
  const totalPagarVencendo = pagarVencendo.reduce((s, c) => s + Number(c.valor || 0), 0);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4">
          <p className="text-[10px] text-neutral-500">Saldo Total</p>
          <p className="mt-0.5 text-xl font-semibold text-emerald-400">{fmtBRL(saldoTotal)}</p>
          <p className="mt-1 text-[10px] text-neutral-500">Bancos {fmtBRL(saldoBancos)} + Cofres {fmtBRL(saldoCofres)}</p>
        </div>
        <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4">
          <p className="text-[10px] text-neutral-500">A Receber (7 dias)</p>
          <p className="mt-0.5 text-xl font-semibold text-neutral-100">{fmtBRL(totalReceberVencendo)}</p>
          <p className="mt-1 text-[10px] text-neutral-500">{receberVencendo.length} conta(s)</p>
        </div>
        <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4">
          <p className="text-[10px] text-neutral-500">A Pagar (7 dias)</p>
          <p className="mt-0.5 text-xl font-semibold text-neutral-100">{fmtBRL(totalPagarVencendo)}</p>
          <p className="mt-1 text-[10px] text-neutral-500">{pagarVencendo.length} conta(s)</p>
        </div>
        <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4">
          <p className="text-[10px] text-neutral-500">DRE do Mês</p>
          <p className={`mt-0.5 text-xl font-semibold ${dre?.lucro ? "text-emerald-400" : "text-red-400"}`}>{fmtBRL(dre?.resultado || 0)}</p>
          <p className="mt-1 text-[10px] text-neutral-500">{dre?.lucro ? "Lucro" : "Prejuízo"}</p>
        </div>
      </div>

      <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4">
        <p className="mb-3 text-xs font-semibold text-neutral-300">Fluxo de Caixa — Últimos 30 dias</p>
        {fluxoDiario.length === 0 ? (
          <p className="text-xs text-neutral-500">Sem lançamentos no período</p>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={fluxoDiario}>
              <CartesianGrid strokeDasharray="3 3" stroke="#404040" />
              <XAxis dataKey="data" tick={{ fontSize: 10, fill: "#a3a3a3" }} />
              <YAxis tick={{ fontSize: 10, fill: "#a3a3a3" }} />
              <Tooltip contentStyle={{ background: "#262626", border: "1px solid #404040", fontSize: 11 }} formatter={(v) => fmtBRL(Number(v) || 0)} />
              <Line type="monotone" dataKey="entradas" stroke="#34d399" strokeWidth={2} dot={false} name="Entradas" />
              <Line type="monotone" dataKey="saidas" stroke="#f87171" strokeWidth={2} dot={false} name="Saídas" />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {(atrasadas.receber.length > 0 || atrasadas.pagar.length > 0) && (
        <div className="rounded-xl border border-red-900/50 bg-red-950/20 p-4">
          <p className="mb-2 text-xs font-semibold text-red-400">Contas Atrasadas</p>
          <div className="space-y-1 text-xs text-neutral-300">
            {atrasadas.receber.map(c => (
              <div key={`r-${c.id}`} className="flex justify-between gap-2">
                <span className="truncate">Receber — {c.cliente || c.descricao}</span>
                <span className="shrink-0 text-red-400">{fmtBRL(c.valor)} · venceu {fmtDataBR(c.vencimento)}</span>
              </div>
            ))}
            {atrasadas.pagar.map(c => (
              <div key={`p-${c.id}`} className="flex justify-between gap-2">
                <span className="truncate">Pagar — {c.fornecedor || c.descricao}</span>
                <span className="shrink-0 text-red-400">{fmtBRL(c.valor)} · venceu {fmtDataBR(c.vencimento)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
