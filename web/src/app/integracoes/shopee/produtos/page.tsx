"use client";

import { Fragment, useState, useEffect, useCallback } from "react";
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

function itemIdDoAnuncio(anuncioId: string): number | null {
  const base = anuncioId.split("_")[0];
  const n = Number(base);
  return Number.isFinite(n) && n > 0 ? n : null;
}

function ProdutoThumb({ url, titulo }: { url?: string | null; titulo: string }) {
  const [falhou, setFalhou] = useState(false);
  if (!url || falhou) {
    return (
      <div className="w-8 h-8 rounded bg-neutral-800 border border-neutral-700 flex items-center justify-center text-[10px] text-neutral-500 shrink-0">
        {titulo.charAt(0).toUpperCase() || "?"}
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url}
      alt={titulo}
      className="w-8 h-8 rounded object-cover border border-neutral-700 shrink-0"
      onError={() => setFalhou(true)}
    />
  );
}

interface GrupoProduto {
  itemId: string;
  temVariacao: boolean;
  variacoes: ShopeeProdutoSincronizado[];
}

// anuncio_id vem "item_id" (produto simples) ou "item_id_model_id" (1 linha
// por variacao — ver shopee_sync.sync_produtos). Agrupar por item_id junta
// as variacoes do mesmo produto pai na Shopee sob 1 cabecalho expansivel.
function agruparPorProdutoPai(produtos: ShopeeProdutoSincronizado[]): GrupoProduto[] {
  const porItemId = new Map<string, ShopeeProdutoSincronizado[]>();
  for (const p of produtos) {
    const itemId = p.anuncio_id.split("_")[0];
    if (!porItemId.has(itemId)) porItemId.set(itemId, []);
    porItemId.get(itemId)!.push(p);
  }
  return Array.from(porItemId.entries()).map(([itemId, variacoes]) => ({
    itemId,
    temVariacao: variacoes.length > 1 || variacoes.some(v => v.anuncio_id.includes("_")),
    variacoes,
  }));
}

