"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { ShopeeProdutoSincronizado } from "@/lib/api";
import Icon from "@/app/_components/Icon";
import ProdutoVariacoesModal from "./_components/ProdutoVariacoesModal";

type EstoqueFiltro = "todos" | "zerado" | "baixo" | "normal";
type ModoVisualizacao = "cards" | "lista";
type Densidade = "compacto" | "padrao" | "grande";

const DENSIDADE_CARDS: Record<Densidade, { rotulo: string; grid: string; thumb: string; padding: string; titulo: string }> = {
  compacto: { rotulo: "Compacto", grid: "grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5", thumb: "w-10 h-10", padding: "p-2", titulo: "text-xs" },
  padrao: { rotulo: "Padrão", grid: "grid-cols-1 md:grid-cols-2 xl:grid-cols-3", thumb: "w-12 h-12", padding: "p-3", titulo: "text-sm" },
  grande: { rotulo: "Grande", grid: "grid-cols-1 sm:grid-cols-2 xl:grid-cols-2", thumb: "w-16 h-16", padding: "p-4", titulo: "text-base" },
};

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

function statusPillClasses(status: string) {
  if (status === "normal") return "bg-emerald-950/40 border-emerald-900/50 text-emerald-400";
  if (status === "unlist" || status === "banned") return "bg-red-950/40 border-red-900/50 text-red-400";
  return "bg-amber-950/40 border-amber-900/50 text-amber-400";
}

function estoqueTextColor(estoque: number) {
  return estoque <= 0 ? "text-red-400" : estoque < 10 ? "text-amber-400" : "text-emerald-400";
}

function faixaPreco(variacoes: ShopeeProdutoSincronizado[]): string {
  const precos = variacoes.map(v => Number(v.preco || 0));
  const min = Math.min(...precos);
  const max = Math.max(...precos);
  const fmt = (n: number) => n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return min === max ? `R$ ${fmt(min)}` : `R$ ${fmt(min)} – R$ ${fmt(max)}`;
}

function classificarEstoque(estoque: number): EstoqueFiltro {
  if (estoque <= 0) return "zerado";
  if (estoque < 10) return "baixo";
  return "normal";
}

const ROTULO_ESTOQUE: Record<EstoqueFiltro, string> = {
  todos: "Todos",
  zerado: "Sem estoque",
  baixo: "Baixo estoque (<10)",
  normal: "Estoque normal (≥10)",
};

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

