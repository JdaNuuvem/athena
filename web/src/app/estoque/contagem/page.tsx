"use client";

import { useState, useEffect, useCallback } from "react";
import { api, type EstoqueContagemSugestao, type EstoqueContagemHistorico } from "@/lib/api";
import { useStore } from "@/lib/store-context";

const LABEL_AJUSTE: Record<string, { label: string; cls: string }> = {
  sem_diferenca: { label: "Sem diferença", cls: "text-neutral-500" },
  aplicado: { label: "Ajustado", cls: "text-emerald-400" },
  pendente_aprovacao: { label: "Pendente aprovação", cls: "text-amber-400" },
  erro: { label: "Erro", cls: "text-red-400" },
};

export default function ContagemCiclicaPage() {
  const { lojaId, lojas } = useStore();
  const [loja, setLoja] = useState("");
  const [sugestoes, setSugestoes] = useState<EstoqueContagemSugestao[]>([]);
  const [historico, setHistorico] = useState<EstoqueContagemHistorico[]>([]);
  const [contagens, setContagens] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");

  useEffect(() => {
    if (!loja && lojas.length > 0) {
      const atual = lojas.find(l => String(l.id) === lojaId);
      setLoja(atual?.nome || lojas[0].nome);
    }
  }, [lojas, lojaId, loja]);

  const carregar = useCallback(async () => {
    if (!loja) return;
    setLoading(true);
    try {
      const [s, h] = await Promise.all([
        api.estoqueContagemSugestoes(loja),
        api.estoqueContagemHistorico(loja),
      ]);
      setSugestoes(s.sugestoes || []);
      setHistorico(h.historico || []);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar");
    } finally {
      setLoading(false);
    }
  }, [loja]);

  useEffect(() => { carregar(); }, [carregar]);

  const registrar = async (sku: string) => {
    const valor = contagens[sku];
    if (valor === undefined || valor === "") { setErro("Informe a quantidade contada"); return; }
    const qtd = parseFloat(valor);
    if (isNaN(qtd) || qtd < 0) { setErro("Quantidade invalida"); return; }
    setErro(""); setSucesso("");
    try {
      const r = await api.estoqueContagemRegistrar(sku, loja, qtd);
      if (r.erro) { setErro(r.erro); return; }
      const diff = r.diferenca ?? 0;
      setSucesso(`${sku}: contagem registrada (diferença: ${diff > 0 ? "+" : ""}${diff}, status: ${LABEL_AJUSTE[r.ajuste_status || ""]?.label || r.ajuste_status}).`);
      setContagens(c => { const n = { ...c }; delete n[sku]; return n; });
      carregar();
    } catch (e) { setErro(e instanceof Error ? e.message : "Erro ao registrar contagem"); }
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-light text-neutral-300">Contagem Cíclica</h1>
        <p className="text-xs text-neutral-500 mt-0.5">
          Lista semanal dos SKUs de maior valor em estoque ainda não contados nos últimos 30 dias, por loja.
        </p>
      </div>

      <div className="space-y-1 max-w-xs">
        <label className="text-[10px] text-neutral-500 uppercase tracking-wider">Loja</label>
        <select value={loja} onChange={e => setLoja(e.target.value)}
          className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500">
          {lojas.map(l => <option key={l.id} value={l.nome}>{l.nome}</option>)}
        </select>
      </div>

      {erro && <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3">{erro}</div>}
      {sucesso && <div className="text-emerald-400 text-sm bg-emerald-950/30 border border-emerald-900/50 rounded-lg px-4 py-3">{sucesso}</div>}

      {loading ? (
        <div className="text-neutral-500 text-sm">Carregando...</div>
      ) : (
        <>
          <section>
            <h2 className="text-sm font-medium text-neutral-400 mb-2">Sugestões para contar ({sugestoes.length})</h2>
            {sugestoes.length === 0 ? (
              <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 text-center text-neutral-500 text-xs">
                Nenhuma sugestão pendente — tudo foi contado recentemente nesta loja.
              </div>
            ) : (
              <div className="space-y-2">
                {sugestoes.map(s => (
                  <div key={s.sku} className="bg-neutral-900 border border-neutral-800 rounded-lg p-3 flex items-center justify-between gap-3 flex-wrap">
                    <div>
                      <div className="text-sm text-neutral-200 font-medium">{s.nome}</div>
                      <div className="text-xs text-neutral-500">
                        {s.sku} · sistema: {s.quantidade} un · valor em estoque: R$ {Number(s.valor_total).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="number" step="1" min="0" placeholder="Contagem física"
                        value={contagens[s.sku] ?? ""}
                        onChange={e => setContagens(c => ({ ...c, [s.sku]: e.target.value }))}
                        className="w-32 bg-neutral-950 border border-neutral-700 rounded-lg px-2 py-1.5 text-sm text-neutral-100"
                      />
                      <button onClick={() => registrar(s.sku)} className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1.5 rounded-lg">
                        Registrar
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section>
            <h2 className="text-sm font-medium text-neutral-400 mb-2">Histórico de contagens</h2>
            {historico.length === 0 ? (
              <div className="text-neutral-500 text-xs">Nenhuma contagem registrada ainda nesta loja.</div>
            ) : (
              <div className="overflow-x-auto border border-neutral-800 rounded-lg">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-neutral-900 text-neutral-400 text-left">
                      <th className="px-3 py-2 font-medium">Produto</th>
                      <th className="px-3 py-2 font-medium text-right">Sistema</th>
                      <th className="px-3 py-2 font-medium text-right">Contado</th>
                      <th className="px-3 py-2 font-medium text-right">Diferença</th>
                      <th className="px-3 py-2 font-medium">Status</th>
                      <th className="px-3 py-2 font-medium">Operador</th>
                    </tr>
                  </thead>
                  <tbody>
                    {historico.map(h => (
                      <tr key={h.id} className="border-t border-neutral-800 text-neutral-300">
                        <td className="px-3 py-2">{h.produto_nome || h.sku}</td>
                        <td className="px-3 py-2 text-right numeric">{h.quantidade_sistema}</td>
                        <td className="px-3 py-2 text-right numeric">{h.quantidade_contada}</td>
                        <td className={`px-3 py-2 text-right numeric ${h.diferenca < 0 ? "text-red-400" : h.diferenca > 0 ? "text-emerald-400" : "text-neutral-500"}`}>
                          {h.diferenca > 0 ? "+" : ""}{h.diferenca}
                        </td>
                        <td className={`px-3 py-2 ${LABEL_AJUSTE[h.ajuste_status]?.cls || ""}`}>{LABEL_AJUSTE[h.ajuste_status]?.label || h.ajuste_status}</td>
                        <td className="px-3 py-2 text-neutral-500">{h.usuario_nome || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
