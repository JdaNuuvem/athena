"use client";

import { useState, useEffect, useCallback, useMemo } from "react";

interface MovRow {
  id: number; sku: string; loja: string; tipo: string;
  quantidade: number; loja_relacionada: string | null;
  motivo: string | null; data: string; produto_nome: string;
}

const TIPO_LABELS: Record<string, string> = {
  entrada: "Entrada", saida: "Saída",
  transferencia_origem: "Transf. (origem)", transferencia_destino: "Transf. (destino)",
};

export default function MovimentacoesPage() {
  const [rows, setRows] = useState<MovRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [tab, setTab] = useState("todos");
  const [busca, setBusca] = useState("");

  const carregar = useCallback(async () => {
    try {
      setLoading(true); setErro(null);
      const r = await fetch("/api/estoque/movimentacoes?limite=200");
      const d = await r.json();
      setRows(d.movimentacoes || []);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  const filtered = useMemo(() => {
    let r = rows;
    if (tab !== "todos") r = r.filter(m => m.tipo === tab);
    if (busca) {
      const t = busca.toLowerCase();
      r = r.filter(m => m.sku.toLowerCase().includes(t) || m.produto_nome?.toLowerCase().includes(t)
        || m.loja?.toLowerCase().includes(t) || m.motivo?.toLowerCase().includes(t));
    }
    return r;
  }, [rows, tab, busca]);

  const tabTipos = useMemo(() => {
    const tipos = new Set(rows.map(r => r.tipo));
    return ["todos", ...Array.from(tipos)];
  }, [rows]);

  const entradasQtde = rows.filter(r => r.tipo === "entrada" || r.tipo === "transferencia_destino")
    .reduce((s, r) => s + Math.abs(r.quantidade), 0);
  const saidasQtde = rows.filter(r => r.tipo === "saida" || r.tipo === "transferencia_origem")
    .reduce((s, r) => s + Math.abs(r.quantidade), 0);

  const tipoColor = (t: string) => {
    if (t === "entrada" || t === "transferencia_destino") return "bg-emerald-900/30 text-emerald-400";
    if (t === "saida" || t === "transferencia_origem") return "bg-red-900/30 text-red-400";
    return "bg-neutral-700 text-neutral-400";
  };

  const qtdColor = (t: string, q: number) => {
    if (t === "entrada" || t === "transferencia_destino") return "text-emerald-400";
    if (t === "saida" || t === "transferencia_origem") return "text-red-400";
    return "text-neutral-300";
  };

  const formatDt = (s: string) => {
    if (!s) return "—";
    return s.slice(0, 16).replace("T", " ");
  };

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-neutral-100">Movimentações de Estoque</h1>
          <p className="text-xs text-neutral-500 mt-1">{rows.length} registros</p>
        </div>
        <button onClick={() => carregar()} className="px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500">Atualizar</button>
      </div>

      {erro && <div className="bg-red-900/30 border border-red-800 text-red-400 text-xs px-3 py-2 rounded-lg">{erro}</div>}

      {/* KPIs */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-3">
          <div className="text-[10px] text-neutral-500">Total Movimentações</div>
          <div className="text-lg font-bold text-neutral-100">{rows.length}</div>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-3">
          <div className="text-[10px] text-neutral-500">Entradas (qtd)</div>
          <div className="text-lg font-bold text-emerald-400">{entradasQtde}</div>
        </div>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-3">
          <div className="text-[10px] text-neutral-500">Saídas (qtd)</div>
          <div className="text-lg font-bold text-red-400">{saidasQtde}</div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Tabs */}
        <div className="flex items-center gap-1 flex-wrap">
          {tabTipos.map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-2.5 py-1 text-[10px] rounded-full border transition-colors ${tab === t ? "bg-indigo-600/30 border-indigo-500 text-indigo-300" : "border-neutral-600 text-neutral-500 hover:border-neutral-500"}`}>
              {t === "todos" ? "Todos" : TIPO_LABELS[t] || t}
            </button>
          ))}
        </div>
        <input type="text" value={busca} onChange={e => setBusca(e.target.value)}
          placeholder="Buscar SKU, produto, loja..." className="flex-1 min-w-[180px] bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500" />
        <span className="text-xs text-neutral-500">{filtered.length} resultados</span>
      </div>

      {/* Table */}
      {loading ? (
        <div className="text-neutral-500 text-sm py-8 text-center">Carregando...</div>
      ) : filtered.length === 0 ? (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center">
          <p className="text-neutral-400 text-sm">Nenhuma movimentação encontrada</p>
        </div>
      ) : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="text-left p-2">Data</th>
                <th className="text-left p-2">SKU</th>
                <th className="text-left p-2">Produto</th>
                <th className="text-center p-2 w-32">Tipo</th>
                <th className="text-right p-2 w-20">Qtd</th>
                <th className="text-left p-2">Loja</th>
                <th className="text-left p-2">Relacionada</th>
                <th className="text-left p-2">Motivo</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((m, i) => (
                <tr key={m.id} className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}>
                  <td className="p-2 text-neutral-400 text-[11px]">{formatDt(m.data)}</td>
                  <td className="p-2 text-neutral-200 font-mono text-[11px]">{m.sku}</td>
                  <td className="p-2 text-neutral-200 max-w-[160px] truncate" title={m.produto_nome}>{m.produto_nome || m.sku}</td>
                  <td className="p-1.5 text-center">
                    <span className={`inline-block px-2 py-0.5 rounded text-[9px] font-medium ${tipoColor(m.tipo)}`}>
                      {TIPO_LABELS[m.tipo] || m.tipo}
                    </span>
                  </td>
                  <td className={`p-2 text-right font-mono font-bold ${qtdColor(m.tipo, m.quantidade)}`}>
                    {(m.tipo === "entrada" || m.tipo === "transferencia_destino") ? "+" : ""}{m.quantidade}
                  </td>
                  <td className="p-2 text-neutral-400">{m.loja}</td>
                  <td className="p-2 text-neutral-500">{m.loja_relacionada || "—"}</td>
                  <td className="p-2 text-neutral-500 text-[10px] max-w-[120px] truncate" title={m.motivo || ""}>{m.motivo || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
