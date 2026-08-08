"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { fmtBRL as fmt, fmtDataBR } from "@/lib/format";
import ExportButtons from "@/app/_components/ExportButtons";

interface Boleto { id: number; beneficiario: string; valor: number; vencimento: string; nosso_numero: string; codigo_barras: string; status: string; }

export default function BoletosTab() {
  const [data, setData] = useState<Boleto[]>([]);
  const [loading, setLoading] = useState(true);
  const [criando, setCriando] = useState(false);
  const [novo, setNovo] = useState({ beneficiario: "", valor: "", vencimento: "", nosso_numero: "", codigo_barras: "" });
  const [erro, setErro] = useState("");

  const load = () => { api.finList("boletos").then((r) => setData((r.data || []) as Boleto[])).catch(() => {}).finally(() => setLoading(false)); };
  useEffect(() => { load(); }, []);

  const abrirCriar = () => {
    setNovo({ beneficiario: "", valor: "", vencimento: "", nosso_numero: "", codigo_barras: "" });
    setErro("");
    setCriando(true);
  };

  const confirmarCriar = async () => {
    if (!novo.beneficiario.trim() || !novo.valor || !novo.vencimento) { setErro("Beneficiário, valor e vencimento são obrigatórios"); return; }
    try {
      const r = await api.finCreate("boletos", {
        beneficiario: novo.beneficiario.trim(),
        valor: Number(novo.valor),
        vencimento: novo.vencimento,
        nosso_numero: novo.nosso_numero.trim(),
        codigo_barras: novo.codigo_barras.trim(),
      });
      if ((r as { error?: string }).error) { setErro((r as { error?: string }).error || "Erro ao criar"); return; }
      setCriando(false);
      load();
    } catch {
      setErro("Erro ao criar boleto");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <button onClick={abrirCriar} className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs px-3 py-1.5 rounded-lg transition-colors">+ Novo Boleto</button>
        <ExportButtons
          columns={["Beneficiário", "Valor", "Vencimento", "Nosso Número", "Status"]}
          rows={data.map(b => [b.beneficiario, fmt(b.valor), b.vencimento ? fmtDataBR(b.vencimento) : "—", b.nosso_numero, b.status])}
          filename="boletos" title="Boletos"
        />
      </div>
      {loading ? <p className="text-xs text-neutral-500">Carregando...</p> : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 text-left">
                <th className="px-4 py-2 font-medium">Beneficiário</th>
                <th className="px-4 py-2 font-medium">Valor</th>
                <th className="px-4 py-2 font-medium">Vencimento</th>
                <th className="px-4 py-2 font-medium">Nosso Número</th>
                <th className="px-4 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.map((b) => {
                const sc = b.status === "pago" ? "bg-emerald-500/20 text-emerald-400" : b.status === "vencido" ? "bg-red-500/20 text-red-400" : "bg-amber-500/20 text-amber-400";
                return (
                  <tr key={b.id} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300">
                    <td className="px-4 py-2.5">{b.beneficiario}</td>
                    <td className="px-4 py-2.5">{fmt(b.valor)}</td>
                    <td className="px-4 py-2.5">{b.vencimento ? new Date(b.vencimento + "T00:00:00").toLocaleDateString("pt-BR") : "—"}</td>
                    <td className="px-4 py-2.5 text-neutral-400">{b.nosso_numero}</td>
                    <td className="px-4 py-2.5"><span className={`px-2 py-0.5 rounded text-[10px] ${sc}`}>{b.status}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {criando && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setCriando(false)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-96" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-neutral-200 mb-3">Novo Boleto</h3>
            {erro && <div className="text-red-400 text-xs bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2 mb-3">{erro}</div>}
            <div className="space-y-2">
              <input value={novo.beneficiario} onChange={e => setNovo({ ...novo, beneficiario: e.target.value })}
                placeholder="Beneficiário" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input type="number" step="0.01" value={novo.valor} onChange={e => setNovo({ ...novo, valor: e.target.value })}
                placeholder="Valor" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input type="date" value={novo.vencimento} onChange={e => setNovo({ ...novo, vencimento: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input value={novo.nosso_numero} onChange={e => setNovo({ ...novo, nosso_numero: e.target.value })}
                placeholder="Nosso número" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
              <input value={novo.codigo_barras} onChange={e => setNovo({ ...novo, codigo_barras: e.target.value })}
                placeholder="Código de barras" className="w-full bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200" />
            </div>
            <div className="flex gap-2 mt-4">
              <button onClick={() => setCriando(false)} className="flex-1 py-2 text-sm text-neutral-400">Cancelar</button>
              <button onClick={confirmarCriar} className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg">Criar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
