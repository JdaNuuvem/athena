"use client";

import { useState, useEffect, useCallback } from "react";
import { api, ShopeeCategoria, ShopeeAtributo, ShopeeMarca } from "@/lib/api";
import Icon from "@/app/_components/Icon";

interface Props {
  produto: Record<string, unknown> | null;
  sku: string;
}

interface Breadcrumb { id: number; nome: string; }
interface ImagemAnuncio { id: string; preview: string; }
interface FaixaAtacado { min: string; max: string; preco: string; }

const MAX_IMAGENS = 9;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <fieldset className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-4"><legend className="text-sm font-medium text-neutral-300 px-1">{title}</legend>{children}</fieldset>;
}
function InputGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="space-y-1"><label className="text-[10px] text-neutral-500 uppercase tracking-wider">{label}</label>{children}</div>;
}
const inputCls = "w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500";

export default function PublicarShopeeTab({ produto, sku }: Props) {
  const p = produto as any;

  // ── Loja ──
  const [lojas, setLojas] = useState<Array<{ id: number; nome: string }>>([]);
  const [lojaId, setLojaId] = useState<number | null>(null);

  // ── Categoria ──
  const [busca, setBusca] = useState("");
  const [resultados, setResultados] = useState<ShopeeCategoria[]>([]);
  const [breadcrumb, setBreadcrumb] = useState<Breadcrumb[]>([]);
  const [categoriaSelecionada, setCategoriaSelecionada] = useState<ShopeeCategoria | null>(null);
  const [carregandoCategorias, setCarregandoCategorias] = useState(false);

  // ── Atributos e marca (compartilhado entre criação e edição) ──
  const [atributos, setAtributos] = useState<ShopeeAtributo[]>([]);
  const [valoresAtributos, setValoresAtributos] = useState<Record<number, string>>({});
  const [marcas, setMarcas] = useState<ShopeeMarca[]>([]);
  const [marcaObrigatoria, setMarcaObrigatoria] = useState(false);
  const [marcaId, setMarcaId] = useState<number>(0);

  // ── Imagens (compartilhado — lista, ate MAX_IMAGENS) ──
  const [imagens, setImagens] = useState<ImagemAnuncio[]>([]);
  const [enviandoImagem, setEnviandoImagem] = useState(false);

  // ── Campos adicionais da Shopee ──
  const [condicao, setCondicao] = useState<"NEW" | "USED">("NEW");
  const [preOrderAtivo, setPreOrderAtivo] = useState(false);
  const [diasParaEnvio, setDiasParaEnvio] = useState("7");
  const [wholesale, setWholesale] = useState<FaixaAtacado[]>([]);
  const [gtinCode, setGtinCode] = useState("");

  // ── Dados finais ──
  const [form, setForm] = useState({
    nome: "", descricao: "", preco: "", estoque: "",
    peso: "", largura: "", altura: "", profundidade: "",
  });

  const [publicando, setPublicando] = useState(false);
  const [resultado, setResultado] = useState<{ ok: boolean; texto: string } | null>(null);
  const [bloqueioMargem, setBloqueioMargem] = useState<{ margem_valor: number; margem_pct: number; custo: number; frete: number; comissao_valor: number } | null>(null);

  // ── Modo edicao (produto ja publicado nesta loja) ──
  const [lojasComShopId, setLojasComShopId] = useState<Record<number, string>>({});
  const [itemIdExistente, setItemIdExistente] = useState<number | null>(null);
  const [ehVariacao, setEhVariacao] = useState(false);
  const [modoEdicao, setModoEdicao] = useState(false);
  const [carregandoEdicao, setCarregandoEdicao] = useState(false);
  const [formEdicao, setFormEdicao] = useState({ nome: "", descricao: "", preco: "", estoque: "", peso: "", largura: "", altura: "", profundidade: "" });
  const [salvandoEdicao, setSalvandoEdicao] = useState(false);
  const [estoqueReservado, setEstoqueReservado] = useState<number | null>(null);
  const [excluindo, setExcluindo] = useState(false);

  const carregarAtributosMarcas = useCallback(async (categoryId: number, lojaAtual?: number | null) => {
    const [attrR, brandR] = await Promise.all([
      api.shopeeAtributos(categoryId, lojaAtual ?? lojaId ?? undefined),
      api.shopeeMarcas(categoryId, lojaAtual ?? lojaId ?? undefined),
    ]);
    setAtributos(attrR.atributos || []);
    setMarcas(brandR.marcas || []);
    setMarcaObrigatoria(brandR.obrigatorio);
    // ponytail: tenta casar com a marca ja cadastrada no catalogo interno (Bling),
    // pra nao obrigar o usuario a re-escolher uma marca que ja existe no produto.
    const nomeMarcaCadastro = String(p?.marca || "").trim().toLowerCase();
    if (nomeMarcaCadastro) {
      const match = (brandR.marcas || []).find(m => m.original_brand_name.trim().toLowerCase() === nomeMarcaCadastro);
      if (match) setMarcaId(match.brand_id);
    }
    return { atributos: attrR.atributos || [], marcas: brandR.marcas || [] };
  }, [lojaId, p?.marca]);

  useEffect(() => {
    api.shopeeLojas().then(r => {
      const l = r.lojas || [];
      setLojas(l);
      if (l.length === 1) setLojaId(l[0].id);
      const mapa: Record<number, string> = {};
      for (const loja of l as Array<{ id: number; shopee_shop_id?: string }>) {
        if (loja.shopee_shop_id) mapa[loja.id] = loja.shopee_shop_id;
      }
      setLojasComShopId(mapa);
    }).catch(() => {});

    setForm(f => ({
      ...f,
      nome: String(p?.descricao || p?.nome || "").slice(0, 120),
      descricao: String(p?.descricao_complementar || p?.descricao_curta || p?.descricao || ""),
      preco: String(p?.valor || ""),
      estoque: String(p?.estoque_atual || ""),
      peso: String(p?.peso_bruto || ""),
      largura: String(p?.largura || ""),
      altura: String(p?.altura || ""),
      profundidade: String(p?.profundidade || ""),
    }));
    setGtinCode(String(p?.codigo_barras || ""));
  }, [p]);

  // Detecta se o produto ja esta publicado na loja selecionada (via estoque_lojas do detalhe)
  useEffect(() => {
    setItemIdExistente(null);
    setModoEdicao(false);
    setAtributos([]);
    setMarcas([]);
    setMarcaId(0);
    setImagens([]);
    setEstoqueReservado(null);
    if (!lojaId) return;
    const shopId = lojasComShopId[lojaId];
    if (!shopId) return;
    const anuncios = (p?.estoque_lojas || []) as Array<{ marketplace: string; shop_id?: string; anuncio_id?: string }>;
    const existente = anuncios.find(a => a.marketplace === "shopee" && a.shop_id === shopId && a.anuncio_id);
    if (!existente?.anuncio_id) return;
    // anuncio_id de uma variacao vem como "item_id_model_id" (ver
    // shopee_sync.sync_produtos) — o item_id do produto pai e' sempre a
    // primeira parte, mesmo formato usado sem variacao.
    const [itemIdStr, modelIdStr] = existente.anuncio_id.split("_");
    const itemId = Number(itemIdStr);
    setItemIdExistente(itemId);
    setEhVariacao(!!modelIdStr);
    setModoEdicao(true);
    setCarregandoEdicao(true);
    api.shopeeDetalheProduto(itemId, lojaId).then(async (r) => {
      const item = r.item || {};
      const priceInfo = (item.price_info as Array<{ current_price?: number }> | undefined)?.[0];
      const stockInfo = (item.stock_info_v2 as { summary_info?: { total_available_stock?: number; total_reserved_stock?: number } } | undefined)?.summary_info;
      const dimension = (item.dimension as { package_length?: number; package_width?: number; package_height?: number } | undefined) || {};
      // Produto com variacao: price_info/stock_info_v2 do item pai vem
      // zerado (o real esta no model). Usa o estoque desse SKU especifico
      // (ja correto) direto do catalogo interno em vez do item pai.
      setFormEdicao({
        nome: String(item.item_name || ""),
        descricao: String(item.description || ""),
        preco: modelIdStr ? "" : String(priceInfo?.current_price ?? ""),
        estoque: modelIdStr ? String(p?.estoque_atual ?? "") : String(stockInfo?.total_available_stock ?? ""),
        peso: String(item.weight ?? ""),
        largura: String(dimension.package_length ?? ""),
        altura: String(dimension.package_height ?? ""),
        profundidade: String(dimension.package_width ?? ""),
      });
      setEstoqueReservado(typeof stockInfo?.total_reserved_stock === "number" ? stockInfo.total_reserved_stock : null);

      const image = (item.image as { image_id_list?: string[]; image_url_list?: string[] } | undefined) || {};
      const ids = image.image_id_list || [];
      const urls = image.image_url_list || [];
      setImagens(ids.map((id, i) => ({ id, preview: urls[i] || "" })));

      const categoryId = Number(item.category_id || 0);
      if (categoryId) {
        await carregarAtributosMarcas(categoryId, lojaId);
        const attributeList = (item.attribute_list as Array<{ attribute_id: number; attribute_value_list?: Array<{ value_id?: number; original_value_name?: string }> }> | undefined) || [];
        const valores: Record<number, string> = {};
        for (const a of attributeList) {
          const v = a.attribute_value_list?.[0];
          if (v) valores[a.attribute_id] = v.value_id != null ? String(v.value_id) : String(v.original_value_name || "");
        }
        setValoresAtributos(valores);
        const brandId = (item.brand as { brand_id?: number } | undefined)?.brand_id;
        setMarcaId(brandId || 0);
      }
    }).catch(() => {}).finally(() => setCarregandoEdicao(false));
  }, [lojaId, lojasComShopId, p, carregarAtributosMarcas]);

  const buildAttributeList = () => atributos
    .filter(a => valoresAtributos[a.attribute_id])
    .map(a => {
      const valor = valoresAtributos[a.attribute_id];
      if (a.attribute_value_list?.length) {
        return { attribute_id: a.attribute_id, attribute_value_list: [{ value_id: Number(valor) }] };
      }
      return { attribute_id: a.attribute_id, attribute_value_list: [{ original_value_name: valor }] };
    });

  const buildDimension = (largura: string, altura: string, profundidade: string) => {
    if (!largura && !altura && !profundidade) return undefined;
    return {
      package_length: Number(largura) || 1,
      package_width: Number(profundidade) || 1,
      package_height: Number(altura) || 1,
    };
  };

  const salvarEdicao = async () => {
    if (!lojaId || !itemIdExistente) return;
    setSalvandoEdicao(true);
    setResultado(null);
    try {
      const payload: Record<string, unknown> = {
        item_name: formEdicao.nome,
        description: formEdicao.descricao,
        weight: Number(formEdicao.peso) || undefined,
      };
      const dimension = buildDimension(formEdicao.largura, formEdicao.altura, formEdicao.profundidade);
      if (dimension) payload.dimension = dimension;
      if (!ehVariacao) {
        const attributeList = buildAttributeList();
        if (attributeList.length) payload.attribute_list = attributeList;
        if (marcaId) payload.brand = { brand_id: marcaId };
        if (imagens.length) payload.image = { image_id_list: imagens.map(i => i.id) };
        if (gtinCode.trim()) payload.gtin_code = gtinCode.trim();
      }
      const r = await api.shopeeEditarProdutoShopee(itemIdExistente, lojaId, payload);
      if (r.error) {
        setResultado({ ok: false, texto: r.error });
      } else {
        const precoNum = Number(formEdicao.preco);
        const estoqueNum = Number(formEdicao.estoque);
        // Produto com variacao nao tem preco a nivel de item (so' por model_id,
        // via product/update_price) — update_price(item_id) sem model_id nao
        // se aplica e a Shopee ignoraria/rejeitaria.
        if (!ehVariacao && precoNum > 0) await api.shopeeAtualizarPreco(itemIdExistente, lojaId, precoNum);
        if (!Number.isNaN(estoqueNum)) await api.shopeeAtualizarEstoqueProduto(sku, lojaId, estoqueNum);
        setResultado({ ok: true, texto: "Anúncio atualizado na Shopee." });
      }
    } catch (e) {
      setResultado({ ok: false, texto: e instanceof Error ? e.message : "Erro ao salvar alterações" });
    } finally {
      setSalvandoEdicao(false);
    }
  };

  const excluirDaShopee = async () => {
    if (!lojaId || !itemIdExistente) return;
    if (!window.confirm(`Excluir definitivamente o anúncio item_id ${itemIdExistente} da Shopee? Esta ação não pode ser desfeita.`)) return;
    setExcluindo(true);
    setResultado(null);
    try {
      const r = await api.shopeeDeletarProdutoShopee(itemIdExistente, lojaId);
      if (r.error) setResultado({ ok: false, texto: r.error });
      else {
        setResultado({ ok: true, texto: "Anúncio excluído da Shopee." });
        setModoEdicao(false);
        setItemIdExistente(null);
      }
    } catch (e) {
      setResultado({ ok: false, texto: e instanceof Error ? e.message : "Erro ao excluir anúncio" });
    } finally {
      setExcluindo(false);
    }
  };

  const carregarCategorias = useCallback(async (parentId?: number) => {
    setCarregandoCategorias(true);
    try {
      const r = await api.shopeeCategorias({ parentId: parentId ?? 0 });
      setResultados(r.categorias || []);
    } finally {
      setCarregandoCategorias(false);
    }
  }, []);

  useEffect(() => { if (!categoriaSelecionada) carregarCategorias(0); }, [carregarCategorias, categoriaSelecionada]);

  const buscarCategorias = async () => {
    if (!busca.trim()) { setBreadcrumb([]); carregarCategorias(0); return; }
    setCarregandoCategorias(true);
    try {
      const r = await api.shopeeCategorias({ busca });
      setResultados(r.categorias || []);
      setBreadcrumb([]);
    } finally {
      setCarregandoCategorias(false);
    }
  };

  const abrirCategoria = async (c: ShopeeCategoria) => {
    if (c.tem_filhos) {
      setBreadcrumb(b => [...b, { id: c.category_id, nome: c.nome }]);
      setBusca("");
      await carregarCategorias(c.category_id);
      return;
    }
    // Categoria-folha: seleciona e busca atributos/marcas
    setCategoriaSelecionada(c);
    await carregarAtributosMarcas(c.category_id);
  };

  const voltarBreadcrumb = (index: number) => {
    const novo = breadcrumb.slice(0, index);
    setBreadcrumb(novo);
    carregarCategorias(novo.length ? novo[novo.length - 1].id : 0);
  };

  const trocarCategoria = () => {
    setCategoriaSelecionada(null);
    setAtributos([]);
    setMarcas([]);
    setMarcaId(0);
    setBreadcrumb([]);
  };

  const adicionarImagemDoCatalogo = async () => {
    if (!lojaId || !p?.imagem_url || imagens.length >= MAX_IMAGENS) return;
    setEnviandoImagem(true);
    try {
      const r = await api.shopeeUploadImagem(lojaId, String(p.imagem_url));
      if (r.image_id) { setImagens(imgs => [...imgs, { id: r.image_id!, preview: r.image_url || String(p.imagem_url) }]); setResultado(null); }
      else setResultado({ ok: false, texto: r.erro || "Falha ao enviar imagem" });
    } finally {
      setEnviandoImagem(false);
    }
  };

  const adicionarImagemArquivo = async (file: File) => {
    if (!lojaId || imagens.length >= MAX_IMAGENS) return;
    setEnviandoImagem(true);
    try {
      const r = await api.shopeeUploadImagem(lojaId, file);
      if (r.image_id) {
        setImagens(imgs => [...imgs, { id: r.image_id!, preview: URL.createObjectURL(file) }]);
      } else {
        setResultado({ ok: false, texto: r.erro || "Falha ao enviar imagem" });
      }
    } finally {
      setEnviandoImagem(false);
    }
  };

  const removerImagem = (index: number) => setImagens(imgs => imgs.filter((_, i) => i !== index));

  const adicionarFaixaAtacado = () => setWholesale(w => [...w, { min: "", max: "", preco: "" }]);
  const atualizarFaixaAtacado = (index: number, campo: keyof FaixaAtacado, valor: string) =>
    setWholesale(w => w.map((f, i) => i === index ? { ...f, [campo]: valor } : f));
  const removerFaixaAtacado = (index: number) => setWholesale(w => w.filter((_, i) => i !== index));

  const prontoParaPublicar = !!(lojaId && categoriaSelecionada && imagens.length > 0 && form.nome && form.preco);

  const publicar = async (forcarPublicacao = false) => {
    if (!lojaId || !categoriaSelecionada) return;
    setPublicando(true);
    setResultado(null);
    if (!forcarPublicacao) setBloqueioMargem(null);
    try {
      const canaisR = await api.shopeeCanaisLogistica(lojaId);
      const canaisHabilitados = (canaisR.canais || []).filter(c => c.enabled);

      const payload: Record<string, unknown> = {
        item_name: form.nome,
        description: form.descricao || form.nome,
        item_sku: sku,
        category_id: categoriaSelecionada.category_id,
        original_price: Number(form.preco),
        weight: Number(form.peso) || 0.1,
        dimension: buildDimension(form.largura, form.altura, form.profundidade) || { package_length: 1, package_width: 1, package_height: 1 },
        image: { image_id_list: imagens.map(i => i.id) },
        brand: marcaId ? { brand_id: marcaId } : { brand_id: 0, original_brand_name: "No Brand" },
        attribute_list: buildAttributeList(),
        logistic_info: canaisHabilitados.map(c => ({ logistic_id: c.logistic_id, enabled: true })),
        seller_stock: [{ stock: Number(form.estoque) || 0 }],
        condition: condicao,
        forcar_publicacao: forcarPublicacao,
      };
      if (gtinCode.trim()) payload.gtin_code = gtinCode.trim();
      if (preOrderAtivo) payload.pre_order = { is_pre_order: true, days_to_ship: Number(diasParaEnvio) || 7 };
      const faixasValidas = wholesale.filter(w => w.min && w.preco);
      if (faixasValidas.length) {
        payload.wholesale = faixasValidas.map(w => ({
          min_count: Number(w.min),
          ...(w.max ? { max_count: Number(w.max) } : {}),
          unit_price: Number(w.preco),
        }));
      }

      const r = await api.shopeeCriarProduto(lojaId, payload);
      if (r.response?.item_id) {
        setResultado({ ok: true, texto: `Produto publicado na Shopee! item_id: ${r.response.item_id}` });
        setBloqueioMargem(null);
      } else if (r.bloqueado_por_margem && r.margem) {
        setBloqueioMargem(r.margem);
        setResultado({ ok: false, texto: r.error || "Publicação bloqueada: produto sairia com prejuízo." });
      } else {
        setResultado({ ok: false, texto: r.error || r.message || "A Shopee recusou o produto — confira categoria/atributos/imagem." });
      }
    } catch (e) {
      setResultado({ ok: false, texto: e instanceof Error ? e.message : "Erro ao publicar" });
    } finally {
      setPublicando(false);
    }
  };

  if (lojas.length === 0) {
    return (
      <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-6 text-center text-neutral-500 text-sm">
        Nenhuma loja Shopee conectada ainda. Conecte uma loja em <span className="text-indigo-400 inline-flex items-center gap-0.5">Integrações <Icon name="chevronRight" size={11} /> Shopee</span> antes de publicar produtos.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {resultado && (
        <div className={`text-xs px-3 py-2 rounded-lg border ${resultado.ok ? "bg-green-950/40 border-green-900/50 text-green-400" : "bg-red-950/40 border-red-900/50 text-red-400"}`}>
          {resultado.texto}
        </div>
      )}

      <Section title="1. Loja Shopee">
        <select value={lojaId ?? ""} onChange={e => setLojaId(e.target.value ? Number(e.target.value) : null)} className={inputCls}>
          <option value="">Selecione a loja...</option>
          {lojas.map(l => <option key={l.id} value={l.id}>{l.nome}</option>)}
        </select>
      </Section>

      {modoEdicao && itemIdExistente && (
        <Section title="Produto já publicado nesta loja">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <p className="text-xs text-neutral-500">item_id: <span className="font-mono text-neutral-400">{itemIdExistente}</span></p>
            <div className="flex flex-wrap items-center gap-3">
              <button onClick={() => setModoEdicao(false)} className="text-xs text-indigo-400 hover:text-indigo-300 text-left">
                Publicar como novo anúncio em vez disso
              </button>
              <button
                onClick={excluirDaShopee}
                disabled={excluindo}
                className="text-[10px] bg-red-900/60 hover:bg-red-900 disabled:opacity-50 text-red-200 px-2.5 py-1.5 rounded-lg shrink-0"
              >
                {excluindo ? "Excluindo..." : "Excluir da Shopee"}
              </button>
            </div>
          </div>
          {ehVariacao && (
            <div className="bg-amber-950/40 border border-amber-900/50 rounded-lg p-3 text-xs text-amber-300 space-y-1">
              <p className="font-medium flex items-center gap-1"><Icon name="alert" size={14} /> Este SKU é uma variação de um produto com múltiplos modelos.</p>
              <p className="text-amber-400/80">
                Nome, descrição, atributos, marca e imagens abaixo são do produto pai (afetam todas as variações). Estoque desta
                variação já é enviado corretamente por este formulário. Preço por variação: ajuste em{" "}
                <span className="font-mono inline-flex items-center gap-0.5">Integrações <Icon name="chevronRight" size={10} /> Shopee <Icon name="chevronRight" size={10} /> Produtos</span> (o campo abaixo está desativado).
              </p>
            </div>
          )}
          {carregandoEdicao ? (
            <p className="text-xs text-neutral-500">Carregando dados atuais da Shopee...</p>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <InputGroup label="Nome do produto">
                  <input value={formEdicao.nome} onChange={e => setFormEdicao({ ...formEdicao, nome: e.target.value })} className={inputCls} />
                </InputGroup>
                <InputGroup label={ehVariacao ? "Preço (produto pai — use a listagem para editar por variação)" : "Preço (R$)"}>
                  <input type="number" value={formEdicao.preco} disabled={ehVariacao} onChange={e => setFormEdicao({ ...formEdicao, preco: e.target.value })} className={`${inputCls} ${ehVariacao ? "opacity-50 cursor-not-allowed" : ""}`} />
                </InputGroup>
              </div>
              <InputGroup label="Descrição">
                <textarea rows={3} value={formEdicao.descricao} onChange={e => setFormEdicao({ ...formEdicao, descricao: e.target.value })} className={inputCls} />
              </InputGroup>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <InputGroup label="Estoque"><input type="number" value={formEdicao.estoque} onChange={e => setFormEdicao({ ...formEdicao, estoque: e.target.value })} className={inputCls} /></InputGroup>
                <InputGroup label="Peso (kg)"><input type="number" value={formEdicao.peso} onChange={e => setFormEdicao({ ...formEdicao, peso: e.target.value })} className={inputCls} /></InputGroup>
                <InputGroup label="Dimensões (cm)">
                  <div className="flex gap-1">
                    <input type="number" placeholder="L" value={formEdicao.largura} onChange={e => setFormEdicao({ ...formEdicao, largura: e.target.value })} className={inputCls} />
                    <input type="number" placeholder="A" value={formEdicao.altura} onChange={e => setFormEdicao({ ...formEdicao, altura: e.target.value })} className={inputCls} />
                    <input type="number" placeholder="P" value={formEdicao.profundidade} onChange={e => setFormEdicao({ ...formEdicao, profundidade: e.target.value })} className={inputCls} />
                  </div>
                </InputGroup>
                <InputGroup label="Estoque reservado (pedidos)">
                  <input value={estoqueReservado ?? "—"} disabled className={`${inputCls} opacity-60`} />
                </InputGroup>
              </div>

              {!ehVariacao && (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {marcas.length > 0 && (
                      <InputGroup label={`Marca${marcaObrigatoria ? " (obrigatório)" : " (opcional)"}`}>
                        <select value={marcaId} onChange={e => setMarcaId(Number(e.target.value))} className={inputCls}>
                          <option value={0}>Sem marca</option>
                          {marcas.map(m => <option key={m.brand_id} value={m.brand_id}>{m.original_brand_name}</option>)}
                        </select>
                      </InputGroup>
                    )}
                    {atributos.length > 0 && atributos.map(a => (
                      <InputGroup key={a.attribute_id} label={`${a.original_attribute_name}${a.is_mandatory ? " *" : ""}`}>
                        {a.attribute_value_list?.length ? (
                          <select
                            value={valoresAtributos[a.attribute_id] || ""}
                            onChange={e => setValoresAtributos(v => ({ ...v, [a.attribute_id]: e.target.value }))}
                            className={inputCls}
                          >
                            <option value="">Selecione...</option>
                            {a.attribute_value_list.map(v => <option key={v.value_id} value={v.value_id}>{v.original_value_name}</option>)}
                          </select>
                        ) : (
                          <input
                            value={valoresAtributos[a.attribute_id] || ""}
                            onChange={e => setValoresAtributos(v => ({ ...v, [a.attribute_id]: e.target.value }))}
                            className={inputCls}
                          />
                        )}
                      </InputGroup>
                    ))}
                  </div>
                  <InputGroup label="Código de barras / GTIN">
                    <input value={gtinCode} onChange={e => setGtinCode(e.target.value)} className={inputCls} />
                  </InputGroup>
                  <InputGroup label={`Imagens (${imagens.length}/${MAX_IMAGENS})`}>
                    <div className="flex items-start gap-2 flex-wrap">
                      {imagens.map((img, i) => (
                        <div key={img.id} className="relative">
                          {img.preview
                            ? <img src={img.preview} alt="" className="w-16 h-16 object-cover rounded-lg border border-neutral-700" />
                            : <div className="w-16 h-16 rounded-lg border border-neutral-700 bg-neutral-800 flex items-center justify-center text-neutral-500 text-[10px]">#{i + 1}</div>}
                          <button onClick={() => removerImagem(i)} className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-red-600 hover:bg-red-500 text-white leading-none flex items-center justify-center">
                            <Icon name="close" size={9} />
                          </button>
                        </div>
                      ))}
                      {imagens.length < MAX_IMAGENS && (
                        <label className="w-16 h-16 flex items-center justify-center rounded-lg border border-dashed border-neutral-700 text-neutral-500 text-xs cursor-pointer hover:border-indigo-500 hover:text-indigo-400">
                          {enviandoImagem ? "..." : "+"}
                          <input type="file" accept="image/*" className="hidden" disabled={!lojaId || enviandoImagem}
                            onChange={e => e.target.files?.[0] && adicionarImagemArquivo(e.target.files[0])} />
                        </label>
                      )}
                    </div>
                  </InputGroup>
                </>
              )}

              <button
                onClick={salvarEdicao}
                disabled={salvandoEdicao || !formEdicao.nome}
                className="w-full py-3 bg-orange-600 hover:bg-orange-500 disabled:opacity-40 text-white text-sm font-medium rounded-lg transition-colors"
              >
                {salvandoEdicao ? "Salvando alterações..." : "Salvar alterações na Shopee"}
              </button>
            </>
          )}
        </Section>
      )}

      {!modoEdicao && (
      <>
      <Section title="2. Categoria">
        {categoriaSelecionada ? (
          <div className="flex items-center justify-between bg-neutral-800/50 rounded-lg px-3 py-2">
            <span className="text-sm text-neutral-200">{categoriaSelecionada.nome}</span>
            <button onClick={trocarCategoria} className="text-xs text-indigo-400 hover:text-indigo-300">Trocar categoria</button>
          </div>
        ) : (
          <>
            <div className="flex gap-2">
              <input value={busca} onChange={e => setBusca(e.target.value)} onKeyDown={e => e.key === "Enter" && buscarCategorias()}
                placeholder="Buscar categoria (ex: camiseta, celular...)" className={inputCls} />
              <button onClick={buscarCategorias} className="px-3 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg shrink-0">Buscar</button>
            </div>
            {breadcrumb.length > 0 && (
              <div className="flex flex-wrap gap-1 text-xs text-neutral-500">
                <button onClick={() => voltarBreadcrumb(0)} className="hover:text-indigo-400">Início</button>
                {breadcrumb.map((b, i) => (
                  <span key={b.id}> / <button onClick={() => voltarBreadcrumb(i + 1)} className="hover:text-indigo-400">{b.nome}</button></span>
                ))}
              </div>
            )}
            <div className="max-h-64 overflow-y-auto border border-neutral-800 rounded-lg divide-y divide-neutral-800">
              {carregandoCategorias ? (
                <p className="text-xs text-neutral-500 p-3">Carregando...</p>
              ) : resultados.length === 0 ? (
                <p className="text-xs text-neutral-500 p-3">Nenhuma categoria encontrada. Se for a 1ª vez, pode levar alguns segundos para sincronizar com a Shopee.</p>
              ) : resultados.map(c => (
                <button key={c.category_id} onClick={() => abrirCategoria(c)} className="w-full text-left px-3 py-2 text-sm text-neutral-300 hover:bg-neutral-800/50 flex items-center justify-between">
                  {c.nome}
                  {c.tem_filhos && <span className="text-neutral-600 text-xs"><Icon name="chevronRight" size={12} /></span>}
                </button>
              ))}
            </div>
          </>
        )}
      </Section>

      {categoriaSelecionada && (
        <>
          <Section title="3. Atributos e Marca">
            {atributos.length === 0 && marcas.length === 0 && (
              <p className="text-xs text-neutral-500">Esta categoria não exige atributos adicionais.</p>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {marcas.length > 0 && (
                <InputGroup label={`Marca${marcaObrigatoria ? " (obrigatório)" : " (opcional)"}`}>
                  <select value={marcaId} onChange={e => setMarcaId(Number(e.target.value))} className={inputCls}>
                    <option value={0}>Sem marca</option>
                    {marcas.map(m => <option key={m.brand_id} value={m.brand_id}>{m.original_brand_name}</option>)}
                  </select>
                </InputGroup>
              )}
              {atributos.map(a => (
                <InputGroup key={a.attribute_id} label={`${a.original_attribute_name}${a.is_mandatory ? " *" : ""}`}>
                  {a.attribute_value_list?.length ? (
                    <select
                      value={valoresAtributos[a.attribute_id] || ""}
                      onChange={e => setValoresAtributos(v => ({ ...v, [a.attribute_id]: e.target.value }))}
                      className={inputCls}
                    >
                      <option value="">Selecione...</option>
                      {a.attribute_value_list.map(v => <option key={v.value_id} value={v.value_id}>{v.original_value_name}</option>)}
                    </select>
                  ) : (
                    <input
                      value={valoresAtributos[a.attribute_id] || ""}
                      onChange={e => setValoresAtributos(v => ({ ...v, [a.attribute_id]: e.target.value }))}
                      className={inputCls}
                    />
                  )}
                </InputGroup>
              ))}
            </div>
            <InputGroup label="Código de barras / GTIN (opcional)">
              <input value={gtinCode} onChange={e => setGtinCode(e.target.value)} className={inputCls} />
            </InputGroup>
          </Section>

          <Section title="4. Imagens">
            <div className="flex items-start gap-2 flex-wrap">
              {imagens.map((img, i) => (
                <div key={img.id} className="relative">
                  {img.preview
                    ? <img src={img.preview} alt="" className="w-20 h-20 object-cover rounded-lg border border-neutral-700" />
                    : <div className="w-20 h-20 rounded-lg border border-neutral-700 bg-neutral-800 flex items-center justify-center text-neutral-500 text-xs">#{i + 1}</div>}
                  <button onClick={() => removerImagem(i)} className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-600 hover:bg-red-500 text-white leading-none flex items-center justify-center">
                    <Icon name="close" size={11} />
                  </button>
                </div>
              ))}
              <div className="space-y-2">
                {p?.imagem_url && imagens.length < MAX_IMAGENS && (
                  <button onClick={adicionarImagemDoCatalogo} disabled={!lojaId || enviandoImagem} className="block px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs rounded-lg">
                    {enviandoImagem ? "Enviando..." : "Usar imagem já cadastrada"}
                  </button>
                )}
                {imagens.length < MAX_IMAGENS && (
                  <label className="block px-3 py-1.5 bg-neutral-700 hover:bg-neutral-600 text-white text-xs rounded-lg cursor-pointer w-fit">
                    {enviandoImagem ? "Enviando..." : "Enviar outra imagem"}
                    <input type="file" accept="image/*" className="hidden" disabled={!lojaId || enviandoImagem}
                      onChange={e => e.target.files?.[0] && adicionarImagemArquivo(e.target.files[0])} />
                  </label>
                )}
                {imagens.length > 0 && (
                  <p className="text-[10px] text-emerald-500 flex items-center gap-1">
                    <svg xmlns="http://www.w3.org/2000/svg" width={10} height={10} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"><path d="M5 13l4 4L19 7" /></svg>
                    {imagens.length}/{MAX_IMAGENS} imagens prontas
                  </p>
                )}
              </div>
            </div>
            <p className="text-[10px] text-neutral-600">Vídeo e tabela de medidas não são suportados aqui (a Shopee exige um fluxo de upload próprio, em várias etapas) — gerencie esses dois pelo Seller Center da Shopee.</p>
          </Section>

          <Section title="5. Dados do Anúncio">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <InputGroup label="Nome do produto"><input value={form.nome} onChange={e => setForm({ ...form, nome: e.target.value })} className={inputCls} /></InputGroup>
              <InputGroup label="Preço (R$)"><input type="number" value={form.preco} onChange={e => setForm({ ...form, preco: e.target.value })} className={inputCls} /></InputGroup>
            </div>
            <InputGroup label="Descrição"><textarea rows={3} value={form.descricao} onChange={e => setForm({ ...form, descricao: e.target.value })} className={inputCls} /></InputGroup>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <InputGroup label="Estoque inicial"><input type="number" value={form.estoque} onChange={e => setForm({ ...form, estoque: e.target.value })} className={inputCls} /></InputGroup>
              <InputGroup label="Peso (kg)"><input type="number" value={form.peso} onChange={e => setForm({ ...form, peso: e.target.value })} className={inputCls} /></InputGroup>
              <InputGroup label="Dimensões (cm)">
                <div className="flex gap-1">
                  <input type="number" placeholder="L" value={form.largura} onChange={e => setForm({ ...form, largura: e.target.value })} className={inputCls} />
                  <input type="number" placeholder="A" value={form.altura} onChange={e => setForm({ ...form, altura: e.target.value })} className={inputCls} />
                  <input type="number" placeholder="P" value={form.profundidade} onChange={e => setForm({ ...form, profundidade: e.target.value })} className={inputCls} />
                </div>
              </InputGroup>
              <InputGroup label="Condição">
                <select value={condicao} onChange={e => setCondicao(e.target.value as "NEW" | "USED")} className={inputCls}>
                  <option value="NEW">Novo</option>
                  <option value="USED">Usado</option>
                </select>
              </InputGroup>
            </div>
          </Section>

          <Section title="6. Sob encomenda (opcional)">
            <label className="flex items-center gap-2 text-sm text-neutral-300">
              <input type="checkbox" checked={preOrderAtivo} onChange={e => setPreOrderAtivo(e.target.checked)} className="rounded" />
              Este produto é sob encomenda (pré-venda)
            </label>
            {preOrderAtivo && (
              <InputGroup label="Dias para envio">
                <input type="number" value={diasParaEnvio} onChange={e => setDiasParaEnvio(e.target.value)} className={inputCls} />
              </InputGroup>
            )}
          </Section>

          <Section title="7. Preço por atacado (opcional)">
            {wholesale.map((f, i) => (
              <div key={i} className="grid grid-cols-4 gap-2 items-end">
                <InputGroup label="Qtd. mínima"><input type="number" value={f.min} onChange={e => atualizarFaixaAtacado(i, "min", e.target.value)} className={inputCls} /></InputGroup>
                <InputGroup label="Qtd. máxima (opcional)"><input type="number" value={f.max} onChange={e => atualizarFaixaAtacado(i, "max", e.target.value)} className={inputCls} /></InputGroup>
                <InputGroup label="Preço unitário (R$)"><input type="number" value={f.preco} onChange={e => atualizarFaixaAtacado(i, "preco", e.target.value)} className={inputCls} /></InputGroup>
                <button onClick={() => removerFaixaAtacado(i)} className="text-xs text-red-400 hover:text-red-300 pb-2">Remover</button>
              </div>
            ))}
            <button onClick={adicionarFaixaAtacado} className="text-xs text-indigo-400 hover:text-indigo-300">+ Adicionar faixa de atacado</button>
          </Section>

          {bloqueioMargem && (
            <div className="bg-red-950/40 border border-red-900/50 rounded-lg p-3 space-y-2 text-xs">
              <p className="text-red-400 font-medium flex items-center gap-1"><Icon name="alert" size={14} /> Este produto sairia com prejuízo nesta loja:</p>
              <ul className="text-neutral-400 space-y-0.5">
                <li>Preço: R$ {Number(form.preco).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</li>
                <li>Comissão: R$ {bloqueioMargem.comissao_valor.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</li>
                <li>Frete médio: R$ {bloqueioMargem.frete.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</li>
                <li>Custo do produto: R$ {bloqueioMargem.custo.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</li>
                <li className="text-red-400 font-medium">Resultado: prejuízo de R$ {Math.abs(bloqueioMargem.margem_valor).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</li>
              </ul>
              <button
                onClick={() => publicar(true)}
                disabled={publicando}
                className="text-[10px] bg-red-900/60 hover:bg-red-900 disabled:opacity-50 text-red-200 px-2.5 py-1.5 rounded-lg"
              >
                Publicar mesmo assim (não recomendado)
              </button>
            </div>
          )}
          <button
            onClick={() => publicar(false)}
            disabled={!prontoParaPublicar || publicando}
            className="w-full py-3 bg-orange-600 hover:bg-orange-500 disabled:opacity-40 text-white text-sm font-medium rounded-lg transition-colors"
          >
            {publicando ? "Publicando na Shopee..." : "Publicar na Shopee"}
          </button>
          {!prontoParaPublicar && (
            <p className="text-[10px] text-neutral-600 text-center">Selecione loja, categoria, imagem, nome e preço para habilitar a publicação.</p>
          )}
        </>
      )}
      </>
      )}
    </div>
  );
}
