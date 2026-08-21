"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { api, atualizarBlingProduto } from "@/lib/api";
import Icon from "@/app/_components/Icon";
import SelectComCriacao from "./SelectComCriacao";

interface Fornecedor { id: number; nome: string; }

function InputGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="space-y-1"><label className="text-[10px] text-neutral-500 uppercase tracking-wider">{label}</label>{children}</div>;
}
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <fieldset className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-4"><legend className="text-sm font-medium text-neutral-300 px-1">{title}</legend>{children}</fieldset>;
}

export default function CadastroTab({ produto, sku, onUpdate }: { produto: Record<string, unknown> | null; sku: string; onUpdate?: () => void }) {
  const [editando, setEditando] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [msgErro, setMsgErro] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [fornecedores, setFornecedores] = useState<Fornecedor[]>([]);
  const [marcas, setMarcas] = useState<{ id: number; nome: string }[]>([]);
  const [fabricantes, setFabricantes] = useState<{ id: number; nome: string }[]>([]);
  const [categorias, setCategorias] = useState<{ id: number; nome: string }[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.cadList("fornecedores").then(r => setFornecedores((r.data ?? []) as Fornecedor[])).catch(() => {});
    api.listarMarcas().then(r => setMarcas(r.data ?? [])).catch(() => {});
    api.listarFabricantes().then(r => setFabricantes(r.data ?? [])).catch(() => {});
    api.listarCategoriasProduto().then(r => setCategorias(r.data ?? [])).catch(() => {});
  }, []);

  const p = produto as any;
  const idBling = p?.id_bling;
  const imagemURL = p?.imagemURL || p?.imagem_url;

  const CAMPOS_EDITAVEIS = [
    "descricao", "categoria", "marca", "ncm", "tipo",
    "codigo_barras", "gtin_embalagem", "descricao_curta", "descricao_complementar",
    "peso_bruto", "peso_liquido", "largura", "altura", "profundidade", "unidade_medida_dimensao",
    "volumes", "itens_por_caixa", "cfop_padrao", "observacoes", "link_externo",
    "fornecedor_nome", "fornecedor_codigo", "fornecedor_id", "preco_custo",
    "custo_transporte", "preco_venda",
    "estoque_minimo", "estoque_maximo", "estoque_localizacao",
    "classificacao", "nome_reduzido", "nome_impressao", "codigo_interno",
    "codigo_erp", "ex_tipi", "modelo", "linha", "colecao",
    "marca_id", "fabricante_id", "categoria_id_norm",
  ];

  const startEdit = () => {
    const f: Record<string, string> = {};
    for (const campo of CAMPOS_EDITAVEIS) f[campo] = String(p?.[campo] ?? "");
    setForm(f);
    setEditando(true);
  };

  const handleSave = async () => {
    setSaving(true); setMsg(""); setMsgErro(false);
    try {
      // fornecedor_id, marca_id, fabricante_id, categoria_id_norm sao BIGINT/INT no banco —
      // string vazia quebraria o UPDATE, so' envia se selecionado
      const payload: Record<string, unknown> = { ...form };
      if (!payload.fornecedor_id) delete payload.fornecedor_id;
      // marca_id/fabricante_id/categoria_id_norm: envia null explicito quando limpo
      // ("— Nenhum —"), ao inves de deletar a chave, para o backend distinguir
      // "campo nao tocado" (chave ausente) de "campo explicitamente limpo" (null).
      for (const campoFk of ["marca_id", "fabricante_id", "categoria_id_norm"]) {
        if (!payload[campoFk]) payload[campoFk] = null;
      }
      // 1. Save locally
      const r = await fetch("/api/produtos/" + sku, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
      });
      const d = await r.json();
      if (d.error) { setMsg(d.error); setMsgErro(true); setSaving(false); return; }

      // 2. Push to Bling (two-way sync)
      if (idBling) {
        try {
          // via api.ts: fetch cru aqui nao mandava Authorization, entao a rota
          // ficava a merce do que o backend exigisse de RBAC.
          await atualizarBlingProduto(Number(idBling), {
            descricao: form.descricao, preco: form.preco,
          });
        } catch (e) { setMsg("Salvo localmente. Erro ao sincronizar com Bling."); setMsgErro(true); setSaving(false); return; }
      }

      setMsg(idBling ? "Salvo e sincronizado com Bling!" : "Salvo localmente.");
      setEditando(false);
      onUpdate?.();
      setTimeout(() => setMsg(""), 3000);
    } catch (e) { setMsg("Erro ao salvar"); setMsgErro(true); }
    finally { setSaving(false); }
  };

  const handleImageUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true); setUploadMsg("");
    // Ultimo arquivo enviado vira a imagem de capa do produto — o upload
    // so' salvava em `documentos` (generico), sem nunca atualizar
    // catalogo_produtos.imagem_url. A UI dizia "Imagem enviada!" mas a foto
    // exibida no produto nunca mudava.
    let ultimoDocId: number | null = null;
    for (const file of Array.from(files)) {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("entidade_tipo", "produto");
      formData.append("entidade_id", String(p?.id || ""));
      formData.append("criado_por", "Admin");
      const r = await fetch("/api/documentos", { method: "POST", body: formData });
      const d = await r.json();
      if (d.error) { setUploadMsg(d.error); setUploading(false); return; }
      ultimoDocId = d.id ?? null;
    }
    if (ultimoDocId != null) {
      const rp = await fetch("/api/produtos/" + sku, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ imagem_url: `/api/documentos/${ultimoDocId}` }),
      });
      const dp = await rp.json();
      if (dp.error) { setUploadMsg("Imagem salva, mas não foi possível vincular ao produto: " + dp.error); setUploading(false); return; }
    }
    setUploading(false);
    setUploadMsg("Imagem enviada!");
    onUpdate?.();
    setTimeout(() => setUploadMsg(""), 2000);
  };

  const field = (k: string) => {
    const val = editando ? form[k] || "" : String(p?.[k] || "");
    if (editando) return <input type="text" value={val || ""} disabled={saving} onChange={e => setForm({...form, [k]: e.target.value})} className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500 disabled:opacity-50" />;
    return <div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200">{val || "—"}</div>;
  };

  const textareaField = (k: string, rows = 3) => {
    const val = editando ? form[k] || "" : String(p?.[k] || "");
    if (editando) return <textarea rows={rows} value={val || ""} disabled={saving} onChange={e => setForm({...form, [k]: e.target.value})} className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500 disabled:opacity-50" />;
    return <div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 whitespace-pre-wrap min-h-[2.5rem]">{val || "—"}</div>;
  };

  const dimensoes = () => {
    if (editando) return null;
    const l = p?.largura, a = p?.altura, prof = p?.profundidade, un = p?.unidade_medida_dimensao || "cm";
    if (!l && !a && !prof) return "—";
    return `${l || 0} x ${a || 0} x ${prof || 0} ${un}`;
  };

  const margemReal = () => {
    const custo = Number(p?.preco_custo || 0);
    const valor = Number(p?.valor || 0);
    if (!custo || !valor) return null;
    return (((valor - custo) / valor) * 100).toFixed(1);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-neutral-400">Dados do Produto</h2>
        <div className="flex gap-2 items-center">
          {msg && <span className={`text-xs ${msgErro ? "text-red-400" : "text-emerald-400"}`}>{msg}</span>}
          {uploadMsg && <span className="text-xs text-blue-400">{uploadMsg}</span>}
          {editando ? (
            <>
              <button onClick={handleSave} disabled={saving} className="px-3 py-1 bg-emerald-600 text-white text-xs rounded-lg">{saving ? "Salvando..." : "Salvar"}</button>
              <button onClick={() => setEditando(false)} className="px-3 py-1 text-xs text-neutral-400">Cancelar</button>
            </>
          ) : (
            <>
              <button onClick={startEdit} className="px-3 py-1 bg-indigo-600 text-white text-xs rounded-lg">Editar</button>
              <Link href={"/pdv?sku=" + sku} className="px-3 py-1 bg-amber-600 hover:bg-amber-500 text-white text-xs rounded-lg inline-flex items-center gap-1">
                <svg xmlns="http://www.w3.org/2000/svg" width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="9" cy="21" r="1" />
                  <circle cx="20" cy="21" r="1" />
                  <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
                </svg>
                Vender
              </Link>
            </>
          )}
        </div>
      </div>

      {/* Image section */}
      <Section title="Imagem">
        <div className="flex items-start gap-4">
          {imagemURL ? (
            <img src={imagemURL} alt={String(p?.nome || sku)} className="w-24 h-24 object-cover rounded-lg border border-neutral-700" />
          ) : (
            <div className="w-24 h-24 rounded-lg border border-neutral-700 bg-neutral-800 flex items-center justify-center text-neutral-500 text-xs">Sem foto</div>
          )}
          <div>
            <button onClick={() => fileRef.current?.click()} disabled={uploading} className="px-3 py-1.5 bg-neutral-700 hover:bg-neutral-600 text-white text-xs rounded-lg inline-flex items-center gap-1">
              {uploading ? "Enviando..." : (
                <>
                  <svg xmlns="http://www.w3.org/2000/svg" width={12} height={12} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                    <path d="M17 8l-5-5-5 5" />
                    <path d="M12 3v12" />
                  </svg>
                  Upload Imagem
                </>
              )}
            </button>
            <input ref={fileRef} type="file" accept="image/*" onChange={e => handleImageUpload(e.target.files)} className="hidden" />
            <p className="text-[10px] text-neutral-600 mt-1">JPG, PNG, WebP</p>
          </div>
        </div>
      </Section>

      <Section title="Identificação">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          <InputGroup label="SKU"><div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-indigo-400 font-mono">{sku}</div></InputGroup>
          <InputGroup label="Nome"><div>{field("descricao")}</div></InputGroup>
          <InputGroup label="Categoria">{field("categoria")}</InputGroup>
          <InputGroup label="Marca">{field("marca")}</InputGroup>
          <InputGroup label="Código de Barras (GTIN)">{field("codigo_barras")}</InputGroup>
          <InputGroup label="GTIN Embalagem">{field("gtin_embalagem")}</InputGroup>
          <InputGroup label="Tipo Bling"><div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-500">{String(p?.bling_tipo || "—")} / {String(p?.formato || "—")}</div></InputGroup>
          <InputGroup label="Situação"><div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-500">{p?.situacao === "A" ? "Ativo" : p?.situacao === "I" ? "Inativo" : String(p?.situacao || "—")}</div></InputGroup>
        </div>
      </Section>

      <Section title="Classificação e Organização">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          <InputGroup label="Classificação">
            {editando ? (
              <select
                value={form.classificacao || "simples"}
                disabled={saving}
                onChange={e => setForm({ ...form, classificacao: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500 disabled:opacity-50"
              >
                <option value="simples">Simples</option>
                <option value="variavel">Variável</option>
                <option value="kit">Kit</option>
                <option value="combo">Combo</option>
              </select>
            ) : (
              <div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 capitalize">
                {String(p?.classificacao || "simples")}
              </div>
            )}
          </InputGroup>
          <InputGroup label="Nome Reduzido">{field("nome_reduzido")}</InputGroup>
          <InputGroup label="Nome para Impressão">{field("nome_impressao")}</InputGroup>
          <InputGroup label="Código Interno">{field("codigo_interno")}</InputGroup>
          <InputGroup label="Código ERP">{field("codigo_erp")}</InputGroup>
          <InputGroup label="EX TIPI">{field("ex_tipi")}</InputGroup>
          <InputGroup label="Modelo">{field("modelo")}</InputGroup>
          <InputGroup label="Linha">{field("linha")}</InputGroup>
          <InputGroup label="Coleção">{field("colecao")}</InputGroup>
          {editando ? (
            <SelectComCriacao
              label="Marca"
              value={form.marca_id || ""}
              options={marcas}
              disabled={saving}
              onChange={id => setForm({ ...form, marca_id: id })}
              onCriar={api.criarMarca}
              onCriado={nova => setMarcas(prev => [...prev, nova])}
            />
          ) : (
            <InputGroup label="Marca">
              <div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200">
                {marcas.find(m => m.id === Number(p?.marca_id))?.nome || "—"}
              </div>
            </InputGroup>
          )}
          {editando ? (
            <SelectComCriacao
              label="Fabricante"
              value={form.fabricante_id || ""}
              options={fabricantes}
              disabled={saving}
              onChange={id => setForm({ ...form, fabricante_id: id })}
              onCriar={api.criarFabricante}
              onCriado={novo => setFabricantes(prev => [...prev, novo])}
            />
          ) : (
            <InputGroup label="Fabricante">
              <div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200">
                {fabricantes.find(f => f.id === Number(p?.fabricante_id))?.nome || "—"}
              </div>
            </InputGroup>
          )}
          {editando ? (
            <SelectComCriacao
              label="Categoria (normalizada)"
              value={form.categoria_id_norm || ""}
              options={categorias}
              disabled={saving}
              onChange={id => setForm({ ...form, categoria_id_norm: id })}
              onCriar={api.criarCategoriaProduto}
              onCriado={nova => setCategorias(prev => [...prev, nova])}
            />
          ) : (
            <InputGroup label="Categoria (normalizada)">
              <div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200">
                {categorias.find(c => c.id === Number(p?.categoria_id_norm))?.nome || "—"}
              </div>
            </InputGroup>
          )}
        </div>
      </Section>

      <Section title="Fiscal">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          <InputGroup label="NCM">{field("ncm")}</InputGroup>
          <InputGroup label="CFOP Padrão">{field("cfop_padrao")}</InputGroup>
          <InputGroup label="Tipo">{field("tipo")}</InputGroup>
          <InputGroup label="Origem"><div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-500">{String(p?.origem_fiscal || "—")}</div></InputGroup>
        </div>
      </Section>

      <Section title="Logística">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          <InputGroup label="Peso Bruto (kg)">{field("peso_bruto")}</InputGroup>
          <InputGroup label="Peso Líquido (kg)">{field("peso_liquido")}</InputGroup>
          <InputGroup label="Largura">{field("largura")}</InputGroup>
          <InputGroup label="Altura">{field("altura")}</InputGroup>
          <InputGroup label="Profundidade">{field("profundidade")}</InputGroup>
          <InputGroup label="Unidade Dimensão">{field("unidade_medida_dimensao")}</InputGroup>
          <InputGroup label="Volumes">{field("volumes")}</InputGroup>
          <InputGroup label="Itens por Caixa">{field("itens_por_caixa")}</InputGroup>
          {!editando && <InputGroup label="Dimensões (L x A x P)"><div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200">{dimensoes()}</div></InputGroup>}
        </div>
      </Section>

      <Section title="Fornecimento">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          <InputGroup label="Fornecedor">
            {editando ? (
              <select
                value={form.fornecedor_id || ""}
                disabled={saving}
                onChange={e => setForm({ ...form, fornecedor_id: e.target.value })}
                className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500 disabled:opacity-50"
              >
                <option value="">— Nenhum —</option>
                {fornecedores.map(f => <option key={f.id} value={f.id}>{f.nome}</option>)}
              </select>
            ) : (
              <div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200">
                {String(p?.fornecedor_cadastro_nome || p?.fornecedor_nome || "—")}
              </div>
            )}
          </InputGroup>
          <InputGroup label="Código no Fornecedor">{field("fornecedor_codigo")}</InputGroup>
          <InputGroup label="Preço de Custo">{field("preco_custo")}</InputGroup>
          <InputGroup label="Custo de Transporte">{field("custo_transporte")}</InputGroup>
          <InputGroup label="Preço de Venda">{field("preco_venda")}</InputGroup>
          {!editando && (
            <InputGroup label="Margem Real">
              <div className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-emerald-400">
                {margemReal() !== null ? `${margemReal()}%` : "—"}
              </div>
            </InputGroup>
          )}
          <InputGroup label="Estoque Mínimo">{field("estoque_minimo")}</InputGroup>
          <InputGroup label="Estoque Máximo">{field("estoque_maximo")}</InputGroup>
          <InputGroup label="Localização">{field("estoque_localizacao")}</InputGroup>
        </div>
      </Section>

      <Section title="Descrição">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <InputGroup label="Descrição Curta">{textareaField("descricao_curta", 2)}</InputGroup>
          <InputGroup label="Link Externo">{field("link_externo")}</InputGroup>
        </div>
        <InputGroup label="Descrição Complementar">{textareaField("descricao_complementar", 4)}</InputGroup>
        <InputGroup label="Observações">{textareaField("observacoes", 2)}</InputGroup>
      </Section>

      <div className="text-xs text-neutral-600 space-y-1">
        <div>ID: {String(p?.id || "—")} | Bling ID: {idBling || "—"} | Variacoes: {(p?.variacoes as any[])?.length || 0}</div>
        {idBling && (
          <div className="text-emerald-600 flex items-center gap-1">
            <svg xmlns="http://www.w3.org/2000/svg" width={11} height={11} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"><path d="M5 13l4 4L19 7" /></svg>
            Sincronizado com Bling (two-way)
          </div>
        )}
      </div>
    </div>
  );
}
