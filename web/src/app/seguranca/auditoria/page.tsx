"use client";
import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";

interface Registro {
  id: number;
  user_id: number | null;
  email: string;
  acao: string;
  modulo: string;
  entidade: string;
  entidade_id: number | null;
  dados_antes: Record<string, unknown> | null;
  dados_depois: Record<string, unknown> | null;
  ip: string;
  user_agent: string;
  created_at: string;
}

const ACAO_COR: Record<string, string> = {
  excluir: "bg-red-500/20 text-red-400",
  login_falha: "bg-red-500/20 text-red-400",
  login_sucesso: "bg-emerald-500/20 text-emerald-400",
};

export default function AuditoriaPage() {
  const [items, setItems] = useState<Registro[]>([]);
  const [modulos, setModulos] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [selecionado, setSelecionado] = useState<Registro | null>(null);

  const [modulo, setModulo] = useState("");
  const [acao, setAcao] = useState("");
  const [email, setEmail] = useState("");
  const [dataInicio, setDataInicio] = useState("");
  const [dataFim, setDataFim] = useState("");

  const carregar = useCallback(() => {
    setLoading(true);
    api.auditoriaList({ modulo, acao, email, data_inicio: dataInicio, data_fim: dataFim, limit: 200 })
      .then(d => setItems((d.auditoria || []) as unknown as Registro[]))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [modulo, acao, email, dataInicio, dataFim]);

  useEffect(() => { carregar(); }, [carregar]);
  useEffect(() => { api.auditoriaModulos().then(d => setModulos(d.modulos || [])).catch(() => {}); }, []);

  const limparFiltros = () => { setModulo(""); setAcao(""); setEmail(""); setDataInicio(""); setDataFim(""); };

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">Auditoria</h1>
        <p className="text-xs text-neutral-500 mt-1">Quem fez o quê — todas as exclusões e ações sensíveis do sistema, com o registro anterior quando disponível.</p>
      </div>

      <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-3 grid grid-cols-2 md:grid-cols-5 gap-2">
        <select value={modulo} onChange={e => setModulo(e.target.value)} className="bg-neutral-900 border border-neutral-700 rounded-lg px-2 py-1.5 text-xs text-neutral-200">
          <option value="">Todos os módulos</option>
          {modulos.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
        <select value={acao} onChange={e => setAcao(e.target.value)} className="bg-neutral-900 border border-neutral-700 rounded-lg px-2 py-1.5 text-xs text-neutral-200">
          <option value="">Toda ação</option>
          <option value="excluir">Excluir</option>
          <option value="aprovar">Aprovar</option>
          <option value="login_sucesso">Login (sucesso)</option>
          <option value="login_falha">Login (falha)</option>
        </select>
        <input value={email} onChange={e => setEmail(e.target.value)} placeholder="E-mail do usuário"
          className="bg-neutral-900 border border-neutral-700 rounded-lg px-2 py-1.5 text-xs text-neutral-200" />
        <input type="date" value={dataInicio} onChange={e => setDataInicio(e.target.value)}
          className="bg-neutral-900 border border-neutral-700 rounded-lg px-2 py-1.5 text-xs text-neutral-200" />
        <div className="flex gap-2">
          <input type="date" value={dataFim} onChange={e => setDataFim(e.target.value)}
            className="flex-1 bg-neutral-900 border border-neutral-700 rounded-lg px-2 py-1.5 text-xs text-neutral-200" />
          <button onClick={limparFiltros} className="text-[11px] text-neutral-500 hover:text-neutral-300 whitespace-nowrap px-2">Limpar</button>
        </div>
      </div>

      {loading ? <p className="text-neutral-500 text-xs">Carregando...</p> : items.length === 0 ? <p className="text-neutral-500 text-xs">Nenhum registro para os filtros selecionados.</p> : (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="border-b border-neutral-700 text-neutral-400 text-left">
              <th className="px-4 py-2 font-medium">Quando</th>
              <th className="px-4 py-2 font-medium">Usuário</th>
              <th className="px-4 py-2 font-medium">Ação</th>
              <th className="px-4 py-2 font-medium">Módulo</th>
              <th className="px-4 py-2 font-medium">Entidade</th>
              <th className="px-4 py-2 font-medium">IP</th>
              <th className="px-4 py-2 font-medium"></th>
            </tr></thead>
            <tbody>{items.map(item => (
              <tr key={item.id} className="border-b border-neutral-700/50 hover:bg-neutral-700/30 text-neutral-300">
                <td className="px-4 py-2 whitespace-nowrap">{String(item.created_at || "").replace("T", " ").slice(0, 19)}</td>
                <td className="px-4 py-2">{item.email || "—"}</td>
                <td className="px-4 py-2"><span className={`px-2 py-0.5 rounded text-[10px] ${ACAO_COR[item.acao] || "bg-neutral-700 text-neutral-300"}`}>{item.acao}</span></td>
                <td className="px-4 py-2">{item.modulo || "—"}</td>
                <td className="px-4 py-2">{item.entidade}{item.entidade_id ? ` #${item.entidade_id}` : ""}</td>
                <td className="px-4 py-2 font-mono text-neutral-500">{item.ip || "—"}</td>
                <td className="px-4 py-2">
                  {(item.dados_antes || item.dados_depois) && (
                    <button onClick={() => setSelecionado(item)} className="text-indigo-400 hover:text-indigo-300 text-[11px]">Ver dados</button>
                  )}
                </td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}

      {selecionado && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setSelecionado(null)}>
          <div className="bg-neutral-800 border border-neutral-700 rounded-xl p-6 w-[32rem] max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-neutral-200">
                {selecionado.acao} — {selecionado.modulo}/{selecionado.entidade}{selecionado.entidade_id ? ` #${selecionado.entidade_id}` : ""}
              </h3>
              <button onClick={() => setSelecionado(null)} className="text-neutral-500 hover:text-neutral-300 text-xs">Fechar</button>
            </div>
            <p className="text-[11px] text-neutral-500 mb-3">
              {selecionado.email || "—"} · {String(selecionado.created_at || "").replace("T", " ").slice(0, 19)} · {selecionado.ip || "—"}
            </p>
            {selecionado.dados_antes && (
              <div className="mb-3">
                <p className="text-[10px] text-amber-400 uppercase tracking-wider mb-1">Antes (excluído/alterado)</p>
                <pre className="bg-neutral-900 border border-neutral-700 rounded-lg p-3 text-[11px] text-neutral-300 whitespace-pre-wrap break-words">
                  {JSON.stringify(selecionado.dados_antes, null, 2)}
                </pre>
              </div>
            )}
            {selecionado.dados_depois && (
              <div>
                <p className="text-[10px] text-emerald-400 uppercase tracking-wider mb-1">Depois</p>
                <pre className="bg-neutral-900 border border-neutral-700 rounded-lg p-3 text-[11px] text-neutral-300 whitespace-pre-wrap break-words">
                  {JSON.stringify(selecionado.dados_depois, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
