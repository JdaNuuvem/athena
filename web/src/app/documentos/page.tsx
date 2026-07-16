"use client";

import { useState, useEffect, useRef, useCallback } from "react";

interface Documento {
  id: number; nome_original: string; nome_armazenado: string;
  entidade_tipo: string; entidade_id: number | null;
  mime_type: string; tamanho_bytes: number; criado_por: string;
  tags: string; created_at: string;
}

const ENTIDADES = [
  { value: "", label: "Sem vinculo" },
  { value: "produto", label: "Produto" },
  { value: "pedido", label: "Pedido" },
  { value: "contrato", label: "Contrato" },
  { value: "fornecedor", label: "Fornecedor" },
  { value: "cliente", label: "Cliente" },
  { value: "nf", label: "Nota Fiscal" },
  { value: "funcionario", label: "Funcionario" },
];

const ICONS: Record<string, string> = {
  pdf: "📄", image: "🖼️", xml: "📋", spreadsheet: "📊", default: "📁",
};
function mimeIcon(mime: string) {
  if (mime.includes("pdf")) return ICONS.pdf;
  if (mime.includes("image")) return ICONS.image;
  if (mime.includes("xml")) return ICONS.xml;
  if (mime.includes("sheet") || mime.includes("excel")) return ICONS.spreadsheet;
  return ICONS.default;
}
function fmtSize(bytes: number) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1024 / 1024).toFixed(1) + " MB";
}

export default function DocumentosPage() {
  const [docs, setDocs] = useState<Documento[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [entidadeTipo, setEntidadeTipo] = useState("");
  const [entidadeId, setEntidadeId] = useState("");
  const [msg, setMsg] = useState("");
  const [stats, setStats] = useState({ total: 0, tamanho_total_bytes: 0 });
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    const [d, s] = await Promise.all([
      fetch("/api/documentos").then(r => r.json()),
      fetch("/api/documentos/stats").then(r => r.json()),
    ]);
    setDocs(d.data || []);
    setStats(s);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    for (const file of Array.from(files)) {
      const form = new FormData();
      form.append("file", file);
      if (entidadeTipo) form.append("entidade_tipo", entidadeTipo);
      if (entidadeId) form.append("entidade_id", entidadeId);
      form.append("criado_por", "Admin");
      const r = await fetch("/api/documentos", { method: "POST", body: form });
      const d = await r.json();
      if (d.error) setMsg(d.error);
    }
    setUploading(false);
    load();
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Remover arquivo?")) return;
    await fetch("/api/documentos/" + id, { method: "DELETE" });
    load();
  };

  const handlePreview = (id: number) => {
    window.open("/api/documentos/" + id, "_blank");
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-neutral-100">Documentos</h1>
          <p className="text-xs text-neutral-500 mt-1">
            {stats.total} arquivos &middot; {fmtSize(stats.tamanho_total_bytes)}
          </p>
        </div>
      </div>

      {msg && <div className="text-xs bg-red-900/30 border border-red-800 text-red-400 px-3 py-2 rounded-lg">{msg}</div>}

      {/* Upload area */}
      <div
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={e => { e.preventDefault(); setDragOver(false); handleUpload(e.dataTransfer.files); }}
        onClick={() => fileRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${dragOver ? "border-indigo-500 bg-indigo-900/20" : "border-neutral-700 hover:border-neutral-500 bg-neutral-800/50"}`}
      >
        <input ref={fileRef} type="file" multiple onChange={e => handleUpload(e.target.files)} className="hidden" />
        {uploading ? (
          <div className="text-neutral-400">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
            <p className="text-sm">Enviando...</p>
          </div>
        ) : (
          <div>
            <p className="text-3xl mb-2">📤</p>
            <p className="text-sm text-neutral-300">Arraste arquivos aqui ou clique para selecionar</p>
            <p className="text-xs text-neutral-600 mt-1">PDF, XML, imagens, planilhas</p>
          </div>
        )}
      </div>

      {/* Vinculo */}
      <div className="flex gap-2 items-end">
        <div>
          <label className="text-[10px] text-neutral-500 block mb-0.5">Vincular a</label>
          <select value={entidadeTipo} onChange={e => setEntidadeTipo(e.target.value)}
            className="bg-neutral-800 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200">
            {ENTIDADES.map(e => <option key={e.value} value={e.value}>{e.label}</option>)}
          </select>
        </div>
        {entidadeTipo && (
          <div>
            <label className="text-[10px] text-neutral-500 block mb-0.5">ID da entidade</label>
            <input type="text" value={entidadeId} onChange={e => setEntidadeId(e.target.value)}
              placeholder="Ex: 123" className="w-20 bg-neutral-800 border border-neutral-700 rounded px-2 py-1.5 text-xs text-neutral-200" />
          </div>
        )}
      </div>

      {/* Grid */}
      {loading ? (
        <p className="text-neutral-500 text-sm">Carregando...</p>
      ) : docs.length === 0 ? (
        <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center">
          <p className="text-sm text-neutral-400">Nenhum documento</p>
          <p className="text-xs text-neutral-600 mt-1">Arraste arquivos na area acima para comecar</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {docs.map(doc => (
            <div key={doc.id}
              className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 hover:border-neutral-600 transition-colors group">
              <div className="flex items-start gap-3">
                <span className="text-2xl">{mimeIcon(doc.mime_type)}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-neutral-200 truncate" title={doc.nome_original}>{doc.nome_original}</p>
                  <p className="text-[10px] text-neutral-500 mt-0.5">
                    {fmtSize(doc.tamanho_bytes)} &middot; {doc.entidade_tipo || "sem vinculo"}
                    {doc.entidade_id && <> #{doc.entidade_id}</>}
                  </p>
                  <p className="text-[9px] text-neutral-600 mt-0.5">{new Date(doc.created_at).toLocaleString("pt-BR")}</p>
                </div>
              </div>
              <div className="flex gap-2 mt-3 opacity-0 group-hover:opacity-100 transition-opacity">
                <button onClick={() => handlePreview(doc.id)}
                  className="flex-1 px-2 py-1 bg-indigo-600 hover:bg-indigo-500 text-white text-xs rounded">Visualizar</button>
                <button onClick={() => handleDelete(doc.id)}
                  className="px-2 py-1 bg-red-600/20 hover:bg-red-600 text-red-400 hover:text-white text-xs rounded">Remover</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
