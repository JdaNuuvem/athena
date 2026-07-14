import type { FastifyInstance } from 'fastify'
import { getPrisma } from '../../shared/infrastructure/persistence/prisma-client'

// ── tipos ──

interface Contrato { id: number; nome: string; parte: string; status: string; vigencia: string; valor: string }
interface Arquivo { nome: string; tamanho: string; data: string }
interface Foto { nome: string; data: string }
interface NotaFiscalDoc { numero: string; emissao: string; valor: string; status: string; tipo: string }
interface XMLDoc { nome: string; tamanho: string; data: string }
interface PDFDoc { nome: string; tamanho: string; data: string }
interface Assinatura { id: number; documento: string; remetente: string; status: string; data: string }
interface Versao { documento: string; versao: string; data: string; autor: string }

// ── generators ──

const contratosMock: Contrato[] = [
  { id:1, nome:"Contrato Fornecedor Plásticos Ltda", parte:"Plásticos Ltda", status:"Ativo", vigencia:"01/2025 - 12/2026", valor:"R$ 48.000,00" },
  { id:2, nome:"Acordo Comercial Mercado Livre", parte:"Mercado Livre", status:"Ativo", vigencia:"03/2025 - 03/2027", valor:"—" },
  { id:3, nome:"Prestação de Serviços TI", parte:"TechServ Ltda", status:"Pendente", vigencia:"06/2025 - 06/2026", valor:"R$ 12.000,00" },
  { id:4, nome:"Locação Galpão Industrial", parte:"Imobiliária Central", status:"Vencido", vigencia:"01/2023 - 01/2025", valor:"R$ 96.000,00" },
]

const arquivosMock: Arquivo[] = [
  { nome:"relatorio_fiscal_2025.pdf", tamanho:"2,4 MB", data:"10/07/2025" },
  { nome:"planilha_custos_q2.xlsx", tamanho:"845 KB", data:"05/07/2025" },
  { nome:"apresentacao_institucional.pptx", tamanho:"5,1 MB", data:"28/06/2025" },
  { nome:"manual_qualidade_v3.docx", tamanho:"1,2 MB", data:"15/06/2025" },
  { nome:"backup_config.json", tamanho:"32 KB", data:"01/06/2025" },
]

const fotosMock: Foto[] = [
  { nome:"produto_vista_frontal.jpg", data:"10/07/2025" },
  { nome:"produto_vista_lateral.jpg", data:"10/07/2025" },
  { nome:"embalagem_nova.png", data:"08/07/2025" },
  { nome:"loja_matriz_fachada.jpg", data:"05/07/2025" },
  { nome:"evento_lancamento_01.jpg", data:"01/07/2025" },
  { nome:"evento_lancamento_02.jpg", data:"01/07/2025" },
]

const nfMock: NotaFiscalDoc[] = [
  { numero:"000.001.234", emissao:"10/07/2025", valor:"R$ 3.450,00", status:"Emitida", tipo:"Saída" },
  { numero:"000.001.235", emissao:"09/07/2025", valor:"R$ 890,50", status:"Emitida", tipo:"Saída" },
  { numero:"000.054.321", emissao:"08/07/2025", valor:"R$ 12.300,00", status:"Cancelada", tipo:"Entrada" },
  { numero:"000.001.236", emissao:"07/07/2025", valor:"R$ 1.520,00", status:"Emitida", tipo:"Saída" },
]

const xmlMock: XMLDoc[] = [
  { nome:"NFe-000001234.xml", tamanho:"56 KB", data:"10/07/2025" },
  { nome:"NFe-000001235.xml", tamanho:"48 KB", data:"09/07/2025" },
  { nome:"NFe-000001236.xml", tamanho:"52 KB", data:"07/07/2025" },
  { nome:"CTe-000000789.xml", tamanho:"34 KB", data:"05/07/2025" },
]

const pdfMock: PDFDoc[] = [
  { nome:"contrato_fornecedor_2025.pdf", tamanho:"1,8 MB", data:"10/07/2025" },
  { nome:"relatorio_fiscal_junho.pdf", tamanho:"2,4 MB", data:"05/07/2025" },
  { nome:"proposta_comercial_abc.pdf", tamanho:"620 KB", data:"01/07/2025" },
  { nome:"laudo_tecnico_qualidade.pdf", tamanho:"3,1 MB", data:"28/06/2025" },
]

const assinaturaMock: Assinatura[] = [
  { id:1, documento:"Contrato Fornecedor 2025", remetente:"Jurídico", status:"Assinado", data:"10/07/2025" },
  { id:2, documento:"Acordo Comercial ML", remetente:"Comercial", status:"Pendente", data:"08/07/2025" },
  { id:3, documento:"Termo de Confidencialidade", remetente:"RH", status:"Aguardando", data:"05/07/2025" },
]

