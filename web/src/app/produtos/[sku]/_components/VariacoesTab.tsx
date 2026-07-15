"use client";

interface Variacao {
  sku: string;
  nome: string;
  valor: number;
  atributo?: string;
}

function Badge({ label, color }: { label: string; color: string }) {
  return <span className={"text-xs px-2 py-0.5 rounded-full font-medium " + color}>{label}</span>;
}

export default function VariacoesTab({ variacoes = [] }: { variacoes?: Variacao[] }) {
  // Parse atributo "Nome:Valor" to group distinct attributes
  const attrMap: Record<string, Set<string>> = {};
  variacoes.forEach(v => {
    if (!v.atributo) return;
    const parts = v.atributo.split(":");
    if (parts.length >= 2) {
      const nome = parts[0].trim();
      const valor = parts.slice(1).join(":").trim();
      if (!attrMap[nome]) attrMap[nome] = new Set();
      attrMap[nome].add(valor);
    }
  });
  const attrKeys = Object.keys(attrMap);

  if (variacoes.length === 0) {
    return (
      <div className="py-8 text-center">
        <p className="text-sm text-neutral-500">Este produto nao tem variacoes cadastradas no Bling.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {attrKeys.length > 0 && (
        <div>
          <h2 className="text-sm font-medium text-neutral-400 mb-3">Atributos Variaveis</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {attrKeys.map(nome => (
              <div key={nome} className="bg-neutral-900 border border-neutral-800 rounded-lg p-3">
                <p className="text-xs text-neutral-400 mb-2">{nome}</p>
                <div className="flex flex-wrap gap-1">
                  {Array.from(attrMap[nome]).map(v => (
                    <span key={v} className="text-xs bg-neutral-800 text-neutral-300 px-2 py-0.5 rounded">{v}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div>
        <h2 className="text-sm font-medium text-neutral-400 mb-3">Variacoes ({variacoes.length})</h2>
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
                <th className="text-left p-3 font-medium">SKU</th>
                <th className="text-left p-3 font-medium">Nome</th>
                <th className="text-right p-3 font-medium">Valor</th>
              </tr>
            </thead>
            <tbody>
              {variacoes.map((v) => (
                <tr key={v.sku} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                  <td className="p-3 text-indigo-400 font-mono text-xs">{v.sku}</td>
                  <td className="p-3 text-neutral-300">{v.nome}</td>
                  <td className="p-3 text-right text-emerald-400 numeric">
                    R$ {Number(v.valor || 0).toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
