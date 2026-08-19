"use client";

import { useState } from "react";
import Link from "next/link";
import Icon from "@/app/_components/Icon";
import type { ShopeeProdutoSincronizado } from "@/lib/api";

type Aba = "estoque" | "detalhes";

function ProdutoThumb({ url, titulo, tamanho = "w-12 h-12" }: { url?: string | null; titulo: string; tamanho?: string }) {
  const [falhou, setFalhou] = useState(false);
  if (!url || falhou) {
    return (
      <div className={`${tamanho} rounded bg-neutral-800 border border-neutral-700 flex items-center justify-center text-xs text-neutral-500 shrink-0`}>
        {titulo.charAt(0).toUpperCase() || "?"}
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url}
      alt={titulo}
      className={`${tamanho} rounded object-cover border border-neutral-700 shrink-0`}
      onError={() => setFalhou(true)}
    />
  );
}

function statusPillClasses(status: string) {
  if (status === "normal") return "bg-emerald-950/40 border-emerald-900/50 text-emerald-400";
  if (status === "unlist" || status === "banned") return "bg-red-950/40 border-red-900/50 text-red-400";
  return "bg-amber-950/40 border-amber-900/50 text-amber-400";
}

function sufixoVariacao(titulo: string): string {
  const partes = titulo.split(" - ");
  return partes.length > 1 ? partes.slice(1).join(" - ") : titulo;
}

interface Props {
  itemId: string;
  variacoes: ShopeeProdutoSincronizado[];
  quantidades: Record<string, string>;
  setQuantidades: (updater: (q: Record<string, string>) => Record<string, string>) => void;
  enviando: string | null;
  onEnviarEstoque: (sku: string) => void;
  onClose: () => void;
}