const versoesMock: Versao[] = [
  { documento:"manual_qualidade.docx", versao:"v3", data:"10/07/2025", autor:"Admin" },
  { documento:"manual_qualidade.docx", versao:"v2", data:"15/06/2025", autor:"Admin" },
  { documento:"manual_qualidade.docx", versao:"v1", data:"01/05/2025", autor:"Admin" },
  { documento:"contrato_fornecedor_2025.pdf", versao:"v2", data:"20/06/2025", autor:"Jurídico" },
  { documento:"contrato_fornecedor_2025.pdf", versao:"v1", data:"10/04/2025", autor:"Jurídico" },
]

// ── DB helpers ──

const fmtDate = (d: Date) => d.toLocaleDateString("pt-BR")
const fmtBRL = (v: number) => `R$ ${v.toFixed(2).replace(".", ",")}`

async function queryNFsFromDB(): Promise<NotaFiscalDoc[] | null> {
  try {
    const invoices = await getPrisma().invoice.findMany({ orderBy: { generatedAt: 'desc' }, take: 20 })
    if (invoices.length === 0) return null
    return invoices.map(inv => ({
      numero: inv.number,
      emissao: fmtDate(inv.generatedAt),
      valor: fmtBRL(inv.amount),
      status: "Emitida",
      tipo: "Saída",
    }))
  } catch { return null }
}

// ── route registration ──

export function registerDocumentosRoutes(server: FastifyInstance): void {

  server.get('/api/documentos/contratos', async () => {
    try {
      const docs = await getPrisma().document.findMany({ where: { type: 'contrato' }, orderBy: { createdAt: 'desc' } })
      if (docs.length > 0) return docs.map(d => ({
        id: d.id, nome: d.name, parte: d.counterparty ?? '—', status: d.status,
        vigencia: d.period ?? '—', valor: d.value ? fmtBRL(d.value) : '—',
      }))
    } catch { /* DB offline, use fallback */ }
    return contratosMock
  })

  server.get('/api/documentos/arquivos', async () => {
    try {
      const files = await getPrisma().documentFile.findMany({ where: { type: 'arquivo' }, orderBy: { createdAt: 'desc' } })
      if (files.length > 0) return files.map(f => ({ nome: f.name, tamanho: f.size, data: fmtDate(f.createdAt) }))
    } catch { /* fallback */ }
    return arquivosMock
  })

  server.get('/api/documentos/fotos', async () => {
    try {
      const files = await getPrisma().documentFile.findMany({ where: { type: 'foto' }, orderBy: { createdAt: 'desc' } })
      if (files.length > 0) return files.map(f => ({ nome: f.name, data: fmtDate(f.createdAt) }))
    } catch { /* fallback */ }
    return fotosMock
  })

  server.get('/api/documentos/nf', async () => {
    const dbNFs = await queryNFsFromDB()
    return dbNFs ?? nfMock
  })

  server.get('/api/documentos/xml', async () => {
    try {
      const files = await getPrisma().documentFile.findMany({ where: { type: 'xml' }, orderBy: { createdAt: 'desc' } })
      if (files.length > 0) return files.map(f => ({ nome: f.name, tamanho: f.size, data: fmtDate(f.createdAt) }))
    } catch { /* fallback */ }
    return xmlMock
  })

  server.get('/api/documentos/pdf', async () => {
    try {
      const files = await getPrisma().documentFile.findMany({ where: { type: 'pdf' }, orderBy: { createdAt: 'desc' } })
      if (files.length > 0) return files.map(f => ({ nome: f.name, tamanho: f.size, data: fmtDate(f.createdAt) }))
    } catch { /* fallback */ }
    return pdfMock
  })

  server.get('/api/documentos/assinatura', async () => {
    try {
      const docs = await getPrisma().document.findMany({ where: { type: 'assinatura' }, orderBy: { createdAt: 'desc' } })
      if (docs.length > 0) return docs.map(d => ({
        id: d.id, documento: d.name, remetente: d.signedBy ?? '—', status: d.status, data: fmtDate(d.createdAt),
      }))
    } catch { /* fallback */ }
    return assinaturaMock
  })

  server.get('/api/documentos/versionamento', async () => {
    try {
      const docs = await getPrisma().document.findMany({ where: { type: 'versao' }, orderBy: { createdAt: 'desc' } })
      if (docs.length > 0) return docs.map(d => ({
        documento: d.name, versao: d.period ?? 'v1', data: fmtDate(d.createdAt), autor: d.signedBy ?? '—',
      }))
    } catch { /* fallback */ }
    return versoesMock
  })
}
