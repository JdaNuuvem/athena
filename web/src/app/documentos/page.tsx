"use client";

import { useState } from "react";

const TABS = [
  { id: "contratos", label: "Contratos" },
  { id: "arquivos", label: "Arquivos" },
  { id: "fotos", label: "Fotos" },
  { id: "nf", label: "NF" },
  { id: "xml", label: "XML" },
  { id: "pdf", label: "PDF" },
  { id: "assinatura", label: "Assinatura" },
  { id: "versionamento", label: "Versionamento" },
] as const;

type TabId = (typeof TABS)[number]["id"];

// ─── mock data ────────────────────────────────────────────────────────

const contratosMock = [
  { id: 1, nome: "Contrato Fornecedor Plásticos Ltda", parte: "Plásticos Ltda", status: "Ativo", vigencia: "01/2025 - 12/2026", valor: "R$ 48.000,00" },
  { id: 2, nome: "Acordo Comercial Mercado Livre", parte: "Mercado Livre", status: "Ativo", vigencia: "03/2025 - 03/2027", valor: "—" },
  { id: 3, nome: "Prestação de Serviços TI", parte: "TechServ Ltda", status: "Pendente", vigencia: "06/2025 - 06/2026", valor: "R$ 12.000,00" },
  { id: 4, nome: "Locação Galpão Industrial", parte: "Imobiliária Central", status: "Vencido", vigencia: "01/2023 - 01/2025", valor: "R$ 96.000,00" },
];

const arquivosMock = [
  { nome: "relatorio_fiscal_2025.pdf", tamanho: "2,4 MB", data: "10/07/2025" },
  { nome: "planilha_custos_q2.xlsx", tamanho: "845 KB", data: "05/07/2025" },
  { nome: "apresentacao_institucional.pptx", tamanho: "5,1 MB", data: "28/06/2025" },
  { nome: "manual_qualidade_v3.docx", tamanho: "1,2 MB", data: "15/06/2025" },
  { nome: "backup_config.json", tamanho: "32 KB", data: "01/06/2025" },
];

const fotosMock = [
  { nome: "produto_vista_frontal.jpg", data: "10/07/2025" },
  { nome: "produto_vista_lateral.jpg", data: "10/07/2025" },
  { nome: "embalagem_nova.png", data: "08/07/2025" },
  { nome: "loja_matriz_fachada.jpg", data: "05/07/2025" },
  { nome: "evento_lancamento_01.jpg", data: "01/07/2025" },
  { nome: "evento_lancamento_02.jpg", data: "01/07/2025" },
];

const nfMock = [
  { numero: "000.001.234", emissao: "10/07/2025", valor: "R$ 3.450,00", status: "Emitida", tipo: "Saída" },
  { numero: "000.001.235", emissao: "09/07/2025", valor: "R$ 890,50", status: "Emitida", tipo: "Saída" },
  { numero: "000.054.321", emissao: "08/07/2025", valor: "R$ 12.300,00", status: "Cancelada", tipo: "Entrada" },
  { numero: "000.001.236", emissao: "07/07/2025", valor: "R$ 1.520,00", status: "Emitida", tipo: "Saída" },
];

const xmlMock = [
  { nome: "NFe-000001234.xml", tamanho: "56 KB", data: "10/07/2025" },
  { nome: "NFe-000001235.xml", tamanho: "48 KB", data: "09/07/2025" },
  { nome: "NFe-000001236.xml", tamanho: "52 KB", data: "07/07/2025" },
  { nome: "CTe-000000789.xml", tamanho: "34 KB", data: "05/07/2025" },
];

const pdfMock = [
  { nome: "contrato_fornecedor_2025.pdf", tamanho: "1,8 MB", data: "10/07/2025" },
  { nome: "relatorio_fiscal_junho.pdf", tamanho: "2,4 MB", data: "05/07/2025" },
  { nome: "proposta_comercial_abc.pdf", tamanho: "620 KB", data: "01/07/2025" },
  { nome: "laudo_tecnico_qualidade.pdf", tamanho: "3,1 MB", data: "28/06/2025" },
];

