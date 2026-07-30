"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { ShopeeProdutoSincronizado } from "@/lib/api";

interface LojaShopee {
  id: number;
  nome: string;
  shopee_shop_id: string;
  tem_token: boolean;
}

function statusColor(status: string) {
  if (status === "normal") return "text-emerald-400";
  if (status === "unlist" || status === "banned") return "text-red-400";
  return "text-amber-400";
}

export default function ShopeeProdutosPage() {
  const [lojas, setLojas] = useState<LojaShopee[]>([]);
  const [lojaId, setLojaId] = useState<number | "">("");
  const [produtos, setProdutos] = useState<ShopeeProdutoSincronizado[]>([]);
  const [loading, setLoading] = useState(false);
  const [sincronizando, setSincronizando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [enviando, setEnviando] = useState<string | null>(null);
  const [quantidades, setQuantidades] = useState<Record<string, string>>({});

  useEffect(() => {
    api.shopeeLojas().then(r => {
      const lojasComToken = (r.lojas || []).filter(l => l.tem_token);
      setLojas(lojasComToken);
      if (lojasComToken.length > 0) setLojaId(lojasComToken[0].id);
    }).catch(() => {});
  }, []);

  const carregar = useCallback(async () => {
    if (!lojaId) return;
    setLoading(true);
    setErro(null);
    try {
      const r = await api.shopeeProdutosSincronizados(Number(lojaId));
      if (r.error) { setErro(r.error); setProdutos([]); }
      else setProdutos(r.produtos || []);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao carregar produtos");
    } finally {
      setLoading(false);
    }
  }, [lojaId]);

  useEffect(() => { if (lojaId) carregar(); }, [lojaId, carregar]);

  const sincronizar = async () => {
    if (!lojaId) return;
    setSincronizando(true);
    setMsg(null);
    setErro(null);
    try {
      const r = await api.shopeeSync(Number(lojaId));
      setMsg(`${r.total} produtos sincronizados${r.erros ? ` · ${r.erros} erros` : ""}`);
      await carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao sincronizar");
    } finally {
      setSincronizando(false);
    }
  };

  const enviarEstoque = async (sku: string) => {
    if (!lojaId) return;
    const qtd = Number(quantidades[sku]);
    if (Number.isNaN(qtd)) return;
    setEnviando(sku);
    setMsg(null);
    try {
      const r = await api.shopeeAtualizarEstoqueProduto(sku, Number(lojaId), qtd);
      if (r.error) setErro(r.error);
      else { setMsg(`${sku}: estoque enviado à Shopee (${qtd} un)`); await carregar(); }
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao enviar estoque");
    } finally {
      setEnviando(null);
      setTimeout(() => setMsg(null), 4000);
    }
  };

  return (
    <div className="p-6 space-y-4 max-w-5xl">
      <div className="flex items-start justify-between">
        <div>
          <Link href="/integracoes/shopee" className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors">← Shopee</Link>
          <h1 className="text-lg font-light text-neutral-300 mt-1">Produtos Shopee</h1>
          <p className="text-xs text-neutral-500 mt-0.5">Produtos sincronizados de cada loja Shopee, com estoque atual e envio manual pro anúncio.</p>
        </div>
        <Link
          href="/produtos/novo"
          title="Cadastre o produto no catálogo e depois publique na aba 'Publicar Shopee' dele"
          className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs px-3 py-1.5 rounded-lg transition-colors shrink-0"
        >
          + Adicionar produto
        </Link>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <select
          value={lojaId}
          onChange={(e) => setLojaId(e.target.value ? Number(e.target.value) : "")}
          className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200"
        >
          {lojas.length === 0 && <option value="">Nenhuma loja com token ativo</option>}
          {lojas.map(l => <option key={l.id} value={l.id}>{l.nome}</option>)}
        </select>
        <button
          onClick={sincronizar}
          disabled={sincronizando || !lojaId}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors"
        >
          {sincronizando ? "Sincronizando..." : "Sincronizar com a Shopee"}
        </button>
      </div>

      {msg && <div className="text-xs px-3 py-2 rounded-lg border bg-green-950/40 border-green-900/50 text-green-400">{msg}</div>}
      {erro && <div className="text-xs px-3 py-2 rounded-lg border bg-red-950/40 border-red-900/50 text-red-400">{erro}</div>}

      {!loading && lojas.length === 0 && (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 text-center text-neutral-500 text-sm">
          Nenhuma loja Shopee com token ativo. Conecte uma loja na tela de Integrações antes de ver produtos.
        </div>
      )}

      {loading ? (
        <p className="text-xs text-neutral-500">Carregando...</p>
      ) : lojas.length > 0 && produtos.length === 0 ? (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 text-center text-neutral-500 text-sm">
          Nenhum produto sincronizado ainda. Clique em &quot;Sincronizar com a Shopee&quot;.
        </div>
      ) : produtos.length > 0 && (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-800 text-neutral-500 text-xs uppercase">
                  <th className="text-left px-4 py-3 font-medium">SKU</th>
                  <th className="text-left px-4 py-3 font-medium">Título</th>
                  <th className="text-right px-4 py-3 font-medium">Preço</th>
                  <th className="text-right px-4 py-3 font-medium">Estoque</th>
                  <th className="text-left px-4 py-3 font-medium">Status</th>
                  <th className="text-center px-4 py-3 font-medium">Editar</th>
                  <th className="text-center px-4 py-3 font-medium">Enviar estoque</th>
                </tr>
              </thead>
              <tbody>
                {produtos.map((p) => (
                  <tr key={p.sku} className="border-b border-neutral-800/50 hover:bg-neutral-800/20">
                    <td className="px-4 py-2.5 font-mono text-xs text-neutral-500">
                      <Link href={`/produtos/${p.sku}`} className="hover:text-indigo-400">{p.sku}</Link>
                    </td>
                    <td className="px-4 py-2.5 text-neutral-300 max-w-xs truncate">{p.titulo}</td>
                    <td className="px-4 py-2.5 text-right text-neutral-300 numeric">R$ {Number(p.preco || 0).toFixed(2)}</td>
                    <td className="px-4 py-2.5 text-right numeric font-medium">
                      <span className={Number(p.estoque) <= 0 ? "text-red-400" : Number(p.estoque) < 10 ? "text-amber-400" : "text-emerald-400"}>
                        {Number(p.estoque)}
                      </span>
                    </td>
                    <td className={`px-4 py-2.5 text-xs font-medium capitalize ${statusColor(p.status)}`}>{p.status}</td>
                    <td className="px-4 py-2.5 text-center">
                      <Link
                        href={`/produtos/${p.sku}?tab=shopee`}
                        className="text-[10px] bg-neutral-800 hover:bg-neutral-700 text-neutral-300 px-2 py-1 rounded inline-block"
                      >
                        Editar
                      </Link>
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center justify-center gap-1">
                        <input
                          type="number"
                          placeholder={String(p.estoque)}
                          value={quantidades[p.sku] ?? ""}
                          onChange={(e) => setQuantidades(q => ({ ...q, [p.sku]: e.target.value }))}
                          className="w-16 bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-right text-neutral-200"
                        />
                        <button
                          onClick={() => enviarEstoque(p.sku)}
                          disabled={enviando === p.sku || quantidades[p.sku] === undefined || quantidades[p.sku] === ""}
                          className="text-[10px] bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white px-2 py-1 rounded"
                        >
                          {enviando === p.sku ? "..." : "Enviar"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
