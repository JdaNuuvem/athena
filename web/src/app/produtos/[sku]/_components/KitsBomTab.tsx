"use client";

import { useState } from "react";

const SUB_TABS = [
  { id: "kit", label: "Kit" },
  { id: "combo", label: "Combo" },
  { id: "producao", label: "Produção" },
  { id: "compostos", label: "Compostos" },
  { id: "bom", label: "BOM" },
] as const;
type SubTabId = (typeof SUB_TABS)[number]["id"];

const kitsMock = [
  { sku: "KIT-VERAO", nome: "Kit Verão", componentes: [{ sku: "MC-001", nome: "Organizador", qtd: 2 }, { sku: "MC-002", nome: "Garrafa Térmica", qtd: 1 }], precoKit: 89.90, estoque: 15 },
  { sku: "KIT-PRESENTE", nome: "Kit Presente", componentes: [{ sku: "MC-001", nome: "Organizador", qtd: 1 }, { sku: "MC-003", nome: "Porta Temperos", qtd: 1 }, { sku: "MC-004", nome: "Jogo de Copos", qtd: 1 }], precoKit: 119.90, estoque: 8 },
];

const combosMock = [
  { sku: "COMBO-LIMPEZA", nome: "Combo Limpeza", componentes: [{ sku: "MC-010", nome: "Kit Limpeza", qtd: 1 }, { sku: "MC-011", nome: "Pano Microfibra", qtd: 3 }], precoOriginal: 74.70, precoCombo: 59.90, estoque: 22 },
];

const producaoMock = [
  { sku: "MC-050-F", nome: "Peça Injetada (Final)", ops: ["Injeção", "Acabamento", "Pintura", "Embalagem"], tempoProducao: "45 min", loteMinimo: 100 },
];

const compostosMock = [
  { sku: "MC-100-PC", nome: "Kit Montado", usadoEm: [{ sku: "KIT-VERAO", nome: "Kit Verão", qtd: 2 }, { sku: "COMBO-LIMPEZA", nome: "Combo Limpeza", qtd: 1 }] },
];

const bomMock = [
  { nivel: 0, codigo: "MP-001", nome: "Polipropileno (PP)", qtd: 0.45, unidade: "kg", tipo: "MP" },
  { nivel: 1, codigo: "MP-002", nome: "Pigmento Branco", qtd: 0.005, unidade: "kg", tipo: "MP" },
  { nivel: 1, codigo: "EMB-001", nome: "Caixa Papelão 30x20x15", qtd: 1, unidade: "un", tipo: "EMB" },
  { nivel: 2, codigo: "ETQ-001", nome: "Etiqueta Adesiva", qtd: 1, unidade: "un", tipo: "MP" },
  { nivel: 2, codigo: "SAC-001", nome: "Saco Plástico PEBD", qtd: 1, unidade: "un", tipo: "EMB" },
];

