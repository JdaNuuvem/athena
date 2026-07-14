"use client";

const mock = {
  sku: "MC-001-P", gtin: "7891234567890", codigoInterno: "INT001",
  codigoFabricante: "FAB-789", marca: "MasterCool", categoria: "Utilidades Domésticas",
  subcategoria: "Organizadores", unidade: "un",
  pesoLiquido: 0.45, pesoBruto: 0.52,
  largura: 25, altura: 15, profundidade: 10,
  larguraEmbalagem: 27, alturaEmbalagem: 17, profundidadeEmbalagem: 12,
  ncm: "3924.10.00", cest: "28.038.00", cfopPadrao: "5102",
  origem: "0", regimeTributario: "Simples Nacional",
  garantiaMeses: 3, descricaoCurta: "Organizador modular para geladeira com divisórias ajustáveis.",
  descricaoCompleta: "Organizador plástico de alta resistência, ideal para otimizar o espaço interno da geladeira. Possui divisórias removíveis e ajustáveis, design modular que permite empilhamento. Material livre de BPA, fácil de limpar.",
  seoTitulo: "Organizador de Geladeira Modular | MasterCool", seoDesc: "Organizador de geladeira com divisórias ajustáveis. Otimize o espaço da sua geladeira com o organizador modular MasterCool.", seoSlug: "organizador-geladeira-modular", seoKw: "organizador geladeira, divisória geladeira, organizador modular",
};

function InputGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="text-[10px] text-neutral-500 uppercase tracking-wider">{label}</label>
      {children}
    </div>
  );
}

function Field({ label, value, type = "text" }: { label: string; value: string | number; type?: string }) {
  return (
    <input
      type={type}
      defaultValue={String(value)}
      readOnly
      className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 cursor-default focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-transparent"
      aria-label={label}
    />
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <fieldset className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-4">
      <legend className="text-sm font-medium text-neutral-300 px-1">{title}</legend>
      {children}
    </fieldset>
  );
}

const imagesMock = Array.from({ length: 4 }, (_, i) => `imagem_${i + 1}.jpg`);
const videosMock = ["https://youtube.com/watch?v=abc123"];
const docsMock = ["ficha_tecnica.pdf", "certificado_ncm.pdf"];

