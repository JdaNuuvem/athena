"use client";

import { useState } from "react";

const SUB_TABS = [
  { id: "lotes", label: "Lotes" },
  { id: "series", label: "Séries" },
] as const;
type SubTabId = (typeof SUB_TABS)[number]["id"];

const lotesMock = [
  { lote: "L2025-0710A", fabricacao: "10/07/2025", validade: "10/07/2026", qtd: 500, status: "Ativo" },
  { lote: "L2025-0620B", fabricacao: "20/06/2025", validade: "20/06/2026", qtd: 320, status: "Ativo" },
  { lote: "L2025-0515C", fabricacao: "15/05/2025", validade: "15/05/2026", qtd: 0, status: "Esgotado" },
  { lote: "L2025-0301D", fabricacao: "01/03/2025", validade: "01/03/2026", qtd: 45, status: "Bloqueado" },
];

const seriesMock = [
  { serial: "SN-2025-00001", lote: "L2025-0710A", tipo: "SERIAL", status: "Disponível", entrada: "10/07/2025", saida: "—" },
  { serial: "SN-2025-00002", lote: "L2025-0710A", tipo: "SERIAL", status: "Vendido", entrada: "10/07/2025", saida: "12/07/2025" },
  { serial: "SN-2025-00003", lote: "L2025-0620B", tipo: "SERIAL", status: "Disponível", entrada: "20/06/2025", saida: "—" },
  { serial: "IMEI-35012345678901", lote: "L2025-0710A", tipo: "IMEI", status: "Garantia", entrada: "10/07/2025", saida: "11/07/2025" },
  { serial: "IMEI-35012345678902", lote: "L2025-0710A", tipo: "IMEI", status: "Disponível", entrada: "10/07/2025", saida: "—" },
];

function Badge({ label, color }: { label: string; color: string }) {
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${color}`}>{label}</span>;
}

function statusBadge(status: string) {
  const map: Record<string, string> = {
    Ativo: "bg-green-900/50 text-green-400",
    Esgotado: "bg-red-900/50 text-red-400",
    Bloqueado: "bg-yellow-900/50 text-yellow-400",
    Disponível: "bg-green-900/50 text-green-400",
    Vendido: "bg-neutral-700 text-neutral-400",
    Garantia: "bg-blue-900/50 text-blue-400",
  };
  return <Badge label={status} color={map[status] || "bg-neutral-700 text-neutral-400"} />;
}

function LotesPanel() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-neutral-300">Controle de Lotes</h3>
        <div className="flex gap-2">
          <input type="text" placeholder="Buscar lote..." className="bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-1.5 text-xs text-neutral-200 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-indigo-600" />
          <button className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1.5 rounded-lg transition-colors">+ Novo Lote</button>
        </div>
      </div>
      <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]">
          <thead>
            <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
              <th className="text-left p-3 font-medium">Nº Lote</th>
              <th className="text-left p-3 font-medium">Fabricação</th>
              <th className="text-left p-3 font-medium">Validade</th>
              <th className="text-right p-3 font-medium">Quantidade</th>
              <th className="text-center p-3 font-medium">Status</th>
              <th className="text-center p-3 font-medium">Ações</th>
            </tr>
          </thead>
          <tbody>
            {lotesMock.map((l) => (
              <tr key={l.lote} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                <td className="p-3 text-indigo-400 font-mono text-xs">{l.lote}</td>
                <td className="p-3 text-neutral-400 text-xs">{l.fabricacao}</td>
                <td className="p-3 text-neutral-400 text-xs">{l.validade}</td>
                <td className="p-3 text-right text-neutral-300 numeric">{l.qtd}</td>
                <td className="p-3 text-center">{statusBadge(l.status)}</td>
                <td className="p-3 text-center">
                  <button className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">Detalhes</button>
                  {l.status === "Ativo" && (
                    <>
                      <span className="text-neutral-600 mx-1">|</span>
                      <button className="text-xs text-red-400 hover:text-red-300 transition-colors">Bloquear</button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SeriesPanel() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-neutral-300">Controle de Séries</h3>
        <div className="flex gap-2">
          <input type="text" placeholder="Buscar serial..." className="bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-1.5 text-xs text-neutral-200 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-indigo-600" />
          <button className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1.5 rounded-lg transition-colors">+ Nova Série</button>
        </div>
      </div>
      <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]">
          <thead>
            <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
              <th className="text-left p-3 font-medium">Nº Série / IMEI</th>
              <th className="text-center p-3 font-medium">Tipo</th>
              <th className="text-left p-3 font-medium">Lote</th>
              <th className="text-center p-3 font-medium">Status</th>
              <th className="text-left p-3 font-medium">Entrada</th>
              <th className="text-left p-3 font-medium">Saída</th>
            </tr>
          </thead>
          <tbody>
            {seriesMock.map((s) => (
              <tr key={s.serial} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                <td className="p-3 text-indigo-400 font-mono text-xs">{s.serial}</td>
                <td className="p-3 text-center">
                  <Badge label={s.tipo} color={s.tipo === "IMEI" ? "bg-purple-900/50 text-purple-400" : "bg-neutral-700 text-neutral-400"} />
                </td>
                <td className="p-3 text-neutral-400 text-xs">{s.lote}</td>
                <td className="p-3 text-center">{statusBadge(s.status)}</td>
                <td className="p-3 text-neutral-400 text-xs">{s.entrada}</td>
                <td className="p-3 text-neutral-400 text-xs">{s.saida}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-neutral-600 text-right">{seriesMock.length} números de série</p>
    </div>
  );
}

const PANELS = {
  lotes: LotesPanel,
  series: SeriesPanel,
};

export default function LotesSeriesTab() {
  const [subTab, setSubTab] = useState<SubTabId>("lotes");
  const Panel = PANELS[subTab];

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {SUB_TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setSubTab(t.id)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              subTab === t.id
                ? "bg-indigo-600/20 text-indigo-300 border border-indigo-600/30"
                : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 border border-transparent"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <Panel />
    </div>
  );
}
