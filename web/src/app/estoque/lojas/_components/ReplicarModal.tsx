"use client";

import { useState } from "react";
import { replicarProdutoLoja } from "@/lib/api";
import type { LojaInfo } from "@/lib/store-context";

export default function ReplicarModal({
  lojaOrigem, sku, lojasDisponiveis, onClose, onDone,
}: {
  lojaOrigem: string;
  sku: string;
  lojasDisponiveis: LojaInfo[];
  onClose: () => void;
  onDone: () => void;
}) {
  const [selecionadas, setSelecionadas] = useState<string[]>([]);
  const [salvando, setSalvando] = useState(false);
  const [resultado, setResultado] = useState<{
    ok?: boolean;
    criados?: string[];
    ja_existentes?: string[];
    erro?: string;
    erros?: { loja: string; erro: string }[];
  } | null>(null);

  const toggle = (lojaId: string) =>
    setSelecionadas((s) => (s.includes(lojaId) ? s.filter((l) => l !== lojaId) : [...s, lojaId]));

  const confirmar = async () => {
    setSalvando(true);
    const r = await replicarProdutoLoja(lojaOrigem, sku, selecionadas);
    setResultado(r);
    setSalvando(false);
  };

  const finalizar = () => {
    if (resultado?.ok) onDone();
    else onClose();
  };

  const destinos = lojasDisponiveis.filter((l) => String(l.id) !== lojaOrigem);

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-neutral-900 border border-neutral-700 rounded-lg p-5 w-full max-w-sm">
        <h3 className="text-sm font-semibold mb-1">Replicar {sku} para outras lojas</h3>
        <p className="text-[11px] text-neutral-500 mb-3">
          Copia só dados cadastrais (nome, descrição, categoria, marca, imagens, atributos, tributação).
          Nunca copia estoque, preço, fornecedor, promoção, localização ou histórico.
        </p>
        <div className="space-y-1 max-h-48 overflow-y-auto mb-3">
          {destinos.length === 0 ? (
            <p className="text-[11px] text-neutral-500">Nenhuma outra loja disponível.</p>
          ) : (
            destinos.map((loja) => (
              <label key={loja.id} className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={selecionadas.includes(String(loja.id))}
                  onChange={() => toggle(String(loja.id))}
                />
                {loja.nome}
              </label>
            ))
          )}
        </div>
        {resultado && (
          <div className="text-[11px] mb-2 space-y-0.5">
            {resultado.erro && <p className="text-red-400">{resultado.erro}</p>}
            {resultado.criados?.length ? <p className="text-emerald-400">Criado em: {resultado.criados.join(", ")}</p> : null}
            {resultado.ja_existentes?.length ? <p className="text-amber-400">Já existia em: {resultado.ja_existentes.join(", ")}</p> : null}
            {resultado.erros?.length ? (
              <p className="text-red-400">
                Falhou em: {resultado.erros.map((e) => `${e.loja} (${e.erro})`).join(", ")}
              </p>
            ) : null}
          </div>
        )}
        <div className="flex justify-end gap-2">
          <button onClick={finalizar} className="text-xs px-3 py-1.5 rounded border border-neutral-700">
            {resultado ? "OK" : "Fechar"}
          </button>
          {!resultado && (
            <button
              onClick={confirmar}
              disabled={salvando || selecionadas.length === 0}
              className="text-xs px-3 py-1.5 rounded bg-blue-600 disabled:opacity-40"
            >
              {salvando ? "Replicando..." : "Replicar"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
