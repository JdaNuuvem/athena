"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { i9logicEstoquePorLoja, estoqueAtualizar, type EstoqueI9LogicItem } from "@/lib/api";

interface Props {
  lojaId: number;
  lojaNome: string;
}

const POLL_INTERVAL_MS = 5000;

export default function EstoqueFisicoI9Logic({ lojaId, lojaNome }: Props) {
  const [itens, setItens] = useState<EstoqueI9LogicItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [atualizando, setAtualizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [avisoColeta, setAvisoColeta] = useState<string | null>(null);
  const [busca, setBusca] = useState("");
  const [editando, setEditando] = useState<number | null>(null);
  const [novaQtd, setNovaQtd] = useState("");
  const [salvando, setSalvando] = useState(false);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancelarPoll = () => {
    if (pollRef.current) {
      clearTimeout(pollRef.current);
      pollRef.current = null;
    }
  };

  const carregar = useCallback(async (primeiraVez = false) => {
    cancelarPoll();
    if (primeiraVez) setLoading(true);
    setErro(null);
    try {
      const r = await i9logicEstoquePorLoja(lojaId);
      setItens(r.data || []);
      setAvisoColeta(r.erro_ultima_coleta || null);
      const processando = r.status === "processando";
      setAtualizando(processando);
      if (processando) {
        pollRef.current = setTimeout(() => carregar(false), POLL_INTERVAL_MS);
      }
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar estoque i9Logic");
      setAtualizando(false);
    } finally {
      if (primeiraVez) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lojaId]);

  useEffect(() => {
    carregar(true);
    return () => cancelarPoll();
  }, [carregar]);

  const iniciarEdicao = (item: EstoqueI9LogicItem) => {
    setEditando(item.idproduto);
    setNovaQtd(String(item.qtd));
  };

  const salvarAjuste = async (item: EstoqueI9LogicItem) => {
    if (!item.sku_athena) return;
    setSalvando(true);
    setErro(null);
    try {
      const r = await estoqueAtualizar(item.sku_athena, lojaNome, Number(novaQtd));
      if (r.erro) {
        setErro(r.erro);
        return;
      }
      setEditando(null);
      await carregar(true);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao ajustar estoque");
    } finally {
      setSalvando(false);
    }
  };

  const filtrados = itens.filter(i => {
    if (!busca) return true;
    const t = busca.toLowerCase();
    return i.codproduto.toLowerCase().includes(t) ||
      (i.sku_athena || "").toLowerCase().includes(t) ||
      (i.descricao || "").toLowerCase().includes(t);
  });

  const semMapeamento = erro?.includes("mapeamento de filial i9Logic");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-neutral-500">
          Estoque fisico — <span className="text-neutral-400">{lojaNome}</span> · fonte: i9Logic
        </p>
        <button onClick={() => carregar(true)} className="px-3 py-1.5 bg-neutral-700 text-neutral-300 text-xs rounded-lg hover:bg-neutral-600">
          Atualizar
        </button>
      </div>

      {erro && (
        <div className="bg-red-900/30 border border-red-800 text-red-400 text-xs px-3 py-2 rounded-lg">
          {erro}
          {semMapeamento && (
            <p className="mt-1 text-red-300/80">
              Cadastre o de-para desta loja em <code className="text-red-200">POST /api/integrations/i9logic/depara</code> (tipo=&quot;filial&quot;) antes de usar esta tela.
            </p>
          )}
        </div>
      )}

      {!erro && atualizando && (
        <div className="bg-indigo-900/20 border border-indigo-800/60 text-indigo-300 text-xs px-3 py-2 rounded-lg">
          Coletando estoque atualizado da i9Logic em segundo plano — filiais grandes podem levar alguns minutos.
          A lista atualiza sozinha quando terminar.
          {avisoColeta && (
            <p className="mt-1 text-amber-400/90">Ultima tentativa falhou ({avisoColeta}) — tentando de novo.</p>
          )}
        </div>
      )}

      {!erro && (
        <input type="text" value={busca} onChange={e => setBusca(e.target.value)}
          placeholder="Buscar SKU, codigo i9Logic ou descricao..."
          className="w-full max-w-md bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-200 placeholder-neutral-500 focus:outline-none focus:border-indigo-500" />
      )}

      {loading ? (
        <div className="text-neutral-500 text-sm py-8 text-center">Consultando i9Logic...</div>
      ) : erro ? null : filtrados.length === 0 ? (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center">
          <p className="text-neutral-400 text-sm">
            {atualizando ? "Nenhum dado coletado ainda — aguardando a primeira coleta da i9Logic..." : "Nenhum produto encontrado"}
          </p>
        </div>
      ) : (
        <div className="instrument-enter bg-neutral-800 border border-neutral-700 rounded-lg overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
                <th className="text-left p-2">Codigo i9Logic</th>
                <th className="text-left p-2">SKU Athena</th>
                <th className="text-left p-2">Descricao</th>
                <th className="text-right p-2">Qtd Fisica</th>
                <th className="text-center p-2">Acoes</th>
              </tr>
            </thead>
            <tbody>
              {filtrados.map((item, i) => (
                <tr key={item.idproduto} className={`instrument-hover border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}>
                  <td className="p-2 text-neutral-400 font-mono text-[11px]">{item.codproduto}</td>
                  <td className="p-2 font-mono text-[11px]">
                    {item.sku_athena ? (
                      <span className="text-neutral-200">{item.sku_athena}</span>
                    ) : (
                      <span className="text-amber-400" title="Sem de-para de produto cadastrado">sem mapeamento</span>
                    )}
                  </td>
                  <td className="p-2 text-neutral-300 max-w-[220px] truncate" title={item.descricao || ""}>{item.descricao || "—"}</td>
                  <td className="p-2 text-right">
                    {editando === item.idproduto ? (
                      <input type="number" value={novaQtd} onChange={e => setNovaQtd(e.target.value)}
                        className="w-20 bg-neutral-900 border border-indigo-600 rounded px-2 py-0.5 text-xs text-right text-neutral-200 focus:outline-none"
                        onKeyDown={e => { if (e.key === "Enter") salvarAjuste(item); if (e.key === "Escape") setEditando(null); }}
                        autoFocus />
                    ) : (
                      <span className={`font-mono numeric font-medium ${item.qtd <= 0 ? "text-red-400" : "text-emerald-400"}`}>{item.qtd}</span>
                    )}
                  </td>
                  <td className="p-2 text-center">
                    {!item.sku_athena ? (
                      <span className="text-neutral-600 text-xs">—</span>
                    ) : editando === item.idproduto ? (
                      <div className="flex gap-1.5 justify-center">
                        <button onClick={() => salvarAjuste(item)} disabled={salvando} className="text-emerald-400 hover:text-emerald-300 disabled:opacity-50">Salvar</button>
                        <button onClick={() => setEditando(null)} className="text-neutral-500 hover:text-neutral-300">Cancelar</button>
                      </div>
                    ) : (
                      <button onClick={() => iniciarEdicao(item)} className="text-indigo-400 hover:text-indigo-300">Ajustar</button>
                    )}
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
