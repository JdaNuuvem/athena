"use client";

import { useState, useEffect, useCallback } from "react";
import { api, ShopeeCategoria, ShopeeAtributo, ShopeeMarca } from "@/lib/api";

interface Props {
  produto: Record<string, unknown> | null;
  sku: string;
}

interface Breadcrumb { id: number; nome: string; }

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

  // ── Atributos e marca ──
  const [atributos, setAtributos] = useState<ShopeeAtributo[]>([]);
  const [valoresAtributos, setValoresAtributos] = useState<Record<number, string>>({});
  const [marcas, setMarcas] = useState<ShopeeMarca[]>([]);
  const [marcaObrigatoria, setMarcaObrigatoria] = useState(false);
  const [marcaId, setMarcaId] = useState<number>(0);

  // ── Imagem ──
  const [imagemId, setImagemId] = useState<string>("");
  const [imagemPreview, setImagemPreview] = useState<string>("");
  const [enviandoImagem, setEnviandoImagem] = useState(false);

  // ── Dados finais ──
  const [form, setForm] = useState({
    nome: "", descricao: "", preco: "", estoque: "",
    peso: "", largura: "", altura: "", profundidade: "",
  });

  const [publicando, setPublicando] = useState(false);
  const [resultado, setResultado] = useState<{ ok: boolean; texto: string } | null>(null);

  // ── Modo edicao (produto ja publicado nesta loja) ──
  const [lojasComShopId, setLojasComShopId] = useState<Record<number, string>>({});
  const [itemIdExistente, setItemIdExistente] = useState<number | null>(null);
  const [modoEdicao, setModoEdicao] = useState(false);
  const [carregandoEdicao, setCarregandoEdicao] = useState(false);
  const [formEdicao, setFormEdicao] = useState({ nome: "", descricao: "", preco: "", estoque: "", peso: "" });
  const [salvandoEdicao, setSalvandoEdicao] = useState(false);

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
    // ponytail: imagem_url do catalogo local (Bling) — reaproveitada com 1 clique, sem re-upload manual
    if (p?.imagem_url) setImagemPreview(String(p.imagem_url));
  }, [p]);

  // Detecta se o produto ja esta publicado na loja selecionada (via estoque_lojas do detalhe)
  useEffect(() => {
    setItemIdExistente(null);
    setModoEdicao(false);
    if (!lojaId) return;
    const shopId = lojasComShopId[lojaId];
    if (!shopId) return;
    const anuncios = (p?.estoque_lojas || []) as Array<{ marketplace: string; shop_id?: string; anuncio_id?: string }>;
    const existente = anuncios.find(a => a.marketplace === "shopee" && a.shop_id === shopId && a.anuncio_id);
    if (!existente?.anuncio_id) return;
    const itemId = Number(existente.anuncio_id);
    setItemIdExistente(itemId);
    setModoEdicao(true);
    setCarregandoEdicao(true);
    api.shopeeDetalheProduto(itemId, lojaId).then(r => {
      const item = r.item || {};
      const priceInfo = (item.price_info as Array<{ current_price?: number }> | undefined)?.[0];
      const stockInfo = (item.stock_info_v2 as { summary_info?: { total_available_stock?: number } } | undefined)?.summary_info;
      setFormEdicao({
        nome: String(item.item_name || ""),
        descricao: String(item.description || ""),
        preco: String(priceInfo?.current_price ?? ""),
        estoque: String(stockInfo?.total_available_stock ?? ""),
        peso: String(item.weight ?? ""),
      });
    }).catch(() => {}).finally(() => setCarregandoEdicao(false));
  }, [lojaId, lojasComShopId, p]);

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
      const r = await api.shopeeEditarProdutoShopee(itemIdExistente, lojaId, payload);
      if (r.error) {
        setResultado({ ok: false, texto: r.error });
      } else {
        const precoNum = Number(formEdicao.preco);
        const estoqueNum = Number(formEdicao.estoque);
        if (precoNum > 0) await api.shopeeAtualizarPreco(itemIdExistente, lojaId, precoNum);
        if (!Number.isNaN(estoqueNum)) await api.shopeeAtualizarEstoqueProduto(sku, lojaId, estoqueNum);
        setResultado({ ok: true, texto: "Anúncio atualizado na Shopee." });
      }
    } catch (e) {
      setResultado({ ok: false, texto: e instanceof Error ? e.message : "Erro ao salvar alterações" });
    } finally {
      setSalvandoEdicao(false);
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
    const [attrR, brandR] = await Promise.all([
      api.shopeeAtributos(c.category_id, lojaId ?? undefined),
      api.shopeeMarcas(c.category_id, lojaId ?? undefined),
    ]);
    setAtributos(attrR.atributos || []);
    setMarcas(brandR.marcas || []);
    setMarcaObrigatoria(brandR.obrigatorio);
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

  const enviarImagemDoCatalogo = async () => {
    if (!lojaId || !p?.imagem_url) return;
    setEnviandoImagem(true);
    try {
      const r = await api.shopeeUploadImagem(lojaId, String(p.imagem_url));
      if (r.image_id) { setImagemId(r.image_id); setResultado(null); }
      else setResultado({ ok: false, texto: r.erro || "Falha ao enviar imagem" });
    } finally {
      setEnviandoImagem(false);
    }
  };

  const enviarImagemArquivo = async (file: File) => {
    if (!lojaId) return;
    setEnviandoImagem(true);
    try {
      const r = await api.shopeeUploadImagem(lojaId, file);
      if (r.image_id) {
        setImagemId(r.image_id);
        setImagemPreview(URL.createObjectURL(file));
      } else {
        setResultado({ ok: false, texto: r.erro || "Falha ao enviar imagem" });
      }
    } finally {
      setEnviandoImagem(false);
    }
  };

  const prontoParaPublicar = !!(lojaId && categoriaSelecionada && imagemId && form.nome && form.preco);

  const publicar = async () => {
    if (!lojaId || !categoriaSelecionada) return;
    setPublicando(true);
    setResultado(null);
    try {
      const canaisR = await api.shopeeCanaisLogistica(lojaId);
      const canaisHabilitados = (canaisR.canais || []).filter(c => c.enabled);

      const attributeList = atributos
        .filter(a => valoresAtributos[a.attribute_id])
        .map(a => {
          const valor = valoresAtributos[a.attribute_id];
          if (a.attribute_value_list?.length) {
            return { attribute_id: a.attribute_id, attribute_value_list: [{ value_id: Number(valor) }] };
          }
          return { attribute_id: a.attribute_id, attribute_value_list: [{ original_value_name: valor }] };
        });

      const payload: Record<string, unknown> = {
        item_name: form.nome,
        description: form.descricao || form.nome,
        item_sku: sku,
        category_id: categoriaSelecionada.category_id,
        original_price: Number(form.preco),
        weight: Number(form.peso) || 0.1,
        dimension: {
          package_length: Number(form.largura) || 1,
          package_width: Number(form.profundidade) || 1,
          package_height: Number(form.altura) || 1,
        },
        image: { image_id_list: [imagemId] },
        brand: marcaId ? { brand_id: marcaId } : { brand_id: 0, original_brand_name: "No Brand" },
        attribute_list: attributeList,
        logistic_info: canaisHabilitados.map(c => ({ logistic_id: c.logistic_id, enabled: true })),
        seller_stock: [{ stock: Number(form.estoque) || 0 }],
      };

      const r = await api.shopeeCriarProduto(lojaId, payload);
      if (r.response?.item_id) {
        setResultado({ ok: true, texto: `Produto publicado na Shopee! item_id: ${r.response.item_id}` });
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
        Nenhuma loja Shopee conectada ainda. Conecte uma loja em <span className="text-indigo-400">Integrações → Shopee</span> antes de publicar produtos.
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
          <div className="flex items-center justify-between">
            <p className="text-xs text-neutral-500">item_id: <span className="font-mono text-neutral-400">{itemIdExistente}</span></p>
            <button onClick={() => setModoEdicao(false)} className="text-xs text-indigo-400 hover:text-indigo-300">
              Publicar como novo anúncio em vez disso
            </button>
          </div>
          {carregandoEdicao ? (
            <p className="text-xs text-neutral-500">Carregando dados atuais da Shopee...</p>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <InputGroup label="Nome do produto">
                  <input value={formEdicao.nome} onChange={e => setFormEdicao({ ...formEdicao, nome: e.target.value })} className={inputCls} />
                </InputGroup>
                <InputGroup label="Preço (R$)">
                  <input type="number" value={formEdicao.preco} onChange={e => setFormEdicao({ ...formEdicao, preco: e.target.value })} className={inputCls} />
                </InputGroup>
              </div>
              <InputGroup label="Descrição">
                <textarea rows={3} value={formEdicao.descricao} onChange={e => setFormEdicao({ ...formEdicao, descricao: e.target.value })} className={inputCls} />
              </InputGroup>
              <div className="grid grid-cols-2 gap-3">
                <InputGroup label="Estoque"><input type="number" value={formEdicao.estoque} onChange={e => setFormEdicao({ ...formEdicao, estoque: e.target.value })} className={inputCls} /></InputGroup>
                <InputGroup label="Peso (kg)"><input type="number" value={formEdicao.peso} onChange={e => setFormEdicao({ ...formEdicao, peso: e.target.value })} className={inputCls} /></InputGroup>
              </div>
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
                  {c.tem_filhos && <span className="text-neutral-600 text-xs">›</span>}
                </button>
              ))}
            </div>
          </>
        )}
      </Section>

      {categoriaSelecionada && (
        <>
          <Section title="3. Atributos e Marca">
            {marcas.length > 0 && (
              <InputGroup label={`Marca${marcaObrigatoria ? " (obrigatório)" : " (opcional)"}`}>
                <select value={marcaId} onChange={e => setMarcaId(Number(e.target.value))} className={inputCls}>
                  <option value={0}>Sem marca</option>
                  {marcas.map(m => <option key={m.brand_id} value={m.brand_id}>{m.original_brand_name}</option>)}
                </select>
              </InputGroup>
            )}
            {atributos.length === 0 ? (
              <p className="text-xs text-neutral-500">Esta categoria não exige atributos adicionais.</p>
            ) : atributos.map(a => (
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
          </Section>

          <Section title="4. Imagem">
            <div className="flex items-start gap-4">
              {imagemPreview ? (
                <img src={imagemPreview} alt="" className="w-20 h-20 object-cover rounded-lg border border-neutral-700" />
              ) : (
                <div className="w-20 h-20 rounded-lg border border-neutral-700 bg-neutral-800 flex items-center justify-center text-neutral-500 text-xs">Sem foto</div>
              )}
              <div className="space-y-2">
                {p?.imagem_url && !imagemId && (
                  <button onClick={enviarImagemDoCatalogo} disabled={!lojaId || enviandoImagem} className="block px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs rounded-lg">
                    {enviandoImagem ? "Enviando..." : "Usar imagem já cadastrada"}
                  </button>
                )}
                <label className="block px-3 py-1.5 bg-neutral-700 hover:bg-neutral-600 text-white text-xs rounded-lg cursor-pointer w-fit">
                  {enviandoImagem ? "Enviando..." : "Enviar outra imagem"}
                  <input type="file" accept="image/*" className="hidden" disabled={!lojaId || enviandoImagem}
                    onChange={e => e.target.files?.[0] && enviarImagemArquivo(e.target.files[0])} />
                </label>
                {imagemId && <p className="text-[10px] text-emerald-500">✓ Imagem pronta para publicar</p>}
              </div>
            </div>
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
            </div>
          </Section>

          <button
            onClick={publicar}
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