export default function CadastroTab() {
  return (
    <div className="space-y-6">
      <Section title="Identificação">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          <InputGroup label="SKU"><Field label="SKU" value={mock.sku} /></InputGroup>
          <InputGroup label="GTIN / EAN"><Field label="GTIN" value={mock.gtin} /></InputGroup>
          <InputGroup label="Código Interno"><Field label="Código Interno" value={mock.codigoInterno} /></InputGroup>
          <InputGroup label="Código Fabricante"><Field label="Código Fabricante" value={mock.codigoFabricante} /></InputGroup>
          <InputGroup label="Marca"><Field label="Marca" value={mock.marca} /></InputGroup>
          <InputGroup label="Categoria"><Field label="Categoria" value={mock.categoria} /></InputGroup>
          <InputGroup label="Subcategoria"><Field label="Subcategoria" value={mock.subcategoria} /></InputGroup>
          <InputGroup label="Unidade"><Field label="Unidade" value={mock.unidade} /></InputGroup>
        </div>
      </Section>

      <Section title="Dimensões e Peso">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <InputGroup label="Peso Líquido (kg)"><Field label="Peso Líquido" value={mock.pesoLiquido} type="number" /></InputGroup>
          <InputGroup label="Peso Bruto (kg)"><Field label="Peso Bruto" value={mock.pesoBruto} type="number" /></InputGroup>
          <InputGroup label="Largura (cm)"><Field label="Largura" value={mock.largura} type="number" /></InputGroup>
          <InputGroup label="Altura (cm)"><Field label="Altura" value={mock.altura} type="number" /></InputGroup>
          <InputGroup label="Profundidade (cm)"><Field label="Profundidade" value={mock.profundidade} type="number" /></InputGroup>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <InputGroup label="Larg. Embalagem (cm)"><Field label="Larg. Embalagem" value={mock.larguraEmbalagem} type="number" /></InputGroup>
          <InputGroup label="Alt. Embalagem (cm)"><Field label="Alt. Embalagem" value={mock.alturaEmbalagem} type="number" /></InputGroup>
          <InputGroup label="Prof. Embalagem (cm)"><Field label="Prof. Embalagem" value={mock.profundidadeEmbalagem} type="number" /></InputGroup>
        </div>
      </Section>

      <Section title="Fiscal">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <InputGroup label="NCM"><Field label="NCM" value={mock.ncm} /></InputGroup>
          <InputGroup label="CEST"><Field label="CEST" value={mock.cest} /></InputGroup>
          <InputGroup label="CFOP Padrão"><Field label="CFOP Padrão" value={mock.cfopPadrao} /></InputGroup>
          <InputGroup label="Origem"><Field label="Origem" value={mock.origem === "0" ? "0 - Nacional" : mock.origem} /></InputGroup>
          <InputGroup label="Regime Tributário"><Field label="Regime Tributário" value={mock.regimeTributario} /></InputGroup>
          <InputGroup label="Garantia (meses)"><Field label="Garantia" value={mock.garantiaMeses} type="number" /></InputGroup>
        </div>
      </Section>

      <Section title="Descrição e SEO">
        <InputGroup label="Descrição Curta">
          <textarea defaultValue={mock.descricaoCurta} readOnly rows={2} className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 resize-none cursor-default focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-transparent" />
        </InputGroup>
        <InputGroup label="Descrição Completa">
          <textarea defaultValue={mock.descricaoCompleta} readOnly rows={4} className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 resize-none cursor-default focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-transparent" />
        </InputGroup>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <InputGroup label="Título SEO"><Field label="Título SEO" value={mock.seoTitulo} /></InputGroup>
          <InputGroup label="Slug"><Field label="Slug" value={mock.seoSlug} /></InputGroup>
          <InputGroup label="Meta Description">
            <textarea defaultValue={mock.seoDesc} readOnly rows={2} className="w-full bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 resize-none cursor-default focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-transparent" />
          </InputGroup>
          <InputGroup label="Palavras-chave"><Field label="Palavras-chave" value={mock.seoKw} /></InputGroup>
        </div>
      </Section>

      <Section title="Mídia">
        <div>
          <p className="text-[10px] text-neutral-500 uppercase tracking-wider mb-2">Imagens</p>
          <div className="grid grid-cols-4 md:grid-cols-6 gap-2">
            {imagesMock.map((nome) => (
              <div key={nome} className="aspect-square bg-neutral-800 border border-neutral-700 rounded-lg flex items-center justify-center text-2xl text-neutral-600 hover:border-neutral-500 cursor-pointer transition-colors">
                🖼️
              </div>
            ))}
            <div className="aspect-square border border-dashed border-neutral-700 rounded-lg flex items-center justify-center text-2xl text-neutral-700 hover:border-neutral-500 cursor-pointer transition-colors">
              +
            </div>
          </div>
        </div>
        <div>
          <p className="text-[10px] text-neutral-500 uppercase tracking-wider mb-2">Vídeos</p>
          {videosMock.map((url) => (
            <div key={url} className="flex items-center gap-3 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2">
              <span className="text-sm">🎬</span>
              <span className="text-xs text-neutral-400 truncate">{url}</span>
            </div>
          ))}
        </div>
        <div>
          <p className="text-[10px] text-neutral-500 uppercase tracking-wider mb-2">Documentos</p>
          <div className="flex flex-wrap gap-2">
            {docsMock.map((nome) => (
              <span key={nome} className="flex items-center gap-2 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-neutral-400">
                📄 {nome}
              </span>
            ))}
          </div>
        </div>
      </Section>
    </div>
  );
}