const assinaturaMock = [
  { id: 1, documento: "Contrato Fornecedor 2025", remetente: "Jurídico", status: "Assinado", data: "10/07/2025" },
  { id: 2, documento: "Acordo Comercial ML", remetente: "Comercial", status: "Pendente", data: "08/07/2025" },
  { id: 3, documento: "Termo de Confidencialidade", remetente: "RH", status: "Aguardando", data: "05/07/2025" },
];

const versoesMock = [
  { documento: "manual_qualidade.docx", versao: "v3", data: "10/07/2025", autor: "Admin" },
  { documento: "manual_qualidade.docx", versao: "v2", data: "15/06/2025", autor: "Admin" },
  { documento: "manual_qualidade.docx", versao: "v1", data: "01/05/2025", autor: "Admin" },
  { documento: "contrato_fornecedor_2025.pdf", versao: "v2", data: "20/06/2025", autor: "Jurídico" },
  { documento: "contrato_fornecedor_2025.pdf", versao: "v1", data: "10/04/2025", autor: "Jurídico" },
];

// ─── sub-components ───────────────────────────────────────────────────

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${color}`}>
      {label}
    </span>
  );
}

function statusBadge(status: string) {
  const map: Record<string, string> = {
    Ativo: "bg-green-900/50 text-green-400",
    Pendente: "bg-yellow-900/50 text-yellow-400",
    Vencido: "bg-red-900/50 text-red-400",
    Assinado: "bg-green-900/50 text-green-400",
    Aguardando: "bg-neutral-700 text-neutral-400",
    Emitida: "bg-green-900/50 text-green-400",
    Cancelada: "bg-red-900/50 text-red-400",
  };
  return <Badge label={status} color={map[status] || "bg-neutral-700 text-neutral-400"} />;
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-12 text-center">
      <p className="text-4xl mb-3">📁</p>
      <p className="text-sm text-neutral-400">{text}</p>
      <p className="text-xs text-neutral-600 mt-1">Nenhum registro encontrado.</p>
    </div>
  );
}

function Header({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-between">
      <h1 className="text-lg font-bold text-neutral-100">{label}</h1>
      <button className="bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1.5 rounded-lg text-xs transition-colors">
        + Novo
      </button>
    </div>
  );
}

// ─── tab panels ───────────────────────────────────────────────────────

function ContratosPanel() {
  return (
    <div className="space-y-4">
      <Header label="Contratos" />
      {contratosMock.length === 0 ? <EmptyState text="Nenhum contrato cadastrado" /> : (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
          <table className="w-full text-sm min-w-[640px]">
            <thead>
              <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
                <th className="text-left p-3 font-medium">Nome</th>
                <th className="text-left p-3 font-medium">Parte</th>
                <th className="text-center p-3 font-medium">Status</th>
                <th className="text-left p-3 font-medium">Vigência</th>
                <th className="text-right p-3 font-medium">Valor</th>
              </tr>
            </thead>
            <tbody>
              {contratosMock.map((c) => (
                <tr key={c.id} className="border-b border-neutral-800/50 hover:bg-neutral-800/30 cursor-pointer">
                  <td className="p-3 text-neutral-300">{c.nome}</td>
                  <td className="p-3 text-neutral-400">{c.parte}</td>
                  <td className="p-3 text-center">{statusBadge(c.status)}</td>
                  <td className="p-3 text-neutral-400 text-xs numeric">{c.vigencia}</td>
                  <td className="p-3 text-right text-neutral-300 numeric">{c.valor}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ArquivosPanel() {
  return (
    <div className="space-y-4">
      <Header label="Arquivos" />
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Buscar arquivos..."
          className="flex-1 bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-transparent"
        />
      </div>
      {arquivosMock.length === 0 ? <EmptyState text="Nenhum arquivo" /> : (
        <div className="grid gap-2">
          {arquivosMock.map((a) => (
            <div key={a.nome} className="flex items-center gap-4 bg-neutral-900 border border-neutral-800 rounded-lg px-4 py-3 hover:bg-neutral-800/50 cursor-pointer transition-colors">
              <span className="text-xl">📄</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-neutral-200 truncate">{a.nome}</p>
                <p className="text-xs text-neutral-500">{a.data}</p>
              </div>
              <span className="text-xs text-neutral-500">{a.tamanho}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function FotosPanel() {
  return (
    <div className="space-y-4">
      <Header label="Fotos" />
      {fotosMock.length === 0 ? <EmptyState text="Nenhuma foto" /> : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {fotosMock.map((f) => (
            <div key={f.nome} className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-hidden hover:border-neutral-600 cursor-pointer transition-colors group">
              <div className="aspect-square bg-neutral-800 flex items-center justify-center text-3xl text-neutral-600 group-hover:text-neutral-400 transition-colors">
                🖼️
              </div>
              <div className="p-2">
                <p className="text-xs text-neutral-300 truncate">{f.nome}</p>
                <p className="text-[10px] text-neutral-500">{f.data}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function NFPanel() {
  return (
    <div className="space-y-4">
      <Header label="Notas Fiscais" />
      {nfMock.length === 0 ? <EmptyState text="Nenhuma nota fiscal" /> : (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
          <table className="w-full text-sm min-w-[640px]">
            <thead>
              <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
                <th className="text-left p-3 font-medium">Número</th>
                <th className="text-left p-3 font-medium">Emissão</th>
                <th className="text-center p-3 font-medium">Tipo</th>
                <th className="text-center p-3 font-medium">Status</th>
                <th className="text-right p-3 font-medium">Valor</th>
                <th className="text-center p-3 font-medium">Ações</th>
              </tr>
            </thead>
            <tbody>
              {nfMock.map((n) => (
                <tr key={n.numero} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                  <td className="p-3 text-indigo-400 font-mono text-xs numeric">{n.numero}</td>
                  <td className="p-3 text-neutral-400 text-xs">{n.emissao}</td>
                  <td className="p-3 text-center">
                    <Badge label={n.tipo} color={n.tipo === "Entrada" ? "bg-blue-900/50 text-blue-400" : "bg-purple-900/50 text-purple-400"} />
                  </td>
                  <td className="p-3 text-center">{statusBadge(n.status)}</td>
                  <td className="p-3 text-right text-neutral-300 numeric">{n.valor}</td>
                  <td className="p-3 text-center">
                    <button className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">XML</button>
                    <span className="text-neutral-600 mx-1">|</span>
                    <button className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">PDF</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function XMLPanel() {
  return (
    <div className="space-y-4">
      <Header label="XML" />
      {xmlMock.length === 0 ? <EmptyState text="Nenhum XML" /> : (
        <div className="grid gap-2">
          {xmlMock.map((x) => (
            <div key={x.nome} className="flex items-center gap-4 bg-neutral-900 border border-neutral-800 rounded-lg px-4 py-3 hover:bg-neutral-800/50 cursor-pointer transition-colors">
              <span className="text-xl">📋</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-neutral-200 truncate">{x.nome}</p>
                <p className="text-xs text-neutral-500">{x.data}</p>
              </div>
              <span className="text-xs text-neutral-500">{x.tamanho}</span>
              <button className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">Download</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PDFPanel() {
  return (
    <div className="space-y-4">
      <Header label="PDF" />
      {pdfMock.length === 0 ? <EmptyState text="Nenhum PDF" /> : (
        <div className="grid gap-2">
          {pdfMock.map((p) => (
            <div key={p.nome} className="flex items-center gap-4 bg-neutral-900 border border-neutral-800 rounded-lg px-4 py-3 hover:bg-neutral-800/50 cursor-pointer transition-colors">
              <span className="text-xl">📕</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-neutral-200 truncate">{p.nome}</p>
                <p className="text-xs text-neutral-500">{p.data}</p>
              </div>
              <span className="text-xs text-neutral-500">{p.tamanho}</span>
              <button className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">Visualizar</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function AssinaturaPanel() {
  return (
    <div className="space-y-4">
      <Header label="Assinatura" />
      {assinaturaMock.length === 0 ? <EmptyState text="Nenhuma assinatura pendente" /> : (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
          <table className="w-full text-sm min-w-[640px]">
            <thead>
              <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
                <th className="text-left p-3 font-medium">Documento</th>
                <th className="text-left p-3 font-medium">Remetente</th>
                <th className="text-center p-3 font-medium">Status</th>
                <th className="text-left p-3 font-medium">Data</th>
                <th className="text-center p-3 font-medium">Ação</th>
              </tr>
            </thead>
            <tbody>
              {assinaturaMock.map((a) => (
                <tr key={a.id} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                  <td className="p-3 text-neutral-300">{a.documento}</td>
                  <td className="p-3 text-neutral-400">{a.remetente}</td>
                  <td className="p-3 text-center">{statusBadge(a.status)}</td>
                  <td className="p-3 text-neutral-400 text-xs">{a.data}</td>
                  <td className="p-3 text-center">
                    {a.status === "Pendente" || a.status === "Aguardando" ? (
                      <button className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-2 py-1 rounded transition-colors">
                        Assinar
                      </button>
                    ) : (
                      <span className="text-xs text-neutral-500">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function VersionamentoPanel() {
  return (
    <div className="space-y-4">
      <Header label="Versionamento" />
      {versoesMock.length === 0 ? <EmptyState text="Nenhum histórico de versão" /> : (
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
          <table className="w-full text-sm min-w-[640px]">
            <thead>
              <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
                <th className="text-left p-3 font-medium">Documento</th>
                <th className="text-center p-3 font-medium">Versão</th>
                <th className="text-left p-3 font-medium">Data</th>
                <th className="text-left p-3 font-medium">Autor</th>
                <th className="text-center p-3 font-medium">Ações</th>
              </tr>
            </thead>
            <tbody>
              {versoesMock.map((v) => (
                <tr key={`${v.documento}-${v.versao}`} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                  <td className="p-3 text-neutral-300">{v.documento}</td>
                  <td className="p-3 text-center">
                    <Badge label={v.versao} color={v.versao === "v3" || v.versao === "v2" ? "bg-indigo-900/50 text-indigo-400" : "bg-neutral-700 text-neutral-400"} />
                  </td>
                  <td className="p-3 text-neutral-400 text-xs">{v.data}</td>
                  <td className="p-3 text-neutral-400">{v.autor}</td>
                  <td className="p-3 text-center">
                    <button className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">Restaurar</button>
                    <span className="text-neutral-600 mx-1">|</span>
                    <button className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">Comparar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const PANELS = {
  contratos: ContratosPanel,
  arquivos: ArquivosPanel,
  fotos: FotosPanel,
  nf: NFPanel,
  xml: XMLPanel,
  pdf: PDFPanel,
  assinatura: AssinaturaPanel,
  versionamento: VersionamentoPanel,
};

// ─── main page ────────────────────────────────────────────────────────

export default function DocumentosPage() {
  const [tab, setTab] = useState<TabId>("contratos");
  const Panel = PANELS[tab];

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-bold text-neutral-100">Documentos</h1>
        <p className="text-xs text-neutral-500 mt-1">Gestão de arquivos e documentos</p>
      </div>

      {/* tabs */}
      <div className="flex gap-2 overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap ${
              tab === t.id
                ? "bg-indigo-600/20 text-indigo-300 border border-indigo-600/30"
                : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 border border-transparent"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* panel */}
      <Panel />
    </div>
  );
}