function EstoqueHealthBar({ variacoes }: { variacoes: ShopeeProdutoSincronizado[] }) {
  const total = variacoes.length;
  if (total <= 1) return null;
  const zerado = variacoes.filter(v => classificarEstoque(Number(v.estoque)) === "zerado").length;
  const baixo = variacoes.filter(v => classificarEstoque(Number(v.estoque)) === "baixo").length;
  const normal = total - zerado - baixo;
  return (
    <div
      className="flex h-1.5 w-20 rounded-full overflow-hidden bg-neutral-800 shrink-0"
      title={`${normal} normal · ${baixo} baixo · ${zerado} sem estoque`}
    >
      {normal > 0 && <div className="bg-emerald-500" style={{ width: `${(normal / total) * 100}%` }} />}
      {baixo > 0 && <div className="bg-amber-500" style={{ width: `${(baixo / total) * 100}%` }} />}
      {zerado > 0 && <div className="bg-red-500" style={{ width: `${(zerado / total) * 100}%` }} />}
    </div>
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

// Complemento de nomeBaseProduto: a parte depois do primeiro " - ", que
// identifica a variacao (ex: "Azul - 38"). Sem esse separador, o titulo
// inteiro nao segue a convencao — mostra ele mesmo como fallback.
function sufixoVariacao(titulo: string): string {
  const partes = titulo.split(" - ");
  return partes.length > 1 ? partes.slice(1).join(" - ") : titulo;
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
  const [modalGrupo, setModalGrupo] = useState<GrupoProduto | null>(null);
  const [busca, setBusca] = useState("");
  const [statusFiltro, setStatusFiltro] = useState("");
  const [estoqueFiltro, setEstoqueFiltro] = useState<EstoqueFiltro>("todos");
  const [somenteVariacao, setSomenteVariacao] = useState(false);
  const [viewMode, setViewMode] = useState<ModoVisualizacao>("cards");
  const [densidade, setDensidade] = useState<Densidade>("padrao");

  const statusDisponiveis = useMemo(
    () => Array.from(new Set(produtos.map(p => p.status))).sort(),
    [produtos]
  );

  const gruposFiltrados = useMemo(() => {
    const q = busca.trim().toLowerCase();
    const bateFiltro = (p: ShopeeProdutoSincronizado) =>
      (q === "" || p.sku.toLowerCase().includes(q) || p.titulo.toLowerCase().includes(q)) &&
      (statusFiltro === "" || p.status === statusFiltro) &&
      (estoqueFiltro === "todos" || classificarEstoque(Number(p.estoque)) === estoqueFiltro);

    return agruparPorProdutoPai(produtos)
      .filter(g => !somenteVariacao || g.temVariacao)
      .map(g => ({ ...g, variacoesFiltradas: g.variacoes.filter(bateFiltro) }))
      .filter(g => g.variacoesFiltradas.length > 0);
  }, [produtos, busca, statusFiltro, estoqueFiltro, somenteVariacao]);

  const totalLinhasFiltradas = gruposFiltrados.reduce((s, g) => s + g.variacoesFiltradas.length, 0);

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

  function LinhaProduto({ p, indentado, variacaoLabel }: { p: ShopeeProdutoSincronizado; indentado?: boolean; variacaoLabel?: string }) {
    return (
      <>
        <tr className={`border-b border-neutral-800/50 hover:bg-neutral-800/30 transition-colors ${indentado ? "bg-neutral-950/30" : ""}`}>
          <td className="pl-4 py-3">
            <ProdutoThumb url={p.imagem_url} titulo={p.titulo} />
          </td>
          <td className={`px-4 py-3 font-mono text-xs text-neutral-500 ${indentado ? "pl-8" : ""}`}>
            <Link href={`/produtos/${p.sku}`} className="hover:text-indigo-400">{p.sku}</Link>
          </td>
          <td className="px-4 py-3 max-w-xs truncate" title={p.titulo}>
            {variacaoLabel ? (
              <span className="text-neutral-400">{variacaoLabel}</span>
            ) : (
              <span className="text-neutral-300">{p.titulo}</span>
            )}
          </td>
          <td className="px-4 py-3 text-right text-neutral-300 numeric">R$ {Number(p.preco || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
          <td className="px-4 py-3 text-right numeric font-medium">
            <span className={Number(p.estoque) <= 0 ? "text-red-400" : Number(p.estoque) < 10 ? "text-amber-400" : "text-emerald-400"}>
              {Number(p.estoque)}
            </span>
          </td>
          <td className={`px-4 py-3 text-xs font-medium capitalize ${statusColor(p.status)}`}>{p.status}</td>
          <td className="px-4 py-3 text-center">
            <Link
              href={`/produtos/${p.sku}?tab=shopee`}
              className="text-xs bg-neutral-800 hover:bg-neutral-700 text-neutral-300 px-2 py-1 rounded inline-block"
            >
              Editar
            </Link>
          </td>
          <td className="px-4 py-3">
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
                className="text-xs bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white px-2 py-1 rounded"
              >
                {enviando === p.sku ? "..." : "Enviar"}
              </button>
            </div>
          </td>
        </tr>
      </>
    );
  }

  function ProdutoAcoes({ p }: { p: ShopeeProdutoSincronizado }) {
    return (
      <div className="flex flex-wrap items-center gap-1.5">
        <input
          type="number"
          placeholder={String(p.estoque)}
          value={quantidades[p.sku] ?? ""}
          onChange={(e) => setQuantidades(q => ({ ...q, [p.sku]: e.target.value }))}
          onKeyDown={(e) => { if (e.key === "Enter" && quantidades[p.sku]) enviarEstoque(p.sku); }}
          className="w-14 bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-right text-neutral-200"
        />
        <button
          onClick={() => enviarEstoque(p.sku)}
          disabled={enviando === p.sku || quantidades[p.sku] === undefined || quantidades[p.sku] === ""}
          className="text-xs bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white px-2 py-1 rounded"
        >
          {enviando === p.sku ? "..." : "Enviar"}
        </button>
        <Link
          href={`/produtos/${p.sku}?tab=shopee`}
          className="text-xs bg-neutral-800 hover:bg-neutral-700 text-neutral-300 px-2 py-1 rounded"
        >
          Editar
        </Link>
      </div>
    );
  }

  function LinhaCard({ p, variacaoLabel }: { p: ShopeeProdutoSincronizado; variacaoLabel?: string }) {
    const cfg = DENSIDADE_CARDS[densidade];
    return (
      <div className={`${cfg.padding} flex flex-col gap-2`}>
        <div className="flex items-center gap-3">
          <ProdutoThumb url={p.imagem_url} titulo={p.titulo} tamanho={cfg.thumb} />
          <div className="flex-1 min-w-0">
            <p className={`${cfg.titulo} text-neutral-200 truncate`} title={p.titulo}>{variacaoLabel ?? p.titulo}</p>
            <Link href={`/produtos/${p.sku}`} className="font-mono text-xs text-neutral-500 hover:text-indigo-400">{p.sku}</Link>
          </div>
          <div className="text-right shrink-0">
            <p className="numeric text-sm text-neutral-300">R$ {Number(p.preco || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
            <p className={`numeric text-xs font-medium ${estoqueTextColor(Number(p.estoque))}`}>{Number(p.estoque)} un</p>
          </div>
          <span className={`text-xs px-2 py-0.5 rounded-full border capitalize shrink-0 ${statusPillClasses(p.status)}`}>{p.status}</span>
        </div>
        <ProdutoAcoes p={p} />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <Link href="/integracoes/shopee" className="text-xs text-neutral-500 hover:text-neutral-300 transition-colors inline-flex items-center gap-1"><Icon name="chevronLeft" size={14} /> Shopee</Link>
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
        <>
          <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 flex flex-wrap items-center gap-3">
            <input
              type="text"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Buscar por SKU ou título..."
              className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 w-56 placeholder:text-neutral-500"
            />
            <select
              value={statusFiltro}
              onChange={(e) => setStatusFiltro(e.target.value)}
              className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 capitalize"
            >
              <option value="">Todos os status</option>
              {statusDisponiveis.map(s => <option key={s} value={s} className="capitalize">{s}</option>)}
            </select>
            <select
              value={estoqueFiltro}
              onChange={(e) => setEstoqueFiltro(e.target.value as EstoqueFiltro)}
              className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200"
            >
              {(Object.keys(ROTULO_ESTOQUE) as EstoqueFiltro[]).map(k => (
                <option key={k} value={k}>{ROTULO_ESTOQUE[k]}</option>
              ))}
            </select>
            <label className="flex items-center gap-2 text-sm text-neutral-400 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={somenteVariacao}
                onChange={(e) => setSomenteVariacao(e.target.checked)}
                className="accent-indigo-500"
              />
              Só com variação
            </label>
            <div className="flex items-center gap-3 ml-auto">
              {viewMode === "cards" && (
                <div className="flex items-center bg-neutral-800 border border-neutral-700 rounded-lg p-0.5">
                  {(Object.keys(DENSIDADE_CARDS) as Densidade[]).map(d => (
                    <button
                      key={d}
                      onClick={() => setDensidade(d)}
                      title={`Cards ${DENSIDADE_CARDS[d].rotulo.toLowerCase()}`}
                      className={`text-xs px-3 py-1.5 rounded-md transition-colors ${densidade === d ? "bg-neutral-700 text-neutral-100" : "text-neutral-500 hover:text-neutral-300"}`}
                    >
                      {DENSIDADE_CARDS[d].rotulo}
                    </button>
                  ))}
                </div>
              )}
              <div className="flex items-center bg-neutral-800 border border-neutral-700 rounded-lg p-0.5">
                <button
                  onClick={() => setViewMode("cards")}
                  className={`text-xs px-3 py-1.5 rounded-md transition-colors ${viewMode === "cards" ? "bg-neutral-700 text-neutral-100" : "text-neutral-500 hover:text-neutral-300"}`}
                >
                  Cards
                </button>
                <button
                  onClick={() => setViewMode("lista")}
                  className={`text-xs px-3 py-1.5 rounded-md transition-colors ${viewMode === "lista" ? "bg-neutral-700 text-neutral-100" : "text-neutral-500 hover:text-neutral-300"}`}
                >
                  Lista
                </button>
              </div>
              <span className="text-xs text-neutral-500">
                {totalLinhasFiltradas} de {produtos.length} produtos
              </span>
            </div>
          </div>

          {gruposFiltrados.length === 0 ? (
            <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 text-center text-neutral-500 text-sm">
              Nenhum produto encontrado com esses filtros.
            </div>
          ) : viewMode === "cards" ? (
            <div className={`instrument-enter grid ${DENSIDADE_CARDS[densidade].grid} gap-4`}>
              {gruposFiltrados.map((grupo) => {
                if (!grupo.temVariacao) {
                  return (
                    <div key={grupo.itemId} className="instrument-hover bg-neutral-900 border border-neutral-800 rounded-xl">
                      <LinhaCard p={grupo.variacoesFiltradas[0]} />
                    </div>
                  );
                }
                const parcial = grupo.variacoesFiltradas.length < grupo.variacoes.length;
                const estoqueTotal = grupo.variacoesFiltradas.reduce((s, v) => s + Number(v.estoque || 0), 0);
                const cfg = DENSIDADE_CARDS[densidade];
                return (
                  <div key={grupo.itemId} className="instrument-hover bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden">
                    <div onClick={() => setModalGrupo(grupo)} className={`${cfg.padding} flex items-center gap-3 cursor-pointer`}>
                      <ProdutoThumb url={grupo.variacoesFiltradas[0].imagem_url} titulo={grupo.variacoesFiltradas[0].titulo} tamanho={cfg.thumb} />
                      <div className="flex-1 min-w-0">
                        <p className={`${cfg.titulo} text-neutral-200 truncate`}>{nomeBaseProduto(grupo.variacoesFiltradas[0].titulo)}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-xs bg-indigo-900/30 text-indigo-400 px-1.5 py-0.5 rounded-full shrink-0">
                            {parcial ? `${grupo.variacoesFiltradas.length} de ${grupo.variacoes.length} variações` : `${grupo.variacoes.length} variações`}
                          </span>
                          <span className="text-xs text-neutral-500 numeric">{faixaPreco(grupo.variacoesFiltradas)}</span>
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-1 shrink-0">
                        <span className={`numeric text-xs font-medium ${estoqueTotal <= 0 ? "text-red-400" : "text-neutral-400"}`}>{estoqueTotal} un total</span>
                        <EstoqueHealthBar variacoes={grupo.variacoesFiltradas} />
                      </div>
                      <span className="text-neutral-600 shrink-0"><Icon name="chevronRight" size={14} /></span>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
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
                    </tr>
                  </thead>
                  <tbody>
                    {gruposFiltrados.map((grupo) => {
                      if (!grupo.temVariacao) {
                        return <LinhaProduto key={grupo.itemId} p={grupo.variacoesFiltradas[0]} />;
                      }
                      const parcial = grupo.variacoesFiltradas.length < grupo.variacoes.length;
                      const estoqueTotal = grupo.variacoesFiltradas.reduce((s, v) => s + Number(v.estoque || 0), 0);
                      return (
                        <tr
                          key={grupo.itemId}
                          onClick={() => setModalGrupo(grupo)}
                          className="border-b border-neutral-800/50 hover:bg-neutral-800/40 cursor-pointer bg-neutral-800/10"
                        >
                          <td className="px-4 py-3 text-neutral-500 text-xs" colSpan={3}>
                            <span className="inline-flex items-center gap-1.5">
                              <span className="text-neutral-600"><Icon name="chevronRight" size={14} /></span>
                              <span className="text-neutral-200">{nomeBaseProduto(grupo.variacoesFiltradas[0].titulo)}</span>
                              <span className="text-xs bg-indigo-900/30 text-indigo-400 px-1.5 py-0.5 rounded-full shrink-0">
                                {parcial ? `${grupo.variacoesFiltradas.length} de ${grupo.variacoes.length} variações` : `${grupo.variacoes.length} variações`}
                              </span>
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right text-neutral-600 numeric text-xs">—</td>
                          <td className="px-4 py-3 text-right numeric font-medium text-xs">
                            <span className={estoqueTotal <= 0 ? "text-red-400" : "text-neutral-400"}>{estoqueTotal} total</span>
                          </td>
                          <td colSpan={3}></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
      {modalGrupo && (
        <ProdutoVariacoesModal
          itemId={modalGrupo.itemId}
          variacoes={modalGrupo.variacoes}
          quantidades={quantidades}
          setQuantidades={setQuantidades}
          enviando={enviando}
          onEnviarEstoque={enviarEstoque}
          onClose={() => setModalGrupo(null)}
        />
      )}
    </div>
  );
}