function Badge({ label, color }: { label: string; color: string }) {
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${color}`}>{label}</span>;
}

function KitPanel() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-neutral-300">Kits Cadastrados</h3>
        <button className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1 rounded-lg transition-colors">+ Novo Kit</button>
      </div>
      {kitsMock.map((k) => (
        <div key={k.sku} className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-sm font-medium text-neutral-200">{k.nome}</span>
              <span className="text-xs text-neutral-500 ml-2 font-mono">{k.sku}</span>
            </div>
            <div className="text-right">
              <p className="text-sm text-neutral-200 numeric">R$ {k.precoKit.toFixed(2)}</p>
              <p className="text-xs text-neutral-500">Estoque: {k.estoque} un</p>
            </div>
          </div>
          <div className="border-t border-neutral-800 pt-2">
            <p className="text-[10px] text-neutral-500 uppercase tracking-wider mb-1">Componentes</p>
            {k.componentes.map((c) => (
              <div key={c.sku} className="flex items-center gap-2 text-xs text-neutral-400 py-0.5">
                <span className="text-neutral-600">{c.qtd}x</span>
                <span className="font-mono text-indigo-400">{c.sku}</span>
                <span>{c.nome}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function ComboPanel() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-neutral-300">Combos Cadastrados</h3>
        <button className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1 rounded-lg transition-colors">+ Novo Combo</button>
      </div>
      {combosMock.map((c) => (
        <div key={c.sku} className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-sm font-medium text-neutral-200">{c.nome}</span>
              <span className="text-xs text-neutral-500 ml-2 font-mono">{c.sku}</span>
            </div>
            <div className="text-right">
              <p className="text-xs text-neutral-500 line-through">R$ {c.precoOriginal.toFixed(2)}</p>
              <p className="text-sm text-green-400 numeric font-medium">R$ {c.precoCombo.toFixed(2)}</p>
            </div>
          </div>
          <div className="border-t border-neutral-800 pt-2">
            <p className="text-[10px] text-neutral-500 uppercase tracking-wider mb-1">Componentes</p>
            {c.componentes.map((comp) => (
              <div key={comp.sku} className="flex items-center gap-2 text-xs text-neutral-400 py-0.5">
                <span className="text-neutral-600">{comp.qtd}x</span>
                <span className="font-mono text-indigo-400">{comp.sku}</span>
                <span>{comp.nome}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function ProducaoPanel() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-neutral-300">Produtos de Produção</h3>
        <button className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1 rounded-lg transition-colors">+ Novo</button>
      </div>
      {producaoMock.map((p) => (
        <div key={p.sku} className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-sm font-medium text-neutral-200">{p.nome}</span>
              <span className="text-xs text-neutral-500 ml-2 font-mono">{p.sku}</span>
            </div>
            <div className="flex items-center gap-3 text-xs text-neutral-400">
              <span>Tempo: {p.tempoProducao}</span>
              <span>Lote mín: {p.loteMinimo}</span>
            </div>
          </div>
          <div className="border-t border-neutral-800 pt-2">
            <p className="text-[10px] text-neutral-500 uppercase tracking-wider mb-1">Operações</p>
            <div className="flex flex-wrap gap-2">
              {p.ops.map((op, i) => (
                <span key={op} className="text-xs bg-neutral-800 text-neutral-300 px-2 py-0.5 rounded flex items-center gap-1">
                  <span className="text-neutral-600">{i + 1}.</span> {op}
                </span>
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function CompostosPanel() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-neutral-300">Produtos Compostos</h3>
        <button className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1 rounded-lg transition-colors">+ Novo</button>
      </div>
      {compostosMock.map((c) => (
        <div key={c.sku} className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-3">
          <div>
            <span className="text-sm font-medium text-neutral-200">{c.nome}</span>
            <span className="text-xs text-neutral-500 ml-2 font-mono">{c.sku}</span>
          </div>
          <div className="border-t border-neutral-800 pt-2">
            <p className="text-[10px] text-neutral-500 uppercase tracking-wider mb-1">Usado em</p>
            {c.usadoEm.map((u) => (
              <div key={u.sku} className="flex items-center gap-2 text-xs text-neutral-400 py-0.5">
                <span className="text-neutral-600">{u.qtd}x</span>
                <span className="font-mono text-indigo-400">{u.sku}</span>
                <span>{u.nome}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function BOMPanel() {
  const tipoBadge = (tipo: string) => {
    const map: Record<string, string> = { MP: "bg-amber-900/50 text-amber-400", EMB: "bg-blue-900/50 text-blue-400", SEMI: "bg-purple-900/50 text-purple-400" };
    return map[tipo] || "bg-neutral-700 text-neutral-400";
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-neutral-300">Bill of Materials (BOM)</h3>
        <button className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1 rounded-lg transition-colors">+ Adicionar</button>
      </div>
      <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
        <table className="w-full text-sm min-w-[500px]">
          <thead>
            <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
              <th className="text-left p-3 font-medium">Código</th>
              <th className="text-left p-3 font-medium">Componente</th>
              <th className="text-right p-3 font-medium">Qtd</th>
              <th className="text-left p-3 font-medium">Un</th>
              <th className="text-center p-3 font-medium">Tipo</th>
            </tr>
          </thead>
          <tbody>
            {bomMock.map((item, i) => (
              <tr key={`${item.codigo}-${i}`} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                <td className="p-3 text-indigo-400 font-mono text-xs">
                  <span style={{ paddingLeft: `${item.nivel * 16}px` }}>
                    {item.nivel > 0 ? "└ " : ""}{item.codigo}
                  </span>
                </td>
                <td className="p-3 text-neutral-300">{item.nome}</td>
                <td className="p-3 text-right text-neutral-300 numeric">{item.qtd.toFixed(item.unidade === "kg" ? 3 : 0)}</td>
                <td className="p-3 text-neutral-400">{item.unidade}</td>
                <td className="p-3 text-center">
                  <Badge label={item.tipo} color={tipoBadge(item.tipo)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const PANELS = {
  kit: KitPanel,
  combo: ComboPanel,
  producao: ProducaoPanel,
  compostos: CompostosPanel,
  bom: BOMPanel,
};

export default function KitsBomTab() {
  const [subTab, setSubTab] = useState<SubTabId>("kit");
  const Panel = PANELS[subTab];

  return (
    <div className="space-y-4">
      <div className="flex gap-2 overflow-x-auto">
        {SUB_TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setSubTab(t.id)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap ${
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
