"use client";

import { useState, useEffect } from "react";

interface SugestaoRotacao {
  sku: string; nome: string;
  loja_excesso: string; qtd_excesso: number;
  loja_escassez: string; qtd_escassez: number;
  sugerir_transferir: number;
}

export default function RotacaoPage() {
  const [sugestoes, setSugestoes] = useState<SugestaoRotacao[]>([]);
  const [loading, setLoading] = useState(true);

  const carregar = () => {
    setLoading(true);
    fetch("/api/estoque/sugestao-rotacao").then(r => r.json()).then(d => setSugestoes(d.data || [])).finally(() => setLoading(false));
  };
  useEffect(() => { carregar(); }, []);

  const transferir = async (sku: string, origem: string, destino: string, qtd: number) => {
    if (!confirm(`Transferir ${qtd} un de ${sku} de "${origem}" para "${destino}"?`)) return;
    try {
      const r = await fetch("/api/estoque/transferir", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sku, origem, destino, quantidade: qtd, motivo: "Rotação automática" }),
      });
      const d = await r.json();
      if (d.erro) { alert(d.erro); return; }
      carregar();
    } catch { alert("Erro ao transferir"); }
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">Rotação de Estoque</h1>
        <p className="text-xs text-neutral-500 mt-1">Sugestões de transferência entre lojas com estoque desbalanceado</p>
      </div>

      {loading ? <p className="text-neutral-500 text-sm">Analisando estoque...</p> : sugestoes.length === 0 ? (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-8 text-center">
          <p className="text-emerald-400 text-sm font-medium">Estoque balanceado!</p>
          <p className="text-neutral-500 text-xs mt-1">Nenhuma sugestão de transferência no momento.</p>
        </div>
      ) : (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-neutral-800 text-neutral-500 text-xs">
              <th className="text-left p-3">SKU</th><th className="text-left p-3">Produto</th>
              <th className="text-right p-3">Excesso</th><th className="text-right p-3">Escassez</th>
              <th className="text-center p-3">Sugestão</th><th className="w-24"></th>
            </tr></thead>
            <tbody>
              {sugestoes.map(s => (
                <tr key={s.sku} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                  <td className="p-3 text-indigo-400 font-mono text-xs">{s.sku}</td>
                  <td className="p-3 text-neutral-200">{s.nome}</td>
                  <td className="p-3 text-right">
                    <span className="text-amber-400 font-medium">{s.qtd_excesso} un</span>
                    <div className="text-[10px] text-neutral-500">{s.loja_excesso}</div>
                  </td>
                  <td className="p-3 text-right">
                    <span className={s.qtd_escassez === 0 ? "text-red-400 font-medium" : "text-neutral-400"}>{s.qtd_escassez} un</span>
                    <div className="text-[10px] text-neutral-500">{s.loja_escassez}</div>
                  </td>
                  <td className="p-3 text-center">
                    <span className="bg-emerald-900/30 text-emerald-400 text-xs px-2 py-0.5 rounded">{s.sugerir_transferir} un</span>
                  </td>
                  <td className="p-3">
                    <button onClick={() => transferir(s.sku, s.loja_excesso, s.loja_escassez, s.sugerir_transferir)}
                      className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1.5 rounded-lg">Transferir</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
