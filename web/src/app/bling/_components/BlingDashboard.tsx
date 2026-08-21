"use client";

import { useEffect, useState } from "react";
import Spinner from "./shared/Spinner";
import Alert from "./shared/Alert";
import StatCard from "./shared/StatCard";
import { resumoVendasBling, getBlingStatus, BlingResumoVendas, BlingStatus } from "@/lib/api";

export default function BlingDashboard() {
  const [status, setStatus] = useState<BlingStatus | null>(null);
  const [resumo, setResumo] = useState<BlingResumoVendas | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function carregar() {
      try {
        setLoading(true);
        const [s, r] = await Promise.all([getBlingStatus(), resumoVendasBling(30)]);
        setStatus(s);
        setResumo(r);
      } catch (e) {
        setErro(e instanceof Error ? e.message : "Erro ao carregar dashboard");
      } finally {
        setLoading(false);
      }
    }
    carregar();
  }, []);

  if (loading) return <Spinner />;
  if (erro) return <Alert message={erro} type="error" />;
  if (!resumo) return <Alert message="Sem dados de vendas" type="info" />;

  const receitaMediaDiaria = resumo.dias_analisados > 0
    ? resumo.total_receita / resumo.dias_analisados
    : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <span className={`inline-block w-2 h-2 rounded-full ${status?.autenticado ? "bg-emerald-400" : "bg-red-400"}`} />
        <span className="text-xs text-neutral-400">
          Bling {status?.autenticado ? "Conectado" : "Desconectado"}
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard icon="💰" label="Receita Total (30d)" value={`R$ ${resumo.total_receita.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`} />
        <StatCard icon="📦" label="Pedidos (30d)" value={resumo.total_pedidos} />
        <StatCard icon="📊" label="Média Diária" value={`R$ ${receitaMediaDiaria.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`} />
        <StatCard icon="🏆" label="Top SKU" value={resumo.top_skus[0]?.sku || "—"} trend={resumo.top_skus[0] ? `R$ ${resumo.top_skus[0].receita.toLocaleString("pt-BR")}` : undefined} />
        <StatCard icon="📈" label="SKUs com Venda" value={resumo.top_skus.length} />
        <StatCard icon="🔄" label="Período" value={`${resumo.dias_analisados} dias`} />
      </div>

      <div>
        <h3 className="text-sm font-semibold text-neutral-200 mb-3">Top 20 SKUs</h3>
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400">
                <th className="text-left p-3">SKU</th>
                <th className="text-right p-3">Qtd</th>
                <th className="text-right p-3">Receita</th>
              </tr>
            </thead>
            <tbody>
              {resumo.top_skus.slice(0, 20).map((item, i) => (
                <tr key={item.sku} className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}>
                  <td className="p-3 text-neutral-200 font-medium">{item.sku}</td>
                  <td className="p-3 text-right text-neutral-300">{item.quantidade}</td>
                  <td className="p-3 text-right text-emerald-400">R$ {item.receita.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