export default function ProdutoVariacoesModal({
  itemId, variacoes, quantidades, setQuantidades, enviando, onEnviarEstoque, onClose,
}: Props) {
  const [aba, setAba] = useState<Aba>("estoque");
  const nomeBase = variacoes[0]?.titulo.split(" - ")[0] ?? itemId;
  const estoqueTotal = variacoes.reduce((s, v) => s + Number(v.estoque || 0), 0);

  return (
    <div className="fixed inset-0 z-50 bg-black/80" onClick={onClose}>
      <div
        className="instrument-enter flex flex-col h-full w-full bg-neutral-950"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 border-b border-neutral-800 px-6 py-4 shrink-0">
          <ProdutoThumb url={variacoes[0]?.imagem_url} titulo={nomeBase} tamanho="w-12 h-12" />
          <div className="flex-1 min-w-0">
            <h2 className="text-base text-neutral-200 truncate">{nomeBase}</h2>
            <p className="text-xs text-neutral-500">{variacoes.length} variações · {estoqueTotal} un no total</p>
          </div>
          <button
            onClick={onClose}
            className="text-neutral-500 hover:text-neutral-300 p-2 rounded-lg hover:bg-neutral-800 shrink-0"
          >
            <Icon name="close" size={20} />
          </button>
        </div>

        <div className="flex items-center gap-1 border-b border-neutral-800 px-6 shrink-0">
          <button
            onClick={() => setAba("estoque")}
            className={`text-sm px-4 py-3 border-b-2 transition-colors ${aba === "estoque" ? "border-indigo-500 text-neutral-100" : "border-transparent text-neutral-500 hover:text-neutral-300"}`}
          >
            Estoque
          </button>
          <button
            onClick={() => setAba("detalhes")}
            className={`text-sm px-4 py-3 border-b-2 transition-colors ${aba === "detalhes" ? "border-indigo-500 text-neutral-100" : "border-transparent text-neutral-500 hover:text-neutral-300"}`}
          >
            Detalhes
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {aba === "estoque" ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-800 text-neutral-500 text-xs uppercase sticky top-0 bg-neutral-950">
                  <th className="px-6 py-3 font-medium"></th>
                  <th className="text-left px-4 py-3 font-medium">SKU</th>
                  <th className="text-left px-4 py-3 font-medium">Variação</th>
                  <th className="text-right px-4 py-3 font-medium">Estoque atual</th>
                  <th className="text-center px-6 py-3 font-medium">Novo estoque</th>
                </tr>
              </thead>
              <tbody>
                {variacoes.map((v) => (
                  <tr key={v.sku} className="border-b border-neutral-800/50 hover:bg-neutral-900/60">
                    <td className="pl-6 py-3">
                      <ProdutoThumb url={v.imagem_url} titulo={v.titulo} tamanho="w-10 h-10" />
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-neutral-500">{v.sku}</td>
                    <td className="px-4 py-3 text-neutral-300">{sufixoVariacao(v.titulo)}</td>
                    <td className="px-4 py-3 text-right numeric font-medium">
                      <span className={Number(v.estoque) <= 0 ? "text-red-400" : Number(v.estoque) < 10 ? "text-amber-400" : "text-emerald-400"}>
                        {Number(v.estoque)}
                      </span>
                    </td>
                    <td className="px-6 py-3">
                      <div className="flex items-center justify-center gap-1.5">
                        <input
                          type="number"
                          placeholder={String(v.estoque)}
                          value={quantidades[v.sku] ?? ""}
                          onChange={(e) => setQuantidades((q) => ({ ...q, [v.sku]: e.target.value }))}
                          onKeyDown={(e) => { if (e.key === "Enter" && quantidades[v.sku]) onEnviarEstoque(v.sku); }}
                          className="w-20 bg-neutral-800 border border-neutral-700 rounded px-2 py-1.5 text-sm text-right text-neutral-200"
                        />
                        <button
                          onClick={() => onEnviarEstoque(v.sku)}
                          disabled={enviando === v.sku || quantidades[v.sku] === undefined || quantidades[v.sku] === ""}
                          className="text-xs bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white px-3 py-1.5 rounded"
                        >
                          {enviando === v.sku ? "..." : "Enviar"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-800 text-neutral-500 text-xs uppercase sticky top-0 bg-neutral-950">
                  <th className="px-6 py-3 font-medium"></th>
                  <th className="text-left px-4 py-3 font-medium">SKU</th>
                  <th className="text-left px-4 py-3 font-medium">Título</th>
                  <th className="text-right px-4 py-3 font-medium">Preço</th>
                  <th className="text-right px-4 py-3 font-medium">Preço de custo</th>
                  <th className="text-left px-4 py-3 font-medium">Status</th>
                  <th className="text-center px-6 py-3 font-medium">Editar</th>
                </tr>
              </thead>
              <tbody>
                {variacoes.map((v) => (
                  <tr key={v.sku} className="border-b border-neutral-800/50 hover:bg-neutral-900/60">
                    <td className="pl-6 py-3">
                      <ProdutoThumb url={v.imagem_url} titulo={v.titulo} tamanho="w-10 h-10" />
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-neutral-500">{v.sku}</td>
                    <td className="px-4 py-3 text-neutral-300 max-w-md truncate" title={v.titulo}>{v.titulo}</td>
                    <td className="px-4 py-3 text-right numeric text-neutral-300">
                      R$ {Number(v.preco || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
                    <td className="px-4 py-3 text-right numeric">
                      {v.preco_custo != null ? (
                        <span className="text-neutral-400">R$ {Number(v.preco_custo).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                      ) : (
                        <span className="text-neutral-600 text-xs">não cadastrado</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full border capitalize ${statusPillClasses(v.status)}`}>{v.status}</span>
                    </td>
                    <td className="px-6 py-3 text-center">
                      <Link
                        href={`/produtos/${v.sku}?tab=shopee`}
                        className="text-xs bg-neutral-800 hover:bg-neutral-700 text-neutral-300 px-2 py-1 rounded inline-block"
                      >
                        Editar
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