// Nome comum das variacoes costuma vir como "Produto - Variacao" (ver
// shopee_sync). Extrai so' o "Produto" (parte antes do primeiro " - ") pra
// exibir no cabecalho do grupo, sem repetir a variacao no titulo geral.
function nomeBaseProduto(titulo: string): string {
  return titulo.split(" - ")[0];
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
  const [gruposExpandidos, setGruposExpandidos] = useState<Set<string>>(new Set());
  const [duplicando, setDuplicando] = useState<{ sku: string; novoSku: string } | null>(null);
  const [salvandoDuplicata, setSalvandoDuplicata] = useState(false);
  const [clonando, setClonando] = useState<{ sku: string; itemId: number; destino: number | "" } | null>(null);
  const [clonandoEnviando, setClonandoEnviando] = useState(false);

  const toggleGrupo = (itemId: string) => {
    setGruposExpandidos(prev => {
      const next = new Set(prev);
      if (next.has(itemId)) next.delete(itemId); else next.add(itemId);
      return next;
    });
  };

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

  const confirmarDuplicar = async () => {
    if (!duplicando || !duplicando.novoSku.trim()) return;
    setSalvandoDuplicata(true);
    setMsg(null);
    setErro(null);
    try {
      const r = await api.shopeeDuplicarProduto(duplicando.sku, duplicando.novoSku.trim());
      if (r.error) setErro(r.error);
      else { setMsg(`Produto duplicado: ${r.produto?.sku}. Publique na aba Shopee dele.`); setDuplicando(null); }
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao duplicar produto");
    } finally {
      setSalvandoDuplicata(false);
    }
  };

  const abrirClonar = (p: ShopeeProdutoSincronizado) => {
    const itemId = itemIdDoAnuncio(p.anuncio_id);
    if (!itemId) { setErro(`${p.sku}: anuncio_id invalido para clonagem`); return; }
    setClonando({ sku: p.sku, itemId, destino: "" });
  };

  const confirmarClonar = async () => {
    if (!clonando || !lojaId || clonando.destino === "") return;
    setClonandoEnviando(true);
    setMsg(null);
    setErro(null);
    try {
      const r = await api.shopeeClonarProdutoParaLoja(clonando.itemId, Number(lojaId), Number(clonando.destino));
      if (r.error) setErro(r.error);
      else if (r.sucesso === false) setErro(r.mensagem || "Falha ao clonar produto");
      else { setMsg(r.mensagem || `${clonando.sku}: clonado com sucesso`); setClonando(null); }
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao clonar produto para outra loja");
    } finally {
      setClonandoEnviando(false);
    }
  };

  function LinhaProduto({ p, indentado }: { p: ShopeeProdutoSincronizado; indentado?: boolean }) {
    return (
      <>
        <tr className={`border-b border-neutral-800/50 hover:bg-neutral-800/20 ${indentado ? "bg-neutral-950/30" : ""}`}>
          <td className="pl-4 py-2.5">
            <ProdutoThumb url={p.imagem_url} titulo={p.titulo} />
          </td>
          <td className={`px-4 py-2.5 font-mono text-xs text-neutral-500 ${indentado ? "pl-8" : ""}`}>
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
                onKeyDown={(e) => { if (e.key === "Enter" && quantidades[p.sku]) enviarEstoque(p.sku); }}
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
          <td className="px-4 py-2.5">
            <div className="flex items-center justify-center gap-1">
              <button
                onClick={() => setDuplicando({ sku: p.sku, novoSku: "" })}
                className="text-[10px] bg-neutral-800 hover:bg-neutral-700 text-neutral-300 px-2 py-1 rounded"
              >
                Duplicar
              </button>
              <button
                onClick={() => abrirClonar(p)}
                disabled={lojas.length < 2}
                title={lojas.length < 2 ? "Conecte outra loja Shopee para clonar" : "Clonar este produto para outra loja Shopee"}
                className="text-[10px] bg-indigo-700 hover:bg-indigo-600 disabled:opacity-40 text-white px-2 py-1 rounded"
              >
                Clonar p/ loja
              </button>
            </div>
          </td>
        </tr>
        {duplicando?.sku === p.sku && (
          <tr className="border-b border-neutral-800/50 bg-neutral-800/30">
            <td colSpan={9} className="px-4 py-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-neutral-400">Novo SKU para a cópia de <span className="font-mono">{p.sku}</span>:</span>
                <input
                  type="text"
                  autoFocus
                  value={duplicando.novoSku}
                  onChange={(e) => setDuplicando(d => d && { ...d, novoSku: e.target.value })}
                  onKeyDown={(e) => { if (e.key === "Enter") confirmarDuplicar(); if (e.key === "Escape") setDuplicando(null); }}
                  placeholder="ex: SKU-COPIA"
                  className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200 w-40"
                />
                <button
                  onClick={confirmarDuplicar}
                  disabled={salvandoDuplicata || !duplicando.novoSku.trim()}
                  className="text-[10px] bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-2 py-1 rounded"
                >
                  {salvandoDuplicata ? "..." : "Confirmar"}
                </button>
                <button
                  onClick={() => setDuplicando(null)}
                  className="text-[10px] bg-neutral-700 hover:bg-neutral-600 text-neutral-300 px-2 py-1 rounded"
                >
                  Cancelar
                </button>
              </div>
            </td>
          </tr>
        )}
        {clonando?.sku === p.sku && (
          <tr className="border-b border-neutral-800/50 bg-neutral-800/30">
            <td colSpan={9} className="px-4 py-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-neutral-400">Clonar <span className="font-mono">{p.sku}</span> para:</span>
                <select
                  autoFocus
                  value={clonando.destino}
                  onChange={(e) => setClonando(c => c && { ...c, destino: e.target.value ? Number(e.target.value) : "" })}
                  className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200"
                >
                  <option value="">Selecione a loja destino</option>
                  {lojas.filter(l => l.id !== Number(lojaId)).map(l => (
                    <option key={l.id} value={l.id}>{l.nome}</option>
                  ))}
                </select>
                <button
                  onClick={confirmarClonar}
                  disabled={clonandoEnviando || clonando.destino === ""}
                  className="text-[10px] bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white px-2 py-1 rounded"
                >
                  {clonandoEnviando ? "..." : "Confirmar"}
                </button>
                <button
                  onClick={() => setClonando(null)}
                  className="text-[10px] bg-neutral-700 hover:bg-neutral-600 text-neutral-300 px-2 py-1 rounded"
                >
                  Cancelar
                </button>
              </div>
            </td>
          </tr>
        )}
      </>
    );
  }

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
                  <th className="px-4 py-3 font-medium"></th>
                  <th className="text-left px-4 py-3 font-medium">SKU</th>
                  <th className="text-left px-4 py-3 font-medium">Título</th>
                  <th className="text-right px-4 py-3 font-medium">Preço</th>
                  <th className="text-right px-4 py-3 font-medium">Estoque</th>
                  <th className="text-left px-4 py-3 font-medium">Status</th>
                  <th className="text-center px-4 py-3 font-medium">Editar</th>
                  <th className="text-center px-4 py-3 font-medium">Enviar estoque</th>
                  <th className="text-center px-4 py-3 font-medium">Ações</th>
                </tr>
              </thead>
              <tbody>
                {agruparPorProdutoPai(produtos).map((grupo) => {
                  if (!grupo.temVariacao) {
                    return <LinhaProduto key={grupo.itemId} p={grupo.variacoes[0]} />;
                  }
                  const expandido = gruposExpandidos.has(grupo.itemId);
                  const estoqueTotal = grupo.variacoes.reduce((s, v) => s + Number(v.estoque || 0), 0);
                  return (
                    <Fragment key={grupo.itemId}>
                      <tr
                        onClick={() => toggleGrupo(grupo.itemId)}
                        className="border-b border-neutral-800/50 hover:bg-neutral-800/30 cursor-pointer bg-neutral-800/10"
                      >
                        <td className="px-4 py-2.5 text-neutral-500 text-xs" colSpan={3}>
                          <span className="inline-flex items-center gap-1.5">
                            <span className={`text-neutral-600 transition-transform ${expandido ? "rotate-90" : ""}`}>›</span>
                            <span className="text-neutral-200">{nomeBaseProduto(grupo.variacoes[0].titulo)}</span>
                            <span className="text-[10px] bg-indigo-900/30 text-indigo-400 px-1.5 py-0.5 rounded-full shrink-0">
                              {grupo.variacoes.length} variações
                            </span>
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-right text-neutral-600 numeric text-xs">—</td>
                        <td className="px-4 py-2.5 text-right numeric font-medium text-xs">
                          <span className={estoqueTotal <= 0 ? "text-red-400" : "text-neutral-400"}>{estoqueTotal} total</span>
                        </td>
                        <td colSpan={4}></td>
                      </tr>
                      {expandido && grupo.variacoes.map((v) => (
                        <LinhaProduto key={v.sku} p={v} indentado />
                      ))}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
