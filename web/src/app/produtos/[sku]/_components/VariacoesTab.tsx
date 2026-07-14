"use client";

const variacoesMock = {
  atributos: [
    { nome: "Cor", valores: ["Branco", "Preto", "Azul"] },
    { nome: "Tamanho", valores: ["P", "M", "G"] },
    { nome: "Material", valores: ["Plástico ABS", "Plástico PP", "Silicone"] },
    { nome: "Modelo", valores: ["Standard", "Premium", "Econômico"] },
  ],
  combinacoes: [
    { sku: "MC-001-P-BR", atributos: { Cor: "Branco", Tamanho: "P", Material: "Plástico ABS", Modelo: "Standard" }, preco: 29.90, estoque: 45 },
    { sku: "MC-001-P-BM", atributos: { Cor: "Branco", Tamanho: "M", Material: "Plástico ABS", Modelo: "Standard" }, preco: 29.90, estoque: 32 },
    { sku: "MC-001-P-BG", atributos: { Cor: "Branco", Tamanho: "G", Material: "Plástico PP", Modelo: "Premium" }, preco: 32.90, estoque: 18 },
    { sku: "MC-001-P-PP", atributos: { Cor: "Preto", Tamanho: "P", Material: "Plástico ABS", Modelo: "Standard" }, preco: 29.90, estoque: 60 },
    { sku: "MC-001-P-PM", atributos: { Cor: "Preto", Tamanho: "M", Material: "Silicone", Modelo: "Premium" }, preco: 39.90, estoque: 14 },
    { sku: "MC-001-P-PG", atributos: { Cor: "Preto", Tamanho: "G", Material: "Plástico PP", Modelo: "Econômico" }, preco: 24.90, estoque: 22 },
    { sku: "MC-001-P-AP", atributos: { Cor: "Azul", Tamanho: "P", Material: "Plástico ABS", Modelo: "Econômico" }, preco: 24.90, estoque: 15 },
    { sku: "MC-001-P-AM", atributos: { Cor: "Azul", Tamanho: "M", Material: "Silicone", Modelo: "Premium" }, preco: 41.90, estoque: 8 },
    { sku: "MC-001-P-AG", atributos: { Cor: "Azul", Tamanho: "G", Material: "Plástico PP", Modelo: "Premium" }, preco: 34.90, estoque: 5 },
  ],
};

function Badge({ label, color }: { label: string; color: string }) {
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${color}`}>{label}</span>;
}

export default function VariacoesTab() {
  const attrNomes = variacoesMock.atributos.map((a) => a.nome);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-sm font-medium text-neutral-400 mb-3">Atributos Variáveis</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {variacoesMock.atributos.map((attr) => (
            <div key={attr.nome} className="bg-neutral-900 border border-neutral-800 rounded-lg p-3">
              <p className="text-xs text-neutral-400 mb-2">{attr.nome}</p>
              <div className="flex flex-wrap gap-1">
                {attr.valores.map((v) => (
                  <span key={v} className="text-xs bg-neutral-800 text-neutral-300 px-2 py-0.5 rounded">{v}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium text-neutral-400">Grade de Combinações</h2>
          <button className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1 rounded-lg transition-colors">+ Nova Variação</button>
        </div>
        <div className="bg-neutral-900 border border-neutral-800 rounded-lg overflow-x-auto">
          <table className="w-full text-sm min-w-[640px]">
            <thead>
              <tr className="border-b border-neutral-800 text-neutral-500 text-[10px] uppercase tracking-wider">
                {attrNomes.map((n) => (
                  <th key={n} className="text-left p-3 font-medium">{n}</th>
                ))}
                <th className="text-left p-3 font-medium">SKU</th>
                <th className="text-right p-3 font-medium">Preço</th>
                <th className="text-right p-3 font-medium">Estoque</th>
                <th className="text-center p-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {variacoesMock.combinacoes.map((c) => (
                <tr key={c.sku} className="border-b border-neutral-800/50 hover:bg-neutral-800/30">
                  {attrNomes.map((n) => (
                    <td key={n} className="p-3 text-neutral-300">{c.atributos[n as keyof typeof c.atributos]}</td>
                  ))}
                  <td className="p-3 text-indigo-400 font-mono text-xs">{c.sku}</td>
                  <td className="p-3 text-right text-neutral-300 numeric">
                    R$ {c.preco.toFixed(2)}
                  </td>
                  <td className="p-3 text-right numeric">
                    <span className={c.estoque < 10 ? "text-red-400" : c.estoque < 30 ? "text-yellow-400" : "text-green-400"}>
                      {c.estoque}
                    </span>
                  </td>
                  <td className="p-3 text-center">
                    <Badge label={c.estoque > 0 ? "Ativo" : "Esgotado"} color={c.estoque > 0 ? "bg-green-900/50 text-green-400" : "bg-red-900/50 text-red-400"} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-neutral-600 mt-1 text-right">{variacoesMock.combinacoes.length} variações</p>
      </div>
    </div>
  );
}
