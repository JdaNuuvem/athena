"use client";
export default function DocumentosPage() {
  return (
    <div className="p-6 space-y-6">
      <div><h1 className="text-lg font-bold text-neutral-100">Documentos</h1><p className="text-xs text-neutral-500 mt-1">Gestao de arquivos e documentos</p></div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {["Notas Fiscais","Contratos","Certificados","Manuais","Fichas Tecnicas","Laudos","Planilhas","Outros"].map(cat => (
          <div key={cat} className="bg-neutral-800 border border-neutral-700 rounded-lg p-4 hover:bg-neutral-750 cursor-pointer transition-colors">
            <p className="text-sm font-semibold text-neutral-200">{cat}</p>
            <p className="text-[10px] text-neutral-600 mt-1">0 arquivos</p>
          </div>
        ))}
      </div>
    </div>
  );
}
