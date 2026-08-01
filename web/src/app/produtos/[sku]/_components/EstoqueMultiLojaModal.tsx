"use client";

import { useEffect, useState } from "react";
import { estoqueLojas, estoqueAtualizar } from "@/lib/api";
import type { LojaInfo } from "@/lib/store-context";

interface EstoqueMultiLojaModalProps {
  sku: string;
  nome: string;
  lojas: LojaInfo[];
  onClose: () => void;
  onSucesso: () => void;
}

type SaveStatus = "enviando" | "ok" | "erro";

export default function EstoqueMultiLojaModal({ sku, nome, lojas, onClose, onSucesso }: EstoqueMultiLojaModalProps) {
  const [etapa, setEtapa] = useState<"selecao" | "edicao">("selecao");
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [estoqueAtualPorLoja, setEstoqueAtualPorLoja] = useState<Record<string, number>>({});
  const [selecionadas, setSelecionadas] = useState<Set<string>>(new Set());
  const [valores, setValores] = useState<Record<string, string>>({});
  const [salvando, setSalvando] = useState(false);
  const [status, setStatus] = useState<Record<string, SaveStatus>>({});
  const [concluido, setConcluido] = useState(false);

  useEffect(() => {
    let ativo = true;
    setCarregando(true);
    estoqueLojas(`busca=${encodeURIComponent(sku)}&por_pagina=200`)
      .then((r) => {
        if (!ativo) return;
        const mapa: Record<string, number> = {};
        (r.estoque || []).filter((e) => e.sku === sku).forEach((e) => { mapa[e.loja] = Number(e.quantidade) || 0; });
        setEstoqueAtualPorLoja(mapa);
      })
      .catch((e: unknown) => { if (ativo) setErro(e instanceof Error ? e.message : "Erro ao carregar estoque atual"); })
      .finally(() => { if (ativo) setCarregando(false); });
    return () => { ativo = false; };
  }, [sku]);

  const toggleLoja = (nomeLoja: string) => {
    setSelecionadas(prev => {
      const next = new Set(prev);
      if (next.has(nomeLoja)) next.delete(nomeLoja); else next.add(nomeLoja);
      return next;
    });
  };

  const avancarParaEdicao = () => {
    if (selecionadas.size === 0) return;
    const iniciais: Record<string, string> = {};
    selecionadas.forEach(nomeLoja => { iniciais[nomeLoja] = String(estoqueAtualPorLoja[nomeLoja] ?? 0); });
    setValores(iniciais);
    setEtapa("edicao");
  };

  const handleSalvar = async () => {
    setSalvando(true);
    setConcluido(false);
    const nomesLojas = Array.from(selecionadas);
    const statusInicial: Record<string, SaveStatus> = {};
    nomesLojas.forEach(nomeLoja => { statusInicial[nomeLoja] = "enviando"; });
    setStatus(statusInicial);

    await Promise.all(nomesLojas.map(async (nomeLoja) => {
      const atual = estoqueAtualPorLoja[nomeLoja] ?? 0;
      const novo = Number(valores[nomeLoja]);
      if (!Number.isFinite(novo) || novo === atual) {
        setStatus(prev => ({ ...prev, [nomeLoja]: "ok" }));
        return;
      }
      try {
        const r = await estoqueAtualizar(sku, nomeLoja, novo);
        setStatus(prev => ({ ...prev, [nomeLoja]: r.erro ? "erro" : "ok" }));
      } catch {
        setStatus(prev => ({ ...prev, [nomeLoja]: "erro" }));
      }
    }));
    setSalvando(false);
    setConcluido(true);
    onSucesso();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-neutral-900 border border-neutral-700 rounded-xl p-6 w-full max-w-lg mx-4 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-medium text-neutral-200">Estoque por loja</h2>
            <p className="text-xs font-mono text-neutral-500 mt-0.5">{sku} — {nome}</p>
          </div>
          <button onClick={onClose} className="text-neutral-500 hover:text-neutral-300 text-lg">&times;</button>
        </div>

        {erro && (
          <div className="text-red-400 text-sm bg-red-950/40 border border-red-900/50 rounded-lg px-4 py-3 mb-4">{erro}</div>
        )}

        {carregando ? (
          <div className="text-neutral-500 text-sm py-8 text-center">Carregando estoque atual...</div>
        ) : etapa === "selecao" ? (
          <div className="space-y-4">
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs text-neutral-500 uppercase tracking-wider">
                  Lojas ({selecionadas.size} de {lojas.length})
                </label>
                <div className="flex items-center gap-2">
                  <button onClick={() => setSelecionadas(new Set(lojas.map(l => l.nome)))} className="text-[10px] text-indigo-400 hover:text-indigo-300">Selecionar todas</button>
                  <span className="text-neutral-700">·</span>
                  <button onClick={() => setSelecionadas(new Set())} className="text-[10px] text-neutral-500 hover:text-neutral-300">Limpar</button>
                </div>
              </div>
              <div className="max-h-56 overflow-y-auto space-y-1 border border-neutral-800 rounded-lg p-2">
                {lojas.map(l => (
                  <label key={l.id} className="flex items-center justify-between gap-2 text-xs text-neutral-300 px-1 py-1 hover:bg-neutral-800/50 rounded cursor-pointer">
                    <span className="flex items-center gap-2">
                      <input type="checkbox" checked={selecionadas.has(l.nome)} onChange={() => toggleLoja(l.nome)} className="accent-indigo-600" />
                      {l.nome}
                    </span>
                    <span className="font-mono numeric text-neutral-500">{estoqueAtualPorLoja[l.nome] ?? 0}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={onClose} className="text-xs text-neutral-500 hover:text-neutral-300 px-3 py-1.5">Cancelar</button>
              <button
                onClick={avancarParaEdicao}
                disabled={selecionadas.size === 0}
                className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs px-4 py-1.5 rounded-lg transition-colors"
              >
                Continuar
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-800 text-neutral-500 text-xs uppercase">
                  <th className="text-left px-2 py-1.5 font-medium">Loja</th>
                  <th className="text-right px-2 py-1.5 font-medium">Estoque</th>
                  {concluido && <th className="text-right px-2 py-1.5 font-medium">Status</th>}
                </tr>
              </thead>
              <tbody>
                {Array.from(selecionadas).map((nomeLoja) => (
                  <tr key={nomeLoja} className="border-b border-neutral-800/30">
                    <td className="px-2 py-1.5 text-neutral-300 text-xs">{nomeLoja}</td>
                    <td className="px-2 py-1.5 text-right">
                      <input
                        type="number"
                        step="0.01"
                        value={valores[nomeLoja] ?? ""}
                        onChange={(e) => setValores(v => ({ ...v, [nomeLoja]: e.target.value }))}
                        disabled={salvando || concluido}
                        className="w-20 bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-right text-neutral-200 numeric disabled:opacity-60"
                      />
                    </td>
                    {concluido && (
                      <td className="px-2 py-1.5 text-right text-xs">
                        {status[nomeLoja] === "ok" && <span className="text-emerald-400">salvo</span>}
                        {status[nomeLoja] === "erro" && <span className="text-red-400">falhou</span>}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex justify-end gap-2 pt-2">
              {!concluido && (
                <button onClick={() => setEtapa("selecao")} disabled={salvando} className="text-xs text-neutral-500 hover:text-neutral-300 px-3 py-1.5">
                  Voltar
                </button>
              )}
              <button onClick={onClose} className="text-xs text-neutral-500 hover:text-neutral-300 px-3 py-1.5">
                {concluido ? "Fechar" : "Cancelar"}
              </button>
              {!concluido && (
                <button
                  onClick={handleSalvar}
                  disabled={salvando}
                  className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs px-4 py-1.5 rounded-lg transition-colors"
                >
                  {salvando ? "Salvando..." : "Salvar"}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